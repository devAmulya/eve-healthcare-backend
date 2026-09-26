from datetime import datetime
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import BookingStatus, PaymentStatus

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Generic offset-pagination envelope reused across list endpoints."""

    items: list[T]
    total: int
    skip: int
    limit: int

# ---------- Auth ----------


class UserSignup(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Centres & Tests ----------


class DiagnosticTestOut(BaseModel):
    id: str
    name: str
    price: float

    model_config = ConfigDict(from_attributes=True)


class DiagnosticCentreOut(BaseModel):
    id: str
    name: str
    location: str
    tests: list[DiagnosticTestOut] = []

    model_config = ConfigDict(from_attributes=True)


# ---------- Bookings ----------


class BookingCreate(BaseModel):
    test_id: str
    appointment_time: datetime


class BookingOut(BaseModel):
    id: str
    user_id: str
    test_id: str
    centre_id: str
    appointment_time: datetime
    amount: float
    status: BookingStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- Payments ----------


class PaymentInitiate(BaseModel):
    booking_id: str
    # Optional override so tests/interviewers can force a deterministic
    # outcome instead of relying on the random simulator.
    force_result: Optional[PaymentStatus] = None


class PaymentOut(BaseModel):
    id: str
    booking_id: str
    amount: float
    status: PaymentStatus
    provider_event_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebhookPayload(BaseModel):
    event_id: str
    booking_id: str
    status: PaymentStatus
