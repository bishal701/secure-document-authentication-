import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from backend.database.db import get_connection

class DocumentRepository:
    @staticmethod
    def create_document(doc_id: str, issuer_id: str, doc_hash: str, watermark_hash: str, template_id: str, metadata: dict) -> dict:
        conn = get_connection()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            "INSERT INTO documents (document_id, issuer_id, document_hash, watermark_hash, template_id, metadata_json, created_at, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (doc_id, issuer_id, doc_hash, watermark_hash, template_id, json.dumps(metadata), now, 'ISSUED')
        )
        conn.commit()
        conn.close()
        return {
            "document_id": doc_id,
            "issuer_id": issuer_id,
            "document_hash": doc_hash,
            "watermark_hash": watermark_hash,
            "template_id": template_id,
            "created_at": now,
            "status": "ISSUED"
        }

    @staticmethod
    def get_document(doc_id: str) -> Optional[dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE document_id = ?", (doc_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return dict(row)

class SignatureRepository:
    @staticmethod
    def save_signature(doc_id: str, key_id: str, signature: str, algorithm: str = "Ed25519") -> str:
        sig_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO signatures (signature_id, document_id, key_id, signature, algorithm, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (sig_id, doc_id, key_id, signature, algorithm, now)
        )
        conn.commit()
        conn.close()
        return sig_id

class TrustRegistryRepository:
    @staticmethod
    def register_issuer(issuer_id: str, domain: str, public_key_hex: str, key_id: str, expires_at: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO trust_registry (issuer_id, domain, public_key, key_id, status, created_at, expires_at, revoked_at) VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?, NULL)",
            (issuer_id, domain.lower(), public_key_hex, key_id, now, expires_at)
        )
        conn.commit()
        conn.close()
        return {
            "issuer_id": issuer_id,
            "domain": domain.lower(),
            "public_key": public_key_hex,
            "key_id": key_id,
            "status": "ACTIVE",
            "created_at": now,
            "expires_at": expires_at
        }

    @staticmethod
    def get_issuer_by_domain(domain: str) -> Optional[dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trust_registry WHERE domain = ?", (domain.lower(),))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_issuer_by_key_id(key_id: str) -> Optional[dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trust_registry WHERE key_id = ?", (key_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def list_all() -> List[dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trust_registry ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def update_status(key_id: str, status: str) -> bool:
        now = datetime.now(timezone.utc).isoformat() if status == 'REVOKED' else None
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE trust_registry SET status = ?, revoked_at = ? WHERE key_id = ?",
            (status, now, key_id)
        )
        affected = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return affected

class VerificationLogRepository:
    @staticmethod
    def log_verification(data: dict) -> str:
        ver_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO verification_logs (
                verification_id, document_id, qr_status, signature_status,
                watermark_status, watermark_score, copy_status, copy_score,
                domain_status, ai_status, ai_score, final_status, diagnostic_notes, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ver_id,
                data.get("document_id"),
                data.get("qr_status"),
                data.get("signature_status"),
                data.get("watermark_status"),
                data.get("watermark_score", 0.0),
                data.get("copy_status"),
                data.get("copy_score", 0.0),
                data.get("domain_status"),
                data.get("ai_status"),
                data.get("ai_score", 0.0),
                data.get("final_status"),
                json.dumps(data.get("diagnostic_notes", {})),
                now
            )
        )
        conn.commit()
        conn.close()
        return ver_id

    @staticmethod
    def get_recent_logs(limit: int = 25) -> List[dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM verification_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

class ExperimentRepository:
    @staticmethod
    def log_experiment(record: dict) -> str:
        exp_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO experiments (
                experiment_id, document_id, printer, paper, template, script,
                attack_type, rotation, lighting, device, qr_success,
                watermark_score, copy_score, signature_valid, domain_valid,
                ai_score, final_result, verification_time, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                exp_id,
                record.get("document_id"),
                record.get("printer", "N/A"),
                record.get("paper", "N/A"),
                record.get("template", "standard"),
                record.get("script", "latin"),
                record.get("attack_type", "NONE"),
                record.get("rotation", 0.0),
                record.get("lighting", "normal"),
                record.get("device", "desktop"),
                1 if record.get("qr_success") else 0,
                float(record.get("watermark_score", 0.0)),
                float(record.get("copy_score", 0.0)),
                1 if record.get("signature_valid") else 0,
                1 if record.get("domain_valid") else 0,
                float(record.get("ai_score", 0.0)),
                record.get("final_result", "UNKNOWN"),
                float(record.get("verification_time", 0.0)),
                now
            )
        )
        conn.commit()
        conn.close()
        return exp_id

    @staticmethod
    def list_all() -> List[dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM experiments ORDER BY timestamp DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
