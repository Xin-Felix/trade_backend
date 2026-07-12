"""同步数据库操作的异步包装工具。

当前服务层仍使用同步 SQLAlchemy Session。为了让 async FastAPI 路径操作函数
不阻塞事件循环，可将同步 service 调用通过 `run_sync_call` 放到线程池执行。

后续若要彻底改造，可迁移到 AsyncSession + asyncpg，届时本工具可作为过渡层
逐步替换为原生 await。
"""

from collections.abc import Callable
from typing import ParamSpec, TypeVar

from starlette.concurrency import run_in_threadpool

P = ParamSpec("P")
T = TypeVar("T")


async def run_sync_call(func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    """在线程池中执行同步函数并 await 返回结果。

    用法：
        result = await run_sync_call(service.some_func, db, arg1, arg2)
    """
    return await run_in_threadpool(lambda: func(*args, **kwargs))
