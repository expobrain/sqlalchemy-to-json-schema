from collections.abc import Iterable
from typing import Any, Union

import sqlalchemy as sa
from result import Result, is_ok
from sqlalchemy import TypeDecorator
from sqlalchemy.orm import DeclarativeMeta, declarative_base
from sqlalchemy.sql.type_api import TypeEngine
from sqlalchemy.types import String

from sqlalchemy_to_json_schema.schema_factory import Schema, SchemaFactory
from sqlalchemy_to_json_schema.walkers import StructuralWalker


def _callFUT(model: DeclarativeMeta, /) -> Result[Schema, str]:
    # see: https://github.com/expobrain/sqlalchemy_to_json_schema/issues/6

    factory = SchemaFactory(StructuralWalker)
    schema_result = factory(model)

    return schema_result


def _makeType(impl_: Union[type[TypeEngine], TypeEngine]) -> type[TypeDecorator]:
    class Choice(TypeDecorator):
        impl = impl_

        def __init__(self, choices: Iterable[tuple[str, Any]], **kw: Any) -> None:
            self.choices = dict(choices)
            super().__init__(**kw)

        def process_bind_param(self, value: Any, dialect: Any) -> Any:
            return [k for k, v in self.choices.items() if v == value][0]

        def process_result_value(self, value: Any, dialect: Any) -> Any:
            return self.choices[value]

    return Choice


def test_it() -> None:
    Base = declarative_base()
    Choice = _makeType(impl_=String)

    class Hascolor(Base):
        __tablename__ = "hascolor"
        hascolor_id = sa.Column(sa.Integer, primary_key=True)
        candidates = [(c, c) for c in ["r", "g", "b", "y"]]
        color: sa.Column[str] = sa.Column(Choice(choices=candidates, length=1), nullable=False)

    result = _callFUT(Hascolor)

    assert is_ok(result)
    assert result.value["properties"]["color"] == {"type": "string", "maxLength": 1}


def test_it__impl_is_not_callable() -> None:
    Base = declarative_base()
    Choice = _makeType(impl_=String(length=1))

    class Hascolor(Base):
        __tablename__ = "hascolor"
        hascolor_id = sa.Column(sa.Integer, primary_key=True)
        candidates = [(c, c) for c in ["r", "g", "b", "y"]]
        color: sa.Column[str] = sa.Column(Choice(choices=candidates), nullable=False)

    result = _callFUT(Hascolor)

    assert is_ok(result)
    assert result.unwrap()["properties"]["color"] == {"type": "string", "maxLength": 1}
