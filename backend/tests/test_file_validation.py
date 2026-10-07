from __future__ import annotations

import pytest

from backend.app.errors import UnsupportedMedia
from backend.app.security.file_validation import validate_upload
from backend.app.services.media import parse_range
from backend.app.errors import RangeNotSatisfiable

ALLOWED = {"video/mp4", "video/webm", "image/jpeg", "image/png", "audio/webm", "application/pdf", "audio/mpeg"}
MP4 = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
PDF = b"%PDF-1.7\n%\xe2\xe3"
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 12


def test_accepts_valid_types():
    assert validate_upload("a.mp4", "video/mp4", MP4, kind="video", allowed=ALLOWED).extension == "mp4"
    assert validate_upload("p.png", "image/png", PNG, kind="photo", allowed=ALLOWED).mime_type == "image/png"
    assert validate_upload("d.pdf", "application/pdf", PDF, kind="document", allowed=ALLOWED).extension == "pdf"
    # MediaRecorder voice note labelled video/webm with codec params
    assert validate_upload("blob", "video/webm;codecs=opus", WEBM, kind="audio", allowed=ALLOWED).extension == "webm"
    # octet-stream falls back to the extension
    assert validate_upload("clip.mp4", "application/octet-stream", MP4, kind="video", allowed=ALLOWED).mime_type == "video/mp4"


@pytest.mark.parametrize("name,ctype,head,kind,code", [
    ("evil.exe", "application/x-msdownload", b"MZ\x90\x00", "document", "unsupported_media_type"),
    ("a.mp4", "video/mp4", b"MZ\x90\x00" + b"\x00" * 20, "video", "content_mismatch"),
    ("a.png", "image/png", PDF, "photo", "content_mismatch"),
    ("a.jpg", "video/mp4", MP4, "video", "extension_mismatch"),
    ("a.mp4", "video/mp4", MP4, "photo", "kind_mismatch"),
    ("a.html", "text/html", b"<html>", "document", "unsupported_media_type"),
    ("a.mov", "video/quicktime", MP4, "video", "unsupported_media_type"),  # not in this allow-list
])
def test_rejects(name, ctype, head, kind, code):
    with pytest.raises(UnsupportedMedia) as e:
        validate_upload(name, ctype, head, kind=kind, allowed=ALLOWED)
    assert e.value.code == code
    assert e.value.status_code == 415


def test_parse_range():
    assert parse_range(None, 100) is None
    assert parse_range("bytes=0-9", 100) == (0, 9)
    assert parse_range("bytes=90-", 100) == (90, 99)
    assert parse_range("bytes=-10", 100) == (90, 99)
    assert parse_range("bytes=50-1000", 100) == (50, 99)
    with pytest.raises(RangeNotSatisfiable):
        parse_range("bytes=200-300", 100)
    with pytest.raises(RangeNotSatisfiable):
        parse_range("items=0-1", 100)
