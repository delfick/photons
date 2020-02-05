# coding: spec

from photons_app import helpers as hp

from unittest import mock
import os

describe "add_error":
    it "calls the error_catcher with the error if it's a callable":
        error = mock.Mock(name="error")
        catcher = mock.Mock(name="catcher")
        hp.add_error(catcher, error)
        catcher.assert_called_once_with(error)

    it "appends to the error catcher if it's a list":
        error = mock.Mock(name="error")
        catcher = []
        hp.add_error(catcher, error)
        assert catcher == [error]

    it "adds to the error catcher if it's a set":
        error = mock.Mock(name="error")
        catcher = set()
        hp.add_error(catcher, error)
        assert catcher == set([error])

describe "a_temp_file":
    it "gives us the tmpfile":
        with hp.a_temp_file() as fle:
            fle.write(b"wassup")
            fle.seek(0)
            assert os.path.exists(fle.name)
            assert fle.read() == b"wassup"
        assert not os.path.exists(fle.name)

    it "doesn't fail if we delete the file early":
        with hp.a_temp_file() as fle:
            fle.close()
            os.remove(fle.name)
        assert not os.path.exists(fle.name)

describe "nested_dict_retrieve":
    it "returns us the dflt if we can't find the key":
        data = {"one": {"two": {"three": 3}}}
        dflt = mock.Mock(name="dflt")
        for keys in (
            ["one", "four"],
            ["four", "five"],
            ["one", "two", "five"],
            ["one", "two", "three", "four"],
        ):
            assert hp.nested_dict_retrieve(data, keys, dflt) is dflt

    it "returns us what it finds":
        data = {"one": {"two": {"three": 3}}}
        dflt = mock.Mock(name="dflt")

        assert hp.nested_dict_retrieve(data, [], dflt) == data
        assert hp.nested_dict_retrieve(data, ["one"], dflt) == {"two": {"three": 3}}
        assert hp.nested_dict_retrieve(data, ["one", "two"], dflt) == {"three": 3}
        assert hp.nested_dict_retrieve(data, ["one", "two", "three"], dflt) == 3

describe "memoized_property":
    it "caches on the instance":
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

    it "caches on the instance if the return is None":
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

        assert thing._blah == None
        assert thing.blah is None
        assert called == [1]

    it "caches on the instance if the return is False":
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

        assert thing._blah == False
        assert thing.blah is False
        assert called == [1]

    it "can set the value":
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

    it "can delete the cache":
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
