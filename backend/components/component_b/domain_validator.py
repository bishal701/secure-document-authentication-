import unicodedata
from typing import Tuple, List, Dict, Any

class DomainValidator:
    """
    Component B: Semantic Domain Validation.
    Detects typosquatting, character substitution, and homoglyph/confusable attacks.
    """

    # Common cross-script homoglyphs (Cyrillic, Greek, lookalikes) mapped to ASCII
    HOMOGLYPH_MAP = {
        'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p', 'с': 'c', 'у': 'y', 'х': 'x',
        'і': 'i', 'ј': 'j', 'ѕ': 's', 'ԁ': 'd', 'ԛ': 'q', 'ԝ': 'w',
        '0': 'o', '1': 'l', '3': 'e', '5': 's', '8': 'b',
        'α': 'a', 'β': 'b', 'ο': 'o', 'ρ': 'p', 'ν': 'v'
    }

    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """Standard Levenshtein edit distance."""
        if len(s1) < len(s2):
            return DomainValidator.levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

    @classmethod
    def normalize_homoglyphs(cls, domain: str) -> str:
        """
        Normalizes unicode characters and replaces lookalike homoglyphs with standard ASCII.
        """
        domain_clean = unicodedata.normalize('NFKD', domain.lower().strip())
        normalized_chars = []
        for ch in domain_clean:
            normalized_chars.append(cls.HOMOGLYPH_MAP.get(ch, ch))
        return "".join(normalized_chars)

    @classmethod
    def calculate_similarity(cls, candidate: str, reference: str) -> float:
        """
        Computes normalized similarity [0.0, 1.0] between candidate and reference domain.
        Higher score indicates closer match / potential typosquatting imitation.
        """
        c_norm = cls.normalize_homoglyphs(candidate)
        r_norm = cls.normalize_homoglyphs(reference)

        dist = cls.levenshtein_distance(c_norm, r_norm)
        max_len = max(len(c_norm), len(r_norm))
        if max_len == 0:
            return 1.0
        similarity = 1.0 - (dist / max_len)
        return round(similarity, 4)

    @classmethod
    def check_typosquatting(cls, candidate_domain: str, trusted_domains: List[str]) -> Dict[str, Any]:
        """
        Evaluates whether candidate_domain is an exact match, a harmless distinct domain,
        or a dangerously similar typosquatted imitation of a trusted domain.
        """
        candidate_clean = candidate_domain.lower().strip()
        
        # Exact match
        if candidate_clean in [d.lower().strip() for d in trusted_domains]:
            return {
                "is_trusted": True,
                "is_typosquat": False,
                "matched_domain": candidate_clean,
                "similarity": 1.0,
                "warning": None
            }

        # Check similarities against all registered trusted domains
        highest_sim = 0.0
        closest_domain = None
        for trusted in trusted_domains:
            sim = cls.calculate_similarity(candidate_clean, trusted)
            if sim > highest_sim:
                highest_sim = sim
                closest_domain = trusted

        # If similarity is high (e.g. >= 0.75) but not exact, it's a likely typosquatting attempt
        is_typosquat = (highest_sim >= 0.72)
        warning = None
        if is_typosquat:
            warning = f"High visual similarity ({highest_sim*100:.1f}%) to authoritative domain '{closest_domain}'. Possible phishing or impersonation attempt!"

        return {
            "is_trusted": False,
            "is_typosquat": is_typosquat,
            "matched_domain": closest_domain,
            "similarity": highest_sim,
            "warning": warning
        }
