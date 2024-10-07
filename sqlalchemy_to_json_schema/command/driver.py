import inspect
import json
import sys
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Optional, Union, cast

import yaml
from result import Err, Ok, Result
from sqlalchemy.ext.declarative import DeclarativeMeta

from sqlalchemy_to_json_schema.command.transformer import (
    AbstractTransformer,
    AsyncAPI2Transformer,
    JSONSchemaTransformer,
    OpenAPI2Transformer,
    OpenAPI3Transformer,
)
from sqlalchemy_to_json_schema.decisions import (
    AbstractDecision,
    RelationDecision,
    UseForeignKeyIfPossibleDecision,
)
from sqlalchemy_to_json_schema.schema_factory import Schema, SchemaFactory
from sqlalchemy_to_json_schema.types import Decision, Format, Layout, Walker
from sqlalchemy_to_json_schema.utils.imports import load_module_or_symbol
from sqlalchemy_to_json_schema.walkers import (
    AbstractWalker,
    ForeignKeyWalker,
    NoForeignKeyWalker,
    StructuralWalker,
)

TRANSFORMER_MAP: Mapping[Layout, type[AbstractTransformer]] = {
    Layout.SWAGGER_2: OpenAPI2Transformer,
    Layout.OPENAPI_2: OpenAPI2Transformer,
    Layout.OPENAPI_3: OpenAPI3Transformer,
    Layout.JSON_SCHEMA: JSONSchemaTransformer,
    Layout.ASYNCAPI_2: AsyncAPI2Transformer,
}

WALKER_MAP: Mapping[Walker, type[AbstractWalker]] = {
    Walker.STRUCTURAL: StructuralWalker,
    Walker.NOFOREIGNKEY: NoForeignKeyWalker,
    Walker.FOREIGNKEY: ForeignKeyWalker,
}

DECISION_MAP: Mapping[Decision, type[AbstractDecision]] = {
    Decision.DEFAULT: RelationDecision,
    Decision.USE_FOREIGN_KEY: UseForeignKeyIfPossibleDecision,
}


class Driver:
    def __init__(self, walker: Walker, decision: Decision, layout: Layout, /):
        self.transformer = self.build_transformer(walker, decision, layout)

    def build_transformer(
        self, walker: Walker, decision: Decision, layout: Layout, /
    ) -> Callable[
        [Iterable[Union[ModuleType, DeclarativeMeta]], Optional[int]], Result[Schema, str]
    ]:
        walker_factory = WALKER_MAP[walker]
        relation_decision = DECISION_MAP[decision]()
        schema_factory = SchemaFactory(walker_factory, relation_decision=relation_decision)
        transformer_factory = TRANSFORMER_MAP[layout]

        return transformer_factory(schema_factory).transform

    def run(
        self,
        targets: Sequence[str],
        /,
        *,
        filename: Optional[Path] = None,
        format: Optional[Format] = None,
        depth: Optional[int] = None,
    ) -> Result[None, str]:
        modules_and_types = (load_module_or_symbol(target) for target in targets)
        modules_and_models = cast(
            Iterator[Union[ModuleType, DeclarativeMeta]],
            (
                item
                for item in modules_and_types
                if inspect.ismodule(item) or isinstance(item, DeclarativeMeta)
            ),
        )

        schema = self.transformer(modules_and_models, depth)

        if schema.is_err():
            return Err(schema.unwrap_err())

        self.dump(schema.unwrap(), filename=filename, format=format)

        return Ok(None)

    def dump(
        self,
        data: dict[str, Any],
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
