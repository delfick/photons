from photons_app.formatter import MergedOptionStringFormatter
from photons_app.errors import TargetNotFound
from photons_app.registers import Target

from delfick_project.norms import sb, BadSpecValue
import tokenize
import uuid
import ast


class task_specifier_spec(sb.Spec):
    def setup(self):
        self.target_spec = Target.FieldSpec(formatter=MergedOptionStringFormatter)

    def normalise_empty(self, meta):
        return sb.NotSpecified, "list_tasks"

    def normalise_filled(self, meta, val):
        if isinstance(val, list):
            val = tuple(val)

        if isinstance(val, tuple):
            return sb.tuple_spec(
                sb.optional_spec(sb.string_spec()), sb.required(sb.string_spec())
            ).normalise(meta, val)

        task = sb.or_spec(sb.string_spec(), sb.none_spec()).normalise(meta, val)
        if not task:
            task = "list_tasks"

        target = ""
        if ":" in task:
            target, task = val.rsplit(":", 1)

        if "(" not in target:
            return target or sb.NotSpecified, task

        tokens = self.initial_parse(val)

        chosen_task = tokens.pop().string
        tokens.pop()

        collector = meta.everything["collector"]
        target_register = collector.configuration["target_register"]

        target_name = tokens.pop(0).string
        target_name = self.parse_overridden_target(
            meta, val, collector, target_register, target_name, tokens
        )
        return target_name, chosen_task

    def initial_parse(self, val):
        lines = [val.encode(), b""]
        readline = lambda size=-1: lines.pop(0)

        try:
            tokens = list(tokenize.tokenize(readline))
        except tokenize.TokenError as e:
            raise BadSpecValue("Failed to parse specifier", error=e)

        if tokens[0].type is tokenize.ENCODING:
            tokens.pop(0)

        if tokens[-1].type is tokenize.ENDMARKER:
            tokens.pop(-1)

        if tokens[-1].type is tokenize.NEWLINE:
            tokens.pop(-1)

        return tokens

    def parse_overridden_target(self, meta, val, collector, target_register, target_name, tokens):
        if target_name not in target_register.targets:
            raise TargetNotFound(name=target_name, available=list(target_register.targets.keys()))

        if tokens[0].string != "(" or tokens[-1].string != ")":
            raise BadSpecValue("target with options should have options in parenthesis", got=val)

        parent_target_options = collector.configuration.get(
            ["targets", target_name], ignore_converters=True
        ).as_dict()

        target = self.parse_target(meta, parent_target_options, target_name, tokens)

        name = f"{target_name}_{uuid.uuid4().hex}"
        target_register.add_target(name, target)

        return name

    def parse_target(self, meta, target_options, target_name, tokens):
        tokens = [
            (tokenize.NAME, "dict"),
            *[(toknum, tokval) for toknum, tokval, *_ in tokens],
        ]

        overrides = {}
        untokenized = tokenize.untokenize(tokens)

        try:
            val = ast.parse(untokenized)
        except SyntaxError as e:
            raise BadSpecValue(
                "Target options must be valid dictionary syntax", error=e, got=untokenized
            )
        else:
            for kw in val.body[0].value.keywords:
                try:
                    overrides[kw.arg] = ast.literal_eval(kw.value)
                except ValueError:
                    bad = self.determine_bad(kw.value, untokenized)
                    raise BadSpecValue(f"target options can only be python literals: not ({bad})")

        if "options" not in target_options:
            target_options["options"] = {}

        target_options["options"].update(overrides)
        return self.target_spec.normalise(meta, target_options)

    def determine_bad(self, node, untokenized):
        if hasattr(node, "end_col_offset"):
            return untokenized[node.col_offset : node.end_col_offset]

        if hasattr(node, "string"):
            return node.string

        if hasattr(node, "id"):
            return node.id

        return "<unknown>"
