
from delfick_project.errors_pytest import assertRaises
from photons_app import helpers as hp
from photons_app.errors import PhotonsAppError, RunErrors
from photons_transport import catch_errors

class TestThrowError:
    def test_it_passes_on_errors_if_error_catcher_is_a_callable(self):
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

    def test_it_passes_on_errors_if_error_catcher_is_a_list(self):
        es = []

        e1 = ValueError("NOPE")
        e2 = ValueError("NUP")

        with catch_errors(es) as error_catcher:
            hp.add_error(error_catcher, e1)
            raise e2

        assert error_catcher is es
        assert es == [e1, e2]

    def test_it_does_nothing_if_no_errors(self):
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

    def test_it_throws_the_error_if_just_one(self):
        with assertRaises(ValueError, "NOPE"):
            with catch_errors():
                raise ValueError("NOPE")

    def test_it_merges_multiple_of_the_same_error_together(self):
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

    def test_it_combines_multiple_of_different_errors_into_a_RunErrors(self):
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
