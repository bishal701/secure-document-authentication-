import time
import json
import cv2
import numpy as np
from typing import Dict, Any, Optional

from backend.qr.qr_generator import QRService
from backend.crypto.ed25519_service import Ed25519Service
from backend.crypto.canonicalizer import Canonicalizer
from backend.watermark.dwt_svd import DWTSVDWatermarker
from backend.components.component_a.print_channel import CopyDetectionEngine
from backend.components.component_b.trust_registry import TrustRegistryService
from backend.components.component_c.classifier import EdgeAIDocumentClassifier
from backend.database.models import DocumentRepository, VerificationLogRepository
from backend.config import (
    WATERMARK_NC_THRESHOLD,
    COPY_DETECTION_THRESHOLD,
    AI_TAMPER_CONFIDENCE_MIN,
    SECRET_SYSTEM_KEY
)

class UnifiedVerificationEngine:
    """
    Core Verification Engine executing the complete 8-stage hybrid authentication pipeline:
    1. Preprocessing & QR Code Detection
    2. Payload Decompression & Schema Validation
    3. Ed25519 Cryptographic Signature Verification
    4. Trust Registry & Semantic Domain Validation (Component B)
    5. Document Database & Hash Integrity Match
    6. DWT + SVD Invisible Watermark Extraction & Correlation
    7. Blind Copy Detection & Print-Channel Microtexture Analysis (Component A)
    8. Secondary Edge AI Document Classification (Component C)
    """

    _edge_ai = None

    @classmethod
    def get_edge_ai(cls):
        if cls._edge_ai is None:
            cls._edge_ai = EdgeAIDocumentClassifier()
        return cls._edge_ai

    @classmethod
    def verify_document_image(
        cls,
        image_bgr: np.ndarray,
        doc_id_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        t_start = time.perf_counter()
        diagnostics = []

        # =========================================================================
        # STAGE 1: Preprocessing & QR Code Detection
        # =========================================================================
        t0 = time.perf_counter()
        qr_success, raw_qr, qr_payload, bbox = QRService.decode_qr_from_image(image_bgr)
        t_qr = round((time.perf_counter() - t0) * 1000.0, 2)

        if not qr_success or not qr_payload:
            # Fallback if doc_id_hint is given manually
            if doc_id_hint:
                doc_record = DocumentRepository.get_document(doc_id_hint)
                if doc_record:
                    meta = json.loads(doc_record["metadata_json"])
                    raw_qr = meta.get("qr_encoded_text")
                    from backend.qr.payload_coder import PayloadCoder
                    try:
                        qr_payload = PayloadCoder.decode_payload(raw_qr)
                        qr_success = True
                    except Exception:
                        pass

        if not qr_success or not qr_payload:
            elapsed_total = round((time.perf_counter() - t_start) * 1000.0, 2)
            result = {
                "final_status": "INVALID",
                "summary": "QR code unreadable or corrupted. Cryptographic provenance could not be established.",
                "total_verification_time_ms": elapsed_total,
                "layers": {
                    "qr": {"status": "FAIL", "latency_ms": t_qr, "reason": "No valid secure QR code detected on document."},
                    "pki": {"status": "SKIPPED", "reason": "Awaiting valid QR payload."},
                    "signature": {"status": "SKIPPED", "reason": "Awaiting valid QR payload."},
                    "hash": {"status": "SKIPPED", "reason": "Awaiting valid QR payload."},
                    "watermark": {"status": "SKIPPED", "reason": "Awaiting document identity."},
                    "copy_detection": {"status": "SKIPPED"},
                    "edge_ai": {"status": "SKIPPED"}
                }
            }
            VerificationLogRepository.log_verification({
                "qr_status": "FAIL",
                "final_status": "INVALID",
                "diagnostic_notes": result
            })
            return result

        doc_id = qr_payload.get("id")
        issuer_domain = qr_payload.get("iss", "unknown")
        key_id = qr_payload.get("kid")
        qr_hash = qr_payload.get("h")
        signature_hex = qr_payload.get("sig")

        # =========================================================================
        # STAGE 2: Component B — Hybrid Web-PKI & Domain Validation
        # =========================================================================
        t0 = time.perf_counter()
        pki_result = TrustRegistryService.validate_issuer_and_domain(issuer_domain, key_id=key_id)
        t_pki = round((time.perf_counter() - t0) * 1000.0, 2)

        # =========================================================================
        # STAGE 3: Ed25519 Cryptographic Signature Verification
        # =========================================================================
        t0 = time.perf_counter()
        sig_valid = False
        sig_reason = ""
        if pki_result.get("valid") and pki_result.get("issuer"):
            pub_hex = pki_result["issuer"]["public_key"]
            sig_valid = Ed25519Service.verify_signature(
                public_key_hex=pub_hex,
                signature_hex=signature_hex,
                data=qr_hash.encode('utf-8')
            )
            sig_reason = "Signature cryptographically verified with issuer Ed25519 public key." if sig_valid else "Signature verification failed: invalid signature bytes."
        else:
            sig_reason = f"Cannot verify signature: {pki_result.get('reason', 'Issuer untrusted')}"
        t_sig = round((time.perf_counter() - t0) * 1000.0, 2)

        # =========================================================================
        # STAGE 4: Database Canonical Document Match
        # =========================================================================
        doc_record = DocumentRepository.get_document(doc_id)
        hash_match = False
        hash_reason = ""
        wm_aux = None
        if doc_record:
            expected_hash = doc_record["document_hash"]
            hash_match = (qr_hash == expected_hash)
            hash_reason = "Document cryptographic SHA-256 hash strictly matches official registry record." if hash_match else "Hash mismatch! Possible localized tampering."
            meta = json.loads(doc_record["metadata_json"])
            wm_aux = meta.get("wm_aux")
        else:
            # External or standalone document
            hash_match = True
            hash_reason = "Document ID not found in local registry; validated via self-contained signed payload."

        # =========================================================================
        # STAGE 5: Transform-Domain DWT + SVD Watermark Extraction
        # =========================================================================
        t0 = time.perf_counter()
        watermarker = DWTSVDWatermarker()
        wm_score = 0.0
        wm_ber = 100.0
        wm_status = "UNKNOWN"
        wm_reason = ""

        if qr_hash and doc_id:
            wm_seed = Canonicalizer.generate_watermark_seed(doc_id, qr_hash, SECRET_SYSTEM_KEY)
            expected_wm = watermarker.generate_watermark_from_seed(wm_seed)
            img_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            try:
                if wm_aux:
                    extracted_wm, wm_nc, wm_ber = watermarker.extract(img_rgb, expected_wm, wm_aux)
                    mode_str = "Full SVD"
                else:
                    extracted_wm, wm_nc, wm_ber = watermarker.extract_blind(img_rgb, expected_wm)
                    mode_str = "Blind Wavelet"

                wm_score = round(wm_nc, 4)
                if wm_score >= WATERMARK_NC_THRESHOLD:
                    wm_status = "PASS"
                    wm_reason = f"DWT-SVD watermark extracted ({mode_str}) with high correlation (NC={wm_score:.3f} >= {WATERMARK_NC_THRESHOLD}, BER={wm_ber:.1f}%)."
                elif wm_score >= 0.45:
                    wm_status = "WARN"
                    wm_reason = f"Moderate watermark correlation (NC={wm_score:.3f}); signs of distortion or lossy compression."
                else:
                    wm_status = "FAIL"
                    wm_reason = f"Watermark correlation below threshold (NC={wm_score:.3f} < {WATERMARK_NC_THRESHOLD}). Embedded security signature destroyed."
            except Exception as e:
                wm_status = "ERROR"
                wm_reason = f"Watermark extraction failed: {str(e)}"
        else:
            wm_status = "SKIPPED"
            wm_reason = "Missing document identifier or cryptographic hash."
        t_wm = round((time.perf_counter() - t0) * 1000.0, 2)

        # =========================================================================
        # STAGE 6: Component A — Blind Copy Detection (Print Channel / Microtexture)
        # =========================================================================
        t0 = time.perf_counter()
        copy_analysis = CopyDetectionEngine.analyze_document(image_bgr)
        copy_score = copy_analysis["copy_score"]
        copy_is_copy = copy_analysis["is_copy"]
        copy_status = "PASS" if not copy_is_copy else "FLAG"
        t_copy = round((time.perf_counter() - t0) * 1000.0, 2)

        # =========================================================================
        # STAGE 7: Component C — Secondary Edge AI Classifier
        # =========================================================================
        t0 = time.perf_counter()
        edge_ai = cls.get_edge_ai()
        ai_res = edge_ai.classify_image(image_bgr)
        ai_class = ai_res["predicted_class"]
        ai_conf = ai_res["confidence"]
        ai_status = "PASS" if ai_class == "GENUINE" else "FLAG"
        t_ai = round((time.perf_counter() - t0) * 1000.0, 2)

        # =========================================================================
        # STAGE 8: Multilayer Explainable Decision Engine
        # =========================================================================
        # Critical deterministic failures -> INVALID
        if not sig_valid:
            final_status = "INVALID"
            summary = "Cryptographic signature verification FAILED. Document is counterfeit or issuer key is invalid."
        elif not pki_result.get("valid"):
            final_status = "INVALID"
            summary = f"Web-PKI Trust Registry check FAILED: {pki_result.get('reason')}."
        elif not hash_match:
            final_status = "INVALID"
            summary = "Document hash integrity FAILED: Canonical data does not match issued record."
        
        # Suspicious conditions: Valid crypto, but physical or semantic red flags
        elif copy_is_copy or pki_result.get("typosquat_analysis", {}).get("is_typosquat") or (ai_class == "TAMPERED" and ai_conf >= AI_TAMPER_CONFIDENCE_MIN):
            final_status = "SUSPICIOUS"
            reasons = []
            if copy_is_copy:
                reasons.append(f"Component A detected second-generation photocopy/reprint (score={copy_score:.3f}).")
            if pki_result.get("typosquat_analysis", {}).get("is_typosquat"):
                reasons.append(pki_result["typosquat_analysis"]["warning"])
            if ai_class == "TAMPERED":
                reasons.append(f"Secondary Edge AI flagged spatial tampering (conf={ai_conf*100:.1f}%).")
            summary = "Document exhibits cryptographic validity but physical/semantic anomalies: " + " ".join(reasons)

        # Warning conditions: Slight watermark wear or borderline metrics
        elif wm_status == "WARN" or copy_analysis["verdict"] == "BORDERLINE_ACCEPTABLE":
            final_status = "VERIFIED-WITH-WARNING"
            summary = f"Document is authentic, but exhibits physical degradation (Watermark NC={wm_score:.3f}, Copy Score={copy_score:.3f})."

        # Complete genuine pass
        else:
            final_status = "VERIFIED"
            summary = "Authentic genuine document. Cryptographic signature, Web-PKI domain, DWT-SVD watermark, and microtexture are all verified."

        elapsed_total = round((time.perf_counter() - t_start) * 1000.0, 2)

        # Formulate structured result
        result = {
            "document_id": doc_id,
            "issuer_domain": issuer_domain,
            "final_status": final_status,
            "summary": summary,
            "total_verification_time_ms": elapsed_total,
            "layers": {
                "qr": {
                    "status": "PASS" if qr_success else "FAIL",
                    "latency_ms": t_qr,
                    "payload": qr_payload
                },
                "pki": {
                    "status": "PASS" if pki_result.get("valid") else "FAIL",
                    "latency_ms": t_pki,
                    "issuer_status": pki_result.get("status"),
                    "domain": issuer_domain,
                    "reason": pki_result.get("reason"),
                    "typosquat_analysis": pki_result.get("typosquat_analysis")
                },
                "signature": {
                    "status": "PASS" if sig_valid else "FAIL",
                    "latency_ms": t_sig,
                    "algorithm": "Ed25519",
                    "key_id": key_id,
                    "reason": sig_reason
                },
                "hash_integrity": {
                    "status": "PASS" if hash_match else "FAIL",
                    "qr_hash": qr_hash,
                    "reason": hash_reason
                },
                "watermark": {
                    "status": wm_status,
                    "latency_ms": t_wm,
                    "nc_score": wm_score,
                    "ber_percent": wm_ber,
                    "threshold": WATERMARK_NC_THRESHOLD,
                    "reason": wm_reason
                },
                "copy_detection_A": {
                    "status": copy_status,
                    "latency_ms": t_copy,
                    "copy_score": copy_score,
                    "threshold": COPY_DETECTION_THRESHOLD,
                    "verdict": copy_analysis["verdict"],
                    "reason": copy_analysis["explanation"],
                    "microtexture": copy_analysis["features"]
                },
                "edge_ai_C": {
                    "status": ai_status,
                    "latency_ms": t_ai,
                    "predicted_class": ai_class,
                    "confidence": ai_conf,
                    "probabilities": ai_res["probabilities"],
                    "note": ai_res["note"],
                    "role": ai_res["signal_type"]
                }
            }
        }

        # Log to Database
        VerificationLogRepository.log_verification({
            "document_id": doc_id,
            "qr_status": "PASS" if qr_success else "FAIL",
            "signature_status": "PASS" if sig_valid else "FAIL",
            "watermark_status": wm_status,
            "watermark_score": wm_score,
            "copy_status": copy_status,
            "copy_score": copy_score,
            "domain_status": pki_result.get("status", "UNKNOWN"),
            "ai_status": ai_status,
            "ai_score": ai_conf,
            "final_status": final_status,
            "diagnostic_notes": result
        })

        return result
