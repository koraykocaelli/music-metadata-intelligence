import re
import unicodedata


NOISE_PATTERNS = [
    r"\bofficial audio\b",
    r"\bofficial video\b",
    r"\blyric video\b",
    r"\blyrics\b",
]


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