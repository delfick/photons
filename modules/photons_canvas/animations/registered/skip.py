from photons_canvas.animations import Animation, Finish, an_animation

from delfick_project.norms import dictobj


class Options(dictobj.Spec):
    pass


@an_animation("skip", Options)
class Animation(Animation):
    def process_event(self, event):
        raise Finish("Skip")
