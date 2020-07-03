# coding: spec

from interactor.database.connection import Base

from photons_app.errors import PhotonsAppError

from delfick_project.errors_pytest import assertRaises
from sqlalchemy import Column, String, Boolean
import sqlalchemy.exc
import pytest


@pytest.fixture(scope="module")
def ThingModel():
    class ThingModel(Base):
        one = Column(String(64), nullable=True, unique=True)
        two = Column(Boolean(), nullable=True)

        __repr_columns__ = ("one", "two")

        def as_dict(self):
            return {"one": self.one, "two": self.two}

    return ThingModel


@pytest.fixture(scope="module", autouse=True)
async def cleanup(ThingModel):
    try:
        yield
    finally:
        del Base._decl_class_registry["ThingModel"]
        tables = dict(Base.metadata.tables)
        del tables["thingmodel"]
        Base.metadata.tables = tables


@pytest.fixture()
async def runner(db_runner, ThingModel):
    async with db_runner(start_db_queue=True) as runner:
        yield runner


describe "DatabaseConnection":
    async it "can execute queries", runner:

        def do_set(db):
            one = db.queries.create_thing_model(one="one", two=True)
            db.add(one)

        await runner.db_queue.request(do_set)

        def do_get(db):
            return db.queries.get_one_thing_model().as_dict()

        got = await runner.db_queue.request(do_get)
        assert got == {"one": "one", "two": True}

    async it "retries on OperationalError", runner:
        tries = [True, True]

        def do_error(db):
            tries.pop(0)
            raise sqlalchemy.exc.OperationalError("select", {}, "")

        with assertRaises(sqlalchemy.exc.OperationalError):
            await runner.db_queue.request(do_error)

        assert tries == []

    async it "can work after the first OperationalError", runner:
        tries = [True, True]

        def do_error(db):
            tries.pop(0)
            if len(tries) == 1:
                raise sqlalchemy.exc.OperationalError("select", {}, "")
            else:
                one = db.queries.create_thing_model(one="one", two=True)
                db.add(one)

        await runner.db_queue.request(do_error)

        def do_get(db):
            return db.queries.get_one_thing_model().as_dict()

        got = await runner.db_queue.request(do_get)
        assert got == {"one": "one", "two": True}

        assert tries == []

    async it "does not retry other errors", runner:
        errors = [sqlalchemy.exc.InvalidRequestError(), PhotonsAppError("blah"), ValueError("nope")]

        for error in errors:
            tries = [True]

            def do_error(db):
                tries.pop(0)
                raise error

            with assertRaises(type(error)):
                await runner.db_queue.request(do_error)
            assert tries == []
