
import uuid
from unittest import mock

import pytest
from photons_control.device_finder import Collection, Collections

class TestCollection:
    def test_it_has_properties(self):
        typ = str(uuid.uuid1())
        cuuid = str(uuid.uuid1())
        name = str(uuid.uuid1())

        collection = Collection.FieldSpec().empty_normalise(typ=typ, uuid=cuuid, name=name)

        assert collection.typ == typ
        assert collection.uuid == cuuid
        assert collection.name == name
        assert collection.newest_timestamp is None

    class TestAddName:
        def test_it_adds_new_name_if_we_dont_have_a_timestamp_yet(self):
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

        def test_it_only_adds_new_name_if_we_a_greater_timestamp(self):
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

    class TestEquality:
        def test_it_says_no_if_not_a_collection(self):

            class Other:
                pass

            collection = Collection.FieldSpec().empty_normalise(uuid="stuff", typ="group")
            assert collection != Other()

        def test_it_says_no_if_not_the_same_typ(self):

            class Other:
                pass

            collection1 = Collection.FieldSpec().empty_normalise(uuid="stuff", typ="group")
            collection2 = Collection.FieldSpec().empty_normalise(uuid="stuff", typ="location")
            assert collection1 != collection2

        def test_it_says_no_if_not_the_same_uuid(self):

            class Other:
                pass

            collection1 = Collection.FieldSpec().empty_normalise(uuid="stuff", typ="group")
            collection2 = Collection.FieldSpec().empty_normalise(uuid="meh", typ="group")
            assert collection1 != collection2

        def test_it_says_yes_if_the_same_uuid_and_typ(self):

            class Other:
                pass

            collection1 = Collection.FieldSpec().empty_normalise(uuid="stuff", typ="group")
            collection2 = Collection.FieldSpec().empty_normalise(uuid="stuff", typ="group")
            assert collection1 == collection2

        def test_it_says_yes_if_the_same_uuid_and_typ_even_if_names_are_different(self):

            class Other:
                pass

            collection1 = Collection.FieldSpec().empty_normalise(
                uuid="stuff", typ="group", name="one"
            )
            collection2 = Collection.FieldSpec().empty_normalise(
                uuid="stuff", typ="group", name="two"
            )
            assert collection1 == collection2

class TestCollections:
    def test_it_starts_with_collections(self):
        collections = Collections()
        assert collections.collections == {"group": {}, "location": {}}

    def test_it_starts_with_a_spec_for_creating_collection_objects(self):
        typ = str(uuid.uuid1())
        cuuid = str(uuid.uuid1())
        collection = Collections().collection_spec.empty_normalise(typ=typ, uuid=cuuid)
        assert type(collection) == Collection
        assert collection.typ == typ
        assert collection.uuid == cuuid

    class TestAdding:

        @pytest.fixture()
        def V(self):
            class V:
                uid = str(uuid.uuid1())
                updated_at = mock.Mock(name="updated_at")
                label = str(uuid.uuid1())
                collections = Collections()

            return V()

        class TestAddGroup:
            def test_it_uses_add_collection(self, V):
                add_collection = mock.Mock(name="add_collection")
                with mock.patch.object(V.collections, "add_collection", add_collection):
                    V.collections.add_group(V.uid, V.updated_at, V.label)

                add_collection.assert_called_once_with("group", V.uid, V.updated_at, V.label)

        class TestAddLocation:
            def test_it_uses_add_collection(self, V):
                add_collection = mock.Mock(name="add_collection")
                with mock.patch.object(V.collections, "add_collection", add_collection):
                    V.collections.add_location(V.uid, V.updated_at, V.label)

                add_collection.assert_called_once_with("location", V.uid, V.updated_at, V.label)

        class TestAddCollection:
            def test_it_creates_the_collection_if_it_doesnt_exist(self, V):
                collection = mock.Mock(name="collection")
                collection_spec = mock.Mock(name="collection_spec")
                collection_spec.empty_normalise.return_value = collection

                assert V.collections.collections == {"group": {}, "location": {}}

                with mock.patch.object(V.collections, "collection_spec", collection_spec):
                    assert V.collections.add_collection("group", V.uid, 1, V.label) is collection

                collection_spec.empty_normalise.assert_called_once_with(typ="group", uuid=V.uid)
                collection.add_name.assert_called_with(1, V.label)

            def test_it_doesnt_recreate_collection_if_it_exists(self, V):
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
