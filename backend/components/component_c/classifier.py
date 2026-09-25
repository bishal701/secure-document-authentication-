import time
import joblib
import numpy as np
from pathlib import Path
from typing import Dict, Any, Tuple
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from backend.components.component_c.feature_extractor import EdgeAIFeatureExtractor
from backend.config import MODELS_DIR

MODEL_PATH = MODELS_DIR / "edge_ai_classifier.joblib"

class EdgeAIDocumentClassifier:
    """
    Component C: Secondary Edge AI Classifier.
    Classes:
      0: GENUINE
      1: REPRINTED
      2: TAMPERED
    Operates in <15ms on edge/CPU. Non-blocking supporting signal.
    """

    CLASS_NAMES = ["GENUINE", "REPRINTED", "TAMPERED"]

    def __init__(self):
        self.model = None
        self._load_or_train_bootstrap()

    def _bootstrap_synthetic_dataset(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Synthesizes a multi-condition feature dataset for Edge AI bootstrapping:
        - Class 0 (Genuine): Crisp edges, balanced gradients, minimal residual noise
        - Class 1 (Reprinted): Attenuated high-frequencies, blur, halftoning noise
        - Class 2 (Tampered): Strong local quadrant variance spikes, boundary cuts, splicing
        """
        np.random.seed(42)
        dummy_img = np.full((256, 256, 3), 200, dtype=np.uint8)
        sample_feats = EdgeAIFeatureExtractor.extract_features(dummy_img)
        n_features = len(sample_feats)

        X = []
        y = []

        # Class 0: GENUINE (n=100)
        for _ in range(100):
            base = np.random.normal(0.4, 0.08, n_features)
            # Higher sharpness, lower noise
            base[8] = np.random.uniform(0.6, 0.9)  # Laplacian variance
            base[20] = np.random.uniform(0.01, 0.04) # noise
            X.append(base)
            y.append(0)

        # Class 1: REPRINTED (n=100)
        for _ in range(100):
            base = np.random.normal(0.35, 0.1, n_features)
            base[8] = np.random.uniform(0.1, 0.35) # reduced sharpness
            base[20] = np.random.uniform(0.08, 0.22) # elevated print noise
            base[16:20] *= 0.5
            X.append(base)
            y.append(1)

        # Class 2: TAMPERED (n=100)
        for _ in range(100):
            base = np.random.normal(0.42, 0.12, n_features)
            base[10:14] += np.random.uniform(0.3, 0.7, 4)
            base[20] = np.random.uniform(0.15, 0.4)
            X.append(base)
            y.append(2)

        return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32)

    def _load_or_train_bootstrap(self):
        dummy_img = np.full((256, 256, 3), 200, dtype=np.uint8)
        sample_feats = EdgeAIFeatureExtractor.extract_features(dummy_img)
        
        if MODEL_PATH.exists():
            try:
                loaded = joblib.load(MODEL_PATH)
                # Test feature compatibility
                loaded.predict_proba([sample_feats])
                self.model = loaded
                return
            except Exception:
                pass

        # Train fast calibrated classifier
        X, y = self._bootstrap_synthetic_dataset()
        base_rf = RandomForestClassifier(n_estimators=40, max_depth=6, random_state=42)
        calibrated = CalibratedClassifierCV(estimator=base_rf, method='sigmoid', cv=3)
        calibrated.fit(X, y)
        self.model = calibrated
        joblib.dump(self.model, MODEL_PATH)

    def classify_image(self, img_bgr: np.ndarray) -> Dict[str, Any]:
        """
        Runs Edge AI inference on document image.
        Returns:
            predicted_class: 'GENUINE', 'REPRINTED', or 'TAMPERED'
            confidence: float in [0.0, 1.0]
            probabilities: dict of class probabilities
            inference_time_ms: float
            role: 'SECONDARY_SUPPORTING_SIGNAL'
        """
        t0 = time.perf_counter()
        features = EdgeAIFeatureExtractor.extract_features(img_bgr)
        probs = self.model.predict_proba([features])[0]
        t_infer = (time.perf_counter() - t0) * 1000.0

        top_class_idx = int(np.argmax(probs))
        top_class_name = self.CLASS_NAMES[top_class_idx]
        confidence = float(probs[top_class_idx])

        prob_dict = {
            name: round(float(p), 4)
            for name, p in zip(self.CLASS_NAMES, probs)
        }

        # Explainable note
        if top_class_name == "GENUINE":
            note = f"Visual texture and edge distributions align with genuine digital/physical originals ({confidence*100:.1f}% confidence)."
        elif top_class_name == "REPRINTED":
            note = f"Edge softness and spatial noise patterns indicate possible physical reproduction or re-capture ({confidence*100:.1f}% confidence)."
        else:
            note = f"Local gradient anomalies and patch variance spikes suggest localized digital tampering or splicing ({confidence*100:.1f}% confidence)."

        return {
            "predicted_class": top_class_name,
            "confidence": round(confidence, 4),
            "probabilities": prob_dict,
            "inference_time_ms": round(t_infer, 2),
            "note": note,
            "signal_type": "SECONDARY_SUPPORTING_EVIDENCE"
        }
