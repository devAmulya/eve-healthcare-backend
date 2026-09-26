from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import DiagnosticCentre
from app.pagination import PaginationParams, pagination_params
from app.schemas import DiagnosticCentreOut, Page

router = APIRouter(prefix="/centres", tags=["centres"])


@router.get("/", response_model=Page[DiagnosticCentreOut])
def list_centres(
    db: Session = Depends(get_db),
    pagination: PaginationParams = Depends(pagination_params),
):
    query = db.query(DiagnosticCentre).options(joinedload(DiagnosticCentre.tests))
    total = query.count()
    items = query.order_by(DiagnosticCentre.id).offset(pagination.skip).limit(pagination.limit).all()
    return Page(items=items, total=total, skip=pagination.skip, limit=pagination.limit)


@router.get("/{centre_id}", response_model=DiagnosticCentreOut)
def get_centre(centre_id: str, db: Session = Depends(get_db)):
    centre = (
        db.query(DiagnosticCentre)
        .options(joinedload(DiagnosticCentre.tests))
        .filter(DiagnosticCentre.id == centre_id)
        .first()
    )
    if not centre:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic centre not found")
    return centre
