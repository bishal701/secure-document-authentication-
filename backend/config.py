import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "dataset"
RESULTS_DIR = BASE_DIR / "results"
MODELS_DIR = BASE_DIR / "models"
DOCS_DIR = BASE_DIR / "docs"
STATIC_DIR = BASE_DIR / "frontend"

DB_PATH = BASE_DIR / "backend" / "database" / "secure_auth.db"

# Ensure runtime directories exist
for folder in [DATASET_DIR, RESULTS_DIR, MODELS_DIR, DOCS_DIR, STATIC_DIR, DB_PATH.parent]:
    folder.mkdir(parents=True, exist_ok=True)

# Watermark parameters
DWT_WAVELET = "haar"
WATERMARK_ALPHA = 1.0
WATERMARK_SIZE = (64, 64)

# Thresholds for decision engine
WATERMARK_NC_THRESHOLD = 0.70       # Normalized correlation minimum for genuine watermark
COPY_DETECTION_THRESHOLD = 0.45    # Below 0.45 is likely genuine; above is suspected reprint
AI_TAMPER_CONFIDENCE_MIN = 0.60    # Edge AI confidence threshold for tampering alert
DOMAIN_SIMILARITY_THRESHOLD = 0.80 # Warning if typosquat similarity is above this

SECRET_SYSTEM_KEY = os.environ.get("SDA_SYSTEM_KEY", "SECURE_DOCUMENT_AUTH_SECRET_2026_VIT")
