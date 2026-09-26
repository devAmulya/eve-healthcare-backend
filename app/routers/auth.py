from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.logging_config import get_logger
from app.models import User
from app.rate_limit import limiter
from app.schemas import Token, UserLogin, UserOut, UserSignup
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger(__name__)


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def signup(request: Request, payload: UserSignup, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        logger.warning("signup_duplicate_email", email=payload.email)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("user_signed_up", user_id=user.id)
    return user


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
def login(request: Request, payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        # Deliberately identical error for "no such user" and "wrong password"
        # so login can't be used to enumerate registered emails. The log line
        # can be more specific than the API response — that distinction is
        # itself the point of logging separately from the response body.
        logger.warning("login_failed", email=payload.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = create_access_token(subject=user.id)
    logger.info("login_succeeded", user_id=user.id)
    return Token(access_token=token)
