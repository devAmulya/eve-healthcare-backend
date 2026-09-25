import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class BookingStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    bookings = relationship("Booking", back_populates="user")


class DiagnosticCentre(Base):
    __tablename__ = "diagnostic_centres"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    location = Column(String, nullable=False)

    tests = relationship("DiagnosticTest", back_populates="centre", cascade="all, delete-orphan")


class DiagnosticTest(Base):
    __tablename__ = "diagnostic_tests"

    id = Column(String, primary_key=True, default=gen_uuid)
    centre_id = Column(String, ForeignKey("diagnostic_centres.id"), nullable=False)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)

    centre = relationship("DiagnosticCentre", back_populates="tests")


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    test_id = Column(String, ForeignKey("diagnostic_tests.id"), nullable=False)
    centre_id = Column(String, ForeignKey("diagnostic_centres.id"), nullable=False)
    appointment_time = Column(DateTime, nullable=False)

    # Snapshotted from DiagnosticTest.price at creation time so a later
    # price change never retroactively alters an existing booking.
    amount = Column(Float, nullable=False)

    status = Column(Enum(BookingStatus), nullable=False, default=BookingStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="bookings")
    test = relationship("DiagnosticTest")
    centre = relationship("DiagnosticCentre")
    payment = relationship("Payment", back_populates="booking", uselist=False)


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True, default=gen_uuid)

    # One booking can have at most one settled payment. This is what makes
    # the "was this booking already paid" check a cheap unique lookup
    # instead of an aggregate query.
    booking_id = Column(String, ForeignKey("bookings.id"), unique=True, nullable=False)

    amount = Column(Float, nullable=False)
    status = Column(Enum(PaymentStatus), nullable=False)

    # The idempotency key. Every simulated payment attempt AND every
    # webhook delivery carries one of these. A unique DB constraint (not
    # just an application-level check) is what actually prevents a race
    # between two near-simultaneous deliveries of the same event from
    # both slipping through.
    provider_event_id = Column(String, unique=True, nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    booking = relationship("Booking", back_populates="payment")

    __table_args__ = (UniqueConstraint("booking_id", name="uq_payment_booking"),)
