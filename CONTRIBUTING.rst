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

We use the black project (https://black.readthedocs.io/en/stable/) to format the
python code in this repository.

Note that because of the noseOfYeti tests, I need to use the master branch of
black combined with a monkey patch of black to support the different grammar.

All you need to know is that you can run from the root of this project::

   $ ./format

And everything will be formatted.

You can setup vim to do this for you with something like:

.. code-block:: vim

   Plug 'sbdchd/neoformat'

   augroup fmt
      autocmd!
      autocmd BufWritePre *.py Neoformat
      autocmd BufWritePre */photons/scripts/* Neoformat
   augroup END

   let g:neoformat_enabled_python = ['black']

   function SetBlackOptions()
      let g:neoformat_enabled_python = ['black']
   endfunction

   function SetNoyBlackOptions()
      let g:neoformat_enabled_python = ['noy_black']
   endfunction

   function SetNoBlackOptions()
      let g:neoformat_enabled_python = []
   endfunction

   autocmd BufEnter * call SetBlackOptions()
   autocmd BufEnter *test*.py call SetNoyBlackOptions()
   autocmd BufEnter */site-packages/*.py call SetNoBlackOptions()

Note that for this to work you need black and noy_black in your python
environment when you open up vim.

I recommend creating a virtualenv somewhere and doing::

   $ cd tools/black/black
   $ pip install -e .
   $ cd ../noy_black
   $ pip install -e .

In VSCode you will need the following options to enable formatting on save:

.. code-block:: json

   "editor.formatOnSave": true,
   "python.formatting.blackPath": "/path/to/photons/extra/black/vscode_black",
   "python.formatting.provider": "black",
   "python.linting.pylamaArgs": ["-o", "/path/to/photons/pylama.ini"],
   "editor.formatOnSaveTimeout": 5000

The formatOnSaveTimeout is so that black has enough time to format the test files.

Linting
-------

I use pylama as my code linter, just run::

   $ ./lint

If you don't want the "too complicated" warnings, then run::

   $ ./lint -i C901
