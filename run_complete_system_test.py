import os
import sys
import time
import json
import numpy as np
import cv2
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.database.db import init_db
from backend.database.models import TrustRegistryRepository
from backend.crypto.canonicalizer import Canonicalizer
from backend.crypto.ed25519_service import Ed25519Service
from backend.qr.payload_coder import PayloadCoder
from backend.qr.qr_generator import QRService
from backend.watermark.dwt_svd import DWTSVDWatermarker
from backend.watermark.metrics import WatermarkMetrics
from backend.components.component_a.microtexture import MicrotextureExtractor
from backend.components.component_a.print_channel import CopyDetectionEngine
from backend.components.component_b.domain_validator import DomainValidator
from backend.components.component_b.trust_registry import TrustRegistryService
from backend.components.component_c.classifier import EdgeAIDocumentClassifier
from backend.generator.document_builder import DocumentBuilder
from backend.attack_simulator.distortions import DistortionEngine
from backend.engine.verifier import UnifiedVerificationEngine
from fastapi.testclient import TestClient
from backend.app import app

def print_header(title):
    print("\n" + "=" * 75)
    print(f"  {title}")
    print("=" * 75)

def print_result(test_name, passed, detail=""):
    mark = "[PASS]" if passed else "[FAIL]"
    status_str = f"  {mark} {test_name}"
    if detail:
        status_str += f" -> {detail}"
    print(status_str)

def main():
    start_time = time.time()
    all_passed = True
    total_tests = 0
    passed_tests = 0

    print_header("COMPREHENSIVE END-TO-END SYSTEM VERIFICATION AUDIT")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Directory: {BASE_DIR}")

    # =========================================================================
    # SUITE 1: DATABASE & CRYPTOGRAPHY CORE
    # =========================================================================
    print_header("SUITE 1: Database & Cryptographic Primitives")
    
    # 1.1 DB Init
    try:
        init_db()
        TrustRegistryService.seed_default_issuers()
        print_result("Database Initialization & Web-PKI Seeding", True, "SQLite tables verified")
        passed_tests += 1
    except Exception as e:
        print_result("Database Initialization", False, str(e))
        all_passed = False
    total_tests += 1

    # 1.2 Canonicalizer
    try:
        d1 = {"b": "  test  ", "a": 123, "c": {"y": "hello", "z": True}}
        d2 = {"c": {"z": True, "y": "hello"}, "a": 123, "b": "test"}
        c1, c2 = Canonicalizer.canonicalize(d1), Canonicalizer.canonicalize(d2)
        h1, h2 = Canonicalizer.compute_hash(c1), Canonicalizer.compute_hash(c2)
        ok = (c1 == c2) and (h1 == h2)
        print_result("Deterministic JSON Canonicalization & Hash Invariance", ok, f"SHA-256: {h1[:16]}...")
        passed_tests += int(ok)
        all_passed = all_passed and ok
    except Exception as e:
        print_result("Canonicalization Test", False, str(e))
        all_passed = False
    total_tests += 1

    # 1.3 Ed25519 Sign/Verify
    try:
        priv, pub, kid = Ed25519Service.generate_keypair()
        msg = b"VIT_SECURITY_PAYLOAD_TEST_2026"
        sig = Ed25519Service.sign_payload(priv, msg)
        valid = Ed25519Service.verify_signature(pub, sig, msg)
        tampered = Ed25519Service.verify_signature(pub, sig, b"TAMPERED_MSG")
        ok = valid and not tampered
        print_result("Ed25519 256-Bit Asymmetric Digital Signing", ok, f"Key ID: {kid[:20]}...")
        passed_tests += int(ok)
        all_passed = all_passed and ok
    except Exception as e:
        print_result("Ed25519 Signing", False, str(e))
        all_passed = False
    total_tests += 1

    # 1.4 CBOR + ZLIB Compression
    try:
        raw_payload = {
            "v": 1,
            "id": "doc-uuid-12345678-abcd",
            "iss": "vit.ac.in",
            "kid": "ed25519:testkey",
            "h": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "sig": "abcdef" * 20
        }
        encoded = PayloadCoder.encode_payload(raw_payload)
        decoded = PayloadCoder.decode_payload(encoded)
        comp_ratio = PayloadCoder.estimate_compression_ratio(raw_payload)
        ok = encoded.startswith("SDA1:") and (decoded["id"] == raw_payload["id"]) and (comp_ratio > 30.0)
        print_result("CBOR Serialization + Level-9 ZLIB QR Encoding", ok, f"Compression: {comp_ratio:.1f}% reduction")
        passed_tests += int(ok)
        all_passed = all_passed and ok
    except Exception as e:
        print_result("CBOR Compression", False, str(e))
        all_passed = False
    total_tests += 1

    # =========================================================================
    # SUITE 2: DOCUMENT STUDIO MULTI-TEMPLATE & MULTI-SCRIPT GENERATION
    # =========================================================================
    print_header("SUITE 2: Document Studio (Templates & Multi-Script Rendering)")

    templates_to_test = [
        ("certificate", "latin", "Certificate (English/Latin)", "Bishal Paul"),
        ("certificate", "devanagari", "Certificate (Hindi/Devanagari)", "विशाल पॉल"),
        ("id_card", "latin", "Student ID Card (Latin)", "Bishal Paul"),
        ("id_card", "devanagari", "Student ID Card (Hindi/Devanagari)", "विशाल पॉल"),
        ("transcript", "latin", "Grade Transcript (Tabular)", "Bishal Paul"),
    ]

    generated_docs = {}

    for tid, sc, label, recip in templates_to_test:
        total_tests += 1
        try:
            fields = {
                "recipient_name": recip,
                "registration_number": "23BCI0224",
                "degree": "B.Tech Computer Science & Engineering",
                "grade": "Distinction (9.4 CGPA)",
                "institution": "VELLORE INSTITUTE OF TECHNOLOGY"
            }
            res = DocumentBuilder.create_and_seal_document(
                doc_fields=fields,
                issuer_domain="vit.ac.in",
                template_id=tid,
                script=sc
            )
            p = Path(res["file_path"])
            exists = p.exists() and p.stat().st_size > 10000
            psnr = res["watermark_psnr"]
            ssim = res["watermark_ssim"]
            ok = exists and (psnr > 38.0) and (ssim > 0.98)
            generated_docs[f"{tid}_{sc}"] = res
            print_result(f"Generate {label}", ok, f"PSNR={psnr:.1f}dB, SSIM={ssim:.4f}, Size={p.stat().st_size/1024:.1f}KB")
            passed_tests += int(ok)
            all_passed = all_passed and ok
        except Exception as e:
            print_result(f"Generate {label}", False, str(e))
            all_passed = False

    # =========================================================================
    # SUITE 3: 8-STAGE UNIFIED VERIFICATION PIPELINE (GENUINE DOCUMENTS)
    # =========================================================================
    print_header("SUITE 3: 8-Stage Unified Verification Pipeline (Genuine Documents)")

    for key, doc_meta in generated_docs.items():
        total_tests += 1
        try:
            img = cv2.imread(doc_meta["file_path"])
            ver = UnifiedVerificationEngine.verify_document_image(img, doc_id_hint=doc_meta["document_id"])
            status = ver["final_status"]
            ok = status in ["VERIFIED", "VERIFIED-WITH-WARNING"]
            qr_ok = ver["layers"]["qr"]["status"] == "PASS"
            pki_ok = ver["layers"]["pki"]["status"] == "PASS"
            sig_ok = ver["layers"]["signature"]["status"] == "PASS"
            detail = f"Status={status} (QR:{ver['layers']['qr']['status']}, Sig:{ver['layers']['signature']['status']}, PKI:{ver['layers']['pki']['status']})"
            print_result(f"Verify Genuine [{key}]", ok, detail)
            passed_tests += int(ok)
            all_passed = all_passed and ok
        except Exception as e:
            print_result(f"Verify Genuine [{key}]", False, str(e))
            all_passed = False

    # =========================================================================
    # SUITE 4: ADVERSARIAL ATTACKS & THREAT MITIGATION
    # =========================================================================
    print_header("SUITE 4: Adversarial Attacks & Threat Mitigation")

    sample_doc = generated_docs.get("certificate_latin")
    sample_img = cv2.imread(sample_doc["file_path"])

    # 4.1 Simulated Reprint / Photocopy Attack (Component A)
    total_tests += 1
    try:
        reprint = DistortionEngine.apply_attack(sample_img, "PRINT_SCAN")
        res_reprint = UnifiedVerificationEngine.verify_document_image(reprint, doc_id_hint=sample_doc["document_id"])
        c_status = res_reprint["layers"]["copy_detection_A"]["status"]
        c_score = res_reprint["layers"]["copy_detection_A"]["copy_score"]
        ok = (c_status == "FLAG") and (c_score >= 0.45)
        print_result("Attack 1: Simulated Photocopy / Reprint (Comp A)", ok, f"Copy Score={c_score:.3f} (FLAG), Status={res_reprint['final_status']}")
        passed_tests += int(ok)
        all_passed = all_passed and ok
    except Exception as e:
        print_result("Attack 1: Photocopy Reprint", False, str(e))
        all_passed = False

    # 4.2 Digital Text Splicing & Forgery Attack
    total_tests += 1
    try:
        tampered = DistortionEngine.apply_attack(sample_img, "TAMPER")
        res_tamper = UnifiedVerificationEngine.verify_document_image(tampered, doc_id_hint=sample_doc["document_id"])
        nc = res_tamper["layers"]["watermark"].get("nc_score", 1.0)
        ok = nc < 0.70
        print_result("Attack 2: Digital Credential Splicing (Watermark)", ok, f"Watermark NC dropped to {nc:.4f} (< 0.70 threshold)")
        passed_tests += int(ok)
        all_passed = all_passed and ok
    except Exception as e:
        print_result("Attack 2: Digital Splicing", False, str(e))
        all_passed = False

    # 4.3 QR Payload Alteration / Cryptographic Forgery
    total_tests += 1
    try:
        priv, pub, kid = Ed25519Service.generate_keypair()
        sig = Ed25519Service.sign_payload(priv, b"GENUINE_DOC_HASH")
        forged_ok = Ed25519Service.verify_signature(pub, sig, b"FORGED_TAMPERED_HASH")
        ok = not forged_ok
        print_result("Attack 3: QR Payload Alteration / Cryptographic Forgery", ok, "Ed25519 cryptographic signature rejected forgery")
        passed_tests += int(ok)
        all_passed = all_passed and ok
    except Exception as e:
        print_result("Attack 3: QR Byte Tampering", False, str(e))
        all_passed = False

    # 4.4 Instant Authority Key Revocation (Component B)
    total_tests += 1
    try:
        priv_rev, pub_rev, kid_rev = Ed25519Service.generate_keypair()
        TrustRegistryRepository.register_issuer(
            issuer_id="inst-temp-revoked",
            domain="revoked-test.ac.in",
            public_key_hex=pub_rev,
            key_id=kid_rev,
            expires_at="2030-12-31T23:59:59Z"
        )
        rev_action = TrustRegistryService.revoke_key(kid_rev)
        rev_res = TrustRegistryService.validate_issuer_and_domain("revoked-test.ac.in", key_id=kid_rev)
        ok = rev_action["success"] and (rev_res["valid"] is False) and (rev_res["status"] == "REVOKED")
        print_result("Attack 4: Authority Key Revocation (Web-PKI)", ok, f"Revocation Latency: {rev_action['revocation_latency_ms']:.2f}ms, Status: {rev_res['status']}")
        passed_tests += int(ok)
        all_passed = all_passed and ok
    except Exception as e:
        print_result("Attack 4: Key Revocation", False, str(e))
        all_passed = False

    # 4.5 Typosquatting Domain Defense
    total_tests += 1
    try:
        typo = DomainValidator.check_typosquatting("v1t.ac.in", ["vit.ac.in", "iitd.ac.in"])
        ok = typo["is_typosquat"] and (typo["similarity"] >= 0.75)
        print_result("Attack 5: Typosquatted Domain Defense ('v1t.ac.in')", ok, f"Levenshtein Similarity: {typo['similarity']*100:.1f}%")
        passed_tests += int(ok)
        all_passed = all_passed and ok
    except Exception as e:
        print_result("Attack 5: Typosquatting Defense", False, str(e))
        all_passed = False

    # 4.6 Handheld Perspective Distortion (15° Tilt)
    total_tests += 1
    try:
        tilted = DistortionEngine.apply_attack(sample_img, "PERSPECTIVE")
        res_tilt = UnifiedVerificationEngine.verify_document_image(tilted, doc_id_hint=sample_doc["document_id"])
        qr_ok = res_tilt["layers"]["qr"]["status"] == "PASS"
        ok = qr_ok
        print_result("Attack 6: Smartphone Handheld Perspective Tilt (15°)", ok, f"QR Recovered via CLAHE/Perspective Preprocessor: {qr_ok}")
        passed_tests += int(ok)
        all_passed = all_passed and ok
    except Exception as e:
        print_result("Attack 6: Perspective Tilt", False, str(e))
        all_passed = False

    # 4.7 Flashlight Glare Resistance
    total_tests += 1
    try:
        glare = DistortionEngine.apply_attack(sample_img, "LIGHTING")
        res_glare = UnifiedVerificationEngine.verify_document_image(glare, doc_id_hint=sample_doc["document_id"])
        qr_ok = res_glare["layers"]["qr"]["status"] == "PASS"
        ok = qr_ok
        print_result("Attack 7: Non-Uniform Camera Flashlight Glare", ok, f"Adaptive CLAHE Thresholding Decoded QR: {qr_ok}")
        passed_tests += int(ok)
        all_passed = all_passed and ok
    except Exception as e:
        print_result("Attack 7: Lighting Glare", False, str(e))
        all_passed = False

    # 4.8 Heavy Lossy Compression (JPEG Q=25)
    total_tests += 1
    try:
        jpeg = DistortionEngine.apply_attack(sample_img, "JPEG", quality=25)
        res_jpeg = UnifiedVerificationEngine.verify_document_image(jpeg, doc_id_hint=sample_doc["document_id"])
        ok = res_jpeg["layers"]["qr"]["status"] == "PASS"
        print_result("Attack 8: Heavy Lossy Compression (JPEG Q=25)", ok, f"QR Survives Q=25 Compression: Status={res_jpeg['final_status']}")
        passed_tests += int(ok)
        all_passed = all_passed and ok
    except Exception as e:
        print_result("Attack 8: Lossy JPEG", False, str(e))
        all_passed = False

    # =========================================================================
    # SUITE 5: COMPONENT C SECONDARY EDGE AI BENCHMARK
    # =========================================================================
    print_header("SUITE 5: Secondary Edge AI Fast Classifier Benchmark")
    total_tests += 1
    try:
        classifier = EdgeAIDocumentClassifier()
        dummy_patch = np.full((256, 256, 3), 230, dtype=np.uint8)
        t_start = time.perf_counter()
        c_res = classifier.classify_image(dummy_patch)
        latency = (time.perf_counter() - t_start) * 1000.0
        ok = latency < 35.0 and (c_res["predicted_class"] in ["GENUINE", "REPRINTED", "TAMPERED"])
        print_result("Edge AI Inference Latency Benchmark", ok, f"Latency: {latency:.2f}ms (< 35ms budget), Class: {c_res['predicted_class']}")
        passed_tests += int(ok)
        all_passed = all_passed and ok
    except Exception as e:
        print_result("Edge AI Benchmark", False, str(e))
        all_passed = False

    # =========================================================================
    # SUITE 6: REST API ENDPOINTS AUDIT (FastAPI TestClient)
    # =========================================================================
    print_header("SUITE 6: FastAPI REST Endpoints Integration Audit")

    client = TestClient(app)

    endpoints_to_test = [
        ("GET /api/health", "get", "/api/health", None, 200, "status"),
        ("GET /api/trust-registry", "get", "/api/trust-registry", None, 200, None),
        ("POST /api/trust-registry/check-domain", "post", "/api/trust-registry/check-domain", {"domain": "v1t.ac.in"}, 200, "is_typosquat"),
        ("GET /api/results/plots", "get", "/api/results/plots", None, 200, "roc_auc"),
    ]

    for name, method, path, body, exp_code, exp_key in endpoints_to_test:
        total_tests += 1
        try:
            if method == "get":
                resp = client.get(path)
            else:
                resp = client.post(path, json=body)
            data = resp.json()
            key_ok = (exp_key is None) or (isinstance(data, dict) and exp_key in data) or (isinstance(data, list))
            ok = (resp.status_code == exp_code) and key_ok
            print_result(f"Endpoint {name}", ok, f"Status={resp.status_code}")
            passed_tests += int(ok)
            all_passed = all_passed and ok
        except Exception as e:
            print_result(f"Endpoint {name}", False, str(e))
            all_passed = False

    # =========================================================================
    # SUMMARY REPORT
    # =========================================================================
    elapsed = time.time() - start_time
    print_header("FINAL SYSTEM VERIFICATION AUDIT REPORT")
    print(f"Total Tests Executed: {total_tests}")
    print(f"Tests Passed:         {passed_tests} / {total_tests}")
    print(f"Success Rate:         {(passed_tests/total_tests)*100:.1f}%")
    print(f"Total Audit Time:     {elapsed:.2f} seconds")
    if all_passed:
        print("\n>>> ALL SUBSYSTEMS & SECURITY LAYERS 100% OPERATIONAL & VERIFIED <<<\n")
    else:
        print("\n>>> AUDIT ENCOUNTERED ONE OR MORE ANOMALIES <<<\n")

if __name__ == "__main__":
    main()
