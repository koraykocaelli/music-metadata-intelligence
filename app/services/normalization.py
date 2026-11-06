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


# Latin letters that have no Unicode decomposition to an ASCII base letter.
# Previously these were silently dropped (e.g. "Mø" -> "m").
LATIN_TRANSLITERATIONS = str.maketrans(
    {
        "ß": "ss",
        "ẞ": "ss",
        "æ": "ae",
        "Æ": "ae",
        "œ": "oe",
        "Œ": "oe",
        "ø": "o",
        "Ø": "o",
        "ł": "l",
        "Ł": "l",
        "đ": "d",
        "Đ": "d",
        "ð": "d",
        "Ð": "d",
        "þ": "th",
        "Þ": "th",
        "ı": "i",
    }
)


def _is_mark(character: str) -> bool:
    return unicodedata.category(character).startswith("M")


def _strip_latin_diacritics(value: str) -> str:
    # Remove combining marks only when they decorate an ASCII letter
    # ("é" -> "e"). Marks in other scripts (Devanagari vowel signs, Japanese
    # dakuten, ...) carry meaning and are kept, then recomposed with NFC.
    decomposed = unicodedata.normalize("NFKD", value)
    characters: list[str] = []
    previous_base = ""

    for character in decomposed:
        if _is_mark(character):
            if previous_base.isascii():
                continue
        else:
            previous_base = character

        characters.append(character)

    return unicodedata.normalize("NFC", "".join(characters))


def normalize_text(value: str) -> str:
    # Lowercase before stripping diacritics: "İ".lower() yields "i" plus a
    # combining dot, which must also be removed.
    normalized = value.lower().translate(LATIN_TRANSLITERATIONS)
    normalized = _strip_latin_diacritics(normalized)
    # Keep letters, digits and combining marks of any script; everything else
    # (punctuation, symbols, underscores) becomes a separator.
    normalized = "".join(
        character
        if character.isalnum() or _is_mark(character)
        else " "
        for character in normalized
    )
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