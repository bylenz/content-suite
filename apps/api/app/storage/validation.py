"""Pure-Python server-side file validation (design D3).

Magic-byte sniffing for the allowed image types (PNG/JPEG/WebP) plus a
configurable size limit. Deliberately no `python-magic`/libmagic dependency
(would break test-seam portability); the client-declared content type is
never trusted, only the bytes on the wire decide.

Order (D3): validate size -> validate magic bytes. Both run before any
storage call or DB write, so a rejected file never reaches either.
"""

from dataclasses import dataclass

from app.storage.errors import StorageValidationError

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_RIFF_MAGIC = b"RIFF"
_WEBP_MAGIC = b"WEBP"


@dataclass(frozen=True, slots=True)
class ValidatedFile:
    """The real type detected from content, independent of any client claim."""

    content_type: str
    extension: str


def sniff_image_type(content: bytes) -> ValidatedFile | None:
    """Return the detected image type from magic bytes, or None if unrecognized."""
    if content.startswith(_PNG_MAGIC):
        return ValidatedFile(content_type="image/png", extension=".png")
    if content.startswith(_JPEG_MAGIC):
        return ValidatedFile(content_type="image/jpeg", extension=".jpg")
    if len(content) >= 12 and content[0:4] == _RIFF_MAGIC and content[8:12] == _WEBP_MAGIC:
        return ValidatedFile(content_type="image/webp", extension=".webp")
    return None


def validate_upload(content: bytes, *, max_bytes: int) -> ValidatedFile:
    """Validate size then real type; raises `StorageValidationError` (422 at the API boundary).

    Never persists or uploads anything itself -- callers only proceed to
    storage/DB writes once this returns successfully.
    """
    if len(content) == 0:
        raise StorageValidationError("Uploaded file is empty", reason="empty_file")
    if len(content) > max_bytes:
        raise StorageValidationError(
            f"Uploaded file exceeds the maximum allowed size of {max_bytes} bytes",
            reason="file_too_large",
        )
    detected = sniff_image_type(content)
    if detected is None:
        raise StorageValidationError(
            "Uploaded file is not a recognized PNG, JPEG or WebP image",
            reason="unsupported_file_type",
        )
    return detected
