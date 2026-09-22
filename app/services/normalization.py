import re
import unicodedata


NOISE_PATTERNS = [
    r"\bofficial audio\b",
    r"\bofficial video\b",
    r"\bofficial music video\b",
    r"\blyric video\b",
    r"\blyrics\b",
]

VERSION_PATTERNS = {
    "remix": r"\bremix\b",
    "live": r"\blive\b",
    "acoustic": r"\bacoustic\b",
    "instrumental": r"\binstrumental\b",
    "radio_edit": r"\bradio edit\b",
    "extended_mix": r"\bextended mix\b",
    "remastered": r"\bremaster(?:ed)?\b",
    "sped_up": r"\bsped up\b",
    "slowed": r"\bslowed\b",
}


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized.strip()


def normalize_track_title(title: str) -> str:
    normalized = normalize_text(title)

    for pattern in NOISE_PATTERNS:
        normalized = re.sub(pattern, " ", normalized)

    normalized = re.sub(r"\s+", " ", normalized)

    return normalized.strip()


def detect_track_versions(title: str) -> set[str]:
    normalized = normalize_text(title)

    versions = set()

    for version, pattern in VERSION_PATTERNS.items():
        if re.search(pattern, normalized):
            versions.add(version)

    return versions