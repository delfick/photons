Contributing
============

Issues and Pull Requests are very welcome!

Here are some notes about the project that may help make pull requests easier to
merge.

The tests
---------

To run the tests you need to be inside a virtualenv that has lifx-photons-core
installed.

I like virtualenvwrapper for this:

.. code-block:: plain

    # Install python3.6 or above
    # Install virtualenvwrapper (see https://virtualenvwrapper.readthedocs.io/en/latest/)
    
    $ mkvirtualenv photons -p $(which python3)
    $ workon photons
    $ pip install -e .
    $ pip install -e ".[tests]"
    $ ./test.sh

Alternatively you may use tox to run the tests:

.. code-block:: plain

    # Ensure python3.6 is installed
    $ pip3 install tox
    $ tox

The tests are written using http://noseofyeti.readthedocs.io which is a project
that uses python codecs to create a basic RSpec style DSL for writing tests.

We also use the ``photons_app.test_helpers`` package so that tests look like:

.. code-block:: python

    # coding: spec

    # (the "coding: spec" is necessary to activate the codec that transforms the
    #  dsl at import time into python that then gets executed)

    from photons_app.test_helpers import TestCase, AsyncTestCase

    # These are necessary for the before_each, after_each, async before_each and async_after_each
    # helpers on the describes (they map to setUp and tearDown methods on unittest.TestCase)
    # You don't need to import them if you don't use before_each or after_each
    from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp, async_noy_sup_tearDown
    from noseOfYeti.tokeniser.support import noy_sup_setUp, noy_sup_tearDown

    describe TestCase, "non async example":
        before_each:
            # Anything that needs to happen before every test
            self.something = 1

        after_each:
            # anything that needs to happen at the end of every test

        it "has tests":
            assert True

        describe "and as many nested describes as you want":
            it "subclasses from unittest.TestCase":
                # self is the instance of this class
                # And because of photons_app.test_helpers.TestCase
                # we have all the assert methods from unittest.TestCase
                self.assertEqual(self.something, 1)

    describe AsyncTestCase, "async example":
        async before_each:
            # same as before_each in the non async example, but with async!

        async after_each:
            # same as after_each but with async

        async it "needs async in front of every it":
            await asyncio.sleep(1)
            self.assertGreater(2, 1)

        describe "we can have nested describes here as well":
            async it "works":
                assert True

Tests are grouped by their module inside the ``tests`` folder. Note that we name
each folder as "<module>_tests" so that import statements for that module don't
get clobbered by these test files.

Code style
----------

Pep8 is great and all, but I don't follow all of it. Notable mentions include
the following:

Double empty lines
++++++++++++++++++

I cannot stand double empty lines. I always use a single empty line between
anything.

Import statement groups
+++++++++++++++++++++++

I group import blocks into groups and then by length of line within the group.

.. code-block:: plain

    <imports from to the current module>

    <imports from photons_app>

    <imports from other photons modules>

    <other imports>

For example, inside ``photons_socket``:

.. code-block:: python

    from photons_socket.messages import DiscoveryMessages, Services
    from photons_socket.connection import Sockets

    from photons_app.errors import TimedOut, FoundNoDevices

    from photons_transport.target import TransportItem, TransportBridge, TransportTarget
    from photons_protocol.messages import Messages

    from input_algorithms.dictobj import dictobj
    from input_algorithms import spec_base as sb
    import logging

Using import as
+++++++++++++++

I tend to import things directly, but there are two notable exceptions:

.. code-block:: python

    from photons_app import helpers as hp

    from input_algorithms import spec_base as sb

These two happen in many places within the photons codebase because they are both
common and have many different objects underneath them

PyLama
++++++

I use pylama as my code linter, with the following ``~/.config/pycodestyle`` file

.. code-block:: ini

    [pycodestyle]
    ignore = E203,E128,E124,E251,E121,E123,E131,E126,E302,E731,E201,E305,E202,E125,E221,E222,E266,E241,E122,E211

And the following ``~/.pylama.ini``

.. code-block:: init

    [pylama:pyflakes]
    builtins = _

    [pylama:pycodestyle]
    max_line_length = 150

    [pylama:pylint]
    max_line_length = 150
    disable = R

Leading commas
++++++++++++++

I use leading commas because I believe they are easier to read and check.

Basically this means the following:

.. code-block:: python

    my_list = [
          "one"
        , "two"
        , "three"
        ]

    long_function_name_for_example(
          "one"
        , "two"
        )

    nested_thing = {
          "one": "two"
        , "three":
          { "four": "five"
          , "six": ["seven", "eight"]
          , "nine":
            [ "ten"
            , "eleven"
            , "twelve"
            ]
          }
        }

I never indent to the opening brace of something. If it's on a newline then it's
one tab away from the beginning of the last line.
