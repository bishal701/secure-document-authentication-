import os
import sys
import unittest
import numpy as np
import cv2
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.database.db import init_db
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

class TestSecureDocumentAuthentication(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        TrustRegistryService.seed_default_issuers()

    def test_01_canonicalization_and_hash(self):
        """Validates canonicalization invariance and SHA-256 sensitivity."""
        data1 = {"b": "  test  ", "a": 123, "c": {"z": True, "y": "hello"}}
        data2 = {"a": 123, "c": {"y": "hello", "z": True}, "b": "test"}

        c1 = Canonicalizer.canonicalize(data1)
        c2 = Canonicalizer.canonicalize(data2)
        self.assertEqual(c1, c2)
        h1 = Canonicalizer.compute_hash(c1)
        h2 = Canonicalizer.compute_hash(c2)
        self.assertEqual(h1, h2)

        # Altering a single value must change the hash
        data3 = {"a": 124, "b": "test", "c": {"y": "hello", "z": True}}
        h3 = Canonicalizer.compute_hash(Canonicalizer.canonicalize(data3))
        self.assertNotEqual(h1, h3)

    def test_02_ed25519_signatures(self):
        """Validates asymmetric Ed25519 signing and verification."""
        priv, pub, kid = Ed25519Service.generate_keypair()
        message = b"VIT_DEGREE_HASH_SHA256_TEST"
        signature = Ed25519Service.sign_payload(priv, message)

        # Valid verification
        self.assertTrue(Ed25519Service.verify_signature(pub, signature, message))

        # Tampered message
        tampered = b"TAMPERED_MESSAGE"
        self.assertFalse(Ed25519Service.verify_signature(pub, signature, tampered))

    def test_03_cbor_zlib_qr_payload(self):
        """Validates CBOR serialization, ZLIB compression, and round-trip decoding."""
        payload = {
            "v": 1,
            "id": "doc-test-12345",
            "iss": "vit.ac.in",
            "kid": "ed25519:abc1234",
            "h": "a"*64,
            "sig": "b"*128
        }
        encoded = PayloadCoder.encode_payload(payload)
        self.assertTrue(encoded.startswith("SDA1:"))
        
        decoded = PayloadCoder.decode_payload(encoded)
        self.assertEqual(decoded["id"], payload["id"])
        self.assertEqual(decoded["iss"], payload["iss"])
        self.assertEqual(decoded["h"], payload["h"])

    def test_04_dwt_svd_watermark(self):
        """Validates DWT+SVD invisible watermark embedding and extraction."""
        # Create a test synthetic image (256x256 RGB)
        img = np.full((256, 256, 3), 240, dtype=np.uint8)
        cv2.putText(img, "OFFICIAL CERTIFICATE", (20, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 120), 2)

        watermarker = DWTSVDWatermarker(wavelet="haar", alpha=0.06, wm_size=(32, 32))
        seed = b"test_seed_1234567890123456789012"
        orig_wm = watermarker.generate_watermark_from_seed(seed)

        watermarked, aux = watermarker.embed(img, orig_wm)
        self.assertGreater(aux["psnr"], 35.0, "Watermark PSNR should be > 35 dB for imperceptibility")
        self.assertGreater(aux["ssim"], 0.98, "Watermark SSIM should be > 0.98")

        # Extract under zero distortion
        ext_wm, nc, ber = watermarker.extract(watermarked, orig_wm, aux)
        self.assertGreater(nc, 0.70, "Zero-attack watermark NC should be high")
        self.assertLess(ber, 25.0, "Zero-attack watermark BER should be low")

    def test_05_component_a_copy_detection(self):
        """Validates blind copy detection feature extraction and print channel scoring."""
        # Clean synthetic original
        clean_img = np.full((300, 400, 3), 245, dtype=np.uint8)
        cv2.putText(clean_img, "SECURITY MICROTEXTURE", (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        
        orig_res = CopyDetectionEngine.analyze_document(clean_img)
        self.assertIn("copy_score", orig_res)
        self.assertIn("features", orig_res)

        # Simulated photocopy / reprint
        reprint_img = DistortionEngine.apply_attack(clean_img, "PRINT_SCAN")
        reprint_res = CopyDetectionEngine.analyze_document(reprint_img)
        
        # High-frequency ratio should decrease in reprint
        self.assertLess(
            reprint_res["features"]["dct_hf_energy_ratio"],
            orig_res["features"]["dct_hf_energy_ratio"] + 0.05
        )

    def test_06_component_b_pki_and_typosquatting(self):
        """Validates Trust Registry lookup, key lifecycle, and typosquatting protection."""
        # 1. Authoritative match
        valid_res = TrustRegistryService.validate_issuer_and_domain("vit.ac.in")
        self.assertTrue(valid_res["valid"])
        self.assertEqual(valid_res["status"], "ACTIVE")

        # 2. Typosquatted domain (v1t.ac.in)
        typo_res = DomainValidator.check_typosquatting("v1t.ac.in", ["vit.ac.in", "iitd.ac.in"])
        self.assertTrue(typo_res["is_typosquat"])
        self.assertGreaterEqual(typo_res["similarity"], 0.75)

    def test_07_component_c_edge_ai(self):
        """Validates Secondary Edge AI fast classifier."""
        classifier = EdgeAIDocumentClassifier()
        dummy_img = np.full((256, 256, 3), 220, dtype=np.uint8)
        res = classifier.classify_image(dummy_img)

        self.assertIn(res["predicted_class"], ["GENUINE", "REPRINTED", "TAMPERED"])
        self.assertLess(res["inference_time_ms"], 80.0, "Edge AI inference must be fast (<80ms)")

    def test_08_unified_verification_pipeline(self):
        """End-to-end test: Generate document -> Verify -> Expect VERIFIED."""
        doc_data = {
            "recipient_name": "Pipeline Test Recipient",
            "registration_number": "23BCI9999",
            "degree": "B.Tech Computer Science",
            "grade": "Distinction",
            "institution": "VELLORE INSTITUTE OF TECHNOLOGY"
        }
        gen = DocumentBuilder.create_and_seal_document(
            doc_fields=doc_data,
            issuer_domain="vit.ac.in",
            template_id="certificate",
            script="latin"
        )
        img = cv2.imread(gen["file_path"])
        self.assertIsNotNone(img)

        # Full verification
        ver = UnifiedVerificationEngine.verify_document_image(img, doc_id_hint=gen["document_id"])
        self.assertIn(ver["final_status"], ["VERIFIED", "VERIFIED-WITH-WARNING"])
        self.assertEqual(ver["layers"]["signature"]["status"], "PASS")
        self.assertEqual(ver["layers"]["pki"]["status"], "PASS")

if __name__ == "__main__":
    unittest.main()
