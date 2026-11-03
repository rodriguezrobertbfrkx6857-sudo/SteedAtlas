import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth import get_current_user
from app.models.gacha import Collection
from app.models.user import User
from app.models.horse import Horse

router = APIRouter(prefix="/collections", tags=["collections"])


def _normalize_horse_id(value: str | None, db: Session) -> str | None:
    if not value:
        return None
    horse = db.query(Horse).filter(Horse.id == value).first()
    if horse:
        return horse.id
    horse = db.query(Horse).filter(Horse.name == value).first()
    if horse:
        return horse.id
    return value


def _collection_payload(user_id: str, db: Session):
    rows = db.query(Collection).filter(Collection.user_id == user_id).all()
    unique_rows = []
    seen_horse_ids = set()
    for row in rows:
        if row.horse_id in seen_horse_ids:
            continue
        seen_horse_ids.add(row.horse_id)
        unique_rows.append(row)

    return {
        "items": [row.horse_id for row in unique_rows],
        "detail": [_collection_detail(row, db) for row in unique_rows],
    }


def _collection_detail(row: Collection, db: Session):
    horse = db.query(Horse).filter(Horse.id == row.horse_id).first()
    return {
        "horse_id": row.horse_id,
        "horse_name": horse.name if horse else row.horse_id,
        "rarity": horse.rarity if horse else "",
        "source": row.source,
        "obtained_at": row.obtained_at.isoformat() if hasattr(row, "obtained_at") else None,
    }


@router.get("", response_model=dict)
def list_collections(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _collection_payload(user.id, db)


@router.post("", response_model=dict, status_code=201)
def add_collection(body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    horse_id = _normalize_horse_id(body.get("name") or body.get("horse_id"), db)
    if not horse_id:
        raise HTTPException(status_code=400, detail="horse_id required")
    exists = db.query(Collection).filter(Collection.user_id == user.id, Collection.horse_id == horse_id).first()
    if exists:
        return _collection_payload(user.id, db)
    c = Collection(id=f"c_{uuid.uuid4().hex[:12]}", user_id=user.id, horse_id=horse_id, source="client")
    db.add(c)
    db.commit()
    db.refresh(c)
    return _collection_payload(user.id, db)


@router.delete("/{horse_id}", response_model=dict)
def remove_collection(horse_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    normalized_horse_id = _normalize_horse_id(horse_id, db)
    if not normalized_horse_id:
        raise HTTPException(status_code=400, detail="horse_id required")

    rows = db.query(Collection).filter(
        Collection.user_id == user.id,
        Collection.horse_id == normalized_horse_id,
    ).all()

    for row in rows:
        db.delete(row)
    db.commit()

    return _collection_payload(user.id, db)


@router.post("/merge", response_model=dict)
def merge_collections(body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = body.get("items")
    if not items or not isinstance(items, list):
        raise HTTPException(status_code=400, detail="items must be a list of horse ids")

    # Use transaction for atomicity
    added = []
    with db.begin():
        existing_rows = db.query(Collection).filter(Collection.user_id == user.id).all()
        existing = set([c.horse_id for c in existing_rows])
        for raw_horse_id in items:
            horse_id = _normalize_horse_id(raw_horse_id, db)
            if not horse_id or horse_id in existing:
                continue
            c = Collection(id=f"c_{uuid.uuid4().hex[:12]}", user_id=user.id, horse_id=horse_id, source="client")
            db.add(c)
            added.append(horse_id)
            existing.add(horse_id)
    return _collection_payload(user.id, db)
