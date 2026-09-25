import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from backend.database.models import TrustRegistryRepository
from backend.components.component_b.domain_validator import DomainValidator

class TrustRegistryService:
    """
    Component B: Hybrid Web-PKI & Trust Registry Management.
    Tracks institutional public keys, status, and semantic safety.
    """

    @classmethod
    def seed_default_issuers(cls):
        """Pre-seeds standard academic/institutional issuers if registry is empty."""
        existing = TrustRegistryRepository.list_all()
        if not existing:
            # Seed VIT Vellore
            from backend.crypto.ed25519_service import Ed25519Service
            priv, pub, kid = Ed25519Service.generate_keypair()
            TrustRegistryRepository.register_issuer(
                issuer_id="vit-vellore",
                domain="vit.ac.in",
                public_key_hex=pub,
                key_id=kid,
                expires_at="2030-12-31T23:59:59Z"
            )
            # Seed IIT Delhi
            _, pub2, kid2 = Ed25519Service.generate_keypair()
            TrustRegistryRepository.register_issuer(
                issuer_id="iit-delhi",
                domain="iitd.ac.in",
                public_key_hex=pub2,
                key_id=kid2,
                expires_at="2030-12-31T23:59:59Z"
            )

    @classmethod
    def validate_issuer_and_domain(
        cls,
        candidate_domain: str,
        key_id: Optional[str] = None,
        public_key_hex: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive Web-PKI verification:
        1. Exact domain check & key lookup
        2. Status check (ACTIVE, REVOKED, EXPIRED)
        3. Cryptographic key match
        4. Typosquatting / homoglyph similarity analysis
        """
        cls.seed_default_issuers()
        all_issuers = TrustRegistryRepository.list_all()
        trusted_domains = [iss["domain"] for iss in all_issuers]

        typo_check = DomainValidator.check_typosquatting(candidate_domain, trusted_domains)

        # 1. Check if domain exists in registry
        issuer = TrustRegistryRepository.get_issuer_by_domain(candidate_domain)

        # If not found by domain, try lookup by key_id
        if not issuer and key_id:
            issuer = TrustRegistryRepository.get_issuer_by_key_id(key_id)

        if not issuer:
            return {
                "valid": False,
                "status": "UNREGISTERED",
                "issuer": None,
                "reason": f"Domain '{candidate_domain}' is not enrolled in the Web-PKI Trust Registry.",
                "typosquat_analysis": typo_check
            }

        # 2. Check Key ID alignment if provided
        if key_id and issuer["key_id"] != key_id:
            return {
                "valid": False,
                "status": "KEY_MISMATCH",
                "issuer": issuer,
                "reason": f"Key ID in payload ('{key_id}') does not match registry key ('{issuer['key_id']}').",
                "typosquat_analysis": typo_check
            }

        # 3. Check Public Key alignment if provided
        if public_key_hex and issuer["public_key"] != public_key_hex:
            return {
                "valid": False,
                "status": "KEY_MISMATCH",
                "issuer": issuer,
                "reason": "Public key does not match the registry public key for this issuer.",
                "typosquat_analysis": typo_check
            }

        # 4. Check Status (REVOKED or EXPIRED)
        current_status = issuer["status"].upper()
        if current_status == "REVOKED":
            return {
                "valid": False,
                "status": "REVOKED",
                "issuer": issuer,
                "reason": f"Cryptographic key was explicitly REVOKED at {issuer.get('revoked_at', 'unknown')}.",
                "typosquat_analysis": typo_check
            }

        # Check expiration date
        try:
            exp_time = datetime.fromisoformat(issuer["expires_at"].replace("Z", "+00:00"))
            now_utc = datetime.now(timezone.utc)
            if now_utc > exp_time:
                return {
                    "valid": False,
                    "status": "EXPIRED",
                    "issuer": issuer,
                    "reason": f"Issuer certificate expired on {issuer['expires_at']}.",
                    "typosquat_analysis": typo_check
                }
        except Exception:
            pass

        return {
            "valid": True,
            "status": "ACTIVE",
            "issuer": issuer,
            "reason": f"Issuer '{issuer['issuer_id']}' ({issuer['domain']}) is verified, active, and trusted.",
            "typosquat_analysis": typo_check
        }

    @classmethod
    def revoke_key(cls, key_id: str) -> Dict[str, Any]:
        """Revokes an issuer key and benchmarks revocation latency."""
        t0 = time.perf_counter()
        success = TrustRegistryRepository.update_status(key_id, "REVOKED")
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "success": success,
            "key_id": key_id,
            "status": "REVOKED",
            "revocation_latency_ms": round(latency_ms, 3)
        }
