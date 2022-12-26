from delfick_project.norms import dictobj
from photons_canvas.animations import Animation, Finish, an_animation


class Options(dictobj.Spec):
    pass


@an_animation("skip", Options)
class Animation(Animation):
    """
    This animation does literally nothing. Run it for fun.
    """

    def process_event(self, event):
        raise Finish("Skip")
