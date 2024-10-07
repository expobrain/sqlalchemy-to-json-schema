from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any, Union

from result import Err, Ok, Result
from sqlalchemy.orm import MapperProperty
from sqlalchemy.orm.base import MANYTOMANY, MANYTOONE
from sqlalchemy.orm.properties import ColumnProperty
from sqlalchemy.orm.relationships import RelationshipProperty

from sqlalchemy_to_json_schema.types import ColumnPropertyType
from sqlalchemy_to_json_schema.walkers import AbstractWalker

DecisionResult = tuple[
    ColumnPropertyType, Union[ColumnProperty, RelationshipProperty, MapperProperty], dict[str, Any]
]


class AbstractDecision(ABC):
    @abstractmethod
    def decision(
        self,
        walker: AbstractWalker,
        prop: MapperProperty,
        /,
        *,
        toplevel: bool = False,
    ) -> Iterator[Result[DecisionResult, MapperProperty]]:
        pass


class RelationDecision(AbstractDecision):
    def decision(
        self,
        walker: AbstractWalker,
        prop: MapperProperty,
        /,
        *,
        toplevel: bool = False,
    ) -> Iterator[Result[DecisionResult, MapperProperty]]:
        if hasattr(prop, "mapper"):
            yield Ok((ColumnPropertyType.RELATIONSHIP, prop, {}))
        elif hasattr(prop, "columns"):
            yield Ok((ColumnPropertyType.FOREIGNKEY, prop, {}))
        else:
            yield Err(prop)


class UseForeignKeyIfPossibleDecision(AbstractDecision):
    def decision(
        self,
        walker: AbstractWalker,
        prop: MapperProperty,
        /,
        *,
        toplevel: bool = False,
    ) -> Iterator[Result[DecisionResult, MapperProperty]]:
        if hasattr(prop, "mapper"):
            if prop.direction == MANYTOONE:
                if toplevel:
                    for c in prop.local_columns:
                        yield Ok(
                            (
                                ColumnPropertyType.FOREIGNKEY,
                                walker.mapper._props[c.name],
                                {"relation": prop.key},
                            )
                        )
                else:
                    rp = walker.history[0]
                    if prop.local_columns != rp.remote_side:
                        for c in prop.local_columns:
                            yield Ok(
                                (
                                    ColumnPropertyType.FOREIGNKEY,
                                    walker.mapper._props[c.name],
                                    {"relation": prop.key},
                                )
                            )
            elif prop.direction == MANYTOMANY:
                # logger.warning("skip mapper=%s, prop=%s is many to many.", walker.mapper, prop)
                # fixme: this must return a ColumnPropertyType member
                yield Ok(
                    (  # type: ignore[arg-type]
                        {"type": "array", "items": {"type": "string"}},
                        prop,
                        {},
                    )
                )
            else:
                yield Ok((ColumnPropertyType.RELATIONSHIP, prop, {}))
        elif hasattr(prop, "columns"):
            yield Ok((ColumnPropertyType.FOREIGNKEY, prop, {}))
        else:
            yield Err(prop)
