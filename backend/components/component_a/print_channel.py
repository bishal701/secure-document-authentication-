import numpy as np
from typing import Dict, Any, Tuple
from backend.components.component_a.microtexture import MicrotextureExtractor
from backend.config import COPY_DETECTION_THRESHOLD

class CopyDetectionEngine:
    """
    Component A: Blind / Template-Free Copy Detection.
    Evaluates analog print-and-scan degradation, halftoning microtexture,
    and high-frequency modulation loss.
    """

    # Baseline reference statistics estimated from genuine laser/inkjet originals
    GENUINE_BASELINE = {
        "noise_variance": 4.5,
        "dct_hf_energy_ratio": 0.085,
        "glcm_contrast": 0.45,
        "glcm_homogeneity": 0.92,
        "glcm_energy": 0.35
    }

    # Standard deviations for normalization
    FEATURE_STD = {
        "noise_variance": 2.0,
        "dct_hf_energy_ratio": 0.035,
        "glcm_contrast": 0.20,
        "glcm_homogeneity": 0.05,
        "glcm_energy": 0.12
    }

    @classmethod
    def analyze_document(cls, image_bgr: np.ndarray, printer_hint: str = "auto") -> Dict[str, Any]:
        """
        Runs microtexture extraction and computes copy probability score.
        Returns:
            copy_score: float in [0.0, 1.0] (higher means higher likelihood of reprint/copy)
            is_copy: bool (True if copy_score >= threshold)
            features: extracted raw feature dict
            explanation: detailed reasoning
        """
        features = MicrotextureExtractor.extract_all_features(image_bgr)

        # Microtexture Halftoning & Print-Scan Channel Degradation Analysis:
        # Authentic originals retain pristine smoothness (high homogeneity and energy)
        # Second-generation prints/scans introduce halftoning dot-gain and scanner grain
        baseline = cls.GENUINE_BASELINE
        std = cls.FEATURE_STD

        homogeneity_loss = min(
            max(0.0, baseline["glcm_homogeneity"] - features["glcm_homogeneity"])
            / std["glcm_homogeneity"],
            3.0
        )

        energy_loss = min(
            max(0.0, baseline["glcm_energy"] - features["glcm_energy"])
            / std["glcm_energy"],
            3.0
        )

        hf_loss = min(
            max(0.0, baseline["dct_hf_energy_ratio"] - features["dct_hf_energy_ratio"])
            / std["dct_hf_energy_ratio"],
            3.0
        )

        noise_change = min(
            abs(features["noise_variance"] - baseline["noise_variance"])
            / std["noise_variance"],
            3.0
        )

        anomaly_distance = (
            0.35 * homogeneity_loss +
            0.25 * energy_loss +
            0.25 * hf_loss +
            0.15 * noise_change
        )

        # Calibrated Sigmoid to yield copy probability in [0, 1]
        copy_score = float(1.0 / (1.0 + np.exp(-(anomaly_distance - 1.2) * 2.5)))
        copy_score = round(copy_score, 4)

        is_copy = copy_score >= COPY_DETECTION_THRESHOLD

        if copy_score < 0.35:
            verdict = "GENUINE_ORIGINAL_PRINT"
            explanation = "Microtexture and high-frequency spectral ratios match authentic first-generation print characteristics."
        elif copy_score < COPY_DETECTION_THRESHOLD:
            verdict = "BORDERLINE_ACCEPTABLE"
            explanation = "Minor print-channel variations detected, but within acceptable tolerances for varied paper stock."
        elif copy_score < 0.70:
            verdict = "SUSPECTED_REPRINT"
            explanation = "Observable attenuation of high-frequency DCT energy and altered noise variance indicative of rescan or reprint."
        else:
            verdict = "CONFIRMED_PHOTOCOPY_OR_REPRINT"
            explanation = "Severe high-frequency attenuation and unnatural GLCM microtexture signature characteristic of second-generation reproduction."

        return {
            "copy_score": copy_score,
            "is_copy": is_copy,
            "threshold": COPY_DETECTION_THRESHOLD,
            "verdict": verdict,
            "explanation": explanation,
            "features": features
        }
