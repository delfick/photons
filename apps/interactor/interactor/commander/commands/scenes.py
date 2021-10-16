from interactor.commander.command import DeviceChangeMixin
from interactor.database.models import Scene, SceneInfo
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


class dictionary_without_none_spec(sb.Spec):
    def normalise(self, meta, val):
        val = sb.dictionary_spec().normalise(meta, val)
        return self.filtered(val)

    def filtered(self, val):
        if isinstance(val, dict):
            return {k: self.filtered(v) for k, v in val.items() if v is not None}
        else:
            return val


@store.command(name="scene_info")
class SceneInfoCommand(store.Command):
    """
    Retrieve information about scenes in the database
    """

    database = store.injected("database")

    uuid = dictobj.NullableField(
        sb.listof(sb.string_spec()), help="Only get information for scene with these uuid"
    )

    only_meta = dictobj.Field(
        sb.boolean, default=False, help="Only return meta info about the scenes"
    )

    async def execute(self):
        async def get(session, query):
            info = defaultdict(lambda: {"meta": {}, "scene": []})

            fs = []
            ifs = []
            if self.uuid:
                fs.append(Scene.uuid.in_(self.uuid))
                ifs.append(SceneInfo.uuid.in_(self.uuid))

            for sinfo in await query.all(SceneInfo, *ifs):
                info[sinfo.uuid]["meta"] = sinfo.as_dict()

            for scene in await query.all(Scene, *fs, change=lambda q: q.order_by(Scene.matcher)):
                # Make sure there is an entry if no SceneInfo for this scene
                info[scene.uuid]

                if not self.only_meta:
                    dct = dict(scene.as_dict())
                    if "uuid" in dct:
                        del dct["uuid"]
                    info[scene.uuid]["scene"].append(dct)

            if self.only_meta:
                for _, data in info.items():
                    del data["scene"]

            return dict(info)

        return await self.database.request(get)


@store.command(name="scene_change")
class SceneChangeCommand(store.Command):
    """
    Set all the options for a scene
    """

    database = store.injected("database")

    uuid = dictobj.NullableField(
        sb.string_spec, help="The uuid of the scene to change, if None we create a new scene"
    )

    label = dictobj.NullableField(sb.string_spec, help="The label to give this scene")

    description = dictobj.NullableField(sb.string_spec, help="The description to give this scene")

    scene = dictobj.NullableField(
        sb.listof(Scene.DelayedSpec(storing=True)), help="The options for the scene"
    )

    async def execute(self):
        async def make(session, query):
            scene_uuid = self.uuid or str(uuid.uuid4())

            if self.scene is not None:
                for thing in await query.get_scenes(uuid=scene_uuid):
                    await session.delete(thing)

                for part in self.scene:
                    made = await query.create_scene(**part(scene_uuid).as_dict())
                    session.add(made)

            info, _ = await query.get_or_create_scene_info(uuid=scene_uuid)
            if self.label is not None:
                info.label = self.label
            if self.description is not None:
                info.description = self.description
            session.add(info)

            return scene_uuid

        return await self.database.request(make)


@store.command(name="scene_delete")
class SceneDeleteCommand(store.Command):
    """
    Delete a scene
    """

    database = store.injected("database")

    uuid = dictobj.Field(
        sb.or_spec(sb.boolean(), sb.listof(sb.string_spec())),
        wrapper=sb.required,
        help="""
        Which scenes to delete.

        If this is a string or a list of strings, then those strings are seen as the
        uuids of the scenes to delete.

        If this option is given as 'true' then all scenes are removed
        """,
    )

    async def execute(self):
        removed = []

        async def delete(session, query):
            if self.uuid is True:
                for thing in await query.get_scenes():
                    removed.append(thing.uuid)
                    await session.delete(thing)
                (await query.get_scene_infos()).delete()
            else:
                for uu in self.uuid:
                    removed.append(uu)
                    for thing in await query.get_scenes(uuid=uu):
                        await session.delete(thing)
                    for thing in await query.get_scene_infos(uuid=uu):
                        await session.delete(thing)

            return {"deleted": True, "uuid": list(set(removed))}

        return await self.database.request(delete)


@store.command(name="scene_apply")
class SceneApplyCommand(store.Command, DeviceChangeMixin):
    """
    Apply a scene
    """

    database = store.injected("database")
    request_future = store.injected("request_future")

    uuid = dictobj.Field(sb.string_spec, wrapper=sb.required, help="The uuid of the scene to apply")

    overrides = dictobj.Field(dictionary_without_none_spec, help="Overrides to the scene")

    def cap_filter(self, matcher, cap):
        fltr = self.make_filter(matcher)
        if fltr.cap is sb.NotSpecified:
            fltr.cap = []
        fltr.cap.append(cap)
        return fltr

    async def execute(self):
        result = ihp.ResultBuilder()
        self.sender.gatherer.clear_cache()

        async def get(session, query):
            info = []
            for scene in await query.get_scenes(uuid=self.uuid):
                info.append(scene.as_object())
            if not info:
                raise NoSuchScene(uuid=self.uuid)
            return info

        with catch_errors(result.error):
            msgs = []

            async with hp.TaskHolder(self.request_future, name="SceneApplyCommand") as ts:
                for scene in await self.database.request(get):
                    if scene.zones:
                        fltr = self.cap_filter(scene.matcher, "multizone")
                        ts.add(self.apply_zones(fltr, scene, result, msgs))

                        fltr = self.cap_filter(scene.matcher, "not_multizone")
                        ts.add(self.transform(fltr, scene, result, msgs))

                    elif scene.chain:
                        fltr = self.cap_filter(scene.matcher, "matrix")
                        ts.add(self.apply_chain(fltr, scene, result, msgs))

                        fltr = self.cap_filter(scene.matcher, "not_matrix")
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
            elif device.cap.has_matrix:
                chain = []
                for part in parts:
                    chain.append([list(color) for color in part.colors[: part.width * part.height]])
                state["chain"] = chain
            else:
                color = parts[0].colors[0]
                state[
                    "color"
                ] = f"kelvin:{color[3]} saturation:{color[1]} brightness:{color[2]} hue:{color[0]}"

            scene.append(state)

        result.result["results"] = {"scene": sorted(scene, key=lambda s: s["matcher"]["serial"])}

        if self.just_return:
            return result.as_dict()

        args = {
            "uuid": self.uuid,
            "scene": scene,
            "label": self.label,
            "description": self.description,
        }

        try:
            uuid = await self.executor.execute(self.path, {"command": "scene_change", "args": args})
        except asyncio.CancelledError:
            raise
        except Exception as error:
            result.error(error)
            return result.as_dict()

        info = await self.executor.execute(
            self.path, {"command": "scene_info", "args": {"uuid": uuid}}
        )

        if uuid in info:
            return info[uuid]
        else:
            return info
