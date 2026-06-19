from fastapi import FastAPI

from app.routers import categories, products

app = FastAPI(
    title="E-commerce Product Service",
    version="1.0.0",
    description="CRUD and search API for products and categories.",
)

app.include_router(categories.router)
app.include_router(products.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
