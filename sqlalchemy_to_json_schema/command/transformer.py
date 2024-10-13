import inspect
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from types import ModuleType
from typing import Optional, Union

from loguru import logger
from result import Err, Ok, Result
from sqlalchemy.ext.declarative import DeclarativeMeta
from typing_extensions import TypeGuard

from sqlalchemy_to_json_schema.schema_factory import Schema, SchemaFactory


class AbstractTransformer(ABC):
    def __init__(self, schema_factory: SchemaFactory, /):
        self.schema_factory = schema_factory

    @abstractmethod
    def transform(
        self, rawtargets: Iterable[Union[ModuleType, DeclarativeMeta]], depth: Optional[int], /
    ) -> Result[Schema, str]: ...


class JSONSchemaTransformer(AbstractTransformer):
    def transform(
        self, rawtargets: Iterable[Union[ModuleType, DeclarativeMeta]], depth: Optional[int], /
    ) -> Result[Schema, str]:
        definitions = {}

        for item in rawtargets:
            if inspect.isclass(item) and isinstance(item, DeclarativeMeta):
                partial_definitions = self.transform_by_model(item, depth)
            elif inspect.ismodule(item):
                partial_definitions = self.transform_by_module(item, depth)
            else:
                return Err(f"Expected a class or module, got {item}")

            if partial_definitions.is_err():
                return partial_definitions

            definitions.update(partial_definitions.unwrap())

        return Ok(definitions)

    def transform_by_model(
        self, model: DeclarativeMeta, depth: Optional[int], /
    ) -> Result[Schema, str]:
        return self.schema_factory(model, depth=depth)

    def transform_by_module(
        self, module: ModuleType, depth: Optional[int], /
    ) -> Result[Schema, str]:
        subdefinitions = {}
        definitions = {}
        for basemodel in collect_models(module):
            schema_result = self.schema_factory(basemodel, depth=depth)

            if schema_result.is_err():
                return schema_result

            schema = schema_result.unwrap()

            if "definitions" in schema:
                subdefinitions.update(schema.pop("definitions"))
            definitions[schema["title"]] = schema
        d = {}
        d.update(subdefinitions)
        d.update(definitions)
        return Ok({"definitions": definitions})


class OpenAPI2Transformer(AbstractTransformer):
    def transform(
        self, rawtargets: Iterable[Union[ModuleType, DeclarativeMeta]], depth: Optional[int], /
    ) -> Result[Schema, str]:
        definitions = {}

        for target in rawtargets:
            if inspect.isclass(target) and isinstance(target, DeclarativeMeta):
                partial_definitions = self.transform_by_model(target, depth)
            elif inspect.ismodule(target):
                partial_definitions = self.transform_by_module(target, depth)
            else:
                return Err(f"Expected a class or module, got {target}")

            if partial_definitions.is_err():
                return partial_definitions

            definitions.update(partial_definitions.unwrap())

        return Ok({"definitions": definitions})

    def transform_by_model(
        self, model: DeclarativeMeta, depth: Optional[int], /
    ) -> Result[Schema, str]:
        definitions = {}
        schema_result = self.schema_factory(model, depth=depth)

        if schema_result.is_err():
            return schema_result

        schema = schema_result.unwrap()

        if "definitions" in schema:
            definitions.update(schema.pop("definitions"))

        definitions[schema["title"]] = schema

        return Ok(definitions)

    def transform_by_module(
        self, module: ModuleType, depth: Optional[int], /
    ) -> Result[Schema, str]:
        subdefinitions = {}
        definitions = {}

        for basemodel in collect_models(module):
            schema_result = self.schema_factory(basemodel, depth=depth)

            if schema_result.is_err():
                return schema_result

            schema = schema_result.unwrap()

            if "definitions" in schema:
                subdefinitions.update(schema.pop("definitions"))

            definitions[schema["title"]] = schema

        d = {}
        d.update(subdefinitions)
        d.update(definitions)

        return Ok(definitions)


class OpenAPI3Transformer(OpenAPI2Transformer):
    def replace_ref(self, d: Union[dict, list], old_prefix: str, new_prefix: str, /) -> None:
        if isinstance(d, dict):
            for k, v in d.items():
                if k == "$ref":
                    d[k] = v.replace(old_prefix, new_prefix)
                else:
                    self.replace_ref(v, old_prefix, new_prefix)
        elif isinstance(d, list):
            for item in d:
                self.replace_ref(item, old_prefix, new_prefix)

    def transform(
        self, rawtargets: Iterable[Union[ModuleType, DeclarativeMeta]], depth: Optional[int], /
    ) -> Result[Schema, str]:
        definitions_result = super().transform(rawtargets, depth)

        if definitions_result.is_err():
            return Err(definitions_result.unwrap_err())

        definitions = definitions_result.unwrap()

        self.replace_ref(definitions, "#/definitions/", "#/components/schemas/")

        if "components" not in definitions:
            definitions["components"] = {}
        if "schemas" not in definitions["components"]:
            definitions["components"]["schemas"] = {}
        definitions["components"]["schemas"] = definitions.pop("definitions", {})

        return Ok(definitions)


def collect_models(module: ModuleType, /) -> Iterator[DeclarativeMeta]:
    def is_alchemy_model(maybe_model: type, /) -> TypeGuard[DeclarativeMeta]:
        if not inspect.isclass(maybe_model):
            return False

        if not (hasattr(maybe_model, "__table__") or hasattr(maybe_model, "__tablename__")):
            return False

        logger.debug("{maybe_model} is a SQLAlchemy model", maybe_model=maybe_model)

        return True

    items: Iterable[type]

    if hasattr(module, "__all__"):
        logger.debug("Module {module} has an __all__ attribute", module=module)

        items = (getattr(module, name) for name in module.__all__)
    else:
        items = module.__dict__.values()

    models = (item for item in items if is_alchemy_model(item))

    return models


class AsyncAPI2Transformer(OpenAPI3Transformer):
    pass
