import numpy as np
import cv2
from typing import Dict, Any, List

class EdgeAIFeatureExtractor:
    """
    Extracts multi-scale spatial and frequency embeddings for document classification.
    Captures edge discontinuities (tampering) and halftoning / blur signatures (reprinting).
    """

    @staticmethod
    def extract_features(img_bgr: np.ndarray) -> np.ndarray:
        """
        Generates a 48-dimensional normalized feature vector.
        """
        # Resize to fixed standard scale for edge inference
        img_std = cv2.resize(img_bgr, (256, 256))
        gray = cv2.cvtColor(img_std, cv2.COLOR_BGR2GRAY)

        features = []

        # 1. Color channel statistics (Mean & Std for B, G, R) -> 6 dims
        for ch in range(3):
            features.append(float(np.mean(img_std[:, :, ch])) / 255.0)
            features.append(float(np.std(img_std[:, :, ch])) / 128.0)

        # 2. Gradient magnitude & edge distribution (Sobel) -> 8 dims
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        grad_mag = np.sqrt(sobel_x**2 + sobel_y**2)

        features.append(float(np.mean(grad_mag)) / 100.0)
        features.append(float(np.std(grad_mag)) / 100.0)
        features.append(float(np.percentile(grad_mag, 95)) / 200.0)

        # Gradient orientation histogram (4 bins)
        grad_angle = np.arctan2(sobel_y, sobel_x)
        hist_angles, _ = np.histogram(grad_angle, bins=4, range=(-np.pi, np.pi), density=True)
        features.extend([float(x) for x in hist_angles])

        # 3. Laplacian variance (blur / sharpness indicator) -> 2 dims
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        features.append(float(np.var(lap)) / 500.0)
        features.append(float(np.mean(np.abs(lap))) / 50.0)

        # 4. Multi-quadrant patch symmetry & splicing discrepancy (4 quadrants) -> 12 dims
        # Tampered documents typically show local variance discrepancies across quadrants
        h_half, w_half = 128, 128
        quads = [
            gray[0:h_half, 0:w_half],
            gray[0:h_half, w_half:256],
            gray[h_half:256, 0:w_half],
            gray[h_half:256, w_half:256]
        ]
        for q in quads:
            features.append(float(np.mean(q)) / 255.0)
            features.append(float(np.std(q)) / 128.0)
            q_res = cv2.absdiff(q, cv2.GaussianBlur(q, (3, 3), 0.8))
            features.append(float(np.mean(q_res)) / 20.0)

        # 5. Fast Fourier Transform (FFT) radial energy distribution -> 8 dims
        f_transform = np.fft.fft2(gray)
        f_shift = np.fft.fftshift(f_transform)
        magnitude_spectrum = 20 * np.log(np.abs(f_shift) + 1e-6)
        
        # Radial slices (low, mid-low, mid-high, high frequencies)
        center_y, center_x = 128, 128
        y, x = np.ogrid[:256, :256]
        r = np.sqrt((x - center_x)**2 + (y - center_y)**2)
        
        for r_min, r_max in [(0, 32), (32, 64), (64, 96), (96, 128)]:
            mask = (r >= r_min) & (r < r_max)
            val = float(np.mean(magnitude_spectrum[mask])) / 200.0
            features.append(val)
            features.append(float(np.std(magnitude_spectrum[mask])) / 50.0)

        # 6. High-pass noise residual Kurtosis and Skewness -> 4 dims
        denoised = cv2.medianBlur(gray, 3)
        noise = gray.astype(np.float64) - denoised.astype(np.float64)
        features.append(float(np.mean(noise**2)) / 50.0)
        features.append(float(np.mean(noise**4)) / 1000.0)

        # Additional contrast distribution -> 8 dims
        contrast_hist, _ = np.histogram(gray, bins=8, range=(0, 256), density=True)
        features.extend([float(x) * 100.0 for x in contrast_hist])

        feat_arr = np.array(features, dtype=np.float32)
        # Clean any NaN / Inf
        feat_arr = np.nan_to_num(feat_arr, nan=0.0, posinf=1.0, neginf=-1.0)
        return feat_arr
