"""Domain errors for visual_audit. No HTTP mapping here: handlers are
registered centrally in `app/errors.py`, same shape as `app.knowledge.errors`
and `app.ai.errors`."""

from pydantic import ValidationError


class VisionOutputInvalidError(Exception):
    """Raised when the VisionModel output does not satisfy the findings contract
    (design D6): mapped to a sanitized 503 `VISION_OUTPUT_INVALID`, nothing persisted."""

    def __init__(self, cause: ValidationError | Exception) -> None:
        super().__init__("Vision model output does not satisfy the findings contract")
        self.cause = cause
