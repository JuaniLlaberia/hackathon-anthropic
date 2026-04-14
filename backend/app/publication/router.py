from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.shared.deps import get_db
from .models import Category
from .schemas import (
    CategoryResponse,
    ModerationAction,
    PublicationCreate,
    PublicationResponse,
)
from .service import PublicationService

router = APIRouter(prefix="/api/v1/publications", tags=["publications"])


@router.post("/", response_model=PublicationResponse)
async def create_publication(data: PublicationCreate, db: Session = Depends(get_db)):
    service = PublicationService(db)
    return await service.create_publication(data.user_id, data.model_dump())


@router.get("/", response_model=list[PublicationResponse])
async def list_publications(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    service = PublicationService(db)
    return service.list_publications(status=status, category=category, page=page, limit=limit)


@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).all()


@router.get("/{pub_id}", response_model=PublicationResponse)
async def get_publication(pub_id: str, db: Session = Depends(get_db)):
    service = PublicationService(db)
    return service.get_by_id(pub_id)


@router.patch("/{pub_id}/status")
async def moderate_publication(pub_id: str, action: ModerationAction, db: Session = Depends(get_db)):
    service = PublicationService(db)
    return await service.moderate(pub_id, action.action, action.reason)
