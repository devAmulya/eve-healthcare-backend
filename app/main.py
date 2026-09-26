from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.database import Base, engine
from app.logging_config import configure_logging
from app.middleware import RequestLoggingMiddleware
from app.rate_limit import limiter
from app.routers import auth, bookings, centres, payments

configure_logging()

# In a larger project this would be Alembic migrations. For this project's
# scope, create_all on startup is documented in the README as a deliberate
# simplification.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EVE Healthcare - Diagnostic Bookings API",
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


@app.get("/", include_in_schema=False)
def root():
    """
    The root path has no API meaning of its own; redirect it to the
    interactive docs so hitting http://localhost:8000/ directly doesn't
    return a bare 404.
    """
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
