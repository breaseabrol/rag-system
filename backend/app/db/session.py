from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://raguser:ragpass@localhost:5432/ragdb"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)