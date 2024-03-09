import os

for filename in os.listdir(os.path.dirname(__file__)):
    if not filename.startswith("_") and filename.endswith(".py"):
        name = filename[:-3]
        __import__(f"interactor.commander.commands.{name}")
