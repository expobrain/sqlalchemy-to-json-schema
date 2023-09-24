from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.automap import AutomapBase, automap_base

from sqlalchemy_to_json_schema.schema_factory import SchemaFactory
from sqlalchemy_to_json_schema.walkers import StructuralWalker

# using sqlalchemy's automap


@pytest.fixture(scope="module")
def db() -> AutomapBase:
    dbname = Path(__file__).parent.resolve() / "reflection.db"
    engine = create_engine(f"sqlite:///{dbname}", future=True)
    Base = automap_base()
    Base.prepare(autoload_with=engine)
    return Base  # type: ignore[no-any-return]


def _makeOne() -> SchemaFactory:
    return SchemaFactory(StructuralWalker)


def test_it(db: AutomapBase) -> None:
    target = _makeOne()
    schema = target(db.classes.artist)  # type: ignore[arg-type]
    expected = {
        "title": "artist",
        "properties": {
            "artistid": {"type": "integer"},
            "artistname": {"type": "string"},
            "track_collection": {"items": {"$ref": "#/definitions/track"}, "type": "array"},
        },
        "definitions": {
            "track": {
                "properties": {"trackid": {"type": "integer"}, "trackname": {"type": "string"}},
                "required": ["trackid"],
                "type": "object",
            }
        },
        "type": "object",
        "required": ["artistid", "artistname"],
    }
    assert schema == expected


def test_it2(db: AutomapBase) -> None:
    target = _makeOne()
    schema = target(db.classes.track)  # type: ignore[arg-type]
    expected = {
        "title": "track",
        "properties": {
            "trackid": {"type": "integer"},
            "trackname": {"type": "string"},
            "artist": {"$ref": "#/definitions/artist"},
        },
        "definitions": {
            "artist": {
                "properties": {"artistid": {"type": "integer"}, "artistname": {"type": "string"}},
                "required": ["artistid", "artistname"],
                "type": "object",
            }
        },
        "type": "object",
        "required": ["trackid"],
    }
    assert schema == expected
