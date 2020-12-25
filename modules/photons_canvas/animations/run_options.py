from photons_canvas.animations.infrastructure.register import resolve

from photons_app.formatter import MergedOptionStringFormatter

from delfick_project.norms import dictobj, sb, BadSpecValue, Meta
import asyncio
import random
import os


class Chooser:
    def __init__(self, algorithm, choices):
        self.choices = choices
        self.algorithm = algorithm

    def __iter__(self):
        return self

    def __next__(self):
        if self.algorithm == "random":
            return random.choice(self.choices)
        else:
            nxt = self.choices.pop(0)
            self.choices.append(nxt)
            return nxt

    def __bool__(self):
        return bool(self.choices)


class noisy_network_spec(sb.Spec):
    def normalise_empty(self, meta):
        env = os.environ.get("NOISY_NETWORK_LIMIT")
        if env:
            if env == "true":
                env = 2
            elif env == "null":
                env = 0
            return sb.integer_spec().normalise(meta, env)

        animation_options = sb.set_options(
            noisy_network_limit=sb.defaulted(sb.integer_spec(), 0)
        ).normalise(meta, meta.everything.get("animation_options") or {})

        if animation_options["noisy_network_limit"]:
            return animation_options["noisy_network_limit"]

        return 0

    def normalise_filled(self, meta, val):
        return sb.integer_spec().normalise(meta, val)


class animation_spec(sb.Spec):
    def normalise_filled(self, meta, val):
        if not val:
            raise BadSpecValue("Animation option must be non empty", meta=meta)

        if isinstance(val, str):
            val = [val]

        if isinstance(val, (list, tuple)) and hasattr(val[0], "resolve"):
            val = val[0]

        if hasattr(val, "resolve"):
            return val

        if isinstance(val, (list, tuple)):
            if len(val) == 1:
                val = [val[0], sb.NotSpecified, sb.NotSpecified]

            if len(val) == 2:
                val = [val[0], sb.NotSpecified, val[1]]

            val = {"name": val[0], "background": val[1], "options": val[2]}

        if not hasattr(val["name"], "resolver"):
            val["name"] = resolve(val["name"])

        return val["name"].resolver(val["options"], val["background"])


class TransitionOptions(dictobj.Spec):
    run_first = dictobj.Field(
        sb.boolean, default=True, help="Whether to run a transition before feature animations"
    )

    run_last = dictobj.Field(
        sb.boolean,
        default=True,
        help="Whether to run a transition after limit of feature animations",
    )

    run_between = dictobj.Field(
        sb.boolean, default=True, help="Whether to run a transitions between animations"
    )

    animations = dictobj.Field(
        sb.listof(animation_spec()),
        help="Same option as in the ``animations`` option of the root options",
    )


class semaphore_spec(sb.Spec):
    def normalise_empty(self, meta):
        return asyncio.Semaphore()

    def normalise_filled(self, meta, val):
        return val


class RunOptions(dictobj.Spec):
    pauser = dictobj.Field(
        semaphore_spec,
        help="A semaphore that when set will pause the animation",
    )

    combined = dictobj.Field(
        sb.boolean, default=True, help="Whether to join all found tiles into one animation"
    )

    reinstate_on_end = dictobj.Field(
        sb.boolean,
        default=False,
        help="Whether to return the tiles to how they were before the animation",
    )

    reinstate_duration = dictobj.Field(
        sb.float_spec, default=1, help="The duration used when reinstating state"
    )

    noisy_network = dictobj.Field(
        noisy_network_spec(),
        help="""
        If this value is non 0, then we assume the network is a noisy network
        and we'll make some effort to make sure the tiles can keep up.
        The number provided is the max number of messages per device that is
        "inflight" before we drop messages before sending them.

        if this value is 0 (default) then we just send all the messgaes.
    """,
    )

    rediscover_every = dictobj.Field(
        sb.integer_spec,
        default=20,
        help="""
        This value is the number of seconds it should take before we try and
        rediscover devices on the network to add to the animation.
    """,
    )

    animation_limit = dictobj.Field(
        sb.integer_spec(),
        default=0,
        help="""
        This is the number of animations to run before stop running new
        animations.

        It defaults to no limit
    """,
    )

    animation_chooser = dictobj.Field(
        sb.string_choice_spec(["random", "cycle"]),
        default="cycle",
        help="""
        This decides how we determine which feature animation to run next.

        If the option is random (default) then the next feature will be the
        next feature in the animations list. Otherwise if it's set to
        random, then the next one will be chosen at random.
    """,
    )

    transition_chooser = dictobj.Field(
        sb.string_choice_spec(["random", "cycle"]),
        default="cycle",
        help="""
        This decides how we determine which transition animation to use next.

        If the option is random (default) then the next transition will be the
        next transition in the animations list. Otherwise if it's set to
        random, then the next one will be chosen at random.
    """,
    )

    transitions = dictobj.Field(
        TransitionOptions.FieldSpec,
        help="""
        The options for transitions

        run_first
            Run a transition before the first feature animation

        run_last
            Run a transition after the last feature animation (unless animations
            are cancelled)

        run_between
            Run transitions between feature animations

        animations
            Same option as in the ``animations`` option of the root options.
    """,
    )

    animations = dictobj.Field(
        sb.listof(animation_spec()),
        help="""
        The different animations you wish to run.

        These are a list of (name, ), (name, options); or (name, background, options)

        ``name``
            This is the name of the registered animation.

            If it's a tuple of (Animation, Options) where those are the classes
            that represent the animation, then a new animation is created from
            those options.

        ``background``
            If this value is not not specified, or null or true, then the current
            colors on the tiles are used as the starting canvas for the animation.

            If this value is False, then the starting canvas for the animation will
            be empty.

        options
            A dictionary of options relevant to the animation.
    """,
    )

    @property
    def animations_iter(self, register=None):
        features = []
        transitions = []

        for a in self.animations:
            make_animation, background = a.resolve()
            features.append((make_animation, background))

        for t in self.transitions.animations:
            make_animation, background = a.resolve()
            transitions.append((make_animation, background))

        features = iter(Chooser(self.animation_chooser, features))
        transitions = iter(Chooser(self.transition_chooser, transitions))

        def itr():
            if not features and transitions:
                if self.transitions.run_first or self.transitions.run_last:
                    yield next(transitions)
                return

            if transitions and self.transitions.run_first:
                yield next(transitions)

            if features:
                count = 0
                while True:
                    if self.animation_limit and count >= self.animation_limit:
                        break
                    count += 1

                    animation = yield next(features)

                    if animation.skip_next_transition:
                        continue

                    if transitions and self.transitions.run_between:
                        yield next(transitions)

            if transitions and self.transitions.run_last:
                yield next(transitions)

        return itr


def make_run_options(val, animation_options):
    if isinstance(val, RunOptions):
        return val

    if isinstance(val, list):
        val = {"animations": val}

    elif not val or val is sb.NotSpecified:
        val = {
            "animations": [
                ["swipe", {"line_hues": ["0-10", "100-150"], "fade_amount": 0.2}],
                #
                ["falling", {"num_seconds": 10}],
                #
                ["balls", {"num_seconds": 10}],
                #
                ["twinkles", {"num_seconds": 5, "skip_next_transition": True}],
                #
                ["dots", {"skip_next_transition": True}],
                #
                ["dice", {"num_iterations": 1}],
                #
                ["color_cycle", {"changer": "vertical_morph", "num_seconds": 10}],
            ]
        }

    meta = Meta({"animation_options": animation_options}, [])
    return RunOptions.FieldSpec(formatter=MergedOptionStringFormatter).normalise(meta, val)
