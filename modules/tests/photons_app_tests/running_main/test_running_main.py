# coding: spec

import os
import subprocess
import sys

this_dir = os.path.dirname(__file__)
example_dir = os.path.join(this_dir, "example")

describe "Running a mainline":
    it "works":
        process = subprocess.run(
            [
                sys.executable,
                os.path.join(example_dir, "runner.py"),
                "do_the_thing",
                "--config",
                os.path.join(example_dir, "config.yml"),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        assert process.returncode == 0, "STDERR: {}\nSTDOUT:{}".format(
            process.stderr, process.stdout
        )
        assert (
            process.stdout.decode().strip()
            == "8AC5B50C-7278-46F8-A164-9A75E310A466.39786789-9B56-475C-8F26-D04CE48EB206"
        )

    it "works with old an_action":
        process = subprocess.run(
            [
                sys.executable,
                os.path.join(example_dir, "runner.py"),
                "do_the_thing_with_old_an_action",
                "--config",
                os.path.join(example_dir, "config.yml"),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        assert process.returncode == 0, "STDERR: {}\nSTDOUT:{}".format(
            process.stderr, process.stdout
        )
        assert (
            process.stdout.decode().strip()
            == "8AC5B50C-7278-46F8-A164-9A75E310A466.39786789-9B56-475C-8F26-D04CE48EB206"
        )
