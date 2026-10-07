"""Upload validation: MIME allow-list + extension allow-list + magic-byte sniffing.

The declared Content-Type is not trusted on its own: the first bytes of the file must match the
container family of the declared (or extension-derived) type, otherwise 415.
"""
from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import PurePath

from backend.app.errors import UnsupportedMedia

# mime -> allowed extensions (first one is canonical)
EXTENSIONS: dict[str, tuple[str, ...]] = {
    "video/mp4": ("mp4", "m4v"),
    "video/webm": ("webm",),
    "video/quicktime": ("mov", "qt"),
    "image/jpeg": ("jpg", "jpeg"),
    "image/png": ("png",),
    "image/webp": ("webp",),
    "audio/webm": ("webm", "weba"),
    "audio/ogg": ("ogg", "oga", "opus"),
    "audio/mpeg": ("mp3", "mpga"),
    "audio/wav": ("wav",),
    "audio/mp4": ("m4a", "mp4"),
    "application/pdf": ("pdf",),
}

ALIASES = {
    "audio/x-wav": "audio/wav", "audio/wave": "audio/wav", "audio/vnd.wave": "audio/wav",
    "audio/mp3": "audio/mpeg", "audio/x-m4a": "audio/mp4", "image/jpg": "image/jpeg", "audio/opus": "audio/ogg",
}

KIND_FAMILIES: dict[str, tuple[str, ...]] = {
    "video": ("video/",),
    "photo": ("image/",),
    "audio": ("audio/", "video/webm"),  # MediaRecorder often labels voice notes video/webm
    "document": ("application/pdf", "image/"),
}


def _is_iso_bmff(h: bytes) -> bool:
    return len(h) >= 12 and h[4:8] in (b"ftyp", b"moov", b"mdat", b"wide", b"free", b"skip", b"pnot")


def _is_mpeg_audio(h: bytes) -> bool:
    return h[:3] == b"ID3" or (len(h) >= 2 and h[0] == 0xFF and (h[1] & 0xE0) == 0xE0)


SNIFFERS = {
    "video/mp4": _is_iso_bmff,
    "video/quicktime": _is_iso_bmff,
    "audio/mp4": _is_iso_bmff,
    "video/webm": lambda h: h[:4] == b"\x1a\x45\xdf\xa3",
    "audio/webm": lambda h: h[:4] == b"\x1a\x45\xdf\xa3",
    "image/jpeg": lambda h: h[:3] == b"\xff\xd8\xff",
    "image/png": lambda h: h[:8] == b"\x89PNG\r\n\x1a\n",
    "image/webp": lambda h: h[:4] == b"RIFF" and h[8:12] == b"WEBP",
    "audio/wav": lambda h: h[:4] == b"RIFF" and h[8:12] == b"WAVE",
    "audio/ogg": lambda h: h[:4] == b"OggS",
    "audio/mpeg": _is_mpeg_audio,
    "application/pdf": lambda h: h[:5] == b"%PDF-",
}


@dataclass(frozen=True)
class ValidatedFile:
    mime_type: str
    extension: str


def normalise_mime(content_type: str | None) -> str | None:
    if not content_type:
        return None
    base = content_type.split(";", 1)[0].strip().lower()
    return ALIASES.get(base, base)


def validate_upload(filename: str | None, content_type: str | None, head: bytes, *, kind: str,
                    allowed: set[str]) -> ValidatedFile:
    ext = PurePath(filename or "").suffix.lower().lstrip(".")
    mime = normalise_mime(content_type)
    if mime in (None, "", "application/octet-stream"):
        guessed = mimetypes.guess_type(f"x.{ext}")[0] if ext else None
        mime = normalise_mime(guessed)
        if kind == "audio" and ext == "webm":
            mime = "audio/webm"
    if not mime or mime not in EXTENSIONS or mime not in {normalise_mime(a) for a in allowed}:
        raise UnsupportedMedia(f"File type '{mime or 'unknown'}' is not accepted.", "unsupported_media_type")
    if ext and ext not in EXTENSIONS[mime]:
        raise UnsupportedMedia(f"Extension '.{ext}' does not match type {mime}.", "extension_mismatch")
    if not any(mime == f or mime.startswith(f) for f in KIND_FAMILIES.get(kind, ())):
        raise UnsupportedMedia(f"A {mime} file cannot be submitted as kind '{kind}'.", "kind_mismatch")
    if not SNIFFERS[mime](head):
        raise UnsupportedMedia(f"File content does not look like {mime} (magic bytes mismatch).", "content_mismatch")
    return ValidatedFile(mime, ext or EXTENSIONS[mime][0])
