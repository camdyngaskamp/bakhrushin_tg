from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Redis client (optional - for session storage)
try:
    import redis
    redis_client = redis.from_url(settings.redis_url) if hasattr(settings, "redis_url") else None
except ImportError:
    redis_client = None
