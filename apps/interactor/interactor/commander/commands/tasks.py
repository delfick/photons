from interactor.commander.store import store

from photons_app import helpers as hp

from delfick_project.norms import dictobj, sb, Meta


@store.command(name="tasks/pause")
class PauseTaskCommand(store.Command):
    """
    Pause a running task
    """

    task_register = store.injected("task_register")

    name = dictobj.Field(sb.string_spec, wrapper=sb.required, help="The name of the task to pause")

    async def execute(self):
        self.task_register.pause(self.name)
        return await self.task_register.status()


@store.command(name="tasks/resume")
class ResumeTaskCommand(store.Command):
    """
    Resume a running task
    """

    task_register = store.injected("task_register")

    name = dictobj.Field(sb.string_spec, wrapper=sb.required, help="The name of the task to resume")

    async def execute(self):
        self.task_register.resume(self.name)
        return await self.task_register.status()


@store.command(name="tasks/remove")
class RemoveTaskCommand(store.Command):
    """
    Remove a running task
    """

    task_register = store.injected("task_register")

    name = dictobj.Field(sb.string_spec, wrapper=sb.required, help="The name of the task to remove")

    async def execute(self):
        await self.task_register.remove(self.name)
        return await self.task_register.status()


@store.command(name="tasks/add")
class AddTaskCommand(store.Command):
    """
    Add a new task
    """

    task_register = store.injected("task_register")

    name = dictobj.Field(sb.string_spec, wrapper=sb.required, help="The name of the task")
    type = dictobj.Field(sb.string_spec, wrapper=sb.required, help="The type of task")
    options = dictobj.Field(sb.dictionary_spec, help="The options given to the task")

    async def execute(self):
        meta = Meta({}, []).at("request")
        await self.task_register.add(meta, self.name, self.type, self.options)
        return await self.task_register.status()


@store.command(name="tasks/status")
class TaskStatusCommand(store.Command):
    """
    Show status of current running tasks
    """

    task_register = store.injected("task_register")

    async def execute(self):
        return await self.task_register.status()


@store.command(name="tasks/listen")
class TaskListenCommand(store.Command):
    """
    Connect through a websocket to listen to logs from this task
    """

    progress_cb = store.injected("progress_cb")
    task_register = store.injected("task_register")
    request_future = store.injected("request_future")

    name = dictobj.Field(
        sb.string_spec, wrapper=sb.required, help="The name of the task to listen to"
    )

    async def execute(self):
        async with self.task_register.listener_for(self.name, self.progress_cb):
            await hp.wait_for_all_futures(
                self.request_future, name=f"TaskListenCommand::execute[{self.name}]"
            )
