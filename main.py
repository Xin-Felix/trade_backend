"""
兼容入口：保留根目录 main.py，方便 `uvicorn main:app` 启动。
实际应用定义在 app/main.py。
"""

from app.main import app
