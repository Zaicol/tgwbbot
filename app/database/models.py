from sqlalchemy import Column, Integer, String, Float, DateTime, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Product(Base):
    __tablename__ = "products"

    artikul = Column(Integer, primary_key=True, unique=True, nullable=False, comment="Артикул товара")
    name = Column(String, nullable=False, comment="Название товара")
    price = Column(Float, nullable=True, comment="Цена товара в рублях")
    rating = Column(Float, nullable=True, comment="Рейтинг товара")
    stock = Column(Integer, nullable=True, comment="Количество товара на складе")
    last_updated = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(),
                          comment="Время последнего обновления данных")
