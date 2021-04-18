from delfick_project.norms import BadSpecValue, sb
from datetime import datetime


class days_spec(sb.Spec):
    def normalise_empty(self, meta):
        return list(range(7))

    def normalise_filled(self, meta, val):
        val = sb.listof(sb.or_spec(sb.integer_spec(), sb.string_spec())).normalise(meta, val)

        result = []

        for i, v in enumerate(val):
            if isinstance(v, int):
                if v < 0 or v > 6:
                    raise BadSpecValue(
                        "Days as numbers must be between 0 (sunday) and 6 (saturday)",
                        got=v,
                        meta=meta.indexed_at(i),
                    )
                result.append(v)
            else:
                d = None
                for fmt in ("%a", "%A"):
                    try:
                        d = datetime.strptime(v.lower(), fmt)
                        break
                    except ValueError:
                        pass

                if d is None:
                    raise BadSpecValue(
                        "Days as a string must be a valid weekday name for your locale",
                        got=v,
                        meta=meta.indexed_at(i),
                    )
                else:
                    result.append(int(d.strftime("%w")))

        if len(set(result)) != len(result):
            raise BadSpecValue("Some days were repeated", got=result, meta=meta)

        return sorted(result)
