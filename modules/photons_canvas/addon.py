from photons_canvas.animations import register, AnimationRunner, print_help
from photons_canvas.theme import ApplyTheme

from photons_app.errors import PhotonsAppError
from photons_app.actions import an_action

from delfick_project.option_merge import MergedOptions
from delfick_project.addons import addon_hook
from delfick_project.norms import sb
import logging

log = logging.getLogger("photons_canvas.addons")


__shortdesc__ = "Represent colors on devices on a plane"


@addon_hook(extras=[("lifx.photons", "control")])
def __lifx__(collector, *args, **kwargs):
    return
    __import__("photons_canvas.animations.addon")


@an_action(needs_target=True, special_reference=True)
async def apply_theme(collector, target, reference, artifact, **kwargs):
    """
    Apply a theme to specified device

    ``lan:apply_theme d073d5000001 -- `{"colors": [<color>, <color>, ...], "overrides": {<hsbk dictionary>}}'``

    If you don't specify serials, then the theme will apply to all devices found
    on the network.

    Colors may be words like "red", "blue", etc. Or may be [h, s, b, k] arrays
    where each part is optional.

    You may also specify ``duration`` which is how long to take to apply in
    seconds.

    And you may also supply ``overrides`` with ``hue``, ``saturation``,
    ``brightness`` and ``kelvin`` to override the specified colors.
    """

    def errors(e):
        log.error(e)

    msg = ApplyTheme.msg(collector.photons_app.extra_as_json)
    await target.send(msg, reference, error_catcher=errors, message_timeout=2)


@an_action(needs_target=True)
async def animate(collector, target, reference, artifact, **kwargs):
    if reference == "help":
        if artifact in register.animations:
            print_help(
                animation_kls=register.animations[artifact].Animation, animation_name=artifact
            )
        else:
            print_help()
        return

    if reference in register.available_animations():
        ref = artifact
        artifact = reference
        reference = ref

    extra = collector.photons_app.extra_as_json
    reference = collector.reference_object(reference)

    options = {}
    specific_animation = artifact not in (None, "", sb.NotSpecified)

    if specific_animation:
        options = extra
        run_options = extra.pop("run_options", {})
    else:
        run_options = extra
        if isinstance(run_options, list):
            run_options = {"animations": run_options}

    if specific_animation:
        background = sb.NotSpecified
        layered = {"animations": [[artifact, background, options]], "animation_limit": 1}
        run_options = MergedOptions.using(layered, run_options).as_dict()

    def errors(e):
        if isinstance(e, KeyboardInterrupt):
            return

        if not isinstance(e, PhotonsAppError):
            log.exception(e)
        else:
            log.error(e)

    conf = collector.configuration
    photons_app = conf["photons_app"]

    with photons_app.using_graceful_future() as final_future:
        async with target.session() as sender:
            runner = AnimationRunner(
                sender,
                reference,
                run_options,
                final_future=final_future,
                error_catcher=errors,
                animation_options=conf.get("animation_options", {}),
            )
            async with runner:
                await runner.run()
