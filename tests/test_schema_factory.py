from datetime import datetime
from typing import Any, Callable, Dict, Optional, Sequence, Type, Union

import pytest
import sqlalchemy as sa
from sqlalchemy import BigInteger, FetchedValue, Integer, String, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.sql.expression import ColumnElement
from sqlalchemy.sql.type_api import TypeEngine

from sqlalchemy_to_json_schema.schema_factory import SchemaFactory
from sqlalchemy_to_json_schema.walkers import (
    AbstractWalker,
    ForeignKeyWalker,
    NoForeignKeyWalker,
    StructuralWalker,
)
from tests.fixtures.models.base import Base

WALKER_CLASSES: Sequence[Type[AbstractWalker]] = [
    ForeignKeyWalker,
    NoForeignKeyWalker,
    StructuralWalker,
]


class TestSchemaFactory:
    @pytest.mark.parametrize("walker_cls", WALKER_CLASSES)
    @pytest.mark.parametrize("server_default", [None, func.sysdate()])
    @pytest.mark.parametrize("default", [None, datetime.now])
    def test_detect__nullable_is_True__not_required(
        self,
        walker_cls: Type[AbstractWalker],
        default: Optional[Callable[..., datetime]],
        server_default: Optional[Union[FetchedValue, str, TextClause, ColumnElement[Any], None]],
    ) -> None:
        class Model(Base):
            __tablename__ = f"model_nullable_true_{walker_cls}_{default}_{server_default}"

            pk = sa.Column(sa.Integer, primary_key=True, doc="primary key")
            created_at = sa.Column(
                sa.DateTime, nullable=True, default=default, server_default=server_default
            )

        target = SchemaFactory(walker_cls)
        walker = target.walker(Model)

        result = target._detect_required(walker)

        assert result == ["pk"]

    @pytest.mark.parametrize("server_default", [None, func.sysdate()])
    @pytest.mark.parametrize("default", [None, datetime.now])
    @pytest.mark.parametrize("walker_cls", WALKER_CLASSES)
    def test_detect__nullable_is_False__required(
        self,
        walker_cls: Type[AbstractWalker],
        default: Optional[Callable[..., datetime]],
        server_default: Optional[Callable[..., datetime]],
    ) -> None:
        class Model(Base):
            __tablename__ = f"model_nullable_false_{walker_cls}_{default}_{server_default}"

            pk = sa.Column(sa.Integer, primary_key=True, doc="primary key")
            created_at = sa.Column(
                sa.DateTime, nullable=False, default=default, server_default=None
            )

        target = SchemaFactory(walker_cls)
        walker = target.walker(Model)

        result = target._detect_required(walker)

        expected = sorted(["pk", "created_at"])

        assert result == expected

    @pytest.mark.parametrize("walker_cls", WALKER_CLASSES)
    def test_detect__adjust_required(self, walker_cls: Type[AbstractWalker]) -> None:
        class Model(Base):
            __tablename__ = f"model_adjust_required_{walker_cls}"

            pk = sa.Column(sa.Integer, primary_key=True, doc="primary key")

        target = SchemaFactory(walker_cls)
        walker = target.walker(Model)

        result = target._detect_required(
            walker,
            adjust_required=lambda prop, default: False if prop.key == "pk" else default,
        )

        assert result == []

    @pytest.mark.parametrize("walker_cls", WALKER_CLASSES)
    @pytest.mark.parametrize(
        "array_type, expected_type",
        [
            pytest.param(Integer, "integer", id="integer"),
            pytest.param(String, "string", id="string"),
        ],
    )
    def test_column_array(
        self, walker_cls: Type[AbstractWalker], array_type: Type[TypeEngine], expected_type: str
    ) -> None:
        """
        ARRANGE a model with a column that is concatenable
        ACT generate the schema
        ASSERT the column is an array of string
        """

        # arrange
        class Model(Base):
            __tablename__ = f"model_column_array_{expected_type}_{walker_cls}"

            pk = sa.Column(sa.Integer, primary_key=True)
            concatenable = sa.Column(sa.ARRAY(array_type))

        target = SchemaFactory(walker_cls)

        # act
        actual = target(Model)

        # assert
        assert actual == {
            "properties": {
                "pk": {"type": "integer"},
                "concatenable": {"type": "array", "items": {"type": expected_type}},
            },
            "required": ["pk"],
            "title": "Model",
            "type": "object",
        }

    @pytest.mark.parametrize("walker_cls", WALKER_CLASSES)
    def test_column_postgres_uuid(self, walker_cls: Type[AbstractWalker]) -> None:
        class Model(Base):
            __tablename__ = f"model_column_postgres_uuid_{walker_cls}"

            id = sa.Column("id", postgresql.UUID, primary_key=True)

        schema_factory = SchemaFactory(walker_cls)

        actual = schema_factory(Model)

        assert actual == {
            "properties": {"id": {"type": "string", "format": "uuid"}},
            "required": ["id"],
            "title": "Model",
            "type": "object",
        }

    @pytest.mark.parametrize("walker_cls", WALKER_CLASSES)
    def test_column_json(self, walker_cls: Type[AbstractWalker]) -> None:
        class Model(Base):
            __tablename__ = f"model_column_json_{walker_cls}"

            id = sa.Column(sa.Integer, primary_key=True)
            data = sa.Column(sa.JSON)

        schema_factory = SchemaFactory(walker_cls)

        actual = schema_factory(Model)

        assert actual == {
            "properties": {
                "id": {"type": "integer"},
                "data": {"type": "object"},
            },
            "required": ["id"],
            "title": "Model",
            "type": "object",
        }

    @pytest.mark.parametrize("walker_cls", WALKER_CLASSES)
    def test_hybrid_property(self, walker_cls: Type[AbstractWalker]) -> None:
        class Model(Base):
            __tablename__ = f"model_hybrid_property_{walker_cls}"

            _id = sa.Column("id", Integer, primary_key=True)

            @hybrid_property
            def id(self) -> int:
                return self._id

            @id.setter  # type: ignore[no-redef]
            def id(self, id_: int) -> None:
                self._id = id_

        schema_factory = SchemaFactory(walker_cls)

        actual = schema_factory(Model)

        assert actual == {
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
            "title": "Model",
            "type": "object",
        }

    @pytest.mark.parametrize("walker_cls", WALKER_CLASSES)
    def test_hybrid_property_with_mixin(self, walker_cls: Type[AbstractWalker]) -> None:
        class IdMixin:
            _id = sa.Column("id", Integer, primary_key=True)

            @hybrid_property
            def id(self) -> int:
                return self._id

            @id.setter  # type: ignore[no-redef]
            def id(self, id_: int) -> None:
                self._id = id_

        class Model(Base, IdMixin):
            __tablename__ = f"model_hybrid_property_with_mixin_{walker_cls}"

        schema_factory = SchemaFactory(walker_cls)

        actual = schema_factory(Model)

        assert actual == {
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
            "title": "Model",
            "type": "object",
        }

    @pytest.mark.parametrize(
        "walker_cls, expected",
        [
            pytest.param(
                NoForeignKeyWalker,
                {
                    "properties": {"id": {"type": "integer"}},
                    "required": ["id"],
                    "title": "ModelWithRelationship",
                    "type": "object",
                },
            ),
            pytest.param(
                ForeignKeyWalker,
                # Note: `_other_model_id` is returned instead of `other_model_id` because the
                #       `local_table.columns` iterator is returning the real column and not the
                #       hybrid property.
                {
                    "properties": {
                        "id": {"type": "integer"},
                        "_other_model_id": {"type": "integer"},
                    },
                    "required": sorted(["id", "_other_model_id"]),
                    "title": "ModelWithRelationship",
                    "type": "object",
                },
            ),
            pytest.param(
                StructuralWalker,
                {
                    "definitions": {
                        "OtherModel": {
                            "properties": {"id": {"type": "integer"}},
                            "required": ["id"],
                            "type": "object",
                        },
                    },
                    "properties": {
                        "id": {"type": "integer"},
                        "other_model": {"$ref": "#/definitions/OtherModel"},
                    },
                    "required": ["id"],
                    "title": "ModelWithRelationship",
                    "type": "object",
                },
            ),
        ],
    )
    def test_hybrid_property_with_relationship(
        self, walker_cls: Type[AbstractWalker], expected: Dict[str, Any]
    ) -> None:
        class OtherModel(Base):
            __tablename__ = f"submodel_hybrid_property_with_relationship_{walker_cls}"

            id = sa.Column(Integer, primary_key=True)

        class ModelWithRelationship(Base):
            __tablename__ = f"model_hybrid_property_with_relationship_{walker_cls}"

            id = sa.Column(sa.Integer, primary_key=True)
            other_model = relationship(OtherModel, uselist=False, backref="users")

            _other_model_id = sa.Column(Integer, sa.ForeignKey(OtherModel.id), nullable=False)

            @hybrid_property
            def other_model_id(self) -> int:
                return self._other_model_id

            @other_model_id.setter  # type: ignore[no-redef]
            def other_model_id(self, other_model_id: int) -> None:
                self._other_model_id = other_model_id

        schema_factory = SchemaFactory(walker_cls)

        actual = schema_factory(ModelWithRelationship)

        assert actual == expected

    @pytest.mark.parametrize("walker_cls", WALKER_CLASSES)
    @pytest.mark.parametrize(
        "custom_type, expected_type",
        [
            pytest.param(Integer, "integer", id="integer"),
            pytest.param(BigInteger, "integer", id="bingint"),
        ],
    )
    def test_column_custom_column(
        self, walker_cls: Type[AbstractWalker], custom_type: Type[TypeEngine], expected_type: str
    ) -> None:
        # arrange
        class Identifier(Integer):
            def __init__(self, inner: Type[TypeEngine]) -> None:
                self.inner = inner

            def _compiler_dispatch(self, visitor: Any, **kw: Any) -> Any:
                return self.inner._compiler_dispatch(visitor, **kw)

            def is_not_support_big_integer(self) -> bool:
                return True

            def get_dbapi_type(self, dbapi: Any) -> Any:
                return self.inner.get_dbapi_type(dbapi)  # type: ignore[call-arg]

            @property
            def python_type(self) -> Any:
                return self.inner.python_type

            @property
            def _expression_adaptations(self) -> Any:
                return self.inner._expression_adaptations  # type: ignore[attr-defined]

        class Model(Base):
            __tablename__ = f"model_column_custom_column_{custom_type}_{walker_cls}"

            pk = sa.Column(Identifier(Integer), primary_key=True)

        target = SchemaFactory(walker_cls)

        # act
        actual = target(Model)

        # assert
        assert actual == {
            "properties": {"pk": {"type": expected_type}},
            "required": ["pk"],
            "title": "Model",
            "type": "object",
        }
