import logging
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Product
from app.database.database import get_db, engine, async_session
import httpx

from apscheduler import AsyncScheduler, CoalescePolicy, JobLookupError, ScheduleLookupError
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.triggers.interval import IntervalTrigger

app = FastAPI()

BASE_URL = "https://card.wb.ru/cards/v1/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm="

data_store = SQLAlchemyDataStore(engine)
scheduler = AsyncScheduler(data_store)


@app.on_event("startup")
async def startup_event():
    await scheduler.__aenter__()
    await scheduler.get_schedules()  # Восстанавливаем задачи из БД
    await scheduler.start_in_background()


@app.on_event("shutdown")
async def shutdown_event():
    await scheduler.__aexit__(None, None, None)


async def get_product_by_artikul(artikul: int) -> dict:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(BASE_URL + str(artikul))
            response.raise_for_status()
            product = response.json()["data"]["products"][0]
            product_table_data = {
                "artikul": artikul,
                "name": product["name"],
                "price": product["salePriceU"],
                "rating": product["reviewRating"],
                "stock": product["totalQuantity"],
                "last_updated": datetime.utcnow(),
            }
            return product_table_data
        except httpx.HTTPStatusError as exc:
            raise ValueError(f"Error fetching product data: {exc.response.status_code}") from exc
        except KeyError as exc:
            raise ValueError(f"Error fetching product data: {exc}") from exc
        except IndexError as exc:
            raise ValueError(f"Не получилось найти продукт: {exc}") from exc


class ArtikulModel(BaseModel):
    artikul: int


async def upsert_product(product_data: dict, db: AsyncSession):
    upsert = insert(Product).values(**product_data).on_conflict_do_update(
        index_elements=["artikul"],
        set_={
            "name": product_data["name"],
            "price": product_data.get("price"),
            "rating": product_data.get("rating"),
            "stock": product_data.get("stock"),
            "last_updated": product_data.get("last_updated"),
        }
    )

    # Выполняем запрос
    await db.execute(upsert)
    await db.commit()

    return "Product upserted"


async def gs_product(product: ArtikulModel, db: AsyncSession):
    logging.info(f"Fetching product with artikul: {product.artikul}")
    try:
        product_table_data = await get_product_by_artikul(product.artikul)
    except ValueError as e:
        logging.error(f"Error fetching product: {e}")
        raise HTTPException(status_code=404, detail=str(e))

    try:
        message = await upsert_product(product_table_data, db)
    except Exception as e:
        logging.error(f"Error upserting product: {e}")
        raise HTTPException(status_code=400, detail="Could not create product")
    return message, product_table_data


@app.post("/api/v1/products", response_model=dict)
async def get_set_product(product: ArtikulModel, db: AsyncSession = Depends(get_db)):
    message, product_table_data = await gs_product(product, db)
    return {"message": message, "product": product_table_data}


async def sync_wrapper(product: ArtikulModel):
    logging.warn("Sync wrapper called")
    async with async_session() as db:
        await gs_product(product, db)
    return


@app.get("/api/v1/subscribe/{artikul}")
async def subscribe_to_product_updates(artikul: int):
    schedule_id = f"product_update_{artikul}"

    try:
        await scheduler.get_schedule(schedule_id)
        raise HTTPException(status_code=400, detail="Task for this artikul already exists")
    except ScheduleLookupError:
        logging.info(f"Task for artikul {artikul} does not exist")

    try:
        await get_product_by_artikul(artikul)
    except ValueError as e:
        logging.error(f"Error fetching product: {e}")
        raise HTTPException(status_code=404, detail=str(e))

    await scheduler.add_schedule(
        sync_wrapper,
        trigger=IntervalTrigger(minutes=30),
        id=schedule_id,
        args=[ArtikulModel.model_validate({"artikul": artikul})],
        coalesce=CoalescePolicy.latest,
    )
    return {"message": f"Subscribed to updates for artikul {artikul}"}


@app.get("/api/v1/unsubscribe/{artikul}")
async def unsubscribe_from_product_updates(artikul: int):
    schedule_id = f"update_product_{artikul}"

    try:
        await scheduler.remove_schedule(schedule_id)
        return {"message": f"Unsubscribed from updates for artikul {artikul}"}
    except JobLookupError:
        raise HTTPException(status_code=404, detail="No subscription found for this artikul")
