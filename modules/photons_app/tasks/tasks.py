import sys

from delfick_project.norms import Meta, dictobj, sb
from photons_app import helpers as hp
from photons_app.errors import ApplicationStopped
from photons_app.formatter import MergedOptionStringFormatter
from photons_app.tasks.runner import Runner


class photons_app_spec(sb.Spec):
    def normalise(self, meta, val):
        return meta.everything["collector"].photons_app


class TaskMeta(dictobj.Field.metaclass):
    def __repr__(self):
        return f"<Task {self.__name__}>"


class Task(dictobj, metaclass=TaskMeta):
    """
    Responsible for managing the life cycle of a photons program

    It has on it by default the following attributes:

    instantiated_name
        The name that was used when this task was created

    collector
        The :ref:`Collector <collector_root>` used for this Photons session

    photons_app
        The :ref:`PhotonsApp <collector_root>` object associated with this Photons
        session

    task_holder
        A :class:`photons_app.helpers.TaskHolder` instance that wraps the
        execution of the task

    Extra attributes may be added using ``dictobj.Field`` objects via
    `delfick_project.norms <https://delfick-project.readthedocs.io/en/latest/api/norms/index.html>`_.

    The life cycle of the task is contained within the ``run`` method, which
    is responsible for managing the ``task_holder``, running ``execute_task``
    and ensuring ``post`` is run when ``execute_task`` is done regardless of
    whether it raised an exception or not.

    ``execute_task`` must be implemented and is where the body of the task
    should go.

    ``post`` is an optional hook that may be implemented to execute code
    regardless of how ``execute_task`` finished.
    """

    instantiated_name = dictobj.Field(sb.string_spec)

    collector = dictobj.Field(
        sb.overridden("{collector}"),
        format_into=lambda: sb.typed(__import__("photons_app.collector").collector.Collector),
    )

    photons_app = dictobj.Field(
        sb.overridden("{photons_app}"),
        format_into=lambda: sb.typed(__import__("photons_app.photons_app").photons_app.PhotonsApp),
    )

    @classmethod
    def create(kls, collector, where=None, instantiated_name=None, **kwargs):
        if where is None:
            where = "<Task.create>"

        if instantiated_name is None:
            instantiated_name = kls.__name__

        configuration = collector.configuration.wrapped()
        kwargs.update({"instantiated_name": instantiated_name})
        configuration.update(kwargs)
        meta = Meta(configuration, []).at(where)

        # Make errors follow nice order for errors on cli
        spec = kls.FieldSpec(MergedOptionStringFormatter).make_spec(meta)
        transfer_set = {}
        transfer_create = {}
        for key in ("target", "reference", "artifact"):
            if key in spec.expected:
                transfer_set[key] = spec.expected.pop(key)
                transfer_create[key] = spec.expected_spec.options.pop(key)
        transfer_set.update(spec.expected)
        transfer_create.update(spec.expected_spec.options)
        spec.expected_spec.options = transfer_set
        spec.expected = transfer_create

        return spec.normalise(meta, kwargs)

    @hp.memoized_property
    def task_holder(self):
        return hp.TaskHolder(
            self.photons_app.final_future, name=f"Task({self.__class__.__name__})::task_holder"
        )

    def run_loop(self, **kwargs):
        return Runner(self, kwargs).run_loop()

    async def run(self, **kwargs):
        hidden_exc_info = None
        try:
            async with self.task_holder:
                try:
                    return await self.execute_task(**kwargs)
                except:
                    exc_info = sys.exc_info()
                    if not self.hide_exception_from_task_holder(exc_info):
                        raise
                    else:
                        hidden_exc_info = exc_info
                finally:
                    if hidden_exc_info is not None:
                        exc_info = hidden_exc_info
                    else:
                        exc_info = sys.exc_info()
                    await self.post(exc_info, **kwargs)
        finally:
            if hidden_exc_info is not None:
                hidden_exc_info[1].__traceback__ = hidden_exc_info[2]
                raise hidden_exc_info[1]

    async def execute_task(self, **kwargs):
        raise NotImplementedError()

    async def post(self, exc_info, **kwargs):
        pass

    def hide_exception_from_task_holder(self, exc_info):
        return False

    def __repr__(self):
        return f"<Task Instance {self.instantiated_name}>"


class GracefulTask(Task):
    """
    Responsible for managing the life cycle of a photons program that uses the graceful future
    """

    def run_loop(self, **kwargs):
        with self.photons_app.using_graceful_future() as graceful:
            kwargs["graceful_final_future"] = graceful
            super().run_loop(**kwargs)

    def hide_exception_from_task_holder(self, exc_info):
        return exc_info[0] is ApplicationStopped
