from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterator, Sequence

from loguru import logger
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Mapper
from sqlalchemy.orm.properties import ColumnProperty
from sqlalchemy.orm.relationships import RelationshipProperty

from sqlalchemy_to_json_schema.exceptions import InvalidStatus


class AbstractWalker(ABC):
    def __init__(
        self,
        model: DeclarativeMeta | Mapper,
        /,
        *,
        includes: Sequence[str] | None = None,
        excludes: Sequence[str] | None = None,
        history: Any | None = None,
    ) -> None:
        logger.debug("Walking model {model}, {type}", model=model, type=type(model))

        self.mapper = inspect(model).mapper
        self.includes = includes
        self.excludes = excludes
        self.history = history or []
        if includes and excludes:
            if set(includes).intersection(excludes):
                raise InvalidStatus(f"Conflict includes={includes}, exclude={excludes}")

    def clone(
        self,
        name: str,
        mapper: Mapper,
        /,
        *,
        includes: Sequence[str] | None = None,
        excludes: Sequence[str] | None = None,
        history: Any | None = None,
    ) -> AbstractWalker:
        return self.__class__(mapper, includes=includes, excludes=excludes, history=history)

    def from_child(self, model: Mapper) -> AbstractWalker:
        return self.__class__(model, history=self.history)

    @abstractmethod
    def walk(self) -> Iterator[ColumnProperty | RelationshipProperty]:
        pass


# mapper.column_attrs and mapper.attrs is not ordered. define our custom iterate function `iterate'


class ForeignKeyWalker(AbstractWalker):
    def iterate(self) -> Iterator[ColumnProperty]:
        for c in self.mapper.local_table.columns:
            if c.name not in self.mapper._props:
                for prop in self.mapper.iterate_properties:
                    if isinstance(prop, ColumnProperty):
                        columns = {column.name for column in prop.columns}

                        if c.name in columns:
                            yield prop  # danger!! not immutable
            else:
                yield self.mapper._props[c.name]  # danger!! not immutable

    def walk(self) -> Iterator[ColumnProperty | RelationshipProperty]:
        for prop in self.iterate():
            if self.includes is None or prop.key in self.includes:
                if self.excludes is None or prop.key not in self.excludes:
                    yield prop


class NoForeignKeyWalker(AbstractWalker):
    def iterate(self) -> Iterator[ColumnProperty]:
        for c in self.mapper.local_table.columns:
            if c.name not in self.mapper._props:
                for prop in self.mapper.iterate_properties:
                    if isinstance(prop, ColumnProperty):
                        columns = {column.name for column in prop.columns}

                        if c.name in columns:
                            yield prop  # danger!! not immutable
            else:
                yield self.mapper._props[c.name]  # danger!! not immutable

    def walk(self) -> Iterator[ColumnProperty | RelationshipProperty]:
        for prop in self.iterate():
            if self.includes is None or prop.key in self.includes:
                if self.excludes is None or prop.key not in self.excludes:
                    if not any(c.foreign_keys for c in getattr(prop, "columns", {})):
                        yield prop


class StructuralWalker(AbstractWalker):
    def iterate(self) -> Iterator[ColumnProperty]:
        for c in self.mapper.local_table.columns:
            if c.name not in self.mapper._props:
                for prop in self.mapper.iterate_properties:
                    if isinstance(prop, ColumnProperty):
                        columns = {column.name for column in prop.columns}

                        if c.name in columns:
                            yield prop  # danger!! not immutable
            else:
                yield self.mapper._props[c.name]  # danger!! not immutable
        for prop in self.mapper.relationships:
            yield prop

    def walk(self) -> Iterator[ColumnProperty | RelationshipProperty]:
        for prop in self.iterate():
            if isinstance(prop, (ColumnProperty, RelationshipProperty)):
                if self.includes is None or prop.key in self.includes:
                    if self.excludes is None or prop.key not in self.excludes:
                        if prop not in self.history:
                            if not any(c.foreign_keys for c in getattr(prop, "columns", {})):
                                yield prop
