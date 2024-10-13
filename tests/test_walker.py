import pytest
import sqlalchemy as sa
import sqlalchemy.orm as orm
from pytest_unordered import unordered
from result import Err, is_ok
from sqlalchemy.orm import declarative_base

from sqlalchemy_to_json_schema.exceptions import InvalidStatus
from sqlalchemy_to_json_schema.schema_factory import SchemaFactory, pop_marker
from sqlalchemy_to_json_schema.walkers import ForeignKeyWalker


def _makeOne() -> SchemaFactory:
    return SchemaFactory(ForeignKeyWalker)


Base = declarative_base()


class Group(Base):
    """model for test"""

    __tablename__ = "Group"

    pk = sa.Column(sa.Integer, primary_key=True, doc="primary key")
    name = sa.Column(sa.String(255), default="", nullable=False)
    color = sa.Column(sa.Enum("red", "green", "yellow", "blue"))


class User(Base):
    __tablename__ = "User"

    pk = sa.Column(sa.Integer, primary_key=True, doc="primary key")
    name = sa.Column(sa.String(255), default="", nullable=True)
    group_id = sa.Column(sa.Integer, sa.ForeignKey(Group.pk), nullable=False)
    group = orm.relationship(Group, uselist=False, backref="users")


def test_type__is_object() -> None:
    target = _makeOne()
    result = target(Group)

    assert is_ok(result)
    assert "type" in result.unwrap()
    assert result.unwrap()["type"] == "object"


def test_properties__are__all_of_columns() -> None:
    target = _makeOne()
    result = target(Group)

    assert is_ok(result)
    assert "properties" in result.unwrap()
    assert list(result.unwrap()["properties"].keys()) == unordered(["color", "name", "pk"])


def test_title__id__model_class_name() -> None:
    target = _makeOne()
    result = target(Group)

    assert is_ok(result)
    assert "title" in result.unwrap()
    assert result.unwrap()["title"] == Group.__name__


def test_description__is__docstring_of_model() -> None:
    target = _makeOne()
    result = target(Group)

    assert is_ok(result)
    assert "description" in result.unwrap()
    assert result.unwrap()["description"] == Group.__doc__


def test_properties__all__this_is_slackoff_little_bit__all_is_all() -> None:  # hmm.
    target = _makeOne()
    result = target(Group)

    assert is_ok(result)
    assert result.unwrap()["properties"] == {
        "color": {
            "maxLength": 6,
            "enum": ["red", "green", "yellow", "blue"],
            "type": "string",
        },
        "name": {"maxLength": 255, "type": "string"},
        "pk": {"description": "primary key", "type": "integer"},
    }


# adaptive


def test__filtering_by__includes() -> None:
    target = _makeOne()
    result = target(Group, includes=["pk"])

    assert is_ok(result)
    assert list(result.unwrap()["properties"].keys()) == unordered(["pk"])


def test__filtering_by__excludes() -> None:
    target = _makeOne()
    result = target(Group, excludes=["pk"])

    assert is_ok(result)
    assert list(result.unwrap()["properties"].keys()) == unordered(["color", "name"])


def test__filtering_by__excludes_and_includes__conflict() -> None:
    target = _makeOne()
    with pytest.raises(InvalidStatus):
        target(Group, excludes=["pk"], includes=["pk"])


# overrides


@pytest.mark.skip("to be fixed")
def test__overrides__add() -> None:
    target = _makeOne()
    overrides = {"name": {"maxLength": 100}}
    result = target(Group, includes=["name"], overrides=overrides)

    assert is_ok(result)
    assert result.unwrap()["properties"] == {"name": {"maxLength": 100, "type": "string"}}


@pytest.mark.skip("to be fixed")
def test__overrides__pop() -> None:
    target = _makeOne()
    overrides = {"name": {"maxLength": pop_marker}}
    result = target(Group, includes=["name"], overrides=overrides)

    assert is_ok(result)
    assert result.unwrap()["properties"] == {"name": {"type": "string"}}


def test__overrides__wrong_column() -> None:
    target = _makeOne()
    overrides = {"*missing-field*": {"maxLength": 100}}

    actual = target(Group, includes=["name"], overrides=overrides)

    assert actual == Err(f"invalid overrides: {set(overrides.keys())}")
