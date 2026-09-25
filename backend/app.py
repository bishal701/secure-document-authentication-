import os
import io
import base64
import cv2
import numpy as np
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from backend.config import BASE_DIR, STATIC_DIR, RESULTS_DIR, DATASET_DIR
from backend.database.db import init_db
from backend.database.models import DocumentRepository, TrustRegistryRepository, VerificationLogRepository, ExperimentRepository
from backend.generator.document_builder import DocumentBuilder
from backend.engine.verifier import UnifiedVerificationEngine
from backend.attack_simulator.distortions import DistortionEngine
from backend.components.component_b.trust_registry import TrustRegistryService
from backend.components.component_b.domain_validator import DomainValidator
from backend.experiments.runner import ExperimentRunner
from backend.experiments.metrics_exporter import MetricsExporter
from backend.experiments.human_eval import HumanEvaluationSuite

app = FastAPI(
    title="Secure Document Authentication API",
    version="2.0.0",
    description="Research Prototype: Hybrid QR + DWT-SVD Watermarking + Blind Copy Detection + Web-PKI + Edge AI"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Database and default issuers upon startup
@app.on_event("startup")
def startup_event():
    init_db()
    TrustRegistryService.seed_default_issuers()

class GenerateDocRequest(BaseModel):
    recipient_name: str = "Bishal Paul"
    registration_number: str = "23BCI0224"
    degree: str = "B.Tech in Computer Science & Engineering"
    grade: str = "Distinction (9.4 CGPA)"
    institution: str = "VELLORE INSTITUTE OF TECHNOLOGY"
    issuer_domain: str = "vit.ac.in"
    template_id: str = "certificate"
    script: str = "latin"

class RevokeKeyRequest(BaseModel):
    key_id: str

class DomainCheckRequest(BaseModel):
    domain: str

class AttackSimulationRequest(BaseModel):
    document_id: Optional[str] = None
    attack_type: str = "PRINT_SCAN"
    param_val: Optional[float] = None
    image_base64: Optional[str] = None

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "system": "Secure Document Authentication Research Prototype",
        "active_modules": [
            "DWT-SVD Invisible Watermark",
            "Compact CBOR/ZLIB QR Payload",
            "Ed25519 Cryptographic Signatures",
            "Component A: Blind Copy Detection",
            "Component B: Semantic Web-PKI & Trust Registry",
            "Component C: Secondary Edge AI Classifier",
            "Multi-Threat Attack Simulator",
            "Scientific Ablation Benchmarking Suite"
        ]
    }

@app.post("/api/documents/generate")
def generate_document(req: GenerateDocRequest):
    try:
        fields = {
            "recipient_name": req.recipient_name,
            "registration_number": req.registration_number,
            "degree": req.degree,
            "grade": req.grade,
            "institution": req.institution
        }
        result = DocumentBuilder.create_and_seal_document(
            doc_fields=fields,
            issuer_domain=req.issuer_domain,
            template_id=req.template_id,
            script=req.script
        )
        
        # Read saved image and encode base64
        with open(result["file_path"], "rb") as f:
            img_bytes = f.read()
            b64_str = base64.b64encode(img_bytes).decode('utf-8')

        return {
            "success": True,
            "document_id": result["document_id"],
            "issuer_domain": result["issuer_domain"],
            "key_id": result["key_id"],
            "document_hash": result["document_hash"],
            "signature": result["signature"],
            "watermark_metrics": {
                "psnr_db": result["watermark_psnr"],
                "ssim": result["watermark_ssim"]
            },
            "qr_encoded_text": result["qr_encoded_text"],
            "image_base64": f"data:image/png;base64,{b64_str}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/documents/verify")
async def verify_document(request: Request):
    try:
        content_type = request.headers.get("content-type", "")
        img_bytes = None
        doc_id_hint = None

        if "application/json" in content_type:
            body = await request.json()
            doc_id_hint = body.get("doc_id_hint")
            b64 = body.get("image_base64")
            if b64:
                clean_b64 = b64.split(",")[-1]
                img_bytes = base64.b64decode(clean_b64)
        elif "multipart/form-data" in content_type:
            form = await request.form()
            doc_id_hint = form.get("doc_id_hint")
            upload = form.get("file")
            if upload and hasattr(upload, "read"):
                img_bytes = await upload.read()
            elif form.get("image_base64"):
                b64 = form.get("image_base64")
                clean_b64 = b64.split(",")[-1]
                img_bytes = base64.b64decode(clean_b64)
        else:
            # Fallback try json
            try:
                body = await request.json()
                doc_id_hint = body.get("doc_id_hint")
                b64 = body.get("image_base64")
                if b64:
                    clean_b64 = b64.split(",")[-1]
                    img_bytes = base64.b64decode(clean_b64)
            except Exception:
                pass

        if not img_bytes and doc_id_hint:
            doc_path = DATASET_DIR / f"{doc_id_hint}.png"
            if doc_path.exists():
                with open(doc_path, "rb") as f:
                    img_bytes = f.read()

        if not img_bytes:
            raise HTTPException(status_code=400, detail="No document image provided for verification.")

        # Decode image using cv2
        nparr = np.frombuffer(img_bytes, np.uint8)
        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            raise HTTPException(status_code=400, detail="Could not decode image.")

        result = UnifiedVerificationEngine.verify_document_image(img_bgr, doc_id_hint=doc_id_hint)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/attack/simulate")
def simulate_attack(req: AttackSimulationRequest):
    try:
        img_bgr = None
        if req.image_base64:
            clean_b64 = req.image_base64.split(",")[-1]
            img_bytes = base64.b64decode(clean_b64)
            nparr = np.frombuffer(img_bytes, np.uint8)
            img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        elif req.document_id:
            path = DATASET_DIR / f"{req.document_id}.png"
            if path.exists():
                img_bgr = cv2.imread(str(path))

        if img_bgr is None:
            raise HTTPException(status_code=400, detail="No source image available for attack simulation.")

        attacked_bgr = DistortionEngine.apply_attack(img_bgr, req.attack_type)
        
        # Verify attacked document immediately
        verification_result = UnifiedVerificationEngine.verify_document_image(
            attacked_bgr,
            doc_id_hint=req.document_id
        )

        _, encimg = cv2.imencode('.png', attacked_bgr)
        b64_attacked = base64.b64encode(encimg).decode('utf-8')

        return {
            "attack_type": req.attack_type,
            "attacked_image_base64": f"data:image/png;base64,{b64_attacked}",
            "verification_result": verification_result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trust-registry")
def list_trust_registry():
    TrustRegistryService.seed_default_issuers()
    return TrustRegistryRepository.list_all()

@app.post("/api/trust-registry/revoke")
def revoke_key(req: RevokeKeyRequest):
    res = TrustRegistryService.revoke_key(req.key_id)
    return res

@app.post("/api/trust-registry/check-domain")
def check_domain_safety(req: DomainCheckRequest):
    all_issuers = TrustRegistryRepository.list_all()
    trusted = [iss["domain"] for iss in all_issuers]
    return DomainValidator.check_typosquatting(req.domain, trusted)

@app.post("/api/experiments/ablation")
def run_ablation(sample_count: int = 5):
    res = ExperimentRunner.run_ablation_study(sample_count=sample_count)
    MetricsExporter.generate_ablation_chart()
    return res

@app.post("/api/experiments/cross-condition")
def run_cross_conditions():
    return ExperimentRunner.run_cross_condition_evaluation()

@app.post("/api/experiments/human-eval")
def run_human_evaluation():
    return HumanEvaluationSuite.run_human_evaluation_benchmark(num_trials_per_condition=1)

@app.get("/api/results/plots")
def generate_and_get_plots():
    roc_path, auc_score = MetricsExporter.generate_roc_plot()
    ablation_chart = MetricsExporter.generate_ablation_chart()

    with open(roc_path, "rb") as f:
        roc_b64 = base64.b64encode(f.read()).decode('utf-8')
    with open(ablation_chart, "rb") as f:
        abl_b64 = base64.b64encode(f.read()).decode('utf-8')

    return {
        "roc_auc": round(auc_score, 4),
        "roc_plot_base64": f"data:image/png;base64,{roc_b64}",
        "ablation_chart_base64": f"data:image/png;base64,{abl_b64}"
    }

@app.get("/api/logs")
def get_verification_logs(limit: int = 20):
    return VerificationLogRepository.get_recent_logs(limit=limit)

# Mount static files for frontend
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Frontend index.html ready."}
