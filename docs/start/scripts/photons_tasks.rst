.. _photons_task_class:

Photons Task Class
==================

The tasks that are registered with the ``photons_app.tasks.task_register`` will
become instances of the ``photons_app.tasks.Task`` class.

.. autoclass:: photons_app.tasks.Task

The ``task_register`` has on it some helpful methods for creating fields on a
task:

.. code-block:: python

    from photons_app.tasks import task_register as task

    from delfick_project.norms import sb


    @task
    class my_amazing_task(task.Task):

        # This will use ``collector.target_register.resolve`` to get a target
        # object for use in the task
        # 
        # ``task.requires_target`` will ensure that if no ``t1`` was provided
        # then an error will be raised complaining it is required
        #
        # ``task.provides_target`` will mean ``t2`` will be given the value
        # ``delfick_project.norms.sb.NotSpecified`` if no value was given.
        #
        # The options to both include ``target_types`` which is a list of type
        # that are valid; and ``target_names`` which is a list of target names
        # that are valid.
        t1 = task.requires_target(target_types=["lan"])
        t2 = task.provides_target(target_types=["lan"])

        # These helpers are for the reference
        # The following two lines are equivalent
        r1 = task.provides_reference()
        r1 = task.Field(sb.any_spec(), wrapper=sb.optional_spec)

        # And these two are equivalent
        r1 = task.requires_reference()
        r1 = task.Field(sb.any_spec(), wrapper=sb.required_spec)

        # Both of them however also have a ``special`` option
        # where, if there is a value that can be used, photons uses
        # ``collector.reference_object(val)`` on that value
        # Note that for ``provides_reference``, this means not specifying a value
        # will get us a ``photons_app.special.FoundSerials`` object.
        r2 = task.requires_reference(special=True)
        r3 = task.provides_reference(special=True)

        # Finally these two lines are equivalent
        a = task.provides_artifact()
        a = task.Field(sb.any_spec, wrapper=sb.optional_spec)

        async def execute_task(self, **kwargs):
            # In here ``self`` will have all the values above, so

            # self.t1 and self.t2 would be LanTarget objects
            # self.r1 would be either sb.NotSpecified or a string
            # self.r2 and self.r3 would be SpecialReference objects
            # self.a would be either sb.NotSpecified or a string

            # And also self.collector, self.photons_app and self.task_holder
            ...

Life cycle
----------

The life cycle of the task depends on whether you inherit from ``task.Task`` or
``task.GracefulTask``.

For ``task.Task``:

1. self.task_holder is initialized
2. execute_task is called

   * Ends if the function returns or raises an exception
   * Ends if ``photons_app.final_future`` is resolved
   * Ends on unix machines if the application receives a SIGTERM signal
   * Ends if the program receives a KeyboardInterrupt (ctrl-c)
3. The asyncio task representing execute_task may not be finished yet when
   any of those end conditions are met. Because it is not a GracefulTask photons
   tell that asyncio task to cancel, which causes an ``asyncio.CancelledError``
   to be raised in the code
4. The asyncio task is waited to finish any exception handlers or finally
   blocks
5. The post method is called
6. Photons waits for the ``task_holder`` to finish any remaining asyncio
   tasks. Note that it is up to the programmer to ensure these tasks finish
   if ``photons_app.final_future`` is resolved.
7. The functions in the ``photons_app.cleaners`` array are called and errors
   from those are ignored
8. Any photons target that was used is told to cleanup any resources
9. Any remaining tasks and async generators are closed and cleaned up, and
   the asyncio loop photons used is closed and deleted

For ``task.GracefulTask``:

1. self.task_holder is initialized
2. execute_task is called
   
   * Ends if the function returns or raises an exception
   * Ends if ``photons_app.final_future`` is resolved
   * Ends if the program receives a KeyboardInterrupt (ctrl-c)
   * **difference** SIGTERM will resolve ``photons_app.graceful_final_future``
     rather than ``photons_app.final_future``.
3. The asyncio task representing execute_task may not be finished yet when
   any of those end conditions are met.
4. **difference** Because it's a GracefulTask, the
   assumption is that if graceful_final_future is resolved then the task
   will shut itself down without needing to be cancelled. So photons ensures
   that ``graceful_final_future`` is resolved, and leaves the asyncio task
   for ``execute_task`` to continue without being cancelled.
5. The post method is called
6. Photons waits for the ``task_holder`` to finish any remaining asyncio
   tasks. Note that it is up to the programmer to ensure these tasks finish
   if ``photons_app.graceful_final_future`` is resolved.
7. **difference** ``photons_app.final_future`` is cancelled if it remains
   unresolved and ``photons_app.graceful_final_future`` was resolved with
   a cancellation or SIGTERM. Otherwise final_future is resolved how
   graceful_final_future has been resolved.

   The functions in the ``photons_app.cleaners`` array are then called and
   errors from those are ignored
8. Any photons target that was used is told to cleanup any resources
9. Any remaining tasks and async generators are closed and cleaned up, and
   the asyncio loop photons used is closed and deleted

The task will raise the following exceptions based on these events:

* SIGTERM ensures a ``photons_app.errors.ApplicationStopped`` is raised
  unless ``GracefulTask`` was used.
* KeyboardInterrupt raises ``photons-app.errors.UserQuit``
* A ``asyncio.CancelledError`` being raised will result in
  ``photons_app.errors.ApplicationCancelled`` being raised.

.. note:: once the ``post`` handle is called, any exception from ``execute_task``
  or ``post`` will be passed onto the ``task_holder`` and in affect cancel
  anything on it.

  The exception to this is tasks using ``GracefulTask`` will not pass on an
  ``ApplicationStopped`` exception, which is what the ``execute_task`` will
  raise upon getting a ``SIGTERM``.
