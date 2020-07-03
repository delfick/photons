# coding: spec

from interactor.database.connection import DatabaseConnection
from interactor.database.database import migrate, Database

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

            database = DatabaseConnection(database=options.uri)
            inspector = inspect(database.engine)

            tables = sorted(list(inspector.get_table_names()))
            assert tables == ["alembic_version", "scene", "sceneinfo"]
