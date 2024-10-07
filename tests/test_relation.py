from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import sqlalchemy as sa
import sqlalchemy.orm as orm
from pytest_unordered import unordered
from result import is_ok
from sqlalchemy.orm import Mapped, declarative_base

from sqlalchemy_to_json_schema.decisions import UseForeignKeyIfPossibleDecision
from sqlalchemy_to_json_schema.schema_factory import RelationDecision, SchemaFactory
from sqlalchemy_to_json_schema.walkers import (
    AbstractWalker,
    ForeignKeyWalker,
    StructuralWalker,
)


def get_reference(schema: Mapping[str, Any], root_schema: Mapping[str, Any]) -> Mapping[str, Any]:
    ref = schema["$ref"]
    if not ref.startswith("#/"):
        raise NotImplementedError(ref)
    target = root_schema
    for k in ref.split("/")[1:]:
        target = target[k]
    return target


def _makeOne(walker: type[AbstractWalker], *args: Any, **kwargs: Any) -> SchemaFactory:
    return SchemaFactory(walker, *args, **kwargs)


Base = declarative_base()


class Group(Base):
    """model for test"""

    __tablename__ = "Group"

    pk = sa.Column(sa.Integer, primary_key=True, doc="primary key")
    name = sa.Column(sa.String(255), default="", nullable=False)


class User(Base):
    __tablename__ = "User"

    pk = sa.Column(sa.Integer, primary_key=True, doc="primary key")
    name = sa.Column(sa.String(255), default="", nullable=True)
    group_id = sa.Column(sa.Integer, sa.ForeignKey(Group.pk), nullable=False)
    group = orm.relationship(Group, uselist=False, backref="users")


def test_properties__default__includes__foreign_keys() -> None:
    target = _makeOne(ForeignKeyWalker)
    result = target(User)

    assert is_ok(result)
    assert "properties" in result.value
    assert list(result.value["properties"].keys()) == unordered(["group_id", "name", "pk"])


def test_properties__include_OnetoMany_relation() -> None:
    target = _makeOne(StructuralWalker, relation_decision=RelationDecision())
    result = target(User)

    assert is_ok(result)
    assert "required" in result.value
    assert list(result.value["properties"]) == unordered(["group", "name", "pk"])
    assert result.value["properties"]["group"] == {"$ref": "#/definitions/Group"}


def test_properties__include_OnetoMany_relation2() -> None:
    target = _makeOne(StructuralWalker, relation_decision=UseForeignKeyIfPossibleDecision())
    result = target(User)

    assert is_ok(result)
    assert "required" in result.value
    assert list(result.value["properties"]) == unordered(["group_id", "name", "pk"])
    assert result.value["properties"]["group_id"] == {"type": "integer", "relation": "group"}


def test_properties__include_ManytoOne_backref() -> None:
    target = _makeOne(StructuralWalker)
    result = target(Group)

    assert is_ok(result)
    assert "required" in result.value
    assert list(result.value["properties"]) == unordered(["name", "pk", "users"])
    assert result.value["properties"]["users"] == {
        "type": "array",
        "items": {"$ref": "#/definitions/User"},
    }
    assert result.value["definitions"]["User"] == {
        "type": "object",
        "required": ["pk"],
        "properties": {
            "name": {"maxLength": 255, "type": "string"},
            "pk": {"description": "primary key", "type": "integer"},
        },
    }


# depth
class A0(Base):
    __tablename__ = "A0"

    pk = sa.Column(sa.Integer, primary_key=True, doc="primary key")


class A1(Base):
    __tablename__ = "A1"

    pk = sa.Column(sa.Integer, primary_key=True, doc="primary key1")
    parent_id = sa.Column(sa.Integer, sa.ForeignKey(A0.pk), nullable=False)
    parent = orm.relationship(A0, uselist=False, backref="children")


class A2(Base):
    __tablename__ = "A2"

    pk = sa.Column(sa.Integer, primary_key=True, doc="primary key2")
    parent_id = sa.Column(sa.Integer, sa.ForeignKey(A1.pk), nullable=False)
    parent = orm.relationship(A1, uselist=False, backref="children")


class A3(Base):
    __tablename__ = "A3"

    pk = sa.Column(sa.Integer, primary_key=True, doc="primary key3")
    parent_id = sa.Column(sa.Integer, sa.ForeignKey(A2.pk), nullable=False)
    parent = orm.relationship(A2, uselist=False, backref="children")


class A4(Base):
    __tablename__ = "A4"

    pk = sa.Column(sa.Integer, primary_key=True, doc="primary key4")
    parent_id = sa.Column(sa.Integer, sa.ForeignKey(A3.pk), nullable=False)
    parent = orm.relationship(A3, uselist=False, backref="children")


class A5(Base):
    __tablename__ = "A5"

    pk = sa.Column(sa.Integer, primary_key=True, doc="primary key5")
    parent_id = sa.Column(sa.Integer, sa.ForeignKey(A4.pk), nullable=False)
    parent = orm.relationship(A4, uselist=False, backref="children")


def test_properties__default_depth_is__traverse_all_chlidren() -> None:
    target = _makeOne(StructuralWalker)
    result = target(A0)

    assert is_ok(result)
    assert "required" in result.value
    assert list(result.value["properties"]) == unordered(["children", "pk"])
    children0 = get_reference(result.value["properties"]["children"]["items"], result.value)
    children1 = get_reference(children0["properties"]["children"]["items"], result.value)
    children2 = get_reference(children1["properties"]["children"]["items"], result.value)
    children3 = get_reference(children2["properties"]["children"]["items"], result.value)
    children4 = get_reference(children3["properties"]["children"]["items"], result.value)
    assert children4["properties"]["pk"]["description"] == "primary key5"


def test_properties__default_depth_is__2__traverse_depth2() -> None:
    target = _makeOne(StructuralWalker)
    result = target(A0, depth=2)

    assert is_ok(result)
    assert "required" in result.value
    assert list(result.value["properties"]) == unordered(["children", "pk"])
    children0 = get_reference(result.value["properties"]["children"]["items"], result.value)
    assert children0["properties"]["pk"]["description"] == "primary key1"


def test_properties__default_depth_is__3__traverse_depth3() -> None:
    target = _makeOne(StructuralWalker)
    result = target(A0, depth=3)

    assert is_ok(result)
    assert "required" in result.value
    assert list(result.value["properties"]) == unordered(["children", "pk"])
    children0 = get_reference(result.value["properties"]["children"]["items"], result.value)
    children1 = get_reference(children0["properties"]["children"]["items"], result.value)
    assert children1["properties"]["pk"]["description"] == "primary key2"


# regression
# X.y -> Y.z -> Z.y -> Y.z -> Z.y


class Y(Base):
    __tablename__ = "y"
    id = sa.Column(sa.Integer, primary_key=True, doc="primary key")
    z_id = sa.Column(sa.Integer, sa.ForeignKey("z.id"))
    zs: Mapped[X] = orm.relationship("Z", foreign_keys=[z_id])


class X(Base):
    __tablename__ = "x"
    id = sa.Column(sa.Integer, primary_key=True, doc="primary key")
    y_id = sa.Column(sa.Integer, sa.ForeignKey("y.id"))
    ys: Mapped[Y] = orm.relationship(Y, foreign_keys=[y_id])


class Z(Base):
    __tablename__ = "z"
    id = sa.Column(sa.Integer, primary_key=True, doc="primary key")
    y_id = sa.Column(sa.Integer, sa.ForeignKey("y.id"))
    ys: Mapped[Y] = orm.relationship(Y, foreign_keys=[y_id])


def test_properties__infinite_loop() -> None:
    target = _makeOne(StructuralWalker, relation_decision=RelationDecision())
    result = target(X)

    assert is_ok(result)

    ys = result.value["properties"]["ys"]
    zs = get_reference(ys, result.value)["properties"]["zs"]
    xs = get_reference(zs, result.value)["properties"]
    assert "required" in result.value
    assert list(result.value["properties"]) == unordered(["id", "ys"])
    assert xs["id"]["description"] == "primary key"


def test_properties__infinite_loop2() -> None:
    target = _makeOne(StructuralWalker, relation_decision=UseForeignKeyIfPossibleDecision())
    result = target(X)

    assert is_ok(result)
    assert "required" in result.value
    assert list(result.value["properties"]) == unordered(["id", "y_id"])
    assert result.value["properties"]["y_id"] == {"type": "integer", "relation": "ys"}
