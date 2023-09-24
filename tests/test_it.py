# definition
import pytest
import sqlalchemy as sa
import sqlalchemy.orm as orm
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from sqlalchemy.orm import declarative_base

from sqlalchemy_to_json_schema.schema_factory import SchemaFactory
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


class AnotherUser(Base):
    __table__ = User.__table__


def test_it_create_schema__and__valid_params__sucess() -> None:
    target = _makeOne()
    schema = target(Group, excludes=["pk", "users.pk"])
    data = {
        "name": "ravenclaw",
        "color": "blue",
        "users": [{"name": "foo"}, {"name": "bar"}],
    }

    validate(data, schema)


def test_it_create_schema__and__invalid_params__failure() -> None:
    target = _makeOne()
    schema = target(Group, excludes=["pk", "uesrs.pk"])
    data = {
        "name": "blackmage",
        "color": "black",
        "users": [{"name": "foo"}, {"name": "bar"}],
    }

    with pytest.raises(ValidationError):
        validate(data, schema)


def test_it2_create_schema__and__valid_params__success() -> None:
    target = _makeOne()
    schema = target(User, excludes=["pk", "group_id"])
    data = {"name": "foo", "group": {"name": "ravenclaw", "color": "blue", "pk": 1}}
    validate(data, schema)


def test_create_schema__without_tablename() -> None:
    """can generate schema with model(without __tablename__)"""
    target = _makeOne()
    schema = target(AnotherUser)
    assert schema
