from fastapi import FastAPI

from app.database import Base, engine
from app.routers import auth, bookings, centres, payments

# In a larger project this would be Alembic migrations. For this assignment's
# scope, create_all on startup is documented in the README as a deliberate
# simplification.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EVE Healthcare — Diagnostic Bookings API",
    description="Backend service for diagnostic test bookings and simulated payments.",
    version="1.0.0",
)

app.include_router(auth.router)
app.include_router(centres.router)
app.include_router(bookings.router)
app.include_router(payments.router)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
