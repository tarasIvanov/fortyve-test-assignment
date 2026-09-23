import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db import session_factory
from app.exceptions import DomainError, FieldNotFoundError
from app.middleware import AccessLogMiddleware
from app.routers import fields

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")

app = FastAPI(
    title="Fields API",
    description="REST API для управління сільськогосподарськими полями та пошуку полів за координатами точки.",
    version="1.0.0",
)

app.add_middleware(AccessLogMiddleware)
app.include_router(fields.router)


@app.exception_handler(DomainError)
async def handle_domain_error(_: Request, error: DomainError) -> JSONResponse:
    status_code = (
        status.HTTP_404_NOT_FOUND
        if isinstance(error, FieldNotFoundError)
        else status.HTTP_422_UNPROCESSABLE_ENTITY
    )
    return JSONResponse(status_code=status_code, content={"detail": error.message, "code": error.code})


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
    messages = []
    for item in error.errors():
        location = " → ".join(str(part) for part in item["loc"][1:]) or "запит"
        messages.append(f"{location}: {item['msg']}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "; ".join(messages), "code": "validation_error"},
    )


@app.get("/health", tags=["service"])
async def health() -> JSONResponse:
    """Перевіряє не лише те, що процес живий, а й що з'єднання з БД робоче."""
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        logging.getLogger("app.health").exception("Перевірка з'єднання з БД не пройшла")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "База даних недоступна", "code": "database_unavailable"},
        )

    return JSONResponse(content={"status": "ok"})
