class DomainError(Exception):
    """Помилка бізнес-рівня. Про HTTP-коди знає лише шар застосунку."""

    code = "internal_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidGeometryError(DomainError):
    code = "invalid_geometry"


class UnsupportedGeometryError(DomainError):
    code = "unsupported_geometry"


class AreaTooSmallError(DomainError):
    code = "area_too_small"


class FieldNotFoundError(DomainError):
    code = "not_found"
