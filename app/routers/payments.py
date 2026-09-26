import random
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.logging_config import get_logger
from app.models import Booking, BookingStatus, Payment, PaymentStatus, User
from app.retry import retry_on_transient_db_error
from app.schemas import PaymentInitiate, PaymentOut, WebhookPayload

router = APIRouter(prefix="/payments", tags=["payments"])
logger = get_logger(__name__)


def _apply_payment_result(booking: Booking, result: PaymentStatus) -> None:
    booking.status = BookingStatus.CONFIRMED if result == PaymentStatus.SUCCESS else BookingStatus.FAILED


@retry_on_transient_db_error
def _settle_payment(db: Session, booking: Booking, result: PaymentStatus, event_id: str) -> Payment:
    """
    Builds the Payment row, applies the booking transition, and commits -
    all in one retryable unit. See app/retry.py for why this can't just be
    a bare db.commit() retry: a rollback() between attempts would discard
    these db.add()'d objects, so each retry rebuilds them fresh.
    """
    payment = Payment(booking_id=booking.id, amount=booking.amount, status=result, provider_event_id=event_id)
    _apply_payment_result(booking, result)
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


@router.post("/", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def initiate_payment(
    payload: PaymentInitiate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Client-triggered "pay now" simulation. This represents the synchronous
    leg of a payment flow (the user hits pay, we call a provider, we get
    an immediate result). The async confirmation leg is /payments/webhook/.
    """
    booking = db.get(Booking, payload.booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this booking")

    if booking.status != BookingStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Booking is {booking.status.value}, not payable",
        )

    if booking.payment is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Booking already has a payment on file")

    result = payload.force_result or random.choices(
        [PaymentStatus.SUCCESS, PaymentStatus.FAILED], weights=[80, 20], k=1
    )[0]
    event_id = f"sim-{uuid.uuid4()}"

    try:
        payment = _settle_payment(db, booking, result, event_id)
    except IntegrityError:
        # Lost a race with a concurrent payment/webhook for the same booking.
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Booking already has a payment on file")
    except OperationalError:
        # Retries exhausted on a transient DB error. Surface a 503 rather
        # than a bare 500 so a client/caller knows it's safe to retry.
        db.rollback()
        logger.error("payment_initiation_failed_transient_db_error", booking_id=booking.id)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Temporarily unavailable, please retry")

    logger.info(
        "payment_initiated",
        booking_id=booking.id,
        payment_id=payment.id,
        result=result.value,
        provider_event_id=payment.provider_event_id,
    )
    return payment


@router.post("/webhook/")
def payment_webhook(payload: WebhookPayload, db: Session = Depends(get_db)):
    """
    Simulates a payment provider pushing an async status update.

    Idempotency contract: the same event_id may arrive more than once
    (at-least-once delivery is the norm for real providers). Re-delivery
    must be a safe no-op: no duplicate Payment row, no double status
    transition. This is enforced at the DB layer via a unique constraint
    on provider_event_id, not just an application-level "have I seen this
    before" check, so it also holds under concurrent delivery.
    """
    booking = db.get(Booking, payload.booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    # Already-processed event: same event_id seen before. Idempotent no-op.
    existing_by_event = db.query(Payment).filter(Payment.provider_event_id == payload.event_id).first()
    if existing_by_event is not None:
        logger.info(
            "webhook_duplicate_event_ignored",
            booking_id=booking.id,
            event_id=payload.event_id,
        )
        return {"status": "already_processed", "booking_status": booking.status.value}

    # A payment already exists for this booking under a *different* event_id
    # (e.g. a duplicate/late event from the provider for an already-settled
    # booking). Booking is already in a terminal paid state, so ignore.
    if booking.payment is not None:
        logger.info(
            "webhook_duplicate_settlement_ignored",
            booking_id=booking.id,
            event_id=payload.event_id,
            existing_payment_id=booking.payment.id,
        )
        return {"status": "already_processed", "booking_status": booking.status.value}

    # A cancelled booking should never be resurrected by a late webhook.
    if booking.status == BookingStatus.CANCELLED:
        logger.warning(
            "webhook_ignored_booking_cancelled",
            booking_id=booking.id,
            event_id=payload.event_id,
        )
        return {"status": "ignored_booking_cancelled", "booking_status": booking.status.value}

    try:
        payment = _settle_payment(db, booking, payload.status, payload.event_id)
    except IntegrityError:
        # Two concurrent deliveries of the same event both reached this point;
        # exactly one wins the insert, the other backs off cleanly here.
        db.rollback()
        logger.info(
            "webhook_lost_race_already_processed",
            booking_id=booking.id,
            event_id=payload.event_id,
        )
        return {"status": "already_processed", "booking_status": booking.status.value}
    except OperationalError:
        # Retries exhausted on a transient DB error (not an idempotency
        # conflict). Return 5xx on purpose: real payment providers retry
        # webhook delivery on non-2xx responses, so this hands off to that
        # outer retry layer instead of silently losing the event. Combined
        # with the idempotency guarantees above, a re-delivery of the same
        # event_id is always safe once the DB recovers.
        db.rollback()
        logger.error(
            "webhook_processing_failed_transient_db_error",
            booking_id=booking.id,
            event_id=payload.event_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Temporarily unable to process webhook, please retry delivery",
        )

    logger.info(
        "webhook_processed",
        booking_id=booking.id,
        payment_id=payment.id,
        event_id=payload.event_id,
        result=payload.status.value,
    )
    return {"status": "processed", "booking_status": booking.status.value}
