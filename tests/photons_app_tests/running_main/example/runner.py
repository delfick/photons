from photons_app.formatter import MergedOptionStringFormatter
from photons_app.actions import an_action

from delfick_project.addons import addon_hook
from delfick_project.norms import sb, dictobj


class Wat(dictobj.Spec):
    one = dictobj.Field(format_into=sb.string_spec)
    two = dictobj.Field(format_into=sb.string_spec)

    @property
    def thing(self):
        return "{0}.{1}".format(self.one, self.two)


@addon_hook()
def __lifx__(collector, *args, **kwargs):
    collector.register_converters({"wat": Wat.FieldSpec(formatter=MergedOptionStringFormatter)})


@an_action()
async def do_the_thing(collector, target, reference, artifact, **kwargs):
    print(collector.configuration["wat"].thing)


if __name__ == "__main__":
    from photons_app.executor import main

    main()
