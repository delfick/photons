from photons_app.tasks import task_register

# Backwards compatibility with how tasks used to be registered
an_action = task_register.from_function
