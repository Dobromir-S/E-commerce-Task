"""Unit tests for the product search endpoint."""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app import models
from sqlalchemy.orm import Session


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_category(db: Session, name: str, parent_id: int | None = None) -> models.Category:
    cat = models.Category(name=name, parent_id=parent_id)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def _make_product(
    db: Session,
    *,
    title: str,
    sku: str,
    price: str,
    category_id: int,
    description: str = "",
) -> models.Product:
    p = models.Product(
        title=title,
        sku=sku,
        price=Decimal(price),
        category_id=category_id,
        description=description,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def catalog(db):
    """
    Category tree:
        Electronics (id=1)
            └── Phones (id=2)
        Clothing (id=3)

    Products:
        iPhone 15  – SKU=IP15   – $999  – Phones
        Galaxy S24 – SKU=GS24   – $850  – Phones
        Hoodie     – SKU=HDI001 – $45   – Clothing
        Laptop Pro – SKU=LP2024 – $1500 – Electronics
    """
    electronics = _make_category(db, "Electronics")
    phones = _make_category(db, "Phones", parent_id=electronics.id)
    clothing = _make_category(db, "Clothing")

    iphone = _make_product(db, title="iPhone 15", sku="IP15", price="999.00", category_id=phones.id)
    galaxy = _make_product(db, title="Galaxy S24", sku="GS24", price="850.00", category_id=phones.id)
    hoodie = _make_product(db, title="Hoodie", sku="HDI001", price="45.00", category_id=clothing.id)
    laptop = _make_product(db, title="Laptop Pro", sku="LP2024", price="1500.00", category_id=electronics.id)

    return {
        "categories": {
            "electronics": electronics,
            "phones": phones,
            "clothing": clothing,
        },
        "products": {
            "iphone": iphone,
            "galaxy": galaxy,
            "hoodie": hoodie,
            "laptop": laptop,
        },
    }


# ── no filters ────────────────────────────────────────────────────────────────

def test_search_returns_all_when_no_filters(client: TestClient, catalog):
    resp = client.get("/products/search/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 4
    assert len(data["results"]) == 4


# ── text search (q) ───────────────────────────────────────────────────────────

def test_search_by_title_substring(client: TestClient, catalog):
    resp = client.get("/products/search/", params={"q": "galaxy"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["results"][0]["sku"] == "GS24"


def test_search_by_title_case_insensitive(client: TestClient, catalog):
    resp = client.get("/products/search/", params={"q": "IPHONE"})
    data = resp.json()
    assert data["total"] == 1
    assert data["results"][0]["sku"] == "IP15"


def test_search_q_matches_sku_substring(client: TestClient, catalog):
    resp = client.get("/products/search/", params={"q": "LP2024"})
    data = resp.json()
    assert data["total"] == 1
    assert data["results"][0]["title"] == "Laptop Pro"


def test_search_q_no_results(client: TestClient, catalog):
    resp = client.get("/products/search/", params={"q": "nonexistent"})
    data = resp.json()
    assert data["total"] == 0
    assert data["results"] == []


# ── exact SKU ─────────────────────────────────────────────────────────────────

def test_search_by_exact_sku(client: TestClient, catalog):
    resp = client.get("/products/search/", params={"sku": "HDI001"})
    data = resp.json()
    assert data["total"] == 1
    assert data["results"][0]["title"] == "Hoodie"


def test_search_by_sku_wrong_case_returns_nothing(client: TestClient, catalog):
    # SKU matching is exact (case-sensitive)
    resp = client.get("/products/search/", params={"sku": "hdi001"})
    data = resp.json()
    assert data["total"] == 0


# ── price range ───────────────────────────────────────────────────────────────

def test_search_price_min(client: TestClient, catalog):
    resp = client.get("/products/search/", params={"price_min": "900"})
    data = resp.json()
    skus = {p["sku"] for p in data["results"]}
    assert skus == {"IP15", "LP2024"}


def test_search_price_max(client: TestClient, catalog):
    resp = client.get("/products/search/", params={"price_max": "900"})
    data = resp.json()
    skus = {p["sku"] for p in data["results"]}
    assert skus == {"GS24", "HDI001"}


def test_search_price_range(client: TestClient, catalog):
    resp = client.get("/products/search/", params={"price_min": "800", "price_max": "1000"})
    data = resp.json()
    skus = {p["sku"] for p in data["results"]}
    assert skus == {"IP15", "GS24"}


def test_search_price_range_no_results(client: TestClient, catalog):
    resp = client.get("/products/search/", params={"price_min": "2000", "price_max": "5000"})
    data = resp.json()
    assert data["total"] == 0


# ── category filter ───────────────────────────────────────────────────────────

def test_search_by_exact_category(client: TestClient, catalog):
    clothing_id = catalog["categories"]["clothing"].id
    resp = client.get("/products/search/", params={"category_id": clothing_id})
    data = resp.json()
    assert data["total"] == 1
    assert data["results"][0]["sku"] == "HDI001"


def test_search_by_parent_category_includes_subtree(client: TestClient, catalog):
    """Querying Electronics should return products in Electronics AND Phones."""
    electronics_id = catalog["categories"]["electronics"].id
    resp = client.get("/products/search/", params={"category_id": electronics_id})
    data = resp.json()
    skus = {p["sku"] for p in data["results"]}
    assert skus == {"LP2024", "IP15", "GS24"}


def test_search_by_leaf_category(client: TestClient, catalog):
    phones_id = catalog["categories"]["phones"].id
    resp = client.get("/products/search/", params={"category_id": phones_id})
    data = resp.json()
    skus = {p["sku"] for p in data["results"]}
    assert skus == {"IP15", "GS24"}


def test_search_by_nonexistent_category_returns_empty(client: TestClient, catalog):
    resp = client.get("/products/search/", params={"category_id": 9999})
    data = resp.json()
    assert data["total"] == 0


# ── combined filters ──────────────────────────────────────────────────────────

def test_search_combined_q_and_category(client: TestClient, catalog):
    phones_id = catalog["categories"]["phones"].id
    resp = client.get("/products/search/", params={"q": "galaxy", "category_id": phones_id})
    data = resp.json()
    assert data["total"] == 1
    assert data["results"][0]["sku"] == "GS24"


def test_search_combined_q_and_price(client: TestClient, catalog):
    # "phone"-like query but only cheap ones — should be nothing since phones are ≥$850
    resp = client.get("/products/search/", params={"q": "iphone", "price_max": "500"})
    data = resp.json()
    assert data["total"] == 0


# ── pagination ────────────────────────────────────────────────────────────────

def test_pagination_page_size(client: TestClient, catalog):
    resp = client.get("/products/search/", params={"page_size": 2})
    data = resp.json()
    assert data["total"] == 4
    assert len(data["results"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2


def test_pagination_second_page(client: TestClient, catalog):
    resp = client.get("/products/search/", params={"page_size": 2, "page": 2})
    data = resp.json()
    assert data["total"] == 4
    assert len(data["results"]) == 2


def test_pagination_beyond_last_page(client: TestClient, catalog):
    resp = client.get("/products/search/", params={"page_size": 10, "page": 5})
    data = resp.json()
    assert data["total"] == 4
    assert data["results"] == []


def test_pagination_invalid_page_returns_422(client: TestClient, catalog):
    resp = client.get("/products/search/", params={"page": 0})
    assert resp.status_code == 422
