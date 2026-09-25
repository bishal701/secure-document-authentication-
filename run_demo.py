import sys
import time
import webbrowser
import uvicorn
from pathlib import Path

# Configure utf-8 encoding for Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.database.db import init_db
from backend.components.component_b.trust_registry import TrustRegistryService
from backend.experiments.metrics_exporter import MetricsExporter
from backend.generator.document_builder import DocumentBuilder

def bootstrap_system():
    print("==================================================================")
    print(" [SECURE DOCUMENT AUTHENTICATION RESEARCH PROTOTYPE]")
    print(" Course: Digital Watermarking & Steganography (BCSE323L)")
    print("==================================================================")
    print("[1/4] Initializing SQLite database & repository tables...")
    init_db()

    print("[2/4] Enrolling default institutional authorities into Web-PKI...")
    TrustRegistryService.seed_default_issuers()

    print("[3/4] Generating initial baseline ROC curves and ablation figures...")
    try:
        MetricsExporter.generate_roc_plot()
        MetricsExporter.generate_ablation_chart()
    except Exception as e:
        print(f"  Note on plot generation: {e}")

    print("[4/4] Pre-generating sample authentic credentials for instant testing...")
    try:
        sample_doc = DocumentBuilder.create_and_seal_document(
            doc_fields={
                "recipient_name": "Bishal Paul",
                "registration_number": "23BCI0224",
                "degree": "B.Tech in Computer Science & Engineering",
                "grade": "Distinction (9.4 CGPA)",
                "institution": "VELLORE INSTITUTE OF TECHNOLOGY"
            },
            issuer_domain="vit.ac.in",
            template_id="certificate",
            script="latin"
        )
        print(f"  [OK] Pre-generated genuine document: {sample_doc['document_id']}")
    except Exception as e:
        print(f"  Note on sample doc: {e}")

    print("==================================================================")
    print("Starting Web Application Server on http://127.0.0.1:8000 ...")

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    bootstrap_system()
    import threading
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, log_level="info")
