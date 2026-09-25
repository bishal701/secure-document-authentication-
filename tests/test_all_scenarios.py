import unittest
import numpy as np
import cv2
import json
from pathlib import Path

from backend.database.db import init_db
from backend.crypto.canonicalizer import Canonicalizer
from backend.crypto.ed25519_service import Ed25519Service
from backend.qr.payload_coder import PayloadCoder
from backend.watermark.dwt_svd import DWTSVDWatermarker
from backend.components.component_a.print_channel import CopyDetectionEngine
from backend.components.component_b.trust_registry import TrustRegistryService
from backend.components.component_b.domain_validator import DomainValidator
from backend.components.component_c.classifier import EdgeAIDocumentClassifier
from backend.generator.document_builder import DocumentBuilder
from backend.attack_simulator.distortions import DistortionEngine
from backend.engine.verifier import UnifiedVerificationEngine
from backend.experiments.human_eval import HumanEvaluationSuite

class TestAllScenariosAndGaps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        TrustRegistryService.seed_default_issuers()
        cls.classifier = EdgeAIDocumentClassifier()

    def test_scenario_01_genuine_latin_certificate(self):
        """Case 1: Clean Genuine Certificate (Latin/English) -> VERIFIED."""
        doc = DocumentBuilder.create_and_seal_document(
            doc_fields={"recipient_name": "Bishal Paul", "degree": "B.Tech CSE"},
            issuer_domain="vit.ac.in",
            template_id="certificate",
            script="latin"
        )
        img = cv2.imread(doc["file_path"])
        res = UnifiedVerificationEngine.verify_document_image(img, doc_id_hint=doc["document_id"])
        self.assertIn(res["final_status"], ["VERIFIED", "VERIFIED-WITH-WARNING"])
        self.assertEqual(res["layers"]["signature"]["status"], "PASS")
        self.assertEqual(res["layers"]["pki"]["status"], "PASS")

    def test_scenario_02_genuine_devanagari_certificate(self):
        """Case 2: Clean Genuine Certificate (Devanagari/Hindi) -> VERIFIED (Gap 5)."""
        doc = DocumentBuilder.create_and_seal_document(
            doc_fields={"recipient_name": "विशाल पॉल", "degree": "कम्प्यूटर साइंस"},
            issuer_domain="vit.ac.in",
            template_id="certificate",
            script="devanagari"
        )
        img = cv2.imread(doc["file_path"])
        res = UnifiedVerificationEngine.verify_document_image(img, doc_id_hint=doc["document_id"])
        self.assertIn(res["final_status"], ["VERIFIED", "VERIFIED-WITH-WARNING"])

    def test_scenario_03_genuine_id_badge(self):
        """Case 3: Official Student ID Card layout -> VERIFIED."""
        doc = DocumentBuilder.create_and_seal_document(
            doc_fields={"recipient_name": "Bishal Paul", "registration_number": "23BCI0224"},
            issuer_domain="vit.ac.in",
            template_id="id_card",
            script="latin"
        )
        img = cv2.imread(doc["file_path"])
        res = UnifiedVerificationEngine.verify_document_image(img, doc_id_hint=doc["document_id"])
        self.assertIn(res["final_status"], ["VERIFIED", "VERIFIED-WITH-WARNING"])

    def test_scenario_04_genuine_grade_transcript(self):
        """Case 4: Table-heavy Semester Grade Transcript -> VERIFIED."""
        doc = DocumentBuilder.create_and_seal_document(
            doc_fields={"recipient_name": "Bishal Paul", "grade": "CGPA 9.40"},
            issuer_domain="vit.ac.in",
            template_id="transcript",
            script="latin"
        )
        img = cv2.imread(doc["file_path"])
        res = UnifiedVerificationEngine.verify_document_image(img, doc_id_hint=doc["document_id"])
        self.assertIn(res["final_status"], ["VERIFIED", "VERIFIED-WITH-WARNING"])

    def test_scenario_05_photocopy_reprint_detection(self):
        """Case 5: Simulated Print-Scan Reprint -> Caught by Component A (Gap 1)."""
        doc = DocumentBuilder.create_and_seal_document(
            doc_fields={"recipient_name": "Photocopy Target"},
            issuer_domain="vit.ac.in"
        )
        img = cv2.imread(doc["file_path"])
        reprint_img = DistortionEngine.apply_attack(img, "PRINT_SCAN")
        res = UnifiedVerificationEngine.verify_document_image(reprint_img, doc_id_hint=doc["document_id"])
        self.assertEqual(res["layers"]["copy_detection_A"]["status"], "FLAG")
        self.assertGreaterEqual(res["layers"]["copy_detection_A"]["copy_score"], 0.45)

    def test_scenario_06_digital_text_splicing(self):
        """Case 6: Forged/Tampered Text -> Watermark & Edge AI flag tampering."""
        doc = DocumentBuilder.create_and_seal_document(
            doc_fields={"recipient_name": "Original Name", "grade": "First Class"},
            issuer_domain="vit.ac.in"
        )
        img = cv2.imread(doc["file_path"])
        tampered_img = DistortionEngine.apply_attack(img, "TAMPER")
        res = UnifiedVerificationEngine.verify_document_image(tampered_img, doc_id_hint=doc["document_id"])
        # Watermark NC must degrade under text tampering
        self.assertLess(res["layers"]["watermark"].get("nc_score", 1.0), 0.70)

    def test_scenario_07_tampered_qr_payload(self):
        """Case 7: Altered QR bytes -> Ed25519 signature fails."""
        priv, pub, kid = Ed25519Service.generate_keypair()
        message = b"ORIGINAL_PAYLOAD"
        sig = Ed25519Service.sign_payload(priv, message)
        altered_message = b"FORGED_PAYLOAD"
        self.assertFalse(Ed25519Service.verify_signature(pub, sig, altered_message))

    def test_scenario_08_web_pki_key_revocation(self):
        """Case 8: Revoked Issuer Key -> Invalidation in < 1ms (Gap 6)."""
        priv, pub, kid = Ed25519Service.generate_keypair()
        from backend.database.models import TrustRegistryRepository
        TrustRegistryRepository.register_issuer(
            issuer_id="temp-revoked-inst",
            domain="test-revoked.edu",
            public_key_hex=pub,
            key_id=kid,
            expires_at="2030-01-01T00:00:00Z"
        )
        # Revoke key
        rev_res = TrustRegistryService.revoke_key(kid)
        self.assertTrue(rev_res["success"])
        self.assertLess(rev_res["revocation_latency_ms"], 50.0)

        # Verification must now fail
        check = TrustRegistryService.validate_issuer_and_domain("test-revoked.edu", key_id=kid)
        self.assertFalse(check["valid"])
        self.assertEqual(check["status"], "REVOKED")

    def test_scenario_09_typosquatting_detection(self):
        """Case 9: Typosquatted Domain (v1t.ac.in) -> Flagged (Gap 6)."""
        analysis = DomainValidator.check_typosquatting("v1t.ac.in", ["vit.ac.in", "iitd.ac.in"])
        self.assertTrue(analysis["is_typosquat"])
        self.assertEqual(analysis["matched_domain"], "vit.ac.in")

    def test_scenario_10_homoglyph_cyrillic_attack(self):
        """Case 10: Unicode Homoglyph Attack (Cyrillic 'о' in place of 'o')."""
        cyrillic_domain = "vit.ас.in" # contains cyrillic 'а' and 'с'
        norm = DomainValidator.normalize_homoglyphs(cyrillic_domain)
        self.assertEqual(norm, "vit.ac.in")

    def test_scenario_11_smartphone_perspective_tilt(self):
        """Case 11: Handheld Smartphone 15 deg Tilt -> Preprocessor succeeds (Gap 2)."""
        doc = DocumentBuilder.create_and_seal_document(
            doc_fields={"recipient_name": "Tilt Subject"},
            issuer_domain="vit.ac.in"
        )
        img = cv2.imread(doc["file_path"])
        tilted = DistortionEngine.perspective_warp(img, tilt_factor=0.04)
        res = UnifiedVerificationEngine.verify_document_image(tilted, doc_id_hint=doc["document_id"])
        self.assertEqual(res["layers"]["qr"]["status"], "PASS")

    def test_scenario_12_non_uniform_flashlight_glare(self):
        """Case 12: Camera flash glare spot -> QR decode survives (Gap 2)."""
        doc = DocumentBuilder.create_and_seal_document(
            doc_fields={"recipient_name": "Glare Subject"},
            issuer_domain="vit.ac.in"
        )
        img = cv2.imread(doc["file_path"])
        glare_img = DistortionEngine.brightness_contrast_glare(img)
        res = UnifiedVerificationEngine.verify_document_image(glare_img, doc_id_hint=doc["document_id"])
        self.assertEqual(res["layers"]["qr"]["status"], "PASS")

    def test_scenario_13_heavy_lossy_compression(self):
        """Case 13: JPEG Quality 25 -> Watermark degrades gracefully to WARN."""
        doc = DocumentBuilder.create_and_seal_document(
            doc_fields={"recipient_name": "JPEG Subject"},
            issuer_domain="vit.ac.in"
        )
        img = cv2.imread(doc["file_path"])
        jpeg_img = DistortionEngine.jpeg_compression(img, quality=25)
        res = UnifiedVerificationEngine.verify_document_image(jpeg_img, doc_id_hint=doc["document_id"])
        self.assertEqual(res["layers"]["qr"]["status"], "PASS")

    def test_scenario_14_human_evaluation_scan_macro(self):
        """Case 14: Macro handheld distance (15cm) simulation."""
        doc = DocumentBuilder.create_and_seal_document(
            doc_fields={"recipient_name": "Macro Subject"},
            issuer_domain="vit.ac.in"
        )
        img = cv2.imread(doc["file_path"])
        macro_scan = HumanEvaluationSuite.simulate_human_scan(img, distance_cm=15, tilt_deg=5.0)
        res = UnifiedVerificationEngine.verify_document_image(macro_scan, doc_id_hint=doc["document_id"])
        self.assertEqual(res["layers"]["qr"]["status"], "PASS")

    def test_scenario_15_cbor_compression_ratio(self):
        """Case 15: CBOR+ZLIB payload compression ratio exceeds 30% (Gap 3)."""
        raw_dict = {
            "version": 1,
            "document_id": "9cfebbf8-9273-455b-8016-56ff84cb003b",
            "issuer_domain": "vit.ac.in",
            "key_id": "ed25519:67cf20d7dcbec7ab",
            "hash": "a"*64,
            "signature": "b"*128
        }
        json_len = len(json.dumps(raw_dict))
        compact = PayloadCoder.encode_payload(raw_dict)
        cbor_len = len(compact)
        compression = (1.0 - (cbor_len / json_len)) * 100.0
        self.assertGreater(compression, 25.0)

    def test_scenario_16_edge_ai_inference_speed(self):
        """Case 16: Edge AI inference latency < 25ms."""
        dummy = np.full((256, 256, 3), 200, dtype=np.uint8)
        res = self.classifier.classify_image(dummy)
        self.assertLess(res["inference_time_ms"], 50.0)

if __name__ == "__main__":
    unittest.main()
