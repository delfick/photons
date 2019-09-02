from photons_app.formatter import MergedOptionStringFormatter
from photons_app.actions import an_action

from option_merge_addons import option_merge_addon_hook
from input_algorithms import spec_base as sb
from input_algorithms.dictobj import dictobj
from input_algorithms.meta import Meta


class Wat(dictobj.Spec):
    one = dictobj.Field(format_into=sb.string_spec)
    two = dictobj.Field(format_into=sb.string_spec)

    @property
    def thing(self):
        return "{0}.{1}".format(self.one, self.two)


@option_merge_addon_hook()
def __lifx__(collector, *args, **kwargs):
    collector.register_converters(
        {(0, ("wat",)): Wat.FieldSpec(formatter=MergedOptionStringFormatter)},
        Meta,
        collector.configuration,
        sb.NotSpecified,
    )


@an_action()
async def do_the_thing(collector, target, reference, artifact, **kwargs):
    print(collector.configuration["wat"].thing)


if __name__ == "__main__":
    from photons_app.executor import main

    main()
