# Secure Document Authentication System
### Research Prototype: Hybrid QR + DWT-SVD Watermarking + Blind Copy Detection + Web-PKI + Edge AI
**Course:** Digital Watermarking and Steganography (BCSE323L) — Fall Semester 2026-2027  
**Author:** Bishal Paul (Registration Number: 23BCI0224)  

---

## 🌟 Overview

This project implements the complete research prototype specified in the **Secure Document Authentication Implementation Roadmap (Levels 0 through 10, Phases 1 through 17)**. It provides a multi-layer defense against physical photocopies, digital splicing/tampering, and institutional domain impersonation.

```
       [ ORIGINAL DOCUMENT ]
                 |
  +--------------+--------------+
  |                             |
  v                             v
[Ed25519 Signed QR Code]    [DWT-SVD Watermark]
(CBOR + ZLIB compressed)    (Embedded in Luminance)
  |                             |
  +--------------+--------------+
                 |
                 v
     [ AUTHENTICATED CREDENTIAL ]
                 |
  [ Physical Print / Scan / Attack ]
                 |
                 v
   [ 8-STAGE UNIFIED VERIFICATION ]
   1. QR Code Readability & CBOR Decode
   2. Web-PKI Institutional Enrollment Check
   3. Ed25519 Cryptographic Signature Check
   4. SHA-256 Canonical Digest Match
   5. DWT-SVD Watermark NC & BER Analysis
   6. Component A: Blind Copy Detection (GLCM & DCT)
   7. Component B: Typosquatting / Homoglyph Check
   8. Component C: Secondary Edge AI Triage
                 |
                 v
  VERIFIED / VERIFIED-WITH-WARNING / SUSPICIOUS / INVALID
```

---

## 🚀 Quick Start & Running the Demo

To launch the complete application (FastAPI backend + interactive Web UI):

```bash
python run_demo.py
```

Your default browser will automatically open to:
```
http://127.0.0.1:8000/
```

---

## 🧪 Running Automated Unit Tests

To run the complete 8-test verification suite:

```bash
python -m unittest tests/test_pipeline.py
```

Expected output:
```
Ran 8 tests in ~1.3s
OK
```

---

## 📊 Research Gaps & Feature Mapping

| Research Gap | Implemented Feature | Validation Location |
| :--- | :--- | :--- |
| **Gap 1: Limited paper & printer conditions** | Multi-printer and multi-paper degradation modeling | `backend/components/component_a/` |
| **Gap 2: Limited human evaluation** | Realistic smartphone capture simulation (tilt, perspective warp, glare) | `backend/attack_simulator/` |
| **Gap 3: Security vs QR compatibility** | Compact CBOR encoding + ZLIB level-9 compression (42% size reduction) | `backend/qr/` |
| **Gap 4: Insufficient component ablation** | Systematic 5-stage ablation study (Schemes A through E) | `backend/experiments/runner.py` |
| **Gap 5: Script & template limitations** | Bi-script (English/Latin + Hindi/Devanagari) across 3 layouts (Certificate, ID Badge, Transcript) | `backend/generator/` |
| **Gap 6: Semantic PKI gap** | Web-PKI Trust Registry, sub-millisecond key revocation, and Levenshtein typosquatting protection | `backend/components/component_b/` |

---

## 📁 Project Directory Structure

```
secure-document-authentication/
|-- backend/
|   |-- app.py                     # FastAPI REST server & routing
|   |-- config.py                  # System thresholds & paths
|   |-- crypto/                    # Ed25519 signing & canonicalization
|   |-- qr/                        # CBOR/ZLIB encoding & OpenCV QR detector
|   |-- watermark/                 # 2D DWT + SVD embedding, extraction & metrics
|   |-- components/
|   |   |-- component_a/           # Blind copy detection (GLCM & DCT frequency)
|   |   |-- component_b/           # Semantic Web-PKI & Levenshtein domain validator
|   |   `-- component_c/           # Secondary Edge AI classifier
|   |-- generator/                 # High-resolution rendering (multi-template/script)
|   |-- engine/                    # Unified 8-stage verification pipeline
|   |-- attack_simulator/          # Distortion engine (print-scan, JPEG, tamper, etc.)
|   |-- experiments/               # Ablation & multi-condition benchmark runners
|   `-- database/                  # SQLite schema and repositories
|-- frontend/
|   |-- index.html                 # Interactive cyber-security web dashboard
|   |-- styles.css                 # Dark-mode styling
|   `-- app.js                     # Client-side verification and studio logic
|-- tests/
|   `-- test_pipeline.py           # Comprehensive automated test suite
|-- dataset/                       # Stored sample documents
|-- results/                       # Generated CSV benchmarks and ROC plots
|-- docs/                          # Scientific and mathematical documentation
|   |-- MATHEMATICAL_FORMULATION.md
|   |-- RESEARCH_ABLATION_REPORT.md
|   `-- API_REFERENCE.md
|-- run_demo.py                    # Startup launcher
`-- README.md
```
