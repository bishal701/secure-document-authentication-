import json
import hashlib
import hmac
from typing import Dict, Any

class Canonicalizer:
    @staticmethod
    def canonicalize(data: Dict[str, Any]) -> str:
        """
        Creates a deterministic string representation of document fields.
        Keys are sorted recursively, strings stripped, whitespace standardized.
        """
        def clean_val(v):
            if isinstance(v, dict):
                return {k: clean_val(v[k]) for k in sorted(v.keys())}
            elif isinstance(v, list):
                return [clean_val(item) for item in v]
            elif isinstance(v, str):
                return v.strip()
            return v

        cleaned = clean_val(data)
        # Produce compact JSON with sorted keys
        return json.dumps(cleaned, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

    @staticmethod
    def compute_hash(canonical_str: str) -> str:
        """
        Computes SHA-256 hash in hexadecimal.
        """
        return hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()

    @staticmethod
    def generate_watermark_seed(doc_id: str, doc_hash: str, secret_key: str) -> bytes:
        """
        Generates deterministic pseudo-random seed using HMAC-SHA256.
        """
        msg = f"{doc_id}:{doc_hash}".encode('utf-8')
        return hmac.new(secret_key.encode('utf-8'), msg, hashlib.sha256).digest()
