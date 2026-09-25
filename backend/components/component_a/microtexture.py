import numpy as np
import cv2
from scipy import fftpack
from skimage.feature import graycomatrix, graycoprops
from typing import Dict, Any, Tuple

class MicrotextureExtractor:
    """
    Extracts print-channel microtexture descriptors, GLCM features,
    and 2D-DCT high-frequency energy ratios for blind copy detection.
    """

    @staticmethod
    def extract_roi(img: np.ndarray, roi_box: Tuple[float, float, float, float] = (0.1, 0.1, 0.4, 0.4)) -> np.ndarray:
        """
        Extracts a normalized region of interest (ymin, xmin, ymax, xmax as fractions).
        Default extracts top-left background / texture zone.
        """
        h, w = img.shape[:2]
        ymin, xmin, ymax, xmax = roi_box
        y1, y2 = int(ymin * h), int(ymax * h)
        x1, x2 = int(xmin * w), int(xmax * w)
        roi = img[y1:y2, x1:x2]
        if roi.size == 0:
            return img
        return roi

    @staticmethod
    def compute_residual_noise(gray_roi: np.ndarray) -> np.ndarray:
        """
        Calculates high-frequency noise residual: R = |I - GaussianBlur(I)|
        """
        blurred = cv2.GaussianBlur(gray_roi, (5, 5), 1.0)
        residual = cv2.absdiff(gray_roi, blurred)
        return residual

    @staticmethod
    def compute_glcm_features(gray_roi: np.ndarray) -> Dict[str, float]:
        """
        Computes Haralick GLCM texture features.
        """
        # Downsample grayscale to 32 levels for fast, robust co-occurrence
        quantized = (gray_roi // 8).astype(np.uint8)
        glcm = graycomatrix(
            quantized,
            distances=[1, 2, 4],
            angles=[0, np.pi/4, np.pi/2, 3*np.pi/4],
            levels=32,
            symmetric=True,
            normed=True
        )

        contrast = float(np.mean(graycoprops(glcm, 'contrast')))
        dissimilarity = float(np.mean(graycoprops(glcm, 'dissimilarity')))
        homogeneity = float(np.mean(graycoprops(glcm, 'homogeneity')))
        energy = float(np.mean(graycoprops(glcm, 'energy')))
        correlation = float(np.mean(graycoprops(glcm, 'correlation')))

        return {
            "glcm_contrast": contrast,
            "glcm_dissimilarity": dissimilarity,
            "glcm_homogeneity": homogeneity,
            "glcm_energy": energy,
            "glcm_correlation": correlation
        }

    @staticmethod
    def compute_dct_frequency_profile(gray_roi: np.ndarray) -> Dict[str, float]:
        """
        Computes 2D-DCT high-frequency energy ratio and spectral entropy.
        Photocopy and reprint channels lose high-frequency energy.
        """
        roi_float = gray_roi.astype(np.float64) - 128.0
        # Resize to standard 128x128 for uniform DCT spectrum
        roi_std = cv2.resize(roi_float, (128, 128))
        dct_2d = fftpack.dctn(roi_std, norm='ortho')
        energy_matrix = dct_2d ** 2
        total_energy = np.sum(energy_matrix) + 1e-9

        # Mask high frequency triangle (u + v >= 64)
        u, v = np.indices((128, 128))
        high_freq_mask = (u + v) >= 64
        high_freq_energy = np.sum(energy_matrix[high_freq_mask])
        hf_ratio = float(high_freq_energy / total_energy)

        # Mid frequency mask (32 <= u + v < 64)
        mid_freq_mask = ((u + v) >= 32) & ((u + v) < 64)
        mid_freq_energy = np.sum(energy_matrix[mid_freq_mask])
        mf_ratio = float(mid_freq_energy / total_energy)

        return {
            "dct_hf_energy_ratio": hf_ratio,
            "dct_mf_energy_ratio": mf_ratio,
            "dct_total_energy": float(total_energy)
        }

    @classmethod
    def extract_all_features(cls, image_bgr: np.ndarray) -> Dict[str, Any]:
        """
        Full feature pipeline for blind copy detection.
        """
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if len(image_bgr.shape) == 3 else image_bgr
        roi = cls.extract_roi(gray)

        residual = cls.compute_residual_noise(roi)
        noise_variance = float(np.var(residual))
        noise_mean = float(np.mean(residual))

        glcm_feats = cls.compute_glcm_features(roi)
        dct_feats = cls.compute_dct_frequency_profile(roi)

        features = {
            "noise_variance": noise_variance,
            "noise_mean": noise_mean,
            **glcm_feats,
            **dct_feats
        }
        return features
