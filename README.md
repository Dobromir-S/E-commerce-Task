# E-commerce Product Service

A production-ready REST API for managing products and categories in an e-commerce system.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Framework | **FastAPI** | Automatic OpenAPI docs, native Pydantic validation, excellent async support |
| ORM | **SQLAlchemy 2.x** | Type-safe mapped columns, composable queries, database-agnostic |
| Migrations | **Alembic** | Version-controlled schema changes, safe for production deployments |
| Database | **PostgreSQL** (prod) / **SQLite** (tests) | PostgreSQL for production reliability; SQLite in-memory for fast, dependency-free tests |
| Validation | **Pydantic v2** | Strict input/output schemas, automatic 422 responses on bad input |
| Driver | **psycopg3** | Supports Python 3.13+, async-ready, maintained actively |

## Project structure

```
E-commerce-Task/
├── app/
│   ├── config.py          # Settings loaded from environment / .env
│   ├── database.py        # SQLAlchemy engine, session factory, Base
│   ├── models.py          # ORM models: Category (self-referential) + Product
│   ├── schemas.py         # Pydantic schemas for request/response validation
│   ├── main.py            # FastAPI app, router registration
│   └── routers/
│       ├── categories.py  # CRUD endpoints for categories
│       └── products.py    # CRUD + image upload + search endpoint
├── alembic/               # Database migrations
│   └── versions/
│       └── 0001_initial.py
├── tests/
│   ├── conftest.py        # In-memory SQLite fixtures, no Postgres needed
│   └── test_search.py     # 21 unit tests for the search endpoint
├── alembic.ini
├── pytest.ini
├── requirements.txt
└── .env.example
```

## Models

### Category
- `id` — primary key
- `name` — string (max 120 chars)
- `parent_id` — nullable self-FK; `NULL` means root category

Categories form an **arbitrary-depth tree**. The search endpoint resolves a category filter down the full subtree automatically.

### Product
- `id` — primary key
- `title` — string (max 255 chars), indexed
- `description` — text
- `image` — file path to uploaded image (nullable)
- `sku` — unique string identifier, indexed
- `price` — Numeric(12, 2), must be > 0
- `category_id` — FK to Category (required)

## API endpoints

Interactive docs available at `http://localhost:8000/docs` after starting the server.

### Categories
| Method | Path | Description |
|---|---|---|
| `POST` | `/categories/` | Create category |
| `GET` | `/categories/` | List all categories |
| `GET` | `/categories/{id}` | Get single category |
| `PATCH` | `/categories/{id}` | Update category |
| `DELETE` | `/categories/{id}` | Delete category |

### Products
| Method | Path | Description |
|---|---|---|
| `POST` | `/products/` | Create product |
| `GET` | `/products/` | List all products |
| `GET` | `/products/{id}` | Get single product |
| `PATCH` | `/products/{id}` | Update product |
| `DELETE` | `/products/{id}` | Delete product |
| `POST` | `/products/{id}/image` | Upload product image |
| `GET` | `/products/search/` | Search and filter products |

### Search endpoint — `GET /products/search/`

All parameters are optional and combinable:

| Parameter | Type | Description |
|---|---|---|
| `q` | string | Case-insensitive substring match on **title or SKU** |
| `sku` | string | Exact SKU match (case-sensitive) |
| `category_id` | int | Products in this category **and all subcategories** |
| `price_min` | decimal | Minimum price (inclusive) |
| `price_max` | decimal | Maximum price (inclusive) |
| `page` | int | Page number (default: 1) |
| `page_size` | int | Results per page, max 100 (default: 20) |

Response shape:
```json
{
  "total": 42,
  "page": 1,
  "page_size": 20,
  "results": [...]
}
```

## Running locally

### Prerequisites
- Python 3.13+ (note: Python 3.14+ requires SQLAlchemy ≥ 2.0.51 — this is already pinned in requirements.txt)
- Docker (for the database) **or** a PostgreSQL 14+ instance on port 5432

### 1. Start the database

```bash
docker compose up -d
```

This starts a PostgreSQL 16 container with the default credentials (`postgres/postgres`, database `ecommerce`). Skip this step if you have a local Postgres instance — just update `DATABASE_URL` in your `.env`.

### 2. Application setup

```bash
# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env only if your Postgres credentials differ from defaults

# Run database migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload
```

The API is now available at `http://localhost:8000`.
Interactive API docs: `http://localhost:8000/docs`

## Running tests

Tests use an **in-memory SQLite database** — no PostgreSQL required.

```bash
# With the venv active:
pytest

# Verbose output:
pytest -v

# Specific test:
pytest tests/test_search.py::test_search_by_parent_category_includes_subtree
```

All 21 tests cover the search endpoint across:
- No-filter (returns all)
- Title and SKU substring search (`q`)
- Exact SKU match
- Price range filtering
- Category filtering with full subtree resolution
- Combined filters
- Pagination (page size, second page, out-of-bounds page, invalid input)

## Design decisions

**Category subtree search** — when filtering by `category_id`, the service resolves all descendant category IDs via BFS before querying products. This means filtering by "Electronics" automatically includes products in "Phones", "Laptops" etc. without the client needing to know the tree structure.

**Exact vs. fuzzy SKU** — `sku` does an exact match (SKUs are identifiers), while `q` does a case-insensitive ILIKE that covers both title and SKU substrings for general search.

**Image storage** — images are stored on disk (path saved in the DB). For production, swap the upload handler to write to S3/GCS and store the URL instead.

**Numeric price** — `Numeric(12, 2)` avoids floating-point rounding issues common with `Float` for monetary values.
