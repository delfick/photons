# coding: spec

from photons_transport import catch_errors

from photons_app.errors import RunErrors, PhotonsAppError
from photons_app.test_helpers import TestCase
from photons_app import helpers as hp

describe TestCase, "throw_error":
    it "passes on errors if error_catcher is a callable":
        es = []
        def ec(e):
            es.append(e)

        e1 = ValueError("NOPE")
        e2 = ValueError("NUP")

        with catch_errors(ec) as error_catcher:
            hp.add_error(error_catcher, e1)
            raise e2

        self.assertIs(error_catcher, ec)
        self.assertEqual(es, [e1, e2])

    it "passes on errors if error_catcher is a list":
        es = []

        e1 = ValueError("NOPE")
        e2 = ValueError("NUP")

        with catch_errors(es) as error_catcher:
            hp.add_error(error_catcher, e1)
            raise e2

        self.assertIs(error_catcher, es)
        self.assertEqual(es, [e1, e2])

    it "does nothing if no errors":
        with catch_errors():
            pass

        es = []
        def ec(e):
            es.append(e)

        with catch_errors(ec):
            pass
        self.assertEqual(es, [])

        with catch_errors(es):
            pass
        self.assertEqual(es, [])

    it "throws the error if just one":
        with self.fuzzyAssertRaisesError(ValueError, "NOPE"):
            with catch_errors():
                raise ValueError("NOPE")

    it "merges multiple of the same error together":
        e1 = PhotonsAppError("yeap", a=1)
        e2 = PhotonsAppError("yeap", a=1)

        with self.fuzzyAssertRaisesError(PhotonsAppError, "yeap", a=1):
            with catch_errors() as ec:
                hp.add_error(ec, e1)
                raise e2

        with self.fuzzyAssertRaisesError(PhotonsAppError, "yeap", a=1):
            with catch_errors() as ec:
                hp.add_error(ec, e1)
                hp.add_error(ec, e2)

    it "combines multiple of different  errors into a RunErrors":
        e1 = PhotonsAppError("yeap", a=1)
        e2 = PhotonsAppError("yeap", b=1)

        with self.fuzzyAssertRaisesError(RunErrors, _errors=[e1, e2]):
            with catch_errors() as ec:
                hp.add_error(ec, e1)
                raise e2

        with self.fuzzyAssertRaisesError(RunErrors, _errors=[e2, e1]):
            with catch_errors() as ec:
                hp.add_error(ec, e2)
                hp.add_error(ec, e1)
