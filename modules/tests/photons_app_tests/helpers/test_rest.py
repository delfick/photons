import os
from unittest import mock

from delfick_project.errors_pytest import assertRaises
from photons_app import helpers as hp
from photons_messages import fields


class TestFutureToString:
    def test_it_just_reprs_a_not_future(self):

        class Thing:
            def __repr__(s):
                return "<REPR THING>"

        assert hp.fut_to_string(Thing()) == "<REPR THING>"

    def test_it_says_if_the_future_is_pending(self):
        fut = hp.create_future(name="one")
        assert hp.fut_to_string(fut) == "<Future#one(pending)>"

        fut = hp.create_future()
        assert hp.fut_to_string(fut) == "<Future#None(pending)>"

    def test_it_says_if_the_future_is_cancelled(self):
        fut = hp.create_future(name="one")
        fut.cancel()
        assert hp.fut_to_string(fut) == "<Future#one(cancelled)>"

        fut = hp.create_future()
        fut.cancel()
        assert hp.fut_to_string(fut) == "<Future#None(cancelled)>"

    def test_it_says_if_the_future_has_an_exception(self):
        fut = hp.create_future(name="one")
        fut.set_exception(ValueError("HI"))
        assert hp.fut_to_string(fut) == "<Future#one(exception:ValueError:HI)>"

        fut = hp.create_future()
        fut.set_exception(TypeError("NOPE"))
        assert hp.fut_to_string(fut) == "<Future#None(exception:TypeError:NOPE)>"

    def test_it_says_if_the_future_has_a_result(self):
        fut = hp.create_future(name="one")
        fut.set_result(True)
        assert hp.fut_to_string(fut) == "<Future#one(result)>"

        fut = hp.create_future()
        fut.set_result(False)
        assert hp.fut_to_string(fut) == "<Future#None(result)>"


class TestAddError:
    def test_it_calls_the_error_catcher_with_the_error_if_its_a_callable(self):
        error = mock.Mock(name="error")
        catcher = mock.Mock(name="catcher")
        hp.add_error(catcher, error)
        catcher.assert_called_once_with(error)

    def test_it_appends_to_the_error_catcher_if_its_a_list(self):
        error = mock.Mock(name="error")
        catcher = []
        hp.add_error(catcher, error)
        assert catcher == [error]

    def test_it_adds_to_the_error_catcher_if_its_a_set(self):
        error = mock.Mock(name="error")
        catcher = set()
        hp.add_error(catcher, error)
        assert catcher == set([error])


class TestATempFile:
    def test_it_gives_us_the_tmpfile(self):
        with hp.a_temp_file() as fle:
            fle.write(b"wassup")
            fle.seek(0)
            assert os.path.exists(fle.name)
            assert fle.read() == b"wassup"
        assert not os.path.exists(fle.name)

    def test_it_doesnt_fail_if_we_delete_the_file_early(self):
        with hp.a_temp_file() as fle:
            fle.close()
            os.remove(fle.name)
        assert not os.path.exists(fle.name)


class TestJustLogExceptions:
    def test_it_logs_exceptions(self):
        log = mock.Mock(name="log")

        error = ValueError("NOPE")
        with hp.just_log_exceptions(log):
            raise error

        log.error.assert_called_once_with(
            "Unexpected error", exc_info=(ValueError, error, mock.ANY)
        )

    def test_it_can_be_given_a_different_message(self):
        log = mock.Mock(name="log")

        error = ValueError("NOPE")
        with hp.just_log_exceptions(log, message="a different message"):
            raise error

        log.error.assert_called_once_with(
            "a different message", exc_info=(ValueError, error, mock.ANY)
        )

    def test_it_can_reraise_particular_errors(self):
        log = mock.Mock(name="log")

        error = ValueError("NOPE")
        with hp.just_log_exceptions(log, message="a different message", reraise=[TypeError]):
            raise error

        log.error.assert_called_once_with(
            "a different message", exc_info=(ValueError, error, mock.ANY)
        )
        log.error.reset_mock()

        with assertRaises(TypeError, "wat"):
            with hp.just_log_exceptions(log, message="a different message", reraise=[TypeError]):
                raise TypeError("wat")

        log.assert_not_called()


class TestNestedDictRetrieve:
    def test_it_returns_us_the_dflt_if_we_cant_find_the_key(self):
        data = {"one": {"two": {"three": 3}}}
        dflt = mock.Mock(name="dflt")
        for keys in (
            ["one", "four"],
            ["four", "five"],
            ["one", "two", "five"],
            ["one", "two", "three", "four"],
        ):
            assert hp.nested_dict_retrieve(data, keys, dflt) is dflt

    def test_it_returns_us_what_it_finds(self):
        data = {"one": {"two": {"three": 3}}}
        dflt = mock.Mock(name="dflt")

        assert hp.nested_dict_retrieve(data, [], dflt) == data
        assert hp.nested_dict_retrieve(data, ["one"], dflt) == {"two": {"three": 3}}
        assert hp.nested_dict_retrieve(data, ["one", "two"], dflt) == {"three": 3}
        assert hp.nested_dict_retrieve(data, ["one", "two", "three"], dflt) == 3


class TestMemoizedProperty:
    def test_it_caches_on_the_instance(self):
        called = []
        blah = mock.Mock(name="blah")

        class Thing:
            @hp.memoized_property
            def blah(s):
                called.append(1)
                return blah

        thing = Thing()
        assert called == []
        assert thing.blah is blah
        assert called == [1]

        assert thing._blah == blah
        assert thing.blah is blah
        assert called == [1]

    def test_it_caches_on_the_instance_if_the_return_is_None(self):
        called = []

        class Thing:
            @hp.memoized_property
            def blah(s):
                called.append(1)
                return None

        thing = Thing()
        assert called == []
        assert thing.blah is None
        assert called == [1]

        assert thing._blah is None
        assert thing.blah is None
        assert called == [1]

    def test_it_caches_on_the_instance_if_the_return_is_False(self):
        called = []

        class Thing:
            @hp.memoized_property
            def blah(s):
                called.append(1)
                return False

        thing = Thing()
        assert called == []
        assert thing.blah is False
        assert called == [1]

        assert thing._blah is False
        assert thing.blah is False
        assert called == [1]

    def test_it_can_set_the_value(self):
        called = []
        blah = mock.Mock(name="blah")
        meh = mock.Mock(name="meh")

        class Thing:
            @hp.memoized_property
            def blah(s):
                called.append(1)
                return blah

        thing = Thing()
        assert called == []
        assert thing.blah is blah
        assert called == [1]

        assert thing._blah == blah
        thing.blah = meh
        assert thing._blah == meh

        assert thing.blah is meh
        assert called == [1]

    def test_it_can_delete_the_cache(self):
        called = []
        blah = mock.Mock(name="blah")

        class Thing:
            @hp.memoized_property
            def blah(s):
                called.append(1)
                return blah

        thing = Thing()
        assert called == []
        assert thing.blah is blah
        assert called == [1]

        assert thing._blah == blah
        assert thing.blah is blah
        assert called == [1]

        del thing.blah
        assert not hasattr(thing, "_blah")

        assert thing.blah is blah
        assert called == [1, 1]


class TestColor:
    def test_it_can_be_made_and_cloned(self):
        c1 = hp.Color(2, 0, 0.3, 3500)
        c2 = c1.clone()

        assert c1 is not c2

        for c in (c1, c2):
            assert c.hue == 2
            assert c["hue"] == 2

            assert c.saturation == 0
            assert c["saturation"] == 0

            assert c.brightness == 0.3
            assert c["brightness"] == 0.3

            assert c.kelvin == 3500
            assert c["kelvin"] == 3500

        c2.hue = 45
        c2.brightness = 1
        assert c2 == hp.Color(45, 0, 1, 3500)
        assert c1 == hp.Color(2, 0, 0.3, 3500)
        assert c1.as_dict() == {"hue": 2, "saturation": 0, "brightness": 0.3, "kelvin": 3500}

    def test_it_can_be_compared_with_a_tuple(self):
        assert hp.Color(2, 0, 0, 3500) != (2,)
        assert hp.Color(2, 0, 0, 3500) != (2, 0)
        assert hp.Color(2, 0, 0, 3500) != (2, 0, 0)
        assert hp.Color(2, 0, 0, 3500) == (2, 0, 0, 3500)

        assert hp.Color(2, 0, 0, 3500) != (20, 0, 0, 3500)
        assert hp.Color(2, 0, 0, 3500) != (2, 1, 0, 3500)
        assert hp.Color(2, 0, 0, 3500) != (2, 0, 1, 3500)
        assert hp.Color(2, 0, 0, 3500) != (2, 0, 0, 3700)

    def test_it_can_be_compared_with_a_dictionary(self):
        assert hp.Color(2, 0, 0, 3500) != {"hue": 2}
        assert hp.Color(2, 0, 0, 3500) != {"hue": 2, "saturation": 0}
        assert hp.Color(2, 0, 0, 3500) != {"hue": 2, "saturation": 0, "brightness": 0}
        assert hp.Color(2, 0, 0, 3500) == {
            "hue": 2,
            "saturation": 0,
            "brightness": 0,
            "kelvin": 3500,
        }

        assert hp.Color(2, 0, 0, 3500) != {
            "hue": 20,
            "saturation": 0,
            "brightness": 0,
            "kelvin": 3500,
        }
        assert hp.Color(2, 0, 0, 3500) != {
            "hue": 2,
            "saturation": 1,
            "brightness": 0,
            "kelvin": 3500,
        }
        assert hp.Color(2, 0, 0, 3500) != {
            "hue": 2,
            "saturation": 0,
            "brightness": 1,
            "kelvin": 3500,
        }
        assert hp.Color(2, 0, 0, 3500) != {
            "hue": 2,
            "saturation": 0,
            "brightness": 0,
            "kelvin": 3700,
        }

    def test_it_can_be_compared_with_another_hpColor(self):
        assert hp.Color(2, 0, 0, 3500) == hp.Color(2, 0, 0, 3500)

        assert hp.Color(2, 0, 0, 3500) != hp.Color(20, 0, 0, 3500)
        assert hp.Color(2, 0, 0, 3500) != hp.Color(2, 1, 0, 3500)
        assert hp.Color(2, 0, 0, 3500) != hp.Color(2, 0, 1, 3500)
        assert hp.Color(2, 0, 0, 3500) != hp.Color(2, 0, 0, 3700)

    def test_it_can_be_compared_with_a_real_fieldsColor(self):
        assert hp.Color(2, 0, 0, 3500) == fields.Color(
            hue=2, saturation=0, brightness=0, kelvin=3500
        )

        assert hp.Color(2, 0, 0, 3500) != fields.Color(
            hue=20, saturation=0, brightness=0, kelvin=3500
        )
        assert hp.Color(2, 0, 0, 3500) != fields.Color(
            hue=2, saturation=1, brightness=0, kelvin=3500
        )
        assert hp.Color(2, 0, 0, 3500) != fields.Color(
            hue=2, saturation=0, brightness=1, kelvin=3500
        )
        assert hp.Color(2, 0, 0, 3500) != fields.Color(
            hue=2, saturation=0, brightness=0, kelvin=3700
        )

    def test_it_compares_to_4_decimal_places(self):
        assert hp.Color(250.245677, 0.134577, 0.765477, 4568) == (
            250.245699,
            0.134599,
            0.765499,
            4568,
        )
        assert hp.Color(250.245677, 0.134577, 0.765477, 4568) != (
            250.245799,
            0.134699,
            0.765599,
            4568,
        )

    def test_it_compares_hue_35999_to_hue_00(self):
        assert hp.Color(359.99, 1.0, 1.0, 3500) == (
            0.0,
            1.0,
            1.0,
            3500,
        )
