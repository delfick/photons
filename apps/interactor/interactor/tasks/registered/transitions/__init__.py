from interactor.tasks.registered.transitions.options import Options
from interactor.tasks.register import registerer


@registerer
def register(tasks):
    tasks.register("transitions", Options, run)


async def run(final_future, options, progress):
    pass
