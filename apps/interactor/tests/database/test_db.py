# coding: spec

import pytest
import sqlalchemy.exc
from delfick_project.errors_pytest import assertRaises
from photons_app.errors import PhotonsAppError
from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import declarative_base, declared_attr


class Base:
    # Metadata gets set by Sqlalchemy
    metadata = None

    # __repr_columns__ must be set by subclasses of Base
    __repr_columns__ = None

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    id = Column(Integer, primary_key=True)


Base = declarative_base(cls=Base)


class Thing(Base):
    one = Column(String(64), nullable=True, unique=True)
    two = Column(Boolean(), nullable=True)

    __repr_columns__ = ("one", "two")

    def as_dict(self):
        return {"one": self.one, "two": self.two}


@pytest.fixture()
async def runner(db_runner):
    async with db_runner(Base) as runner:
        yield runner


describe "DB":
    async it "can execute queries", runner:

        async def do_set(session, query):
            one = await query.create_thing(one="one", two=True)
            session.add(one)

        await runner.database.request(do_set)

        async def do_get(session, query):
            return (await query.get_one_thing()).as_dict()

        got = await runner.database.request(do_get)
        assert got == {"one": "one", "two": True}

    async it "retries on OperationalError", runner:
        tries = [True, True]

        async def do_error(session, query):
            tries.pop(0)
            raise sqlalchemy.exc.OperationalError("select", {}, "")

        with assertRaises(sqlalchemy.exc.OperationalError):
            await runner.database.request(do_error)

        assert tries == []

    async it "can work after the first OperationalError", runner:
        tries = [True, True]

        async def do_error(session, query):
            tries.pop(0)
            if len(tries) == 1:
                raise sqlalchemy.exc.OperationalError("select", {}, "")
            else:
                one = await query.create_thing(one="one", two=True)
                session.add(one)

        await runner.database.request(do_error)

        async def do_get(session, query):
            return (await query.get_one_thing()).as_dict()

        got = await runner.database.request(do_get)
        assert got == {"one": "one", "two": True}

        assert tries == []

    async it "does not retry other errors", runner:
        errors = [sqlalchemy.exc.InvalidRequestError(), PhotonsAppError("blah"), ValueError("nope")]

        for error in errors:
            tries = [True]

            async def do_error(session, query):
                tries.pop(0)
                raise error

            with assertRaises(type(error)):
                await runner.database.request(do_error)
            assert tries == []
