
import uuid

import pytest
import sqlalchemy.exc
from delfick_project.errors_pytest import assertRaises
from interactor.database.models.scene_info import SceneInfo


@pytest.fixture()
async def runner(db_runner):
    async with db_runner() as runner:
        yield runner


class TestSceneInfo:
    def test_it_can_return_itself_as_a_dict(self):
        info = SceneInfo(uuid="one", label=None, description=None)
        assert info.as_dict() == {"uuid": "one"}

        info = SceneInfo(uuid="two", label="kitchen", description=None)
        assert info.as_dict() == {"uuid": "two", "label": "kitchen"}

        info = SceneInfo(uuid="three", label="bathroom", description="blah")
        assert info.as_dict() == {"uuid": "three", "label": "bathroom", "description": "blah"}

    class TestInteractionWithDatabase:
        async def test_it_Must_have_unique_uuid(self, runner):
            identifier = str(uuid.uuid1())

            kwargs = dict(uuid=identifier, label="blah", description="described")

            async with runner.database.session() as (session, query):
                info = await query.create_scene_info(**kwargs)
                session.add(info)
                await session.commit()

                info2 = await query.create_scene_info(**kwargs)
                session.add(info2)
                try:
                    with assertRaises(sqlalchemy.exc.IntegrityError):
                        await session.commit()
                finally:
                    await session.rollback()

                info3 = await query.create_scene_info(uuid=identifier)
                session.add(info3)
                try:
                    with assertRaises(sqlalchemy.exc.IntegrityError):
                        await session.commit()
                finally:
                    await session.rollback()
