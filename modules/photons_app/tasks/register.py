from photons_app.errors import BadTarget, BadOption

from delfick_project.norms import sb


artifact_spec = lambda: sb.optional_spec(sb.any_spec())


class target_spec(sb.Spec):
    def setup(self, restrictions, *, mandatory=True):
        self.mandatory = mandatory
        self.restrictions = restrictions

    def normalise_empty(self, meta):
        if not self.mandatory:
            return sb.NotSpecified

        usage = "lifx <target>:<task> <reference> <artifact> -- '{{<options>}}'"
        raise BadTarget("This task requires you specify a target", usage=usage, meta=meta)

    def normalise(self, meta, val):
        if val in ("", None, sb.NotSpecified):
            return self.normalise_empty(meta)

        collector = meta.everything["collector"]
        target_register = collector.configuration["target_register"]
        return target_register.restricted(**self.restrictions).resolve(val)


class reference_spec(sb.Spec):
    def setup(self, mandatory=True, special=True):
        self.special = special
        self.mandatory = mandatory

    def normalise_empty(self, meta, val=sb.NotSpecified):
        if not self.mandatory:
            if self.special:
                return meta.everything["collector"].reference_object(val)
            return sb.NotSpecified

        raise BadOption("This task requires you specify a reference, please do so!", meta=meta)

    def normalise_filled(self, meta, val):
        if val in ("", None, sb.NotSpecified):
            return self.normalise_empty(meta, val=val)

        if self.special and isinstance(val, str):
            collector = meta.everything["collector"]
            return collector.reference_object(val)

        return val
