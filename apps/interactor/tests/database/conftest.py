from interactor.database.connection import DatabaseConnection
from interactor.database.db_queue import DBQueue

from photons_app import helpers as hp

import tempfile
import pytest
import os


class DBRunner:
    def __init__(self, start_db_queue=False):
        self.final_future = hp.create_future(name="DBRunner.final_future")
        self.start_db_queue = start_db_queue

    async def __aenter__(self):
        self.tmpfile = tempfile.NamedTemporaryFile(delete=False)
        self.filename = self.tmpfile.name

        uri = f"sqlite:///{self.filename}"
        self.database = DatabaseConnection(database=uri).new_session()
        self.database.create_tables()

        if self.start_db_queue:
            self.db_queue = DBQueue(self.final_future, 5, lambda exc: 1, uri)
            self.db_queue.start()

        return self

    async def __aexit__(self, exc_typ, exc, tb):
        if hasattr(self, "final_future"):
            self.final_future.cancel()

        if hasattr(self, "tmpfile") and self.tmpfile is not None:
            self.tmpfile.close()

        if hasattr(self, "filename") and self.filename and os.path.exists(self.filename):
            os.remove(self.filename)

        if hasattr(self, "database"):
            self.database.close()

        if hasattr(self, "db_queue"):
            await self.db_queue.finish()


@pytest.fixture(scope="session")
def db_runner():
    return DBRunner
