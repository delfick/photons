from interactor.database.connection import Base, DatabaseConnection

from delfick_project.norms import dictobj, sb
from urllib.parse import urlparse
from sqlalchemy import pool
import shlex
import sys
import os


class database_uri_spec(sb.Spec):
    def normalise_empty(self, meta):
        config_root = os.getcwd()
        if "config_root" in meta.everything:
            config_root = meta.everything["config_root"]

        return self.normalise_filled(meta, os.path.join(config_root, "interactor.db"))

    def normalise_filled(self, meta, val):
        val = sb.string_spec().normalise(meta, val)

        val = urlparse(val).path
        while len(val) > 1 and val[:2] == "//":
            val = val[1:]

        directory = os.path.dirname(val)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        return f"sqlite:///{val}"


class Database(dictobj.Spec):
    uri = dictobj.Field(format_into=database_uri_spec(), help="Uri to our database")

    db_migrations = dictobj.Field(
        sb.overridden(os.path.join("{interactor:resource}", "database", "migrations")),
        format_into=sb.directory_spec,
    )


async def migrate(database, extra=""):
    from alembic.config import CommandLine as AlembicCommandLine, Config as AlembicConfig
    from alembic.script import ScriptDirectory

    class Script(ScriptDirectory):
        def run_env(script):
            from alembic import context as alembic_context

            target_metadata = Base.metadata

            def run_migrations_offline():
                alembic_context.configure(
                    url=database.uri, target_metadata=target_metadata, literal_binds=True
                )
                with alembic_context.begin_transaction():
                    alembic_context.run_migrations()

            def run_migrations_online():
                connectable = DatabaseConnection(
                    database=database.uri, poolclass=pool.NullPool
                ).engine
                with connectable.connect() as connection:
                    alembic_context.configure(
                        connection=connection, target_metadata=target_metadata
                    )
                    with alembic_context.begin_transaction():
                        alembic_context.run_migrations()

            if alembic_context.is_offline_mode():
                run_migrations_offline()
            else:
                run_migrations_online()

    def from_config(cfg):
        return Script(database.db_migrations)

    ScriptDirectory.from_config = from_config

    parts = []
    for p in sys.argv:
        if p == "--":
            break
        parts.append(p)

    commandline = AlembicCommandLine(prog=f"{' '.join(parts)} -- ")
    options = commandline.parser.parse_args(shlex.split(extra))
    if not hasattr(options, "cmd"):
        commandline.parser.error("too few arguments after the ' -- '")
    else:
        cfg = AlembicConfig(cmd_opts=options)
        commandline.run_cmd(cfg, options)


# And make all the models available so that the migrate command knows about them
from interactor.database.models.scene_info import SceneInfo  # noqa
from interactor.database.models.scene import Scene  # noqa

# And make vim quiet about unused imports
Scene = Scene
SceneInfo = SceneInfo
