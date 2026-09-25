import cv2
import numpy as np
from PIL import Image
import io
from typing import Dict, Any, Tuple

class DistortionEngine:
    """
    Simulates physical and digital document attacks:
    - Analog Print-and-Scan channel & halftone screening
    - Smartphone camera perspective warp and non-uniform lighting
    - Malicious digital tampering / splicing
    - High-frequency loss, noise, blur, and JPEG compression
    """

    @staticmethod
    def jpeg_compression(img_bgr: np.ndarray, quality: int = 35) -> np.ndarray:
        """Applies lossy JPEG compression artifacting."""
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), max(5, min(quality, 95))]
        _, encimg = cv2.imencode('.jpg', img_bgr, encode_param)
        return cv2.imdecode(encimg, 1)

    @staticmethod
    def gaussian_noise(img_bgr: np.ndarray, sigma: float = 18.0) -> np.ndarray:
        """Adds zero-mean Gaussian noise simulating sensor noise."""
        gauss = np.random.normal(0, sigma, img_bgr.shape).astype(np.float32)
        noisy = np.clip(img_bgr.astype(np.float32) + gauss, 0, 255).astype(np.uint8)
        return noisy

    @staticmethod
    def gaussian_blur(img_bgr: np.ndarray, ksize: int = 7) -> np.ndarray:
        """Applies Gaussian smoothing."""
        k = ksize if ksize % 2 == 1 else ksize + 1
        return cv2.GaussianBlur(img_bgr, (k, k), 1.8)

    @staticmethod
    def rotation_attack(img_bgr: np.ndarray, angle: float = 4.0) -> np.ndarray:
        """Rotates image around center with border reflection."""
        h, w = img_bgr.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        return cv2.warpAffine(img_bgr, M, (w, h), borderMode=cv2.BORDER_REFLECT)

    @staticmethod
    def perspective_warp(img_bgr: np.ndarray, tilt_factor: float = 0.06) -> np.ndarray:
        """Simulates smartphone camera capture at an oblique angle."""
        h, w = img_bgr.shape[:2]
        dx = int(w * tilt_factor)
        dy = int(h * tilt_factor)
        src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst = np.float32([[dx, dy], [w - dx, 0], [w - int(dx * 0.5), h - dy], [int(dx * 0.5), h]])
        M = cv2.getPerspectiveTransform(src, dst)
        return cv2.warpPerspective(img_bgr, M, (w, h), borderMode=cv2.BORDER_REFLECT)

    @staticmethod
    def brightness_contrast_glare(img_bgr: np.ndarray, alpha: float = 1.15, beta: int = 25) -> np.ndarray:
        """Simulates uneven ambient lighting and flashlight glare."""
        adjusted = cv2.convertScaleAbs(img_bgr, alpha=alpha, beta=beta)
        # Add radial glare spot
        h, w = img_bgr.shape[:2]
        center_x, center_y = int(w * 0.4), int(h * 0.3)
        y, x = np.ogrid[:h, :w]
        dist_from_center = np.sqrt((x - center_x)**2 + (y - center_y)**2)
        glare_mask = np.exp(-dist_from_center / (min(w, h) * 0.35)) * 45
        glare_3ch = np.dstack([glare_mask, glare_mask, glare_mask]).astype(np.float32)
        combined = np.clip(adjusted.astype(np.float32) + glare_3ch, 0, 255).astype(np.uint8)
        return combined

    @staticmethod
    def print_scan_simulation(img_bgr: np.ndarray) -> np.ndarray:
        """
        Simulates realistic physical Print-and-Scan degradation:
        1. Downsampling to print resolution (e.g. 150 DPI)
        2. Halftoning microtexture dot-gain
        3. Color desaturation & gamma curve shift
        4. Optical scanner sensor noise & upsampling
        """
        h, w = img_bgr.shape[:2]
        # 1. Downsample (print resolution)
        down = cv2.resize(img_bgr, (w // 2, h // 2), interpolation=cv2.INTER_AREA)

        # 2. Desaturate slightly & gamma shift
        hsv = cv2.cvtColor(down, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] *= 0.88 # slight color fading
        hsv = np.clip(hsv, 0, 255).astype(np.uint8)
        down_faded = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

        # 3. Micro-halftoning noise
        noise = np.random.normal(0, 7.0, down_faded.shape).astype(np.float32)
        half_toned = np.clip(down_faded.astype(np.float32) + noise, 0, 255).astype(np.uint8)

        # 4. Scanner optical re-upsampling with slight blur
        scanned = cv2.resize(half_toned, (w, h), interpolation=cv2.INTER_CUBIC)
        scanned = cv2.GaussianBlur(scanned, (3, 3), 0.6)
        return scanned

    @staticmethod
    def tamper_content(img_bgr: np.ndarray) -> np.ndarray:
        """
        Simulates digital forgery: splicing/altering recipient name and grade area.
        Alters pixels in recipient zone without altering QR signature.
        """
        tampered = img_bgr.copy()
        h, w = img_bgr.shape[:2]
        # Splice forged text rectangle in credential zone
        y1, y2 = int(h * 0.28), int(h * 0.48)
        x1, x2 = int(w * 0.20), int(w * 0.80)
        cv2.rectangle(tampered, (x1, y1), (x2, y2), (252, 252, 250), -1)
        cv2.putText(tampered, "FORGED RECIPIENT NAME", (x1 + 30, y1 + int((y2 - y1) * 0.45)), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (180, 20, 20), 2)
        cv2.putText(tampered, "ALTERED GRADE: FORGED DISTINCTION", (x1 + 30, y1 + int((y2 - y1) * 0.75)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180, 20, 20), 2)
        return tampered

    @classmethod
    def apply_attack(cls, img_bgr: np.ndarray, attack_type: str, **kwargs) -> np.ndarray:
        """Dispatches specified attack."""
        atk = attack_type.upper()
        if atk == "JPEG":
            return cls.jpeg_compression(img_bgr, quality=kwargs.get("quality", 30))
        elif atk == "NOISE":
            return cls.gaussian_noise(img_bgr, sigma=kwargs.get("sigma", 18.0))
        elif atk == "BLUR":
            return cls.gaussian_blur(img_bgr, ksize=kwargs.get("ksize", 7))
        elif atk == "ROTATION":
            return cls.rotation_attack(img_bgr, angle=kwargs.get("angle", 4.0))
        elif atk == "PERSPECTIVE":
            return cls.perspective_warp(img_bgr, tilt_factor=kwargs.get("tilt_factor", 0.06))
        elif atk == "LIGHTING":
            return cls.brightness_contrast_glare(img_bgr)
        elif atk == "PRINT_SCAN" or atk == "REPRINT":
            return cls.print_scan_simulation(img_bgr)
        elif atk == "TAMPER":
            return cls.tamper_content(img_bgr)
        elif atk == "NONE":
            return img_bgr.copy()
        else:
            return img_bgr.copy()
