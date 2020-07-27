from contextlib import contextmanager
from delfick_project.norms import sb
from collections import defaultdict
import os


def print_packet_difference(one, two, ignore_unspecified_expected=True):
    different = False
    if one != two:
        print("\tGOT : {0}".format(one.payload.__class__))
        print("\tWANT: {0}".format(two.payload.__class__))
        if one.payload.__class__ == two.payload.__class__:
            dictc = dict(one)
            dictw = dict(two)
            for k, v in dictc.items():
                if k not in dictw:
                    print("\t\tGot key not in wanted: {0}".format(k))
                    different = True
                elif dictw[k] is sb.NotSpecified and v is not sb.NotSpecified:
                    print(f"\t\tkey {k} | Ignored because expected is NotSpecified | was {v}")
                elif repr(v) != repr(dictw[k]):
                    if isinstance(v, bool) and dictw[k] in (1, 0) and int(v) == dictw[k]:
                        continue
                    print("\t\tkey {0} | got {1} | want {2}".format(k, v, dictw[k]))
                    different = True

            for k in dictw:
                if k not in dictc:
                    print("\t\tGot key in wanted but not in what we got: {0}".format(k))
                    different = True
    return different


def assert_payloads_equals(payload, expected):
    dct = payload.as_dict()

    different = []
    for k, v in expected.items():
        if v != dct[k]:
            different.append([k, dct[k], v])

    for k, got, want in different:
        print(f"KEY: {k} |:| GOT: {got} |:| WANT: {want}")

    assert len(different) == 0


def assertFutCallbacks(fut, *cbs, exhaustive=False):
    callbacks = fut._callbacks

    try:
        from contextvars import Context
    except ImportError:
        Context = None

    if not cbs:
        if Context is not None:
            if callbacks:
                assert len(callbacks) == 1, f"Expect only one context callback: got {callbacks}"
                assert isinstance(
                    callbacks[0], Context
                ), f"Expected just a context callback: got {callbacks}"
        else:
            assert callbacks == [], f"Expected no callbacks, got {callbacks}"

        return

    if not callbacks:
        assert False, f"expected callbacks, got {callbacks}"

    counts = defaultdict(lambda: 0)
    expected = defaultdict(lambda: 0)

    for cb in callbacks:
        if type(cb) is tuple:
            if len(cb) == 2 and Context and isinstance(cb[1], Context):
                cb = cb[0]
            else:
                assert False, f"Got a tuple instead of a callback, {cb} in {callbacks}"

        if not Context or not isinstance(cb, Context):
            counts[cb] += 1

    for cb in cbs:
        expected[cb] += 1

    for cb in cbs:
        msg = f"Expected {expected[cb]} instances of {cb}, got {counts[cb]} in {callbacks}"
        assert counts[cb] == expected[cb], msg

    if exhaustive and len(callbacks) != len(cbs):
        assert False, f"Expected exactly {len(cbs)} callbacks but have {len(callbacks)}"


@contextmanager
def modified_env(**env):
    """
    A context manager that let's you modify environment variables until the block
    has ended where the environment is returned to how it was

    .. code-block:: python

        import os

        assert "ONE" not in os.environ
        assert os.environ["TWO"] == "two"

        with modified_env(ONE="1", TWO="2"):
            assert os.environ["ONE"] == "1"
            assert os.environ["TWO"] == "1"

        assert "ONE" not in os.environ
        assert os.environ["TWO"] == "two"
    """
    previous = {key: os.environ.get(key, sb.NotSpecified) for key in env}
    try:
        for key, val in env.items():
            if val is None:
                if key in os.environ:
                    del os.environ[key]
            else:
                os.environ[key] = val
        yield
    finally:
        for key, val in previous.items():
            if val is sb.NotSpecified:
                if key in os.environ:
                    del os.environ[key]
            else:
                os.environ[key] = val
