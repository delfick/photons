import os

from photons_canvas.animations import options
from photons_canvas.animations.action import AnimationTask, print_help
from photons_canvas.animations.infrastructure import register
from photons_canvas.animations.infrastructure.animation import Animation
from photons_canvas.animations.infrastructure.finish import Finish
from photons_canvas.animations.infrastructure.register import Animator, an_animation
from photons_canvas.animations.run_options import RunOptions, make_run_options
from photons_canvas.animations.runner import AnimationRunner

this_dir = os.path.dirname(__file__)

for filename in os.listdir(os.path.join(this_dir, "registered")):
    location = os.path.join(this_dir, "registered", filename)
    if not filename.startswith("_") or os.path.isdir(location) or filename.endswith(".py"):
        if os.path.isfile(location):
            filename = filename[:-3]

        __import__(f"photons_canvas.animations.registered.{filename}")

__all__ = [
    "register",
    "an_animation",
    "AnimationRunner",
    "Animation",
    "Finish",
    "RunOptions",
    "options",
    "Animator",
    "make_run_options",
    "print_help",
    "AnimationTask",
]
