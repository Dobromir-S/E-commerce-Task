import os
import shutil
import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/products", tags=["products"])

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def _get_or_404(db: Session, product_id: int) -> models.Product:
    obj = db.get(models.Product, product_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return obj


def _category_subtree_ids(db: Session, root_id: int) -> list[int]:
    """Return root_id plus all descendant category IDs."""
    ids: list[int] = []
    queue = [root_id]
    while queue:
        current = queue.pop()
        ids.append(current)
        children = (
            db.query(models.Category.id)
            .filter(models.Category.parent_id == current)
            .all()
        )
        queue.extend(row.id for row in children)
    return ids


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.post("/", response_model=schemas.ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(payload: schemas.ProductCreate, db: Session = Depends(get_db)):
    if not db.get(models.Category, payload.category_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    existing = db.query(models.Product).filter(models.Product.sku == payload.sku).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"SKU '{payload.sku}' already exists",
        )
    obj = models.Product(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return db.query(models.Product).options(selectinload(models.Product.category)).get(obj.id)


@router.get("/", response_model=list[schemas.ProductOut])
def list_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return (
        db.query(models.Product)
        .options(selectinload(models.Product.category))
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{product_id}", response_model=schemas.ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    obj = (
        db.query(models.Product)
        .options(selectinload(models.Product.category))
        .filter(models.Product.id == product_id)
        .first()
    )
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return obj


@router.patch("/{product_id}", response_model=schemas.ProductOut)
def update_product(
    product_id: int,
    payload: schemas.ProductUpdate,
    db: Session = Depends(get_db),
):
    obj = _get_or_404(db, product_id)
    data = payload.model_dump(exclude_unset=True)
    if "category_id" in data and not db.get(models.Category, data["category_id"]):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    if "sku" in data:
        conflict = (
            db.query(models.Product)
            .filter(models.Product.sku == data["sku"], models.Product.id != product_id)
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"SKU '{data['sku']}' already exists",
            )
    for field, value in data.items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return db.query(models.Product).options(selectinload(models.Product.category)).get(obj.id)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    obj = _get_or_404(db, product_id)
    db.delete(obj)
    db.commit()


# ── Image upload ──────────────────────────────────────────────────────────────

@router.post("/{product_id}/image", response_model=schemas.ProductOut)
def upload_image(
    product_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image type '{file.content_type}'",
        )
    obj = _get_or_404(db, product_id)
    os.makedirs(settings.upload_dir, exist_ok=True)
    ext = (file.filename or "").rsplit(".", 1)[-1] or "bin"
    filename = f"{uuid.uuid4().hex}.{ext}"
    dest = os.path.join(settings.upload_dir, filename)
    with open(dest, "wb") as out:
        shutil.copyfileobj(file.file, out)
    obj.image = dest
    db.commit()
    db.refresh(obj)
    return db.query(models.Product).options(selectinload(models.Product.category)).get(obj.id)


# ── Search ────────────────────────────────────────────────────────────────────

@router.get("/search/", response_model=schemas.PaginatedProducts)
def search_products(
    q: Annotated[str | None, Query(description="Search title or SKU")] = None,
    sku: Annotated[str | None, Query(description="Exact SKU match")] = None,
    category_id: Annotated[int | None, Query(description="Category (includes subcategories)")] = None,
    price_min: Annotated[Decimal | None, Query(ge=0)] = None,
    price_max: Annotated[Decimal | None, Query(ge=0)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    db: Session = Depends(get_db),
):
    stmt = select(models.Product).options(selectinload(models.Product.category))

    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                models.Product.title.ilike(pattern),
                models.Product.sku.ilike(pattern),
            )
        )

    if sku:
        stmt = stmt.where(models.Product.sku == sku)

    if category_id is not None:
        category_ids = _category_subtree_ids(db, category_id)
        stmt = stmt.where(models.Product.category_id.in_(category_ids))

    if price_min is not None:
        stmt = stmt.where(models.Product.price >= price_min)

    if price_max is not None:
        stmt = stmt.where(models.Product.price <= price_max)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = db.execute(count_stmt).scalar_one()

    offset = (page - 1) * page_size
    rows = db.execute(stmt.offset(offset).limit(page_size)).scalars().all()

    return schemas.PaginatedProducts(
        total=total,
        page=page,
        page_size=page_size,
        results=list(rows),
    )
