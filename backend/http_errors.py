"""Normalize exception text for FastAPI ``HTTPException.detail`` (never bare ``None``)."""


def exception_detail(exc: BaseException, fallback: str = "Request failed") -> str:
    detail = getattr(exc, "detail", None)
    if isinstance(detail, str):
        trimmed = detail.strip()
        if trimmed and trimmed.lower() != "none":
            return trimmed

    msg = str(exc).strip()
    if msg and msg.lower() != "none":
        return msg

    if isinstance(exc, KeyError):
        if exc.args:
            return f"Missing key: {exc.args[0]!r}"
        return "Missing required key"

    name = type(exc).__name__
    return fallback if name in ("KeyError", "TypeError", "AttributeError") else f"{name}: {fallback}"
