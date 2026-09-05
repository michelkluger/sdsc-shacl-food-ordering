"""Error responses, shaped as RFC 9457 problem details.

Every failure this API produces - a missing dish, a malformed body, a SHACL violation, an
unreachable search backend - comes back in the same envelope, so a client writes one error
handler rather than four. SHACL violations extend it with a ``violations`` array, since a form
needs the failures individually addressed rather than concatenated into one string.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from food_api.shacl.report import Violation

PROBLEM_BASE = "https://sdsc.example/problems/"
PROBLEM_CONTENT_TYPE = "application/problem+json"


class ProblemError(Exception):
    """An error that already knows how it should be rendered."""

    def __init__(
        self,
        *,
        status_code: int,
        title: str,
        detail: str,
        problem_type: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.problem_type = problem_type
        self.extra = extra or {}


class DishNotFoundError(ProblemError):
    def __init__(self, slug: str, known: tuple[str, ...]) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Unknown dish",
            detail=f"No dish is registered under {slug!r}.",
            problem_type=f"{PROBLEM_BASE}unknown-dish",
            extra={"slug": slug, "availableDishes": list(known)},
        )


class SearchDegradedError(ProblemError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            title="Search is unavailable",
            detail=detail,
            problem_type=f"{PROBLEM_BASE}search-unavailable",
        )


class ShaclValidationError(ProblemError):
    """A submitted order violated its dish's shape."""

    def __init__(self, slug: str, violations: tuple[Violation, ...]) -> None:
        count = len(violations)
        plural = "" if count == 1 else "s"
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            title="The order does not satisfy the dish's constraints",
            detail=f"{count} constraint violation{plural} found by SHACL validation.",
            problem_type=f"{PROBLEM_BASE}shacl-validation",
            extra={
                "dish": slug,
                "violations": [violation.as_dict() for violation in violations],
            },
        )


def problem_response(request: Request, error: ProblemError) -> JSONResponse:
    body: dict[str, Any] = {
        "type": error.problem_type,
        "title": error.title,
        "status": error.status_code,
        "detail": error.detail,
        "instance": str(request.url.path),
        **error.extra,
    }
    return JSONResponse(
        status_code=error.status_code,
        content=jsonable_encoder(body),
        media_type=PROBLEM_CONTENT_TYPE,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Route every error class through the problem-details envelope."""

    @app.exception_handler(ProblemError)
    async def _problem(request: Request, exc: ProblemError) -> JSONResponse:
        return problem_response(request, exc)

    @app.exception_handler(RequestValidationError)
    async def _request_validation(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        # FastAPI's own body/query validation, kept in the same envelope as SHACL violations so
        # a client has exactly one error shape to parse. These are transport-level problems -
        # a body that is not an object at all - not constraint failures.
        return problem_response(
            request,
            ProblemError(
                status_code=status.HTTP_400_BAD_REQUEST,
                title="Malformed request",
                detail="The request body or query string could not be read.",
                problem_type=f"{PROBLEM_BASE}malformed-request",
                extra={"errors": jsonable_encoder(exc.errors())},
            ),
        )
