from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# ── Category ──────────────────────────────────────────────────────────────────

class CategoryBase(BaseModel):
    name: str = Field(..., max_length=120)
    parent_id: int | None = None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    parent_id: int | None = None


class CategoryOut(CategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


# ── Product ───────────────────────────────────────────────────────────────────

class ProductBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: str = ""
    sku: str = Field(..., max_length=100)
    price: Decimal = Field(..., gt=0)
    category_id: int


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    title: str | None = Field(None, max_length=255)
    description: str | None = None
    sku: str | None = Field(None, max_length=100)
    price: Decimal | None = Field(None, gt=0)
    category_id: int | None = None


class ProductOut(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    image: str | None
    category: CategoryOut


# ── Search ────────────────────────────────────────────────────────────────────

class ProductSearchParams(BaseModel):
    q: str | None = Field(None, description="Match against title or SKU")
    sku: str | None = Field(None, description="Exact SKU")
    category_id: int | None = Field(None, description="Exact category (subtree included)")
    price_min: Decimal | None = Field(None, ge=0)
    price_max: Decimal | None = Field(None, ge=0)
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class PaginatedProducts(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[ProductOut]
