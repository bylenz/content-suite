"""Storage validation (008 task 3.2): pure-Python magic-byte sniffing + size
limit, and the `FakeStorage` fake used everywhere else in the suite (task 3.1)."""

import asyncio

import pytest

from app.storage.errors import StorageUnavailableError, StorageValidationError
from app.storage.fakes import FakeStorage
from app.storage.validation import sniff_image_type, validate_upload

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 32
WEBP_BYTES = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 16
FAKE_TEXT_DECLARED_AS_IMAGE = b"not actually an image, just plain text bytes"


def test_sniff_detects_png_jpeg_and_webp() -> None:
    png = sniff_image_type(PNG_BYTES)
    jpeg = sniff_image_type(JPEG_BYTES)
    webp = sniff_image_type(WEBP_BYTES)
    assert png is not None and png.content_type == "image/png"
    assert jpeg is not None and jpeg.content_type == "image/jpeg"
    assert webp is not None and webp.content_type == "image/webp"


def test_sniff_returns_none_for_unrecognized_content() -> None:
    assert sniff_image_type(FAKE_TEXT_DECLARED_AS_IMAGE) is None


def test_validate_upload_accepts_a_real_png() -> None:
    validated = validate_upload(PNG_BYTES, max_bytes=1_000_000)
    assert validated.content_type == "image/png"
    assert validated.extension == ".png"


def test_validate_upload_rejects_falsified_content_type_bytes() -> None:
    """Content type falsificado (spec scenario): real bytes decide, not any claim."""
    with pytest.raises(StorageValidationError) as exc_info:
        validate_upload(FAKE_TEXT_DECLARED_AS_IMAGE, max_bytes=1_000_000)
    assert exc_info.value.reason == "unsupported_file_type"


def test_validate_upload_rejects_oversized_file() -> None:
    with pytest.raises(StorageValidationError) as exc_info:
        validate_upload(PNG_BYTES, max_bytes=10)
    assert exc_info.value.reason == "file_too_large"


def test_validate_upload_rejects_empty_file() -> None:
    with pytest.raises(StorageValidationError) as exc_info:
        validate_upload(b"", max_bytes=1_000_000)
    assert exc_info.value.reason == "empty_file"


def test_validate_upload_runs_before_any_storage_call() -> None:
    """No orphans (spec scenario): validation never touches the storage fake."""
    storage = FakeStorage()
    with pytest.raises(StorageValidationError):
        validate_upload(FAKE_TEXT_DECLARED_AS_IMAGE, max_bytes=1_000_000)
    assert storage.put_calls == []


def test_fake_storage_put_signed_url_and_remove_round_trip() -> None:
    storage = FakeStorage()

    async def run() -> str:
        await storage.put_object(
            path="brands/b/visuals/v1.png", content=PNG_BYTES, content_type="image/png"
        )
        return await storage.signed_url(path="brands/b/visuals/v1.png", ttl_seconds=300)

    url = asyncio.run(run())
    assert url.startswith("fake-signed://brands/b/visuals/v1.png")
    assert storage.object_exists("brands/b/visuals/v1.png")
    assert not storage.is_expired(url)

    asyncio.run(storage.remove_object(path="brands/b/visuals/v1.png"))
    assert not storage.object_exists("brands/b/visuals/v1.png")


def test_fake_storage_signed_url_expiry_is_simulable_deterministically() -> None:
    storage = FakeStorage()

    async def run() -> str:
        await storage.put_object(path="p", content=PNG_BYTES, content_type="image/png")
        return await storage.signed_url(path="p", ttl_seconds=10)

    url = asyncio.run(run())
    assert not storage.is_expired(url)
    storage.advance_clock(11)
    assert storage.is_expired(url)


def test_fake_storage_signed_url_for_missing_object_raises_unavailable() -> None:
    storage = FakeStorage()
    with pytest.raises(StorageUnavailableError):
        asyncio.run(storage.signed_url(path="missing", ttl_seconds=300))


def test_fake_storage_records_calls_deterministically() -> None:
    storage = FakeStorage()
    asyncio.run(storage.put_object(path="p1", content=PNG_BYTES, content_type="image/png"))
    assert storage.put_calls == [
        {"path": "p1", "content_type": "image/png", "size": len(PNG_BYTES)}
    ]
