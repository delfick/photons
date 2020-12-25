from photons_app.errors import PhotonsAppError
from photons_app import helpers as hp

from delfick_project.norms import Meta, sb


class NoSuchAnimation(PhotonsAppError):
    desc = "Couldn't find specified animation"


animations = {}


def available_animations():
    return sorted(animations)


class Animator:
    def __init__(self, Animation, Options, *, name=None):
        if name is None:
            name = f"animation_{len(animations)+1}"
            animations[name] = self

        self.name = name
        self.Options = Options
        self.Animation = Animation

    def resolver(self, options=None, background=None):
        if options is None:
            options = {}

        background = (
            background if background in (True, False) else background in (sb.NotSpecified, None)
        )

        return self.Resolver(self, options, background)

    class Resolver:
        def __init__(self, animator, options, background):
            self.options = options
            self.animator = animator
            self.background = background

        def resolve(self):
            def make_animation(final_future, pauser=None):
                options = self.animator.Options.FieldSpec().normalise(Meta.empty(), self.options)
                animation = self.animator.Animation(final_future, options, pauser=pauser)
                if self.options is not sb.NotSpecified:
                    for attr in animation.overridable:
                        if attr in self.options:
                            setattr(animation, attr, self.options[attr])
                return animation

            # Make sure the options can be resolved
            fut = hp.create_future(name="Animator>Resolver::resolve[fut]")
            fut.cancel()
            make_animation(fut)

            return make_animation, self.background


class an_animation:
    def __init__(self, name, Options):
        self.name = name
        self.Options = Options

    def __call__(self, Animation):
        self.Animation = Animation
        Animation.__registered_name__ = self.name
        animations[self.name] = Animator(Animation, self.Options, name=self.name)
        return Animation


def resolve(name):
    if isinstance(name, tuple):
        return Animator(*name)

    if name not in animations:
        raise NoSuchAnimation(wanted=name, available=available_animations())

    return animations[name]
