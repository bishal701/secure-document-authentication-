from typing import Dict, Any

TEMPLATES = {
    "certificate": {
        "name": "Academic Degree / Certificate of Excellence",
        "category": "certificate",
        "dimensions": (1200, 850),
        "primary_color": (26, 54, 93),      # Deep Navy
        "accent_color": (197, 160, 89),     # Gold
        "bg_color": (253, 252, 248),        # Warm Ivory
        "border_style": "ornate_double"
    },
    "id_card": {
        "name": "Official Student / Faculty ID Card",
        "category": "id_style",
        "dimensions": (900, 560),
        "primary_color": (15, 76, 129),     # Classic Blue
        "accent_color": (214, 69, 41),      # Coral Red
        "bg_color": (248, 250, 252),        # Crisp Light Gray
        "border_style": "modern_badge"
    },
    "transcript": {
        "name": "Official Grade Sheet / Transcript",
        "category": "table_heavy",
        "dimensions": (950, 1200),
        "primary_color": (34, 47, 62),      # Slate Gray
        "accent_color": (46, 134, 222),     # Sapphire
        "bg_color": (255, 255, 255),        # Pure White
        "border_style": "tabular_formal"
    }
}

DEFAULT_SCRIPTS = {
    "latin": {
        "title_prefix": "VELLORE INSTITUTE OF TECHNOLOGY",
        "doc_title": "CERTIFICATE OF MERIT",
        "recipient_label": "This is awarded to:",
        "program_label": "For outstanding achievement in:",
        "auth_footer": "Cryptographically Sealed & Watermarked via Hybrid Web-PKI"
    },
    "devanagari": {
        "title_prefix": "वेल्लोर प्रौद्योगिकी संस्थान (VIT)",
        "doc_title": "उत्कृष्टता प्रमाण पत्र",
        "recipient_label": "यह प्रमाण पत्र प्रदान किया जाता है:",
        "program_label": "उल्लेखनीय प्रदर्शन हेतु:",
        "auth_footer": "सुरक्षित डिजिटल वॉटरमार्क एवं वेब-पीकेआई द्वारा प्रमाणित"
    }
}
