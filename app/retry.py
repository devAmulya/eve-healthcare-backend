import structlog
from sqlalchemy.exc import OperationalError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = structlog.get_logger("retry")


def _rollback_and_log(retry_state):
    """
    Runs after a failed attempt, before the next retry.

    A failed flush/commit leaves a SQLAlchemy session in a state that
    requires an explicit rollback() before it can be used again - so this
    rolls the session back so the next attempt starts clean, and logs the
    retry for observability.

    Assumes the decorated function's first positional argument is the
    Session being committed, which is true everywhere this is used.
    """
    session = retry_state.args[0] if retry_state.args else None
    if session is not None:
        session.rollback()

    exc = retry_state.outcome.exception()
    logger.warning(
        "transient_db_error_retrying",
        attempt=retry_state.attempt_number,
        exception=str(exc),
    )


# Retries only OperationalError - connection drops, deadlocks, statement
# timeouts. These are genuinely transient conditions worth waiting out.
# IntegrityError (our idempotency-conflict signal) is deliberately excluded:
# retrying it would just raise the identical conflict again, since "this
# event/booking was already processed" isn't a transient condition.
#
# Important: the *whole* decorated function gets retried, not just a bare
# db.commit() call. rollback() between attempts discards any pending
# db.add()'d objects, so retrying only the commit after a rollback would
# silently commit nothing. Every function wrapped with this decorator
# rebuilds its objects from scratch on each attempt for that reason.
retry_on_transient_db_error = retry(
    retry=retry_if_exception_type(OperationalError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.05, max=0.5),
    before_sleep=_rollback_and_log,
    reraise=True,
)
