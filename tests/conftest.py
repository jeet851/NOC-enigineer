import os
import sys
import pytest

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Override DB path for test runs before imports
os.environ["DATABASE_URL"] = "sqlite:///test_network_noc.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"

from fastapi.testclient import TestClient
from api.app import app
from database.session import engine, SessionLocal
from database.base import Base
from database.seed import seed_db

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    # Force initialize the SQLite test database schema
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    # Run seeding logic
    seed_db()
    
    yield
    
    # Clean up test database connection
    Base.metadata.drop_all(bind=engine)
    
    # Attempt to delete the test database file
    db_file = "test_network_noc.db"
    if os.path.exists(db_file):
        try:
            # Clear WAL files if SQLite created them
            if os.path.exists(f"{db_file}-wal"):
                os.remove(f"{db_file}-wal")
            if os.path.exists(f"{db_file}-shm"):
                os.remove(f"{db_file}-shm")
            os.remove(db_file)
        except Exception:
            pass

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
