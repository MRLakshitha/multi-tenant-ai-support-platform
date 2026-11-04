import sys
from sqlalchemy import create_engine
from app.core.config import settings
from app.models import Base

def init_db():
    print(f"Initializing database schema at {settings.SYNC_DATABASE_URL}...")
    engine = create_engine(settings.SYNC_DATABASE_URL, echo=False)
    Base.metadata.create_all(bind=engine)
    print("Database tables initialized successfully!")

if __name__ == "__main__":
    init_db()
