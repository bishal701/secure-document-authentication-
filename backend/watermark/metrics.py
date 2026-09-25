import numpy as np
import cv2
from skimage.metrics import structural_similarity as ssim

class WatermarkMetrics:
    @staticmethod
    def calculate_mse(img1: np.ndarray, img2: np.ndarray) -> float:
        """Mean Squared Error between two images."""
        if img1.shape != img2.shape:
            img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
        return float(np.mean((img1.astype(np.float64) - img2.astype(np.float64)) ** 2))

    @staticmethod
    def calculate_psnr(img1: np.ndarray, img2: np.ndarray) -> float:
        """Peak Signal-to-Noise Ratio in dB."""
        mse = WatermarkMetrics.calculate_mse(img1, img2)
        if mse == 0:
            return 100.0 # Identical images
        max_pixel = 255.0
        return float(20 * np.log10(max_pixel / np.sqrt(mse)))

    @staticmethod
    def calculate_ssim(img1: np.ndarray, img2: np.ndarray) -> float:
        """Structural Similarity Index Measure."""
        if img1.shape != img2.shape:
            img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
        
        # Determine channel axis if color
        if len(img1.shape) == 3:
            return float(ssim(img1, img2, channel_axis=2, data_range=255))
        else:
            return float(ssim(img1, img2, data_range=255))

    @staticmethod
    def calculate_nc(wm1: np.ndarray, wm2: np.ndarray) -> float:
        """
        Normalized Correlation (NC) between original and extracted watermark.
        Formula: sum(wm1 * wm2) / sqrt(sum(wm1^2) * sum(wm2^2))
        """
        w1 = wm1.astype(np.float64).flatten()
        w2 = wm2.astype(np.float64).flatten()
        if len(w1) != len(w2):
            w2 = cv2.resize(wm2, (wm1.shape[1], wm1.shape[0])).astype(np.float64).flatten()
        
        norm1 = np.linalg.norm(w1)
        norm2 = np.linalg.norm(w2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(w1, w2) / (norm1 * norm2))

    @staticmethod
    def calculate_ber(wm1: np.ndarray, wm2: np.ndarray) -> float:
        """
        Bit Error Rate (BER) between binary watermarks as a percentage (0 to 100).
        """
        b1 = (wm1.flatten() > 0.5).astype(int)
        b2 = (wm2.flatten() > 0.5).astype(int)
        if len(b1) != len(b2):
            w2_resized = cv2.resize(wm2, (wm1.shape[1], wm1.shape[0]))
            b2 = (w2_resized.flatten() > 0.5).astype(int)
        
        bit_errors = np.sum(b1 != b2)
        total_bits = len(b1)
        return float((bit_errors / total_bits) * 100.0)
