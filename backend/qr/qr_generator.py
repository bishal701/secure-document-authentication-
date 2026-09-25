import qrcode
import cv2
import numpy as np
from PIL import Image
import io
import base64
from typing import Tuple, Optional, Dict, Any
from backend.qr.payload_coder import PayloadCoder

class QRService:
    @staticmethod
    def generate_qr_image(
        payload_text: str,
        box_size: int = 6,
        border: int = 2,
        error_correction: str = "M"
    ) -> Image.Image:
        """
        Generates a PIL Image QR code with configurable error correction.
        """
        ec_map = {
            "L": qrcode.constants.ERROR_CORRECT_L,
            "M": qrcode.constants.ERROR_CORRECT_M,
            "Q": qrcode.constants.ERROR_CORRECT_Q,
            "H": qrcode.constants.ERROR_CORRECT_H,
        }
        ec_level = ec_map.get(error_correction.upper(), qrcode.constants.ERROR_CORRECT_M)

        qr = qrcode.QRCode(
            version=None, # Automatically fit smallest version
            error_correction=ec_level,
            box_size=box_size,
            border=border
        )
        qr.add_data(payload_text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        return img

    @staticmethod
    def decode_qr_from_image(img_np: np.ndarray) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]], Optional[np.ndarray]]:
        """
        Detects and decodes QR code in an image using OpenCV QRCodeDetector.
        Returns: (success, raw_text, decoded_dict, bbox)
        """
        detector = cv2.QRCodeDetector()
        
        # Try original
        raw_text, bbox, _ = detector.detectAndDecode(img_np)
        
        # If not detected, try grayscale, CLAHE, and adaptive thresholding
        if not raw_text:
            gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY) if len(img_np.shape) == 3 else img_np
            raw_text, bbox, _ = detector.detectAndDecode(gray)

        if not raw_text:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray if 'gray' in locals() else cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY))
            raw_text, bbox, _ = detector.detectAndDecode(enhanced)

        if not raw_text:
            return False, None, None, None

        try:
            payload = PayloadCoder.decode_payload(raw_text)
            return True, raw_text, payload, bbox
        except Exception:
            # Maybe raw text was uncompressed string or standard QR
            return True, raw_text, {"raw": raw_text}, bbox
