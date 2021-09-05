# coding: spec

from interactor.database.database import migrate, Database
from sqlalchemy import create_engine

from photons_app.formatter import MergedOptionStringFormatter
from photons_app import helpers as hp

from sqlalchemy import inspect

describe "DatabaseMigration":
    async it "can create a database":
        with hp.a_temp_file() as fle:
            uri = f"sqlite:///{fle.name}"
            options = Database.FieldSpec(formatter=MergedOptionStringFormatter).empty_normalise(
                uri=uri
            )
            await migrate(options, "upgrade head")

            inspector = inspect(create_engine(options.uri))

            tables = sorted(list(inspector.get_table_names()))
            assert tables == ["alembic_version", "scene", "sceneinfo"]
