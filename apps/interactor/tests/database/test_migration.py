
from interactor.database.database import Database, migrate
from photons_app import helpers as hp
from photons_app.formatter import MergedOptionStringFormatter
from sqlalchemy import create_engine, inspect

class TestDatabaseMigration:
    async def test_it_can_create_a_database(self):
        with hp.a_temp_file() as fle:
            uri = f"sqlite:///{fle.name}"
            options = Database.FieldSpec(formatter=MergedOptionStringFormatter).empty_normalise(
                uri=uri
            )
            await migrate(options, "upgrade head")

            inspector = inspect(create_engine(options.uri))

            tables = sorted(list(inspector.get_table_names()))
            assert tables == ["alembic_version", "scene", "sceneinfo"]
