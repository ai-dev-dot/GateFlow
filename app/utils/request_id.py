"""Per-request UUID middleware.

Generates a request_id (or honors an inbound X-Request-ID header for
distributed tracing) and exposes it on `request.state.request_id`.
The same id is echoed back in the response header so clients can quote
it when reporting errors — the server-side logger has the full
exception context keyed by this id.

Why this matters for P0-4 (don't leak internal exception messages to
clients): we replace `str(exception)` in API responses with a fixed
user-facing message, but we still need a way for the user to give us
enough info to find the original error in logs. The request_id is
that bridge — opaque to the user, but enough for us to grep logs.
"""

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

REQUEST_ID_HEADER = "X-Request-ID"

# ContextVar so background tasks and downstream helpers can read the
# current request's id without threading it through every function.
# Set by the middleware at the start of each request.
current_request_id: ContextVar[str] = ContextVar("current_request_id", default="-")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Honor inbound header (lets upstream proxies / load balancers
        # preserve their trace id), else generate fresh.
        rid = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = rid
        token = current_request_id.set(rid)
        try:
            response = await call_next(request)
        finally:
            current_request_id.reset(token)
        response.headers[REQUEST_ID_HEADER] = rid
        return response


def get_request_id() -> str:
    """Read the current request's id. Returns '-' outside a request scope."""
    return current_request_id.get()
