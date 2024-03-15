import asyncio
import uuid
from collections import defaultdict
from itertools import chain
from typing import Annotated, ClassVar, Self

import attrs
import sanic
import strcs
from delfick_project.norms import Meta as norms_Meta
from delfick_project.norms import sb
from interactor.commander import helpers as ihp
from interactor.commander import selector
from interactor.commander.devices import DeviceFinder
from interactor.commander.errors import NoSuchScene
from interactor.commander.store import Command, reg, store
from interactor.database import DB
from interactor.database.models import Scene, SceneInfo
from photons_app import helpers as hp
from photons_app import special
from photons_control.device_finder import Filter, Finder
from photons_control.script import FromGenerator
from photons_control.transform import Transformer
from photons_transport import catch_errors
from photons_transport.comms.base import Communication
from photons_web_server import commander


@attrs.define(slots=False, kw_only=True)
class TimeoutBody:
    timeout: selector.Timeout = attrs.field(default=20)


@attrs.define(slots=False, kw_only=True)
class CommandAndTimeoutBody(TimeoutBody):
    command: str


@attrs.define(slots=False, kw_only=True)
class TimeoutParams:
    timeout: int = -1

    def update_with_put_body(self, body: TimeoutBody) -> Self:
        if self.timeout == -1:
            return attrs.evolve(self, timeout=body.timeout.value)
        else:
            return self


@attrs.define(slots=False, kw_only=True)
class SceneInfoBody:
    database: Annotated[DB, strcs.FromMeta("database")]

    uuid: list[str] = attrs.field(factory=list)
    """Only get information for scene with these uuids"""

    only_meta: bool = False
    """Only return meta info about the scenes"""

    class Docs:
        uuid: str = """Only get information for scene with these uuids"""

        only_meta: str = """Only return meta info about the scenes"""


@attrs.define(slots=False, kw_only=True)
class SceneChangeBody:
    database: Annotated[DB, strcs.FromMeta("database")]

    label: str | None = None
    """The label to give this scene"""

    description: str | None = None
    """The description to give this scene"""

    scene: list[dict[str, object]] = attrs.field(factory=list)
    """The options for the scene"""

    uuid: str
    """The uuid of the scene to change, if None we create a new scene"""

    def normalised_scene(self) -> list[Scene]:
        return sb.listof(Scene.DelayedSpec(storing=True)).normalise(norms_Meta.empty(), self.scene)

    class Docs:
        label: str = """The label to give this scene"""

        description: str = """The description to give this scene"""

        scene: str = """The options for the scene"""

        uuid: str = """The uuid of the scene to change, if None we create a new scene"""


@attrs.define(slots=False, kw_only=True)
class SceneDeleteBody:
    database: Annotated[DB, strcs.FromMeta("database")]

    uuid: selector.AllOrSomeScenes

    class Docs:
        uuid: str = """
        Which scenes to delete.

        If this is a string or a list of strings, then those strings are seen as the
        uuids of the scenes to delete.

        If this option is given as 'true' then all scenes are removed
        """


@attrs.define(slots=False, kw_only=True)
class SceneApplyBody(TimeoutBody):
    database: Annotated[DB, strcs.FromMeta("database")]
    finder: Annotated[Finder, strcs.FromMeta("finder")]

    uuid: str
    """The uuid of the scene to apply"""

    overrides: Annotated[
        dict[str, object], strcs.Ann(creator=selector.create_dict_without_none)
    ] = attrs.field(factory=dict)
    """Overrides to the scene"""

    def make_filter(self, matcher: dict | str | None) -> Filter:
        if matcher is None:
            return Filter.empty()

        elif type(matcher) is str:
            return Filter.from_key_value_str(matcher)

        else:
            return Filter.from_options(matcher)

    def cap_filter(self, matcher, cap):
        fltr = self.make_filter(matcher)
        if fltr.cap is sb.NotSpecified:
            fltr.cap = []
        fltr.cap.append(cap)
        return fltr

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


@attrs.define(slots=False, kw_only=True)
class SceneCaptureBody(TimeoutBody):
    database: Annotated[DB, strcs.FromMeta("database")]

    uuid: str | None = None
    """The uuid of the scene to change, if None we create a new scene"""

    label: str | None = None
    """The label to give this scene"""

    description: str | None = None
    """The description to give this scene"""

    just_return: bool = False
    """Just return the scene rather than storing it in the database"""


@attrs.define(slots=False, kw_only=True)
class V1SceneCaptureBody(SceneCaptureBody):
    matcher: selector.Matcher


@attrs.define(slots=False, kw_only=True)
class V2SceneCaptureBody(SceneCaptureBody):
    selector: selector.Selector


@store.command
class ScenesCommands(Command):
    @classmethod
    def add_routes(kls, routes: commander.RouteTransformer) -> None:
        routes.http(kls.scenes_put, "/v2/scenes", name="v2_scenes_put")

    async def scenes_info(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        _body: SceneInfoBody,
    ) -> commander.Response:
        """
        Retrieve information about scenes in the database
        """

        async def get(session, query):
            info = defaultdict(lambda: {"meta": {}, "scene": []})

            fs = []
            ifs = []
            if _body.uuid:
                fs.append(Scene.uuid.in_(_body.uuid))
                ifs.append(SceneInfo.uuid.in_(_body.uuid))

            for sinfo in await query.all(SceneInfo, *ifs):
                info[sinfo.uuid]["meta"] = sinfo.as_dict()

            for scene in await query.all(Scene, *fs, change=lambda q: q.order_by(Scene.matcher)):
                # Make sure there is an entry if no SceneInfo for this scene
                info[scene.uuid]

                if not _body.only_meta:
                    dct = dict(scene.as_dict())
                    if "uuid" in dct:
                        del dct["uuid"]
                    info[scene.uuid]["scene"].append(dct)

            if _body.only_meta:
                for _, data in info.items():
                    del data["scene"]

            return dict(info)

        return sanic.json(await _body.database.request(get))

    async def scenes_change(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        _body: SceneChangeBody,
    ) -> commander.Response:
        """
        Set all the options for a scene
        """

        async def make(session, query):
            scene_uuid = _body.uuid or str(uuid.uuid4())

            if _body.scene is not None:
                for thing in await query.get_scenes(uuid=scene_uuid):
                    await session.delete(thing)

                for part in _body.normalised_scene():
                    made = await query.create_scene(**part(scene_uuid).as_dict())
                    session.add(made)

            info, _ = await query.get_or_create_scene_info(uuid=scene_uuid)
            if _body.label is not None:
                info.label = _body.label
            if _body.description is not None:
                info.description = _body.description
            session.add(info)

            return scene_uuid

        return sanic.text(await _body.database.request(make))

    async def scenes_delete(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        _body: SceneDeleteBody,
    ) -> commander.Response:

        removed = []

        async def delete(session, query):
            if _body.uuid.all_scenes:
                for thing in await query.get_scenes():
                    removed.append(thing.uuid)
                    await session.delete(thing)
                (await query.get_scene_infos()).delete()
            else:
                for uu in _body.uuid.uuid:
                    removed.append(uu)
                    for thing in await query.get_scenes(uuid=uu):
                        await session.delete(thing)
                    for thing in await query.get_scene_infos(uuid=uu):
                        await session.delete(thing)

            return {"deleted": True, "uuid": list(set(removed))}

        return sanic.json(await _body.database.request(delete))

    async def scenes_apply(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        _body: SceneApplyBody,
        _params: TimeoutParams,
        request_future: asyncio.Future,
        sender: Communication,
    ) -> commander.Response:
        """
        Apply a scene
        """
        _params = _params.update_with_put_body(_body)

        result = ihp.ResultBuilder()
        sender.gatherer.clear_cache()

        async def get(session, query):
            info = []
            for scene in await query.get_scenes(uuid=_body.uuid):
                info.append(scene.as_object())
            if not info:
                raise NoSuchScene(uuid=_body.uuid)
            return info

        with catch_errors(result.error):
            msgs = []

            async with hp.TaskHolder(request_future, name="SceneApplyCommand") as ts:
                for scene in await _body.database.request(get):
                    if scene.zones:
                        fltr = _body.cap_filter(scene.matcher, "multizone")
                        ts.add(_body.apply_zones(fltr, scene, result, msgs))

                        fltr = _body.cap_filter(scene.matcher, "not_multizone")
                        ts.add(_body.transform(fltr, scene, result, msgs))

                    elif scene.chain:
                        fltr = _body.cap_filter(scene.matcher, "matrix")
                        ts.add(_body.apply_chain(fltr, scene, result, msgs))

                        fltr = _body.cap_filter(scene.matcher, "not_matrix")
                        ts.add(_body.transform(fltr, scene, result, msgs))

                    else:
                        ts.add(
                            _body.transform(_body.make_filter(scene.matcher), scene, result, msgs)
                        )

            def make_gen(msg_and_serials):
                async def gen(reference, sender, **kwargs):
                    yield msg_and_serials[0]

                return FromGenerator(gen, reference_override=msg_and_serials[1])

            if msgs:
                serials = list(set(chain.from_iterable([ss for _, ss in msgs])))
                devices = self.create(
                    DeviceFinder,
                    {"selector": special.HardCodedSerials(serials), "timeout": _params.timeout},
                )
                await devices.send(
                    list(map(make_gen, msgs)), serials=serials, add_replies=False, result=result
                )

        return sanic.json(result.as_dict())

    async def scenes_capture(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        _body: V2SceneCaptureBody,
        _params: TimeoutParams,
    ) -> commander.Response:
        """
        Capture a scene
        """
        _params = _params.update_with_put_body(_body)
        devices = self.create(
            DeviceFinder, {"selector": _body.selector, "timeout": _params.timeout}
        )
        plans = devices.sender.make_plans("power", "parts_and_colors")
        serials = await devices.serials

        scene = []

        result = ihp.ResultBuilder()
        async for serial, complete, info in devices.sender.gatherer.gather_per_serial(
            plans, serials, error_catcher=result.error, message_timeout=_params.timeout
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
                state["color"] = (
                    f"kelvin:{color[3]} saturation:{color[1]} brightness:{color[2]} hue:{color[0]}"
                )

            scene.append(state)

        result.result["results"] = {"scene": sorted(scene, key=lambda s: s["matcher"]["serial"])}

        if _body.just_return:
            return result.as_dict()

        try:
            result = await self.scenes_change(
                progress,
                request,
                _body=SceneChangeBody(
                    database=_body.database,
                    uuid=_body.uuid,
                    scene=scene,
                    label=_body.label,
                    description=_body.description,
                ),
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            result.error(error)
            return result.as_dict()
        else:
            identifier = result.body.decode()

        info = (
            await self.scenes_info(
                progress, request, _body=SceneInfoBody(database=_body.database, uuid=[identifier])
            )
        ).raw_body

        if identifier in info:
            return sanic.json(info[identifier])
        else:
            return sanic.json(info)

    known_routes = {
        "scene_info": scenes_info,
        "scene_change": scenes_change,
        "scene_delete": scenes_delete,
        "scene_apply": scenes_apply,
        "scene_capture": scenes_capture,
    }

    async def scenes_put(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        _body: CommandAndTimeoutBody,
        _params: TimeoutParams,
    ) -> commander.Response:
        route = self.known_routes.get(command := _body.command)

        if route is None:
            raise sanic.BadRequest(
                message=f"Unknown command '{command}', available: {sorted(self.known_routes)}"
            )

        _params = _params.update_with_put_body(_body)
        return await getattr(self, route.__name__)(
            progress, request, _body.selector, _params=_params
        )

    implements_v1_commands: ClassVar[set[str]] = {
        "scene_info",
        "scene_change",
        "scene_delete",
        "scene_apply",
        "scene_capture",
    }

    @classmethod
    def help_for_v1_command(cls, command: str, type_cache: strcs.TypeCache) -> str | None:
        if command not in cls.implements_v1_commands:
            return None

        doc = cls.known_routes[command].__doc__
        if command == "scene_info":
            body_kls = SceneInfoBody
        elif command == "scene_change":
            body_kls = SceneChangeBody
        elif command == "scene_delete":
            body_kls = SceneDeleteBody
        elif command == "scene_apply":
            body_kls = SceneApplyBody
        elif command == "scene_capture":
            body_kls = V1SceneCaptureBody
        else:
            return doc

        return ihp.v1_help_text_from_body(
            doc=doc,
            body_typ=strcs.Type.create(body_kls, cache=type_cache),
        )

    async def run_v1_http(
        self,
        progress: commander.Progress,
        request: commander.Request,
        *,
        command: str,
        args: dict[str, object],
        meta: strcs.Meta,
    ) -> commander.Response | None:
        if command in self.implements_v1_commands:
            if command == "scene_info":
                body = self.create(SceneInfoBody, args)
                return await self.scenes_info(progress, request, _body=body)
            elif command == "scene_change":
                body = self.create(SceneChangeBody, args)
                return await self.scenes_change(progress, request, _body=body)
            elif command == "scene_delete":
                body = self.create(SceneDeleteBody, args)
                return await self.scenes_delete(progress, request, _body=body)
            elif command == "scene_apply":
                body = self.create(SceneApplyBody, args)
                return await self.scenes_apply(
                    progress,
                    request,
                    _body=body,
                    _params=TimeoutParams(),
                    request_future=meta.retrieve_one(
                        asyncio.Future, "request_future", type_cache=reg.type_cache
                    ),
                    sender=meta.retrieve_one(Communication, "sender", type_cache=reg.type_cache),
                )
            elif command == "scene_capture":
                v1body = self.create(V1SceneCaptureBody, args)
                match = self.create(selector.Selector, v1body.matcher.raw)
                body = self.create(
                    V2SceneCaptureBody,
                    {
                        **{f.name: getattr(v1body, f.name) for f in attrs.fields(v1body.__class__)},
                        "timeout": v1body.timeout,
                        "selector": match,
                    },
                )
                return await self.scenes_capture(
                    progress, request, _body=body, _params=TimeoutParams()
                )
