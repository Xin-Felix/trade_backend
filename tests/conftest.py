import os

# 测试环境必须在导入 app 前设置环境变量
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["TUSHARE_TOKEN"] = ""
os.environ["MOCK_STOCK_DATA"] = "true"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base, SessionLocal, engine, get_db
from app.main import app


def _remove_test_db():
    db_file = "test.db"
    if os.path.exists(db_file):
        os.remove(db_file)


@pytest.fixture(scope="session", autouse=True)
def _setup_test_database():
    """会话级：清理旧测试库并创建表结构，供 API 测试的 lifespan 使用。"""
    _remove_test_db()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    _remove_test_db()


@pytest.fixture(scope="function")
def db():
    """函数级独立内存数据库会话，供 service 单元测试使用，完全隔离。"""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


@pytest.fixture(scope="module")
def client() -> TestClient:
    """模块级 HTTP 客户端：触发一次 lifespan 创建种子数据，供 API 测试共用。"""

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
