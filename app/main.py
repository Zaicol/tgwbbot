import logging
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Product
from app.database.database import get_db
import httpx

app = FastAPI()

BASE_URL = "https://card.wb.ru/cards/v1/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm="


async def get_product_by_artikul(artikul: int) -> dict:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(BASE_URL + str(artikul))
            response.raise_for_status()
            product = response.json()["data"]["products"][0]
            return product
        except httpx.HTTPStatusError as exc:
            raise ValueError(f"Error fetching product data: {exc.response.status_code}") from exc
        except KeyError as exc:
            raise ValueError(f"Error fetching product data: {exc}") from exc


class ProductCreate(BaseModel):
    artikul: int


async def upsert_product(db: AsyncSession, product_data: dict):
    upsert = insert(Product).values(**product_data).on_conflict_do_update(
        index_elements=["artikul"],
        set_={
            "name": product_data["name"],
            "price": product_data.get("price"),
            "rating": product_data.get("rating"),
            "stock": product_data.get("stock"),
        }
    )

    # Выполняем запрос
    await db.execute(upsert)
    await db.commit()

    return "Product upserted"


@app.post("/api/v1/products", response_model=dict)
async def get_product(product: ProductCreate, db: AsyncSession = Depends(get_db)):
    try:
        # Обращаемся к внешнему API
        product_data = await get_product_by_artikul(product.artikul)
    except ValueError as e:
        logging.error(f"Error fetching product: {e}")
        raise HTTPException(status_code=404, detail=str(e))

    product_table_data = {
        "artikul": product.artikul,
        "name": product_data["name"],
        "price": product_data["salePriceU"],
        "rating": product_data["reviewRating"],
        "stock": product_data["totalQuantity"],
        "last_updated": datetime.utcnow(),
    }

    try:
        message = await upsert_product(db, product_table_data)
    except Exception as e:
        logging.error(f"Error upserting product: {e}")
        raise HTTPException(status_code=400, detail="Could not create product")

    return {"message": message, "product": product_table_data}
