import uuid
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import cv2
import io
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

from backend.generator.templates import TEMPLATES, DEFAULT_SCRIPTS
from backend.crypto.canonicalizer import Canonicalizer
from backend.crypto.ed25519_service import Ed25519Service
from backend.qr.payload_coder import PayloadCoder
from backend.qr.qr_generator import QRService
from backend.watermark.dwt_svd import DWTSVDWatermarker
from backend.database.models import DocumentRepository, SignatureRepository, TrustRegistryRepository
from backend.config import SECRET_SYSTEM_KEY, DATASET_DIR

class DocumentBuilder:
    """
    Renders high-resolution authentic documents across templates and scripts.
    Integrates Canonicalization, Ed25519 Digital Signing, CBOR-ZLIB QR encoding,
    and DWT-SVD Transform-Domain Watermarking.
    """

    @staticmethod
    def _has_devanagari(text: Any) -> bool:
        if not text:
            return False
        return any('\u0900' <= char <= '\u097f' for char in str(text))

    @classmethod
    def _get_font(cls, size: int, bold: bool = False, script: str = "latin", text: str = ""):
        is_devanagari = (script == "devanagari") or cls._has_devanagari(text)

        if is_devanagari:
            # Check for Windows Nirmala UI font collection (Index 0: Regular, Index 1: Bold)
            nirmala = Path("C:/Windows/Fonts/Nirmala.ttc")
            if nirmala.exists():
                try:
                    return ImageFont.truetype(str(nirmala), size, index=1 if bold else 0)
                except Exception:
                    pass
            for name in ["Nirmala.ttf", "mangal.ttf", "aparaj.ttf", "kokila.ttf"]:
                p = Path(f"C:/Windows/Fonts/{name}")
                if p.exists():
                    try:
                        return ImageFont.truetype(str(p), size)
                    except Exception:
                        pass

        # Standard Latin typography
        latin_names = [
            "arial.ttf", "calibri.ttf", "segoeui.ttf", "georgia.ttf", "DejaVuSans.ttf"
        ] if not bold else [
            "arialbd.ttf", "calibrib.ttf", "segoeuib.ttf", "georgiab.ttf", "DejaVuSans-Bold.ttf"
        ]
        for fn in latin_names:
            try:
                return ImageFont.truetype(fn, size)
            except Exception:
                continue

        # Fallback to Nirmala if available (supports both Latin and Devanagari)
        nirmala = Path("C:/Windows/Fonts/Nirmala.ttc")
        if nirmala.exists():
            try:
                return ImageFont.truetype(str(nirmala), size, index=1 if bold else 0)
            except Exception:
                pass

        return ImageFont.load_default()

    @classmethod
    def _render_certificate(
        cls,
        w: int,
        h: int,
        cfg: Dict[str, Any],
        script_data: Dict[str, Any],
        doc_data: Dict[str, Any],
        qr_img: Image.Image,
        script: str
    ) -> Image.Image:
        bg = cfg["bg_color"]
        prim = cfg["primary_color"]
        acc = cfg["accent_color"]

        img = Image.new("RGB", (w, h), color=bg)
        draw = ImageDraw.Draw(img)

        # 1. Ornate Security Borders (Double outer/inner frame)
        margin = 32
        draw.rectangle([(margin, margin), (w - margin, h - margin)], outline=prim, width=4)
        draw.rectangle([(margin + 9, margin + 9), (w - margin - 9, h - margin - 9)], outline=acc, width=2)
        
        # Corner security rosettes & flourishes
        for cx, cy in [(margin, margin), (w - margin, margin), (margin, h - margin), (w - margin, h - margin)]:
            draw.rectangle([(cx - 5, cy - 5), (cx + 5, cy + 5)], fill=acc)
            draw.rectangle([(cx - 2, cy - 2), (cx + 2, cy + 2)], fill=prim)

        # 2. Institutional Header
        inst_name = doc_data.get("institution", script_data["title_prefix"])
        font_inst = cls._get_font(27, bold=True, script=script, text=inst_name)
        draw.text((w // 2, 85), inst_name, fill=prim, font=font_inst, anchor="mm")

        # Subtle gold divider line with center rosette
        draw.line([(w // 2 - 280, 118), (w // 2 + 280, 118)], fill=acc, width=2)
        draw.polygon([(w // 2, 112), (w // 2 + 6, 118), (w // 2, 124), (w // 2 - 6, 118)], fill=acc)

        # 3. Document Title
        title_text = doc_data.get("title", script_data["doc_title"])
        font_title = cls._get_font(32, bold=True, script=script, text=title_text)
        draw.text((w // 2, 160), title_text, fill=acc, font=font_title, anchor="mm")

        # 4. Body Content (Generous spacing, perfectly centered, guaranteed no overlap)
        recip_label = script_data.get("recipient_label", "This is awarded to:")
        font_label = cls._get_font(18, bold=False, script=script, text=recip_label)
        draw.text((w // 2, 230), recip_label, fill=(90, 95, 105), font=font_label, anchor="mm")

        recipient = doc_data.get("recipient_name", "Bishal Paul")
        font_name = cls._get_font(36, bold=True, script=script, text=recipient)
        draw.text((w // 2, 290), recipient, fill=prim, font=font_name, anchor="mm")
        # Underline recipient
        draw.line([(w // 2 - 200, 320), (w // 2 + 200, 320)], fill=acc, width=2)

        deg = doc_data.get("degree", "B.Tech Computer Science & Engineering")
        prog_text = f"{script_data['program_label']} {deg}"
        font_prog = cls._get_font(21, bold=False, script=script, text=prog_text)
        draw.text((w // 2, 370), prog_text, fill=(45, 50, 60), font=font_prog, anchor="mm")

        reg_no = doc_data.get("registration_number", "23BCI0224")
        grade_val = doc_data.get("grade", "Distinction (9.4 CGPA)")
        details_text = f"Registration No: {reg_no}   |   Classification: {grade_val}"
        font_details = cls._get_font(19, bold=False, script=script, text=details_text)
        draw.text((w // 2, 420), details_text, fill=(60, 65, 75), font=font_details, anchor="mm")

        # Horizontal accent rule separating body and authorization band
        draw.line([(180, 480), (w - 180, 480)], fill=(220, 225, 235), width=1)

        # 5. Security Stamp Area (Component A repeatable ROI - Left Column)
        stamp_cx, stamp_cy = 200, 605
        draw.ellipse([(stamp_cx - 55, stamp_cy - 55), (stamp_cx + 55, stamp_cy + 55)], outline=acc, width=3)
        draw.ellipse([(stamp_cx - 46, stamp_cy - 46), (stamp_cx + 46, stamp_cy + 46)], outline=prim, width=1)
        # Ornate star center
        draw.polygon([
            (stamp_cx, stamp_cy - 8), (stamp_cx + 3, stamp_cy - 3),
            (stamp_cx + 8, stamp_cy), (stamp_cx + 3, stamp_cy + 3),
            (stamp_cx, stamp_cy + 8), (stamp_cx - 3, stamp_cy + 3),
            (stamp_cx - 8, stamp_cy), (stamp_cx - 3, stamp_cy - 3)
        ], fill=acc)
        font_stamp_prim = cls._get_font(12, bold=True, script="latin")
        font_stamp_acc = cls._get_font(11, bold=True, script="latin")
        draw.text((stamp_cx, stamp_cy - 16), "OFFICIAL SEAL", fill=prim, font=font_stamp_prim, anchor="mm")
        draw.text((stamp_cx, stamp_cy + 16), "VIT AUTHENTIC", fill=acc, font=font_stamp_acc, anchor="mm")
        font_stamp_sub = cls._get_font(11, bold=False, script="latin")
        draw.text((stamp_cx, 680), "Institutional Security Seal", fill=(120, 125, 135), font=font_stamp_sub, anchor="mm")

        # 6. Center Column: Authorized Signatory
        sig_cx = w // 2
        draw.line([(sig_cx - 130, 630), (sig_cx + 130, 630)], fill=prim, width=2)
        draw.arc([(sig_cx - 70, 580), (sig_cx + 70, 625)], start=160, end=350, fill=prim, width=2)
        font_sig_name = cls._get_font(15, bold=True, script="latin")
        draw.text((sig_cx, 652), "Dean of Academic Affairs", fill=prim, font=font_sig_name, anchor="mm")
        font_sig_title = cls._get_font(12, bold=False, script="latin")
        draw.text((sig_cx, 674), "Authorized Registrar & Signatory", fill=(110, 115, 125), font=font_sig_title, anchor="mm")

        # 7. Hybrid QR Code placement (Right Column)
        qr_resized = qr_img.resize((140, 140))
        qr_x = w - margin - 9 - 140 - 30
        qr_y = 535
        img.paste(qr_resized, (qr_x, qr_y))
        
        font_meta = cls._get_font(11, bold=True, script="latin")
        draw.text((qr_x + 70, qr_y + 155), "Scan to Verify Web-PKI", fill=(100, 105, 115), font=font_meta, anchor="mm")

        # 8. Document ID & Timestamp Footer (Safely above the bottom border)
        doc_id = doc_data.get("document_id", "DOC-UNKNOWN")
        footer_text = f"Doc ID: {doc_id}  |  Issuer: {doc_data.get('issuer_domain', 'vit.ac.in')}  |  {script_data['auth_footer']}"
        font_footer = cls._get_font(11, bold=False, script=script, text=footer_text)
        draw.text((w // 2, 775), footer_text, fill=(110, 115, 125), font=font_footer, anchor="mm")

        return img

    @classmethod
    def _render_id_card(
        cls,
        w: int,
        h: int,
        cfg: Dict[str, Any],
        script_data: Dict[str, Any],
        doc_data: Dict[str, Any],
        qr_img: Image.Image,
        script: str
    ) -> Image.Image:
        bg = cfg.get("bg_color", (253, 252, 248))
        prim = cfg.get("primary_color", (26, 54, 93))
        acc = cfg.get("accent_color", (197, 160, 89))

        img = Image.new("RGB", (w, h), color=bg)
        draw = ImageDraw.Draw(img)

        # Double border
        margin = 20
        draw.rectangle([(margin, margin), (w - margin, h - margin)], outline=prim, width=3)
        draw.rectangle([(margin + 6, margin + 6), (w - margin - 6, h - margin - 6)], outline=acc, width=1)

        # Institutional Header
        inst_name = doc_data.get("institution", script_data["title_prefix"])
        font_inst = cls._get_font(22, bold=True, script=script, text=inst_name)
        draw.text((w // 2, 55), inst_name, fill=prim, font=font_inst, anchor="mm")

        # Decorative line
        draw.line([(w // 2 - 220, 82), (w // 2 + 220, 82)], fill=acc, width=2)
        font_card_title = cls._get_font(13, bold=True, script="latin")
        draw.text((w // 2, 105), "OFFICIAL STUDENT & SCHOLAR IDENTITY CARD", fill=acc, font=font_card_title, anchor="mm")

        # Recipient Name
        recipient = doc_data.get("recipient_name", "Bishal Paul")
        draw.text((w // 2, 155), "STUDENT / CREDENTIAL HOLDER", fill=(120, 125, 135), font=cls._get_font(11, bold=False), anchor="mm")
        font_name = cls._get_font(28, bold=True, script=script, text=recipient)
        draw.text((w // 2, 192), recipient, fill=prim, font=font_name, anchor="mm")
        draw.line([(w // 2 - 160, 215), (w // 2 + 160, 215)], fill=acc, width=1)

        # Details
        reg_no = doc_data.get("registration_number", "23BCI0224")
        deg = doc_data.get("degree", "B.Tech Computer Science & Engineering")
        grade_val = doc_data.get("grade", "Distinction (9.4 CGPA)")
        draw.text((w // 2, 252), f"Registration No: {reg_no}   |   Program: {deg}", fill=(50, 55, 65), font=cls._get_font(15, bold=False, script=script, text=deg), anchor="mm")
        draw.text((w // 2, 288), f"Classification: {grade_val}   |   Status: Active Scholar", fill=(60, 65, 75), font=cls._get_font(14, bold=False, script=script, text=grade_val), anchor="mm")

        # Seal (Left Column)
        stamp_cx, stamp_cy = 160, 410
        draw.ellipse([(stamp_cx - 45, stamp_cy - 45), (stamp_cx + 45, stamp_cy + 45)], outline=acc, width=2)
        draw.ellipse([(stamp_cx - 37, stamp_cy - 37), (stamp_cx + 37, stamp_cy + 37)], outline=prim, width=1)
        draw.text((stamp_cx, stamp_cy - 10), "OFFICIAL SEAL", fill=prim, font=cls._get_font(10, bold=True), anchor="mm")
        draw.text((stamp_cx, stamp_cy + 10), "VIT AUTHENTIC", fill=acc, font=cls._get_font(9, bold=True), anchor="mm")

        # QR Code (Right Column)
        qr_resized = qr_img.resize((125, 125))
        qr_x = w - margin - 6 - 125 - 35
        qr_y = 350
        img.paste(qr_resized, (qr_x, qr_y))
        draw.text((qr_x + 62, qr_y + 138), "Scan to Verify Web-PKI", fill=(100, 105, 115), font=cls._get_font(10, bold=True), anchor="mm")

        # Footer
        doc_id = doc_data.get("document_id", "DOC-UNKNOWN")
        footer_text = f"Doc ID: {doc_id}  |  Issuer: {doc_data.get('issuer_domain', 'vit.ac.in')}  |  {script_data['auth_footer']}"
        draw.text((w // 2, h - 35), footer_text, fill=(110, 115, 125), font=cls._get_font(10, bold=False, script=script, text=footer_text), anchor="mm")

        return img

    @classmethod
    def _render_transcript(
        cls,
        w: int,
        h: int,
        cfg: Dict[str, Any],
        script_data: Dict[str, Any],
        doc_data: Dict[str, Any],
        qr_img: Image.Image,
        script: str
    ) -> Image.Image:
        bg = cfg["bg_color"]
        prim = cfg["primary_color"]
        acc = cfg["accent_color"]

        img = Image.new("RGB", (w, h), color=bg)
        draw = ImageDraw.Draw(img)

        margin = 35
        # Double border
        draw.rectangle([(margin, margin), (w - margin, h - margin)], outline=prim, width=3)
        draw.rectangle([(margin + 8, margin + 8), (w - margin - 8, h - margin - 8)], outline=acc, width=2)

        # Header
        inst_name = doc_data.get("institution", script_data["title_prefix"])
        font_inst = cls._get_font(26, bold=True, script=script, text=inst_name)
        draw.text((w // 2, 80), inst_name, fill=prim, font=font_inst, anchor="mm")

        title_text = "OFFICIAL ACADEMIC TRANSCRIPT & GRADE RECORD"
        font_title = cls._get_font(20, bold=True, script="latin")
        draw.text((w // 2, 118), title_text, fill=acc, font=font_title, anchor="mm")
        draw.line([(w // 2 - 260, 142), (w // 2 + 260, 142)], fill=prim, width=2)

        # Student Information Box
        info_box = [(55, 165), (w - 55, 275)]
        draw.rectangle(info_box, fill=(248, 250, 253), outline=(200, 210, 225), width=1)
        font_hdr = cls._get_font(13, bold=True, script="latin")
        font_bld = cls._get_font(14, bold=True, script=script, text=doc_data.get("recipient_name", ""))
        font_reg = cls._get_font(13, bold=False, script=script, text=doc_data.get("degree", ""))

        recipient = doc_data.get("recipient_name", "Bishal Paul")
        reg_no = doc_data.get("registration_number", "23BCI0224")
        deg = doc_data.get("degree", "B.Tech Computer Science & Engineering")
        grade_val = doc_data.get("grade", "Distinction (9.4 CGPA)")

        draw.text((75, 185), "Student Name:", fill=(100, 105, 115), font=font_hdr)
        draw.text((195, 185), recipient, fill=prim, font=font_bld)
        draw.text((75, 215), "Registration No:", fill=(100, 105, 115), font=font_hdr)
        draw.text((195, 215), reg_no, fill=acc, font=font_bld)
        draw.text((75, 245), "Program:", fill=(100, 105, 115), font=font_hdr)
        draw.text((195, 245), deg, fill=(40, 45, 55), font=font_reg)

        draw.text((540, 185), "Classification:", fill=(100, 105, 115), font=font_hdr)
        draw.text((660, 185), grade_val, fill=prim, font=font_bld)
        draw.text((540, 215), "Issuer Domain:", fill=(100, 105, 115), font=font_hdr)
        draw.text((660, 215), doc_data.get("issuer_domain", "vit.ac.in"), fill=(40, 45, 55), font=font_reg)
        draw.text((540, 245), "Academic Status:", fill=(100, 105, 115), font=font_hdr)
        draw.text((660, 245), "ACTIVE / REGULAR", fill=(16, 185, 129), font=font_bld)

        # Grade Table
        tbl_x1, tbl_x2 = 55, w - 55
        tbl_y = 310
        draw.rectangle([(tbl_x1, tbl_y), (tbl_x2, tbl_y + 35)], fill=prim)
        font_th = cls._get_font(13, bold=True, script="latin")
        draw.text((75, tbl_y + 18), "Course Code", fill=(255, 255, 255), font=font_th, anchor="lm")
        draw.text((230, tbl_y + 18), "Course Title", fill=(255, 255, 255), font=font_th, anchor="lm")
        draw.text((610, tbl_y + 18), "Credits", fill=(255, 255, 255), font=font_th, anchor="mm")
        draw.text((710, tbl_y + 18), "Grade", fill=(255, 255, 255), font=font_th, anchor="mm")
        draw.text((810, tbl_y + 18), "Result", fill=(255, 255, 255), font=font_th, anchor="mm")

        courses = [
            ("BCSE323L", "Cryptography & Network Security", "4", "S", "PASS"),
            ("BCSE308L", "Operating Systems & Kernel Architecture", "4", "S", "PASS"),
            ("BCSE309L", "Database Management Systems", "4", "A", "PASS"),
            ("BMAT201L", "Discrete Mathematics & Graph Theory", "4", "S", "PASS"),
            ("BCSE399J", "Security Capstone Prototype Project", "4", "S", "PASS"),
            ("BCSE350L", "Computer Networks & Distributed Systems", "4", "A", "PASS"),
            ("BCSE312L", "Digital Image Forensics & Steganography", "4", "S", "PASS"),
            ("BENG101L", "Technical Communication for Engineers", "2", "S", "PASS"),
        ]

        font_td = cls._get_font(13, bold=False, script="latin")
        font_td_bld = cls._get_font(13, bold=True, script="latin")
        curr_y = tbl_y + 35
        for idx, (code, title, cred, gr, res) in enumerate(courses):
            bg_row = (248, 250, 253) if idx % 2 == 1 else (255, 255, 255)
            draw.rectangle([(tbl_x1, curr_y), (tbl_x2, curr_y + 38)], fill=bg_row, outline=(225, 230, 240), width=1)
            draw.text((75, curr_y + 19), code, fill=prim, font=font_td_bld, anchor="lm")
            draw.text((230, curr_y + 19), title, fill=(40, 45, 55), font=font_td, anchor="lm")
            draw.text((610, curr_y + 19), cred, fill=(40, 45, 55), font=font_td, anchor="mm")
            draw.text((710, curr_y + 19), gr, fill=acc, font=font_td_bld, anchor="mm")
            draw.text((810, curr_y + 19), res, fill=(16, 185, 129), font=font_td_bld, anchor="mm")
            curr_y += 38

        # CGPA Summary Banner
        summary_y = curr_y + 25
        draw.rectangle([(tbl_x1, summary_y), (tbl_x2, summary_y + 48)], fill=(240, 245, 255), outline=acc, width=2)
        font_summary = cls._get_font(15, bold=True, script="latin")
        draw.text((w // 2, summary_y + 24), "CUMULATIVE GRADE POINT AVERAGE (CGPA): 9.40 / 10.00  |  DISTINCTION", fill=prim, font=font_summary, anchor="mm")

        # Bottom Verification Zone
        bottom_y = summary_y + 80
        # Left: Official Seal & Controller Signature
        stamp_cx, stamp_cy = 200, bottom_y + 65
        draw.ellipse([(stamp_cx - 52, stamp_cy - 52), (stamp_cx + 52, stamp_cy + 52)], outline=acc, width=3)
        draw.ellipse([(stamp_cx - 44, stamp_cy - 44), (stamp_cx + 44, stamp_cy + 44)], outline=prim, width=2)
        font_seal_p = cls._get_font(11, bold=True, script="latin")
        font_seal_a = cls._get_font(10, bold=True, script="latin")
        draw.text((stamp_cx, stamp_cy - 12), "OFFICIAL SEAL", fill=prim, font=font_seal_p, anchor="mm")
        draw.text((stamp_cx, stamp_cy + 12), "VIT AUTHENTIC", fill=acc, font=font_seal_a, anchor="mm")

        sig_cx = 450
        draw.line([(sig_cx - 110, bottom_y + 75), (sig_cx + 110, bottom_y + 75)], fill=prim, width=2)
        draw.arc([(sig_cx - 60, bottom_y + 35), (sig_cx + 60, bottom_y + 72)], start=160, end=350, fill=prim, width=2)
        font_sig_t = cls._get_font(14, bold=True, script="latin")
        font_sig_s = cls._get_font(11, bold=False, script="latin")
        draw.text((sig_cx, bottom_y + 95), "Controller of Examinations", fill=prim, font=font_sig_t, anchor="mm")
        draw.text((sig_cx, bottom_y + 115), "Vellore Institute of Technology", fill=(110, 115, 125), font=font_sig_s, anchor="mm")

        # Right: Web-PKI QR Code
        qr_resized = qr_img.resize((145, 145))
        qr_x = w - margin - 8 - 145 - 35
        qr_y = bottom_y
        img.paste(qr_resized, (qr_x, qr_y))
        font_meta = cls._get_font(11, bold=True, script="latin")
        draw.text((qr_x + 72, qr_y + 160), "Scan to Verify Web-PKI", fill=(100, 105, 115), font=font_meta, anchor="mm")

        # Footer
        doc_id = doc_data.get("document_id", "DOC-UNKNOWN")
        footer_text = f"Doc ID: {doc_id}  |  Issuer: {doc_data.get('issuer_domain', 'vit.ac.in')}  |  {script_data['auth_footer']}"
        font_footer = cls._get_font(11, bold=False, script=script, text=footer_text)
        draw.text((w // 2, h - 55), footer_text, fill=(110, 115, 125), font=font_footer, anchor="mm")

        return img

    @classmethod
    def generate_document_canvas(
        cls,
        template_id: str,
        script: str,
        doc_data: Dict[str, Any],
        qr_img: Image.Image
    ) -> Image.Image:
        """
        Renders the graphic certificate canvas with guilloché security border, text, and QR code.
        Dispatches to template-specific high-fidelity renderers with zero overlap.
        """
        cfg = TEMPLATES.get(template_id, TEMPLATES["certificate"])
        w, h = cfg["dimensions"]
        script_data = DEFAULT_SCRIPTS.get(script, DEFAULT_SCRIPTS["latin"])

        if template_id == "id_card":
            return cls._render_id_card(w, h, cfg, script_data, doc_data, qr_img, script)
        elif template_id == "transcript":
            return cls._render_transcript(w, h, cfg, script_data, doc_data, qr_img, script)
        else:
            return cls._render_certificate(w, h, cfg, script_data, doc_data, qr_img, script)

    @classmethod
    def get_or_create_issuer_keypair(cls, domain: str) -> Tuple[str, str, str]:
        """
        Derives or retrieves a deterministic Ed25519 keypair for an institutional domain
        using the master system key HMAC, ensuring persistent, validatable signatures.
        """
        import hashlib
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        seed = hashlib.sha256(f"ISSUER_KEY:{domain.lower()}:{SECRET_SYSTEM_KEY}".encode('utf-8')).digest()
        priv_obj = Ed25519PrivateKey.from_private_bytes(seed)
        pub_obj = priv_obj.public_key()
        priv_hex = priv_obj.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        ).hex()
        pub_hex = pub_obj.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        ).hex()
        kid = f"ed25519:{hashlib.sha256(pub_hex.encode()).hexdigest()[:16]}"
        return priv_hex, pub_hex, kid

    @classmethod
    def create_and_seal_document(
        cls,
        doc_fields: Dict[str, Any],
        issuer_domain: str = "vit.ac.in",
        template_id: str = "certificate",
        script: str = "latin",
        private_key_hex: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes Level 0 to Level 4 pipeline:
        1. Canonicalize fields & SHA-256
        2. Ed25519 signature
        3. CBOR + ZLIB QR code
        4. Render canvas
        5. DWT-SVD invisible watermark
        6. Persist to SQLite DB & Dataset
        """
        doc_id = doc_fields.get("document_id", str(uuid.uuid4()))
        doc_fields["document_id"] = doc_id
        doc_fields["issuer_domain"] = issuer_domain

        # 1. Look up or auto-generate issuer keys
        det_priv, det_pub, det_kid = cls.get_or_create_issuer_keypair(issuer_domain)
        issuer_record = TrustRegistryRepository.get_issuer_by_domain(issuer_domain)
        if not issuer_record or issuer_record.get("public_key") != det_pub:
            issuer_record = TrustRegistryRepository.register_issuer(
                issuer_id=f"inst-{issuer_domain.split('.')[0]}",
                domain=issuer_domain,
                public_key_hex=det_pub,
                key_id=det_kid,
                expires_at="2030-12-31T23:59:59Z"
            )
        kid = issuer_record["key_id"]
        pub = issuer_record["public_key"]
        signing_key = private_key_hex if private_key_hex else det_priv

        # 2. Canonicalize document fields & compute SHA-256
        canonical_str = Canonicalizer.canonicalize(doc_fields)
        doc_hash = Canonicalizer.compute_hash(canonical_str)

        # 3. Cryptographically sign hash using Ed25519
        signature = Ed25519Service.sign_payload(signing_key, doc_hash.encode('utf-8'))
        SignatureRepository.save_signature(doc_id, kid, signature)

        # 4. Assemble compact QR payload (CBOR + ZLIB)
        qr_payload = {
            "v": 1,
            "id": doc_id,
            "iss": issuer_domain,
            "kid": kid,
            "h": doc_hash,
            "sig": signature
        }
        qr_encoded_text = PayloadCoder.encode_payload(qr_payload)
        qr_img = QRService.generate_qr_image(qr_encoded_text, box_size=5, border=2)

        # 5. Render canvas with template and script
        canvas = cls.generate_document_canvas(template_id, script, doc_fields, qr_img)
        canvas_rgb = np.array(canvas)

        # 6. Generate Watermark pattern from HMAC seed and embed via DWT-SVD
        wm_seed = Canonicalizer.generate_watermark_seed(doc_id, doc_hash, SECRET_SYSTEM_KEY)
        watermarker = DWTSVDWatermarker()
        watermark_pattern = watermarker.generate_watermark_from_seed(wm_seed)
        
        watermarked_rgb, wm_aux = watermarker.embed(canvas_rgb, watermark_pattern)

        # 7. Persist document metadata and files
        doc_record = DocumentRepository.create_document(
            doc_id=doc_id,
            issuer_id=issuer_record["issuer_id"],
            doc_hash=doc_hash,
            watermark_hash=doc_hash[:16],
            template_id=template_id,
            metadata={
                "doc_fields": doc_fields,
                "script": script,
                "template_id": template_id,
                "key_id": kid,
                "wm_aux": wm_aux,
                "qr_encoded_text": qr_encoded_text
            }
        )

        out_path = DATASET_DIR / f"{doc_id}.png"
        Image.fromarray(watermarked_rgb).save(out_path, format="PNG")

        return {
            "document_id": doc_id,
            "issuer_domain": issuer_domain,
            "key_id": kid,
            "document_hash": doc_hash,
            "signature": signature,
            "watermark_psnr": wm_aux["psnr"],
            "watermark_ssim": wm_aux["ssim"],
            "qr_encoded_text": qr_encoded_text,
            "file_path": str(out_path),
            "canonical_fields": doc_fields
        }
