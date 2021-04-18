import importlib
import os


for module in os.listdir(os.path.join(os.path.dirname(__file__), "registered")):
    if module.startswith("_") or module.startswith("."):
        continue
    if module.endswith(".py"):
        module = module[:-3]

    importlib.import_module(f"interactor.tasks.registered.{module}")
