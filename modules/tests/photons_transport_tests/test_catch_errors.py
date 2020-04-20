# coding: spec

from photons_transport import catch_errors

from photons_app.errors import RunErrors, PhotonsAppError
from photons_app import helpers as hp

from delfick_project.errors_pytest import assertRaises

describe "throw_error":
    it "passes on errors if error_catcher is a callable":
        es = []

        def ec(e):
            es.append(e)

        e1 = ValueError("NOPE")
        e2 = ValueError("NUP")

        with catch_errors(ec) as error_catcher:
            hp.add_error(error_catcher, e1)
            raise e2

        assert error_catcher is ec
        assert es == [e1, e2]

    it "passes on errors if error_catcher is a list":
        es = []

        e1 = ValueError("NOPE")
        e2 = ValueError("NUP")

        with catch_errors(es) as error_catcher:
            hp.add_error(error_catcher, e1)
            raise e2

        assert error_catcher is es
        assert es == [e1, e2]

    it "does nothing if no errors":
        with catch_errors():
            pass

        es = []

        def ec(e):
            es.append(e)

        with catch_errors(ec):
            pass
        assert es == []

        with catch_errors(es):
            pass
        assert es == []

    it "throws the error if just one":
        with assertRaises(ValueError, "NOPE"):
            with catch_errors():
                raise ValueError("NOPE")

    it "merges multiple of the same error together":
        e1 = PhotonsAppError("yeap", a=1)
        e2 = PhotonsAppError("yeap", a=1)

        with assertRaises(PhotonsAppError, "yeap", a=1):
            with catch_errors() as ec:
                hp.add_error(ec, e1)
                raise e2

        with assertRaises(PhotonsAppError, "yeap", a=1):
            with catch_errors() as ec:
                hp.add_error(ec, e1)
                hp.add_error(ec, e2)

    it "combines multiple of different  errors into a RunErrors":
        e1 = PhotonsAppError("yeap", a=1)
        e2 = PhotonsAppError("yeap", b=1)

        with assertRaises(RunErrors, _errors=[e1, e2]):
            with catch_errors() as ec:
                hp.add_error(ec, e1)
                raise e2

        with assertRaises(RunErrors, _errors=[e2, e1]):
            with catch_errors() as ec:
                hp.add_error(ec, e2)
                hp.add_error(ec, e1)
