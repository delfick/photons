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
   "python.formatting.blackPath": "/path/to/photons/tools/black/vscode_black",
   "python.formatting.provider": "black",
   "python.linting.pylamaArgs": ["-o", "/path/to/photons/pylama.ini"],
   "editor.formatOnSaveTimeout": 5000

The formatOnSaveTimeout is so that black has enough time to format the test files.

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

    from photons_socket.connection import Sockets

    from photons_app.errors import TimedOut, FoundNoDevices

    from photons_transport.base import TransportItem, TransportBridge, TransportTarget
    from photons_messages import DiscoveryMessages, Services
    from photons_protocol.messages import Messages

    from delfick_project.norms import dictobj, sb
    import logging

Using import as
+++++++++++++++

I tend to import things directly, but I do tend to shortcut photons_app.helpers

.. code-block:: python

    from photons_app import helpers as hp

Linting
-------

I use pylama as my code linter and can be run from::

   $ ./lint

Commits
-------

Please follow Linus'
`guide <https://github.com/torvalds/subsurface-for-dirk/blob/a48494d2fbed58c751e9b7e8fbff88582f9b2d02/README#L88>`_
for good commit messages.

And also have in the title the module or app you are working on in square
brackets::

    [interactor] Fix some memory leaks

    It's possible for python to hold onto frame objects via exceptions so I
    need to be more careful about holding onto those

Here the short description starts with a tag of sorts in square brackets and
a short sentence of what. Followed by a paragraph with how and why.

Comments
--------

Comments in code should explain why something is done more than what is being
done.

Exception is when code is very complicated and it may be difficult to understand
what is happening.

Variable names
--------------

It's incredibly important to try your best to name things consistently. No types
means when changes are made, this makes it a lot easy/possible to ensure that
you find all instances of something that must be changed.

Commented out code
------------------

Please do not commit commented out code. Delete it. It's in git history.

async context managers
----------------------

In Python, a context manager is a cleanup mechanism that uses the ``with`` syntax.

For example, instead of saying:

.. code-block:: python

    wrapper = MyWrapper()

    wrapper.start()
    try:
        do_something()
    finally:
        wrapper.finish()

You would write:

.. code-block:: python

    with MyWrapper() as wrapper:
        do_something()

An async context manager is the same, but uses the ``async/await`` syntax as
well:

.. code-block:: python

    async with MyWrapper() as wrapper:
        do_something()

Photons can create these in two ways.

The first way is using the standard library ``asynccontextmanager`` decorator.
Photons makes this available via ``photons_app.helpers`` to make it easier to
sync with public photons until the minimum version of Python supported by it is
Python3.7 as Python3.6 does not include that function in the standard library and
public photons must polyfill it.

.. code-block:: python

    from photons_app import helpers as hp

    
    @hp.asynccontextmanager
    async def wrap():
        try:
            await something_fun()
            yield
        finally:
            await some_cleanup()

The other way is via manually defining one in a class. The protocol in Python
for a context manager is ``__enter__()/__exit__(exc_typ, exc, tb)`` for
synchronous context managers and ``__aenter__()/__aexit__(exc_typ, exc, tb)`` for
asynchronous context managers.

In Python a context manager is the same as:

.. code-block:: python

    await wrapper.__aenter__()
    try:
        do_something()
    finally:
        await wrapper.__aexit__(...)

But for cleanup purposes it is useful to instead have:

.. code-block:: python

    try:
        await wrapper.__aenter__()
        do_something()
    finally:
        await wrapper.__aexit__(...)

To make this possible, Photons supplies ``hp.AsyncCMMixin`` and you implement
``start()/finish(exc_typ=None, exc=None, tb=None)``:

.. code-block:: python

    from photons_app import helpers as hp


    class Thing(hp.AsyncCMMixin):
        async def start(self):
            ...

        async def finish(self, exc_typ=None, exc=None, tb=None):
            ...

This means all async context managers in Photons will run finish even if an
exception is raised in start, and have ``start`` and ``finish`` if you are not
using the ``with`` syntax.
