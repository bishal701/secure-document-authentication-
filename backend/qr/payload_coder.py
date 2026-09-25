import zlib
import base64
import cbor2
from typing import Dict, Any

class PayloadCoder:
    """
    Compact binary serialization using CBOR + ZLIB compression.
    Payload schema:
    {
      "v": 1,                      # Protocol version
      "id": doc_id,                # Document UUID
      "iss": issuer_domain,        # Issuer institutional domain
      "kid": key_id,               # Public key identifier
      "h": doc_hash[:32],          # Truncated or full SHA-256
      "sig": signature_hex,        # Ed25519 signature
      "iat": timestamp             # Issued timestamp (epoch integer)
    }
    """

    @staticmethod
    def encode_payload(payload_dict: Dict[str, Any]) -> str:
        """
        Serializes dict to CBOR, compresses with ZLIB, and encodes as Base64 string for QR code.
        """
        cbor_bytes = cbor2.dumps(payload_dict)
        compressed = zlib.compress(cbor_bytes, level=9)
        # URL-safe Base64 without padding for high QR density
        encoded = base64.urlsafe_b64encode(compressed).decode('utf-8').rstrip('=')
        return f"SDA1:{encoded}"

    @staticmethod
    def decode_payload(qr_text: str) -> Dict[str, Any]:
        """
        Reverses Base64 -> ZLIB decompress -> CBOR unpack.
        """
        cleaned = qr_text.strip()
        if cleaned.startswith("SDA1:"):
            cleaned = cleaned[5:]
        
        # Re-pad base64 string
        missing_padding = len(cleaned) % 4
        if missing_padding:
            cleaned += '=' * (4 - missing_padding)

        compressed = base64.urlsafe_b64decode(cleaned)
        cbor_bytes = zlib.decompress(compressed)
        payload = cbor2.loads(cbor_bytes)
        return payload

    @staticmethod
    def estimate_compression_ratio(payload_dict: Dict[str, Any]) -> float:
        """Estimates payload compression percentage compared to uncompressed JSON."""
        import json
        raw_json_len = len(json.dumps(payload_dict).encode('utf-8'))
        encoded_len = len(PayloadCoder.encode_payload(payload_dict).encode('utf-8'))
        return round((1.0 - (encoded_len / raw_json_len)) * 100.0, 2)

