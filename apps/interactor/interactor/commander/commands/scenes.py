from interactor.commander.command import DeviceChangeMixin
from interactor.database.database import Scene, SceneInfo
from interactor.commander.errors import NoSuchScene
from interactor.commander import helpers as ihp
from interactor.commander.store import store

from photons_app import helpers as hp

from photons_control.transform import Transformer
from photons_control.script import FromGenerator
from photons_transport import catch_errors

from delfick_project.norms import dictobj, sb
from collections import defaultdict
from itertools import chain
import asyncio
import uuid


@store.command(name="scene_info")
class SceneInfoCommand(store.Command):
    """
    Retrieve information about scenes in the database
    """

    db_queue = store.injected("db_queue")

    uuid = dictobj.NullableField(
        sb.listof(sb.string_spec()), help="Only get information for scene with these uuid"
    )

    only_meta = dictobj.Field(
        sb.boolean, default=False, help="Only return meta info about the scenes"
    )

    async def execute(self):
        def get(db):
            info = defaultdict(lambda: {"meta": {}, "scene": []})

            fs = []
            ifs = []
            if self.uuid:
                fs.append(Scene.uuid.in_(self.uuid))
                ifs.append(SceneInfo.uuid.in_(self.uuid))

            for sinfo in db.query(SceneInfo).filter(*ifs):
                info[sinfo.uuid]["meta"] = sinfo.as_dict()

            for scene in db.query(Scene).filter(*fs):
                # Make sure there is an entry if no SceneInfo for this scene
                info[scene.uuid]

                if not self.only_meta:
                    dct = scene.as_dict()
                    info[scene.uuid]["scene"].append(dct)

            if self.only_meta:
                for _, data in info.items():
                    del data["scene"]

            return dict(info)

        return await self.db_queue.request(get)


@store.command(name="scene_change")
class SceneChangeCommand(store.Command):
    """
    Set all the options for a scene
    """

    db_queue = store.injected("db_queue")

    uuid = dictobj.NullableField(
        sb.string_spec, help="The uuid of the scene to change, if None we create a new scene"
    )

    label = dictobj.NullableField(sb.string_spec, help="The label to give this scene")

    description = dictobj.NullableField(sb.string_spec, help="The description to give this scene")

    scene = dictobj.NullableField(
        sb.listof(Scene.DelayedSpec(storing=True)), help="The options for the scene"
    )

    async def execute(self):
        def make(db):
            scene_uuid = self.uuid or str(uuid.uuid4())

            if self.scene is not None:
                for thing in db.queries.get_scenes(uuid=scene_uuid).all():
                    db.delete(thing)

                for part in self.scene:
                    made = db.queries.create_scene(**part(scene_uuid).as_dict())
                    db.add(made)

            info, _ = db.queries.get_or_create_scene_info(uuid=scene_uuid)
            if self.label is not None:
                info.label = self.label
            if self.description is not None:
                info.description = self.description
            db.add(info)

            return scene_uuid

        return await self.db_queue.request(make)


@store.command(name="scene_delete")
class SceneDeleteCommand(store.Command):
    """
    Delete a scene
    """

    db_queue = store.injected("db_queue")

    uuid = dictobj.Field(
        sb.string_spec, wrapper=sb.required, help="The uuid of the scene to delete"
    )

    async def execute(self):
        def delete(db):
            for thing in db.queries.get_scenes(uuid=self.uuid).all():
                db.delete(thing)
            for thing in db.queries.get_scene_infos(uuid=self.uuid).all():
                db.delete(thing)

            return {"deleted": True, "uuid": self.uuid}

        return await self.db_queue.request(delete)


@store.command(name="scene_apply")
class SceneApplyCommand(store.Command, DeviceChangeMixin):
    """
    Apply a scene
    """

    db_queue = store.injected("db_queue")
    request_future = store.injected("request_future")

    uuid = dictobj.Field(sb.string_spec, wrapper=sb.required, help="The uuid of the scene to apply")

    overrides = dictobj.Field(sb.dictionary_spec, help="Overrides to the scene")

    def cap_filter(self, matcher, cap):
        fltr = self.make_filter(matcher)
        if fltr.cap is sb.NotSpecified:
            fltr.cap = []
        fltr.cap.append(cap)
        return fltr

    async def execute(self):
        result = ihp.ResultBuilder()
        self.sender.gatherer.clear_cache()

        def get(db):
            info = []
            for scene in db.queries.get_scenes(uuid=self.uuid).all():
                info.append(scene.as_object())
            if not info:
                raise NoSuchScene(uuid=self.uuid)
            return info

        with catch_errors(result.error):
            msgs = []

            async with hp.TaskHolder(self.request_future, name="SceneApplyCommand") as ts:
                for scene in await self.db_queue.request(get):
                    if scene.zones:
                        fltr = self.cap_filter(scene.matcher, "multizone")
                        ts.add(self.apply_zones(fltr, scene, result, msgs))

                        fltr = self.cap_filter(scene.matcher, "not_multizone")
                        ts.add(self.transform(fltr, scene, result, msgs))

                    elif scene.chain:
                        fltr = self.cap_filter(scene.matcher, "chain")
                        ts.add(self.apply_chain(fltr, scene, result, msgs))

                        fltr = self.cap_filter(scene.matcher, "not_chain")
                        ts.add(self.transform(fltr, scene, result, msgs))

                    else:
                        ts.add(self.transform(self.make_filter(scene.matcher), scene, result, msgs))

            def make_gen(msg_and_serials):
                async def gen(reference, sender, **kwargs):
                    yield msg_and_serials[0]

                return FromGenerator(gen, reference_override=msg_and_serials[1])

            if msgs:
                serials = list(set(chain.from_iterable([ss for _, ss in msgs])))
                await self.send(
                    list(map(make_gen, msgs)), serials=serials, add_replies=False, result=result
                )

        return result

    async def _serials(self, fltr):
        serials = []
        async for device in self.finder.find(fltr):
            serials.append(device.serial)
        return serials

    async def transform(self, fltr, scene, result, msgs):
        options = scene.transform_options
        options.update(self.overrides)

        msg = Transformer.using(options)
        serials = await self._serials(fltr)
        msgs.append((msg, serials))

    async def apply_zones(self, fltr, scene, result, msgs):
        msg = list(scene.zone_msgs(self.overrides))
        serials = await self._serials(fltr)
        msgs.append((msg, serials))

    async def apply_chain(self, fltr, scene, result, msgs):
        msg = list(scene.chain_msgs(self.overrides))
        serials = await self._serials(fltr)
        msgs.append((msg, serials))


@store.command(name="scene_capture")
class SceneCaptureCommand(store.Command, DeviceChangeMixin):
    """
    Capture a scene
    """

    path = store.injected("path")
    db_queue = store.injected("db_queue")
    executor = store.injected("executor")

    uuid = dictobj.NullableField(
        sb.string_spec, help="The uuid of the scene to change, if None we create a new scene"
    )

    label = dictobj.NullableField(sb.string_spec, help="The label to give this scene")

    description = dictobj.NullableField(sb.string_spec, help="The description to give this scene")

    just_return = dictobj.Field(
        sb.boolean,
        default=False,
        help="Just return the scene rather than storing it in the database",
    )

    async def execute(self):
        plans = self.sender.make_plans("power", "parts_and_colors")
        serials = await self.serials

        scene = []

        result = ihp.ResultBuilder()
        async for serial, complete, info in self.sender.gatherer.gather_per_serial(
            plans, serials, error_catcher=result.error, message_timeout=self.timeout
        ):
            if not complete:
                continue

            parts = info["parts_and_colors"]
            device = parts[0].device

            state = {"power": info["power"]["on"], "matcher": {"serial": device.serial}}

            if device.cap.has_multizone:
                part = parts[0]
                state["zones"] = [list(color) for i, color in zip(range(part.width), part.colors)]
            elif device.cap.has_chain:
                chain = []
                for part in parts:
                    chain.append([list(color) for color in part.colors])
                state["chain"] = chain
            else:
                color = parts[0].colors[0]
                state[
                    "color"
                ] = f"kelvin:{color[3]} saturation:{color[1]} brightness:{color[2]} hue:{color[0]}"

            scene.append(state)

        result.result["results"] = {"scene": scene}

        if self.just_return:
            return result.as_dict()

        args = {
            "uuid": self.uuid,
            "label": self.label,
            "description": self.description,
        }

        result.result["results"]["meta"] = dict(args)
        args["scene"] = scene

        try:
            uuid = await self.executor.execute(self.path, {"command": "scene_change", "args": args})
        except asyncio.CancelledError:
            raise
        except Exception as error:
            result.error(error)
        else:
            result.result["results"]["meta"]["uuid"] = uuid

        return result.as_dict()
