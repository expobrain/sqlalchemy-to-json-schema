def _callFUT(*args, **kwargs):
    from sqlalchemy_to_json_schema.dictify import objectify

    return objectify(*args, **kwargs)


def test_no_required():
    from sqlalchemy_to_json_schema import SchemaFactory, StructuralWalker
    from sqlalchemy_to_json_schema.dictify import ModelLookup
    from tests.fixtures import models

    schema_factory = SchemaFactory(StructuralWalker)
    schema = schema_factory(models.MyModel, excludes=["id"])
    modellookup = ModelLookup(models)

    params = {"name": "foo", "value": 1}
    _callFUT(params, schema, modellookup)
