__doc__ = '''
An interface for working with Photons targets.

.. code-block:: python

    from photons_script.script import ATarget

    async with ATarget(target) as afr:
        target.script(SomeMessage()).run_with(loop, [reference], afr)

Targets use this module to create the response to the ``script`` method and
implement ``args_for_run`` and ``close_args_for_run`` so that ``ATarget`` can
create and properly close the ``afr`` object.

The idea is that the script is able to take an object that can be simplified and
we can then call ``run_with`` using the ``loop``, some ``references`` and the
``afr`` to perform the action set out by the messages.

For example:

.. code-block:: python

    from photons_script.script import ScriptRunner, Pipeline

    class MyTarget(object):
        def script(self, raw):
            return ScriptRunner(self.simplify(raw), target=self)

        async def args_for_run(self, loop, found=None):
            """Create some object that performs the actual transportation"""
            afr = ...
            return afr

        async def close_args_for_run(self, afr):
            """Close an args_for_run"""
            afr.finish()

        def simplify(self, message):
            """From this message return an object with a ``run_with`` method"""
            if hasattr(message, "has_children"):
                return message.simplified(self.simplify)
            else:
                return MyTargetItem(message)

    class MyTargetItem(object):
        def __init__(self, part):
            self.part = part

        async def run_with(self, loop, references, afr):
            ...

.. autoclass:: photons_script.script.ScriptRunner

.. autoclass:: photons_script.script.ATarget

Scripts with functionality
--------------------------

When you do ``target.script(...)`` you may choose to send multiple messages at
the same time or do something based on the reply from particular messages.

To do this, ``photons_script`` provides a few classes for achieving this.

.. autoclass:: photons_script.script.Pipeline

.. autoclass:: photons_script.script.Decider

.. autoclass:: photons_script.script.Repeater
'''
