import os

# 测试环境必须在导入 app 前设置环境变量
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["TUSHARE_TOKEN"] = ""
os.environ["MOCK_STOCK_DATA"] = "true"

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base, SessionLocal, engine, get_db
from app.main import app


def _remove_test_db():
    db_file = "test.db"
    if os.path.exists(db_file):
        os.remove(db_file)


@pytest.fixture(scope="module")
def client() -> TestClient:
    _remove_test_db()

    # 使用应用自身的 engine 创建表，确保 lifespan 和测试请求共享同一连接池
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    _remove_test_db()
