from interactor.database import DB, Base

from photons_app import helpers as hp

import sqlalchemy
import tempfile
import logging
import pytest
import os

log = logging.getLogger("interactor.database")


class DBRunner(hp.AsyncCMMixin):
    def __init__(self, Base=Base):
        self.Base = Base
        self.final_future = hp.create_future(name="DBRunner.final_future")

    async def start(self):
        self.tmpfile = tempfile.NamedTemporaryFile(delete=False)
        self.filename = self.tmpfile.name

        uri = f"sqlite:///{self.filename}"
        self.database = DB(uri, self.Base)
        await self.database.start()

        async with self.database.engine.begin() as conn:
            try:
                await conn.run_sync(self.Base.metadata.drop_all)
            except sqlalchemy.exc.OperationalError as error:
                log.exception(error)

            await conn.run_sync(self.Base.metadata.create_all)

        return self

    async def finish(self, exc_typ=None, exc=None, tb=None):
        if hasattr(self, "final_future"):
            self.final_future.cancel()

        if hasattr(self, "tmpfile") and self.tmpfile is not None:
            self.tmpfile.close()

        if hasattr(self, "filename") and self.filename and os.path.exists(self.filename):
            os.remove(self.filename)

        if hasattr(self, "database"):
            await self.database.finish()


@pytest.fixture(scope="session")
def db_runner():
    return DBRunner
