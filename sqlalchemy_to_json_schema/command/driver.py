import inspect
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    Optional,
    Sequence,
    Type,
    Union,
    cast,
)

import yaml
from sqlalchemy.ext.declarative import DeclarativeMeta

from sqlalchemy_to_json_schema import Schema, SchemaFactory
from sqlalchemy_to_json_schema.command.transformer import (
    AbstractTransformer,
    JSONSchemaTransformer,
    OpenAPI2Transformer,
    OpenAPI3Transformer,
)
from sqlalchemy_to_json_schema.decisions import (
    AbstractDecision,
    RelationDecision,
    UseForeignKeyIfPossibleDecision,
)
from sqlalchemy_to_json_schema.types import Decision, Format, Layout, Walker
from sqlalchemy_to_json_schema.utils.imports import load_module_or_symbol
from sqlalchemy_to_json_schema.walkers import (
    AbstractWalker,
    ForeignKeyWalker,
    NoForeignKeyWalker,
    StructuralWalker,
)


def detect_walker_factory(walker: Walker, /) -> Type[AbstractWalker]:
    if walker == Walker.STRUCTURAL:
        return StructuralWalker
    elif walker == Walker.NOFOREIGNKEY:
        return NoForeignKeyWalker
    elif walker == Walker.FOREIGNKEY:
        return ForeignKeyWalker

    raise ValueError(walker)


def detect_decision(decision: Decision, /) -> AbstractDecision:
    if decision == Decision.DEFAULT:
        return RelationDecision()
    elif decision == Decision.USE_FOREIGN_KEY:
        return UseForeignKeyIfPossibleDecision()

    raise ValueError(decision)


def detect_transformer(layout: Layout, /) -> Type[AbstractTransformer]:
    if layout in [Layout.SWAGGER_2, Layout.OPENAPI_2]:
        return OpenAPI2Transformer
    elif layout == Layout.OPENAPI_3:
        return OpenAPI3Transformer
    elif layout == Layout.JSON_SCHEMA:
        return JSONSchemaTransformer

    raise ValueError(layout)


class Driver:
    def __init__(self, walker: Walker, decision: Decision, layout: Layout, /):
        self.transformer = self.build_transformer(walker, decision, layout)

    def build_transformer(
        self, walker: Walker, decision: Decision, layout: Layout, /
    ) -> Callable[[Iterable[Union[ModuleType, DeclarativeMeta]], Optional[int]], Schema]:
        walker_factory = detect_walker_factory(walker)
        relation_decision = detect_decision(decision)
        schema_factory = SchemaFactory(walker_factory, relation_decision=relation_decision)
        transformer_factory = detect_transformer(layout)
        return transformer_factory(schema_factory).transform

    def run(
        self,
        targets: Sequence[str],
        /,
        *,
        filename: Optional[Path] = None,
        format: Optional[Format] = None,
        depth: Optional[int] = None,
    ) -> None:
        modules_and_types = (load_module_or_symbol(target) for target in targets)
        modules_and_models = cast(
            Iterator[Union[ModuleType, DeclarativeMeta]],
            (
                item
                for item in modules_and_types
                if inspect.ismodule(item) or isinstance(item, DeclarativeMeta)
            ),
        )

        result = self.transformer(modules_and_models, depth)
        self.dump(result, filename=filename, format=format)

    def dump(
        self,
        data: Dict[str, Any],
        /,
        *,
        filename: Optional[Path] = None,
        format: Optional[Format] = None,
    ) -> None:
        dump_function = yaml.dump if format == Format.YAML else json.dump

        if filename is None:
            output_stream = sys.stdout
        else:
            output_stream = filename.open("w")

        dump_function(data, output_stream)  # type: ignore[operator]
