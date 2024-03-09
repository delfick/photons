import logging
import os
import shlex
import sys
from urllib.parse import urlparse

import sqlalchemy
from delfick_project.norms import dictobj, sb
from interactor.database.base import Base
from interactor.database.query import Query
from photons_app import helpers as hp
from photons_app.errors import PhotonsAppError
from sqlalchemy import create_engine, pool
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

log = logging.getLogger("interactor.database.database")


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


class DB(hp.AsyncCMMixin):
    """
    A wrapper for database logic.

    Usage is as follows:

        async def some_action(session, query):
            await session.execute(...)
        await db.request(some_action)

    The `request` method takes in a function that takes in a database sesssion object and
    a filled Query object.

    The function you provide will be retried on operation errors otherwise, appropriate
    rollbacks will be called, exceptions raised and logged.
    """

    def __init__(self, database, Base=Base):
        self.Base = Base
        self.database = database
        if "postgresql" in self.database:
            self.database = urlparse(self.database)._replace(scheme="postgresql+asyncpg").geturl()
        if "sqlite" in self.database:
            self.database = urlparse(self.database)._replace(scheme="sqlite+aiosqlite").geturl()
        self.database = self.database.replace(":", "://", 1)

    async def start(self):
        __import__("interactor.database.models")
        self.engine = create_async_engine(self.database)
        self.async_session = sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def finish(self, exc_typ=None, exc=None, tb=None):
        if hasattr(self, "engine"):
            await self.engine.dispose()

    @hp.asynccontextmanager
    async def session(self):
        async with self.async_session() as session:
            yield session, Query(session, self.Base)

    async def request(self, func):
        tries = 0
        while True:
            tries += 1
            async with self.session() as (session, query):
                async with self.catch_errors(session, tries):
                    return await func(session, query)

    @hp.asynccontextmanager
    async def catch_errors(self, session, tries):
        try:
            yield
            await session.commit()

        except sqlalchemy.exc.OperationalError as error:
            await session.rollback()
            log.error(
                hp.lc("Failed to use database, will rollback and maybe try again", error=error)
            )

            if tries > 1:
                raise

        except sqlalchemy.exc.InvalidRequestError as error:
            await session.rollback()
            log.error(hp.lc("Failed to perform database operation", error=error))
            raise

        except PhotonsAppError as error:
            await session.rollback()
            log.error(hp.lc("Failed to use database", error=error))
            raise

        except:
            await session.rollback()
            exc_info = sys.exc_info()
            log.exception(hp.lc("Unexpected failure when using database", error=exc_info[1]))
            raise


async def migrate(database, extra=""):
    from alembic.config import CommandLine as AlembicCommandLine
    from alembic.config import Config as AlembicConfig
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
                connectable = create_engine(database.uri, poolclass=pool.NullPool)

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
