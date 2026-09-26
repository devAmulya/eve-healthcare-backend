from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.logging_config import get_logger
from app.models import Booking, BookingStatus, DiagnosticTest, User
from app.pagination import PaginationParams, pagination_params
from app.schemas import BookingCreate, BookingOut, Page

router = APIRouter(prefix="/bookings", tags=["bookings"])
logger = get_logger(__name__)


@router.post("/", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    test = db.get(DiagnosticTest, payload.test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic test not found")

    appt = payload.appointment_time
    if appt.tzinfo is None:
        appt = appt.replace(tzinfo=timezone.utc)
    if appt < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Appointment time is in the past")

    booking = Booking(
        user_id=current_user.id,
        test_id=test.id,
        centre_id=test.centre_id,
        appointment_time=payload.appointment_time,
        amount=test.price,  # snapshotted, see models.py comment
        status=BookingStatus.PENDING,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    logger.info(
        "booking_created",
        booking_id=booking.id,
        user_id=current_user.id,
        test_id=test.id,
        amount=booking.amount,
    )
    return booking


@router.get("/", response_model=Page[BookingOut])
def list_my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    pagination: PaginationParams = Depends(pagination_params),
):
    query = db.query(Booking).filter(Booking.user_id == current_user.id)
    total = query.count()
    items = (
        query.order_by(Booking.created_at.desc())
        .offset(pagination.skip)
        .limit(pagination.limit)
        .all()
    )
    return Page(items=items, total=total, skip=pagination.skip, limit=pagination.limit)


def _get_owned_booking(booking_id: str, db: Session, current_user: User) -> Booking:
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.user_id != current_user.id:
        # 403, not 404: the resource exists, the caller just isn't allowed to see it.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this booking")
    return booking


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(
    booking_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_owned_booking(booking_id, db, current_user)


@router.delete("/{booking_id}", response_model=BookingOut)
def cancel_booking(
    booking_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    booking = _get_owned_booking(booking_id, db, current_user)

    if booking.status != BookingStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel a booking in status {booking.status.value}",
        )

    booking.status = BookingStatus.CANCELLED
    db.commit()
    db.refresh(booking)
    logger.info("booking_cancelled", booking_id=booking.id, user_id=current_user.id)
    return booking
