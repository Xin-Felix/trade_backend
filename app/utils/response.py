"""通用响应构建工具。

将 ORM 对象与 Pydantic schema/响应模型之间的转换抽象为可复用函数，
减少 endpoints 中重复的 `_to_dict` + 列表包装代码。
"""

from collections.abc import Callable, Sequence
from typing import TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT")
SchemaT = TypeVar("SchemaT", bound=BaseModel)
ResponseT = TypeVar("ResponseT", bound=BaseModel)


def build_list_response(
    items: Sequence[ModelT],
    response_cls: type[ResponseT],
    schema_cls: type[SchemaT],
    converter: Callable[[ModelT], dict] | None = None,
) -> ResponseT:
    """将 ORM 对象列表转换为 schema 列表并包装为响应对象。

    当 ORM 属性与 schema 字段一一对应时，直接传 schema_cls 即可；
    需要额外计算/附加字段时，提供 converter 函数返回 dict。
    """
    if converter is None:
        data = [schema_cls.model_validate(item, from_attributes=True) for item in items]
    else:
        data = [schema_cls(**converter(item)) for item in items]
    return response_cls(data=data)


def build_item_response(
    item: ModelT,
    response_cls: type[ResponseT],
    schema_cls: type[SchemaT],
    converter: Callable[[ModelT], dict] | None = None,
) -> ResponseT:
    """将单个 ORM 对象转换为 schema 并包装为响应对象。"""
    if converter is None:
        data = schema_cls.model_validate(item, from_attributes=True)
    else:
        data = schema_cls(**converter(item))
    return response_cls(data=data)
