from delfick_project.addons import addon_hook
from delfick_project.norms import dictobj, sb
from photons_app.actions import an_action
from photons_app.formatter import MergedOptionStringFormatter
from photons_app.tasks import task_register as task


class Wat(dictobj.Spec):
    one = dictobj.Field(format_into=sb.string_spec)
    two = dictobj.Field(format_into=sb.string_spec)

    @property
    def thing(self):
        return "{0}.{1}".format(self.one, self.two)


@addon_hook()
def __lifx__(collector, *args, **kwargs):
    collector.register_converters({"wat": Wat.FieldSpec(formatter=MergedOptionStringFormatter)})


@task
class do_the_thing(task.Task):
    async def execute_task(self, **kwargs):
        print(self.collector.configuration["wat"].thing)


@an_action()
async def do_the_thing_with_old_an_action(collector, target, reference, artifact, **kwargs):
    print(collector.configuration["wat"].thing)


if __name__ == "__main__":
    from photons_app.executor import main

    main()
