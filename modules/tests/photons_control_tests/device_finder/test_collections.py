# coding: spec

from photons_control.device_finder import Collection, Collections

from unittest import mock
import pytest
import uuid

describe "Collection":
    it "has properties":
        typ = str(uuid.uuid1())
        cuuid = str(uuid.uuid1())
        name = str(uuid.uuid1())

        collection = Collection.FieldSpec().empty_normalise(typ=typ, uuid=cuuid, name=name)

        assert collection.typ == typ
        assert collection.uuid == cuuid
        assert collection.name == name
        assert collection.newest_timestamp is None

    describe "add_name":
        it "adds new name if we don't have a timestamp yet":
            typ = str(uuid.uuid1())
            cuuid = str(uuid.uuid1())
            name = str(uuid.uuid1())
            timestamp = 123

            collection = Collection.FieldSpec().empty_normalise(typ=typ, uuid=cuuid)

            assert collection.name == ""
            assert collection.newest_timestamp is None

            collection.add_name(timestamp, name)

            assert collection.name == name
            assert collection.newest_timestamp == timestamp

        it "only adds new name if we a greater timestamp":
            typ = str(uuid.uuid1())
            cuuid = str(uuid.uuid1())

            name = str(uuid.uuid1())
            name2 = str(uuid.uuid1())

            collection = Collection.FieldSpec().empty_normalise(typ=typ, uuid=cuuid)

            assert collection.name == ""
            assert collection.newest_timestamp is None

            collection.add_name(1, name)

            assert collection.name == name
            assert collection.newest_timestamp == 1

            collection.add_name(2, name2)

            assert collection.name == name2
            assert collection.newest_timestamp == 2

            collection.add_name(1, name)

            assert collection.name == name2
            assert collection.newest_timestamp == 2

    describe "equality":
        it "says no if not a collection":

            class Other:
                pass

            collection = Collection.FieldSpec().empty_normalise(uuid="stuff", typ="group")
            assert collection != Other()

        it "says no if not the same typ":

            class Other:
                pass

            collection1 = Collection.FieldSpec().empty_normalise(uuid="stuff", typ="group")
            collection2 = Collection.FieldSpec().empty_normalise(uuid="stuff", typ="location")
            assert collection1 != collection2

        it "says no if not the same uuid":

            class Other:
                pass

            collection1 = Collection.FieldSpec().empty_normalise(uuid="stuff", typ="group")
            collection2 = Collection.FieldSpec().empty_normalise(uuid="meh", typ="group")
            assert collection1 != collection2

        it "says yes if the same uuid and typ":

            class Other:
                pass

            collection1 = Collection.FieldSpec().empty_normalise(uuid="stuff", typ="group")
            collection2 = Collection.FieldSpec().empty_normalise(uuid="stuff", typ="group")
            assert collection1 == collection2

        it "says yes if the same uuid and typ even if names are different":

            class Other:
                pass

            collection1 = Collection.FieldSpec().empty_normalise(
                uuid="stuff", typ="group", name="one"
            )
            collection2 = Collection.FieldSpec().empty_normalise(
                uuid="stuff", typ="group", name="two"
            )
            assert collection1 == collection2

describe "Collections":
    it "starts with collections":
        collections = Collections()
        assert collections.collections == {"group": {}, "location": {}}

    it "starts with a spec for creating collection objects":
        typ = str(uuid.uuid1())
        cuuid = str(uuid.uuid1())
        collection = Collections().collection_spec.empty_normalise(typ=typ, uuid=cuuid)
        assert type(collection) == Collection
        assert collection.typ == typ
        assert collection.uuid == cuuid

    describe "adding":

        @pytest.fixture()
        def V(self):
            class V:
                uid = str(uuid.uuid1())
                updated_at = mock.Mock(name="updated_at")
                label = str(uuid.uuid1())
                collections = Collections()

            return V()

        describe "add_group":
            it "uses add_collection", V:
                add_collection = mock.Mock(name="add_collection")
                with mock.patch.object(V.collections, "add_collection", add_collection):
                    V.collections.add_group(V.uid, V.updated_at, V.label)

                add_collection.assert_called_once_with("group", V.uid, V.updated_at, V.label)

        describe "add_location":
            it "uses add_collection", V:
                add_collection = mock.Mock(name="add_collection")
                with mock.patch.object(V.collections, "add_collection", add_collection):
                    V.collections.add_location(V.uid, V.updated_at, V.label)

                add_collection.assert_called_once_with("location", V.uid, V.updated_at, V.label)

        describe "add_collection":
            it "creates the collection if it doesn't exist", V:
                collection = mock.Mock(name="collection")
                collection_spec = mock.Mock(name="collection_spec")
                collection_spec.empty_normalise.return_value = collection

                assert V.collections.collections == {"group": {}, "location": {}}

                with mock.patch.object(V.collections, "collection_spec", collection_spec):
                    assert V.collections.add_collection("group", V.uid, 1, V.label) is collection

                collection_spec.empty_normalise.assert_called_once_with(typ="group", uuid=V.uid)
                collection.add_name.assert_called_with(1, V.label)

            it "doesn't recreate collection if it exists", V:
                collection = mock.Mock(name="collection")
                collection_spec = mock.Mock(name="collection_spec")
                collection_spec.empty_normalise.side_effect = Exception(
                    "Expect empty_normalise to not be called"
                )

                V.collections.collections["location"][V.uid] = collection

                with mock.patch.object(V.collections, "collection_spec", collection_spec):
                    assert V.collections.add_collection("location", V.uid, 1, V.label) is collection

                assert len(collection_spec.empty_normalise.mock_calls) == 0
                collection.add_name.assert_called_with(1, V.label)
