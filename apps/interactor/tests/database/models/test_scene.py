import uuid

import pytest
from delfick_project.norms import Meta
from interactor.database.models.scene import Scene


@pytest.fixture()
async def runner(db_runner):
    async with db_runner() as runner:
        yield runner


class TestScene:
    class TestDelayedSpec:
        def test_it_returns_a_function_that_can_be_provided_the_uuid(self):
            identifier = str(uuid.uuid1())

            kwargs = dict(
                matcher={"label": "den"},
                power=True,
                color="red",
                zones=[[0, 0, 0, 3500], [1, 1, 1, 3500]],
                chain=None,
                duration=1,
            )

            scene = Scene.DelayedSpec(storing=False).normalise(Meta.empty(), kwargs)
            normalised = scene(identifier)

            expect = dict(kwargs)
            expect["uuid"] = identifier

            assert normalised.as_dict() == expect

            scene_for_storing = Scene.DelayedSpec(storing=True).normalise(Meta.empty(), kwargs)
            normalised = scene_for_storing(identifier)

            expect = dict(
                uuid=identifier,
                matcher='{"label": "den"}',
                power=True,
                color="red",
                zones="[[0.0, 0.0, 0.0, 3500], [1.0, 1.0, 1.0, 3500]]",
                chain=None,
                duration=1,
            )

            assert normalised.as_dict() == expect

    class TestInteractionWithDatabase:
        async def test_it_can_store_and_retrieve_from_a_spec(self, runner):
            identifier = str(uuid.uuid1())

            chain = []
            for i in range(5):
                tile = []
                for j in range(64):
                    tile.append([j, 0, 1, 3500])
                chain.append(tile)

            kwargs = dict(
                uuid=identifier,
                matcher={"label": "den"},
                power=True,
                color="red",
                zones=[[0, 0, 0, 3500], [1, 1, 1, 3500]],
                chain=chain,
                duration=1,
            )

            async with runner.database.session() as (session, query):
                scene = Scene.Spec(storing=True).empty_normalise(**kwargs)
                session.add(await query.create_scene(**scene))
                await session.commit()

                got = await query.get_one_scene(uuid=identifier)
                assert got.as_dict() == kwargs

                obj = got.as_object()
                for prop in kwargs.keys():
                    assert getattr(obj, prop) == kwargs[prop]
