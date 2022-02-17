import importlib
import sys
import os

try:
    __import__("venvstarter")
    have_venvstarter = True
except ImportError:
    have_venvstarter = False

if not have_venvstarter:
    os.system(f"{sys.executable} -m pip install venvstarter")
    importlib.reload(__import__("venvstarter"))

venvstarter_version = None
if have_venvstarter:
    venvstarter = __import__("venvstarter")
    if hasattr(venvstarter, "VERSION") and hasattr(venvstarter, "Version"):
        venvstarter_version = venvstarter.Version(venvstarter.VERSION)
    else:
        venvstarter_version = None

wanted_version = "0.11.0"
if venvstarter_version is None or venvstarter_version < venvstarter.Version(wanted_version):
    os.system(f"{sys.executable} -m pip install 'venvstarter>={wanted_version}'")
    importlib.reload(__import__("venvstarter"))
