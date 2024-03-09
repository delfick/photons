import os
import runpy
import sys
from pathlib import Path

deps_dir = Path(__file__).parent / "deps"
if not deps_dir.exists():
    deps_dir.mkdir()

if not (deps_dir / "venvstarter.py").exists():
    if "PIP_REQUIRE_VIRTUALENV" in os.environ:
        del os.environ["PIP_REQUIRE_VIRTUALENV"]
    os.system(f"{sys.executable} -m pip install venvstarter -t {deps_dir}")

sys.path.append(str(deps_dir))
venvstarter_module = runpy.run_path(str(deps_dir / "venvstarter.py"))
sys.path.pop()

wanted_version = "0.12.2"

upgrade = False
VERSION = venvstarter_module.get("VERSION")
if VERSION is None:
    upgrade = True
else:
    Version = venvstarter_module["Version"]
    if Version(VERSION) != Version(wanted_version):
        upgrade = True

if upgrade:
    os.system(f"{sys.executable} -m pip install -U 'venvstarter=={wanted_version}' -t {deps_dir}")

manager = runpy.run_path(str(deps_dir / "venvstarter.py"))["manager"]
