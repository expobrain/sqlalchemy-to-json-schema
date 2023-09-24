from typing import Any, Iterable, Tuple, Type, Union

import sqlalchemy as sa
from sqlalchemy import TypeDecorator
from sqlalchemy.orm import DeclarativeMeta, declarative_base
from sqlalchemy.sql.type_api import TypeEngine
from sqlalchemy.types import String

from sqlalchemy_to_json_schema.schema_factory import Schema, SchemaFactory
from sqlalchemy_to_json_schema.walkers import StructuralWalker


def _callFUT(model: DeclarativeMeta, /) -> Schema:
    # see: https://github.com/expobrain/sqlalchemy_to_json_schema/issues/6

    factory = SchemaFactory(StructuralWalker)
    schema = factory(model)

    return schema


def _makeType(impl_: Union[Type[TypeEngine], TypeEngine]) -> Type[TypeDecorator]:
    class Choice(TypeDecorator):
        impl = impl_

        def __init__(self, choices: Iterable[Tuple[str, Any]], **kw: Any) -> None:
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
        color = sa.Column(Choice(choices=candidates, length=1), nullable=False)

    result = _callFUT(Hascolor)
    assert result["properties"]["color"] == {"type": "string", "maxLength": 1}


def test_it__impl_is_not_callable() -> None:
    Base = declarative_base()
    Choice = _makeType(impl_=String(length=1))

    class Hascolor(Base):
        __tablename__ = "hascolor"
        hascolor_id = sa.Column(sa.Integer, primary_key=True)
        candidates = [(c, c) for c in ["r", "g", "b", "y"]]
        color = sa.Column(Choice(choices=candidates), nullable=False)

    result = _callFUT(Hascolor)
    assert result["properties"]["color"] == {"type": "string", "maxLength": 1}
