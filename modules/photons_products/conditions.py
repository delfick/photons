class Family:
    def __init__(self, family):
        self.family = family

    def __repr__(self):
        return f"family={self.family}"

    def __eq__(self, other):
        return isinstance(other, Family) and other.family == self.family

    def __call__(self, cap):
        return cap.product.family == self.family


class Capability:
    def __init__(self, **want):
        self.want = sorted(want.items())

    def __repr__(self):
        caps = " ".join(f"{k}={v}" for k, v in self.want)
        return f"capabilities({caps})"

    def __eq__(self, other):
        return isinstance(other, Capability) and other.want == self.want

    def __call__(self, cap):
        return all(getattr(cap, k) == v for k, v in self.want)


class NameHas:
    def __init__(self, fragment):
        self.fragment = fragment

    def __repr__(self):
        return f"name_contains({self.fragment})"

    def __eq__(self, other):
        return isinstance(other, NameHas) and other.fragment == self.fragment

    def __call__(self, cap):
        return self.fragment in cap.product.name


class NameExcludes:
    def __init__(self, fragment):
        self.fragment = fragment

    def __repr__(self):
        return f"name_excludes({self.fragment})"

    def __eq__(self, other):
        return isinstance(other, NameExcludes) and other.fragment == self.fragment

    def __call__(self, cap):
        return self.fragment not in cap.product.name


class PidFrom:
    def __init__(self, pid_from):
        self.pid_from = pid_from

    def __repr__(self):
        return f"pid>={self.pid_from}"

    def __eq__(self, other):
        return isinstance(other, PidFrom) and other.pid_from == self.pid_from

    def __call__(self, cap):
        return cap.product.pid >= self.pid_from
