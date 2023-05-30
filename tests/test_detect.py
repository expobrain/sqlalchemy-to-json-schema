from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy_to_json_schema import ForeignKeyWalker, SchemaFactory

Base = declarative_base()


def _getTarget():
    return SchemaFactory


def _makeOne(*args, **kwargs):
    return _getTarget()(*args, **kwargs)


def test_detect__nullable_is_True__not_required():
    class Model0(Base):
        __tablename__ = "Model0"
        pk = sa.Column(sa.Integer, primary_key=True, doc="primary key")
        created_at = sa.Column(sa.DateTime, nullable=True)

    target = _makeOne(ForeignKeyWalker)
    walker = target.walker(Model0)
    result = target._detect_required(walker)
    assert result == ["pk"]


def test_detect__nullable_is_False__required():
    class Model1(Base):
        __tablename__ = "Model1"
        pk = sa.Column(sa.Integer, primary_key=True, doc="primary key")
        created_at = sa.Column(sa.DateTime, nullable=False)

    target = _makeOne(ForeignKeyWalker)
    walker = target.walker(Model1)
    result = target._detect_required(walker)
    assert result == ["pk", "created_at"]


def test_detect__nullable_is_False__but_default_is_exists__not_required():
    class Model2(Base):
        __tablename__ = "Model2"
        pk = sa.Column(sa.Integer, primary_key=True, doc="primary key")
        created_at = sa.Column(sa.DateTime, nullable=False, default=datetime.now)

    target = _makeOne(ForeignKeyWalker)
    walker = target.walker(Model2)
    result = target._detect_required(walker)
    assert result == ["pk"]


def test_detect__nullable_is_False__but_server_default_is_exists__not_required():
    class Model3(Base):
        __tablename__ = "Model3"
        pk = sa.Column(sa.Integer, primary_key=True, doc="primary key")
        created_at = sa.Column(sa.DateTime, nullable=False, server_default="NOW()")

    target = _makeOne(ForeignKeyWalker)
    walker = target.walker(Model3)
    result = target._detect_required(walker)
    assert result == ["pk"]


def test_detect__adjust_required():
    class Model4(Base):
        __tablename__ = "Model4"
        pk = sa.Column(sa.Integer, primary_key=True, doc="primary key")

    target = _makeOne(ForeignKeyWalker)
    walker = target.walker(Model4)

    # default required
    result = target._detect_required(walker)
    assert result == ["pk"]

    # use adjust_required
    result = target._detect_required(
        walker,
        adjust_required=lambda prop, default: False if prop.key == "pk" else default,
    )
    assert result == []