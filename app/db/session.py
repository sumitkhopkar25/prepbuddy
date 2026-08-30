from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.config import database_settings

engine = create_engine(database_settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
