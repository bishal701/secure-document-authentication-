import os
import hashlib
from typing import Tuple
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

class Ed25519Service:
    @staticmethod
    def generate_keypair() -> Tuple[str, str, str]:
        """
        Generates an Ed25519 key pair.
        Returns: (private_key_hex, public_key_hex, key_id)
        """
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        priv_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        pub_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

        priv_hex = priv_bytes.hex()
        pub_hex = pub_bytes.hex()
        # Key ID is SHA-256 fingerprint of the public key
        key_id = f"ed25519:{hashlib.sha256(pub_bytes).hexdigest()[:16]}"
        return priv_hex, pub_hex, key_id

    @staticmethod
    def sign_payload(private_key_hex: str, data: bytes) -> str:
        """
        Signs arbitrary bytes using the Ed25519 private key.
        Returns signature as hex string.
        """
        priv_bytes = bytes.fromhex(private_key_hex)
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(priv_bytes)
        signature = private_key.sign(data)
        return signature.hex()

    @staticmethod
    def verify_signature(public_key_hex: str, signature_hex: str, data: bytes) -> bool:
        """
        Verifies Ed25519 signature against data bytes.
        """
        try:
            pub_bytes = bytes.fromhex(public_key_hex)
            sig_bytes = bytes.fromhex(signature_hex)
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
            public_key.verify(sig_bytes, data)
            return True
        except (InvalidSignature, ValueError, Exception):
            return False
