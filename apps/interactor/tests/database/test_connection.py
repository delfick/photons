# coding: spec

from interactor.database.connection import Base

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
async def database(db_runner, ThingModel):
    async with db_runner() as runner:
        yield runner.database


describe "DatabaseConnection":
    describe "actions":
        it "can create and query the database and delete from the database", database, ThingModel:
            database.add(ThingModel(one="one", two=True))
            database.add(ThingModel(one="two", two=False))
            database.commit()

            made = database.query(ThingModel).order_by(ThingModel.one.asc()).all()
            assert [t.as_dict() for t in made] == [
                ThingModel(one="one", two=True).as_dict(),
                ThingModel(one="two", two=False).as_dict(),
            ]

            database.delete(made[0])
            database.commit()

            made = database.query(ThingModel).order_by(ThingModel.one.asc()).all()
            assert [t.as_dict() for t in made] == [ThingModel(one="two", two=False).as_dict()]

        it "can refresh items", database, ThingModel:
            one = ThingModel(one="one", two=True)
            database.add(one)
            database.commit()

            made = database.query(ThingModel).one()
            made.two = False
            database.add(made)
            database.commit()

            database.refresh(one)
            assert one.two is False

        it "can rollback", database, ThingModel:
            one = ThingModel(one="one", two="wat")
            database.add(one)
            try:
                database.commit()
            except sqlalchemy.exc.StatementError:
                database.rollback()

            one = ThingModel(one="one", two=True)
            database.add(one)
            database.commit()

            made = database.query(ThingModel).one()
            assert made.as_dict() == one.as_dict()

        it "can execute against the database", database, ThingModel:
            one = ThingModel(one="one", two=True)
            database.add(one)
            database.commit()

            result = list(
                database.execute("SELECT * FROM thingmodel WHERE one=:one", {"one": "one"})
            )
            assert result == [(1, "one", 1)]

    describe "queries":
        it "has methods for doing stuff with the database", database, ThingModel:
            one = database.queries.create_thing_model(one="one", two=True)
            database.add(one)
            database.commit()

            two, made = database.queries.get_or_create_thing_model(one="one", two=True)
            assert made is False
            assert one.id == two.id

            three, made = database.queries.get_or_create_thing_model(one="two", two=True)
            assert made is True
            database.add(three)
            database.commit()

            made = database.queries.get_thing_models().order_by(ThingModel.one.asc()).all()
            assert [t.as_dict() for t in made] == [t.as_dict() for t in (one, three)]

            one_got = database.queries.get_thing_model(one="one")
            assert one_got.as_dict() == one.as_dict()
            assert one_got.id == one.id

            with assertRaises(sqlalchemy.orm.exc.MultipleResultsFound):
                database.queries.get_one_thing_model(two=True)
