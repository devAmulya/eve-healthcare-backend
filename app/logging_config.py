import logging
import sys

import structlog


def configure_logging() -> None:
    """
    Configures structlog to emit one JSON object per log line, e.g.:

        {"event": "booking_created", "booking_id": "...", "user_id": "...",
         "request_id": "...", "level": "info", "timestamp": "..."}

    contextvars.merge_contextvars pulls in whatever request_id (and anything
    else) was bound via structlog.contextvars.bind_contextvars() earlier in
    the request — see RequestLoggingMiddleware — so every log line emitted
    while handling a request is automatically tagged with it, without
    threading a logger instance through every function call.
    """
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name)
