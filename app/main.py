from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.database import Base, engine
from app.logging_config import configure_logging
from app.middleware import RequestLoggingMiddleware
from app.rate_limit import limiter
from app.routers import auth, bookings, centres, payments

configure_logging()

# In a larger project this would be Alembic migrations. For this assignment's
# scope, create_all on startup is documented in the README as a deliberate
# simplification.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EVE Healthcare — Diagnostic Bookings API",
    description="Backend service for diagnostic test bookings and simulated payments.",
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(auth.router)
app.include_router(centres.router)
app.include_router(bookings.router)
app.include_router(payments.router)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
