"""Centralized error envelope for every API error response: {error: {code, message, details}}.

Handlers are registered at app level (not per endpoint) and translate three
sources: FastAPI HTTPException (identity/health included), request validation
errors, and domain errors raised by module policies/services.
"""

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.ai.errors import (
    AIOutputValidationError,
    AIProviderNotConfiguredError,
    AIProviderResponseError,
)
from app.brand_dna.policies import InvalidWorkflowTransitionError as BrandDnaTransitionError
from app.creative.policies import InvalidWorkflowTransitionError as CreativeTransitionError
from app.governance.policies import InvalidWorkflowTransitionError as GovernanceTransitionError
from app.identity.policies import PermissionDeniedError
from app.knowledge.errors import KnowledgeNotAvailableError, SyncConflictError
from app.storage.errors import (
    StorageNotConfiguredError,
    StorageUnavailableError,
    StorageValidationError,
)
from app.visual_audit.errors import VisionOutputInvalidError
from app.visual_audit.policies import InvalidWorkflowTransitionError as VisualAuditTransitionError

STATUS_CODE_MAP = {
    400: "BAD_REQUEST",
    401: "UNAUTHENTICATED",
    403: "PERMISSION_DENIED",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "INVALID_WORKFLOW_TRANSITION",
    422: "VALIDATION_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def _code_for_status(status_code: int) -> str:
    if status_code in STATUS_CODE_MAP:
        return STATUS_CODE_MAP[status_code]
    try:
        phrase = HTTPStatus(status_code).phrase
    except ValueError:
        phrase = "UNKNOWN_ERROR"
    return phrase.upper().replace(" ", "_")


def envelope(status_code: int, code: str, message: str, details: dict) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details}},
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        return envelope(500, "INTERNAL_ERROR", str(exc), {})
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {"code": _code_for_status(exc.status_code), "message": message, "details": {}}
        },
        headers=exc.headers,
    )


async def request_validation_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    paths: list[str] = []
    for error in exc.errors():
        path = ".".join(str(part) for part in error["loc"])
        if path not in paths:
            paths.append(path)
    return envelope(
        422,
        "VALIDATION_ERROR",
        "Request validation failed",
        {"field_errors": paths},
    )


async def permission_denied_handler(request: Request, exc: Exception) -> JSONResponse:
    return envelope(403, "PERMISSION_DENIED", str(exc), {})


async def invalid_transition_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(
        exc,
        BrandDnaTransitionError
        | CreativeTransitionError
        | GovernanceTransitionError
        | VisualAuditTransitionError,
    )
    return envelope(409, "INVALID_WORKFLOW_TRANSITION", str(exc), exc.details)


async def sync_conflict_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, SyncConflictError)
    return envelope(409, "INVALID_WORKFLOW_TRANSITION", str(exc), exc.details)


async def ai_provider_not_configured_handler(request: Request, exc: Exception) -> JSONResponse:
    # Sanitized: the capability name only, never configuration values.
    return envelope(503, "SERVICE_UNAVAILABLE", str(exc), {})


async def ai_output_validation_handler(request: Request, exc: Exception) -> JSONResponse:
    # Sanitized 503: contract name only. The underlying ValidationError (which
    # embeds raw provider output) never reaches the response.
    assert isinstance(exc, AIOutputValidationError)
    return envelope(503, "AI_OUTPUT_INVALID", str(exc), {"contract": exc.contract})


async def knowledge_not_available_handler(request: Request, exc: Exception) -> JSONResponse:
    # Fail-safe guard (spec 04): generating/checking/submitting without servable
    # Brand Knowledge answers 503, never generic content.
    message = str(exc) or "Brand Knowledge is not available"
    return envelope(503, "KNOWLEDGE_NOT_AVAILABLE", message, {})


async def storage_unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    # Covers both StorageNotConfiguredError (adapter is None) and
    # StorageUnavailableError (configured adapter failed at runtime): both
    # answer a controlled 503, sanitized to the operation name only (design
    # D2/private-storage spec: no fallback, no partial objects).
    assert isinstance(exc, StorageNotConfiguredError | StorageUnavailableError)
    return envelope(503, "STORAGE_UNAVAILABLE", str(exc), {"operation": exc.operation})


async def storage_validation_handler(request: Request, exc: Exception) -> JSONResponse:
    # File failed size/magic-byte validation (design D3): 422 before any
    # storage call or DB write; the sanitized reason never includes raw bytes.
    assert isinstance(exc, StorageValidationError)
    return envelope(422, "VALIDATION_ERROR", str(exc), {"reason": exc.reason})


async def vision_output_invalid_handler(request: Request, exc: Exception) -> JSONResponse:
    # Sanitized 503 (design D6): the Vision model's raw output never reaches
    # the response; nothing is persisted when this fires.
    assert isinstance(exc, VisionOutputInvalidError)
    return envelope(503, "VISION_OUTPUT_INVALID", str(exc), {})


def register_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.add_exception_handler(PermissionDeniedError, permission_denied_handler)
    app.add_exception_handler(BrandDnaTransitionError, invalid_transition_handler)
    app.add_exception_handler(CreativeTransitionError, invalid_transition_handler)
    app.add_exception_handler(GovernanceTransitionError, invalid_transition_handler)
    app.add_exception_handler(VisualAuditTransitionError, invalid_transition_handler)
    app.add_exception_handler(SyncConflictError, sync_conflict_handler)
    app.add_exception_handler(AIProviderNotConfiguredError, ai_provider_not_configured_handler)
    app.add_exception_handler(AIProviderResponseError, ai_provider_not_configured_handler)
    app.add_exception_handler(AIOutputValidationError, ai_output_validation_handler)
    app.add_exception_handler(KnowledgeNotAvailableError, knowledge_not_available_handler)
    app.add_exception_handler(StorageNotConfiguredError, storage_unavailable_handler)
    app.add_exception_handler(StorageUnavailableError, storage_unavailable_handler)
    app.add_exception_handler(StorageValidationError, storage_validation_handler)
    app.add_exception_handler(VisionOutputInvalidError, vision_output_invalid_handler)
