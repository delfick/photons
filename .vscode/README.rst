Visual Studio Code Settings
===========================

Copy the ``settings-example.json`` as ``settings.json`` for paths to tools in the
virtualenv made from running ``source run.sh activate``.

Note that if visual studio code is not run after doing a ``source run.sh activate``
then at least make sure that ``NOSE_OF_YETI_BLACK_COMPAT=true`` is set as an
environment variable in the context that visual studio code is opened.

Otherwise black won't be able to format the tests.

Also, it's not possible to make pylance understand noseOfYeti (because microsoft
devs on that project refuse to make add what would be necessary to make that
possible) and so visual studio code will not enjoy those files. It can at least
format them with black (but not with isort).
