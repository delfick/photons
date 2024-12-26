import os
import subprocess
import sys

this_dir = os.path.dirname(__file__)
example_dir = os.path.join(this_dir, "example")


class TestRunningAMainline:
    def test_it_works(self):
        process = subprocess.run(
            [
                sys.executable,
                os.path.join(example_dir, "runner.py"),
                "do_the_thing",
                "--config",
                os.path.join(example_dir, "config.yml"),
            ],
            capture_output=True,
        )

        assert process.returncode == 0, f"STDERR: {process.stderr}\nSTDOUT:{process.stdout}"
        assert process.stdout.decode().strip() == "8AC5B50C-7278-46F8-A164-9A75E310A466.39786789-9B56-475C-8F26-D04CE48EB206"

    def test_it_works_with_old_an_action(self):
        process = subprocess.run(
            [
                sys.executable,
                os.path.join(example_dir, "runner.py"),
                "do_the_thing_with_old_an_action",
                "--config",
                os.path.join(example_dir, "config.yml"),
            ],
            capture_output=True,
        )

        assert process.returncode == 0, f"STDERR: {process.stderr}\nSTDOUT:{process.stdout}"
        assert process.stdout.decode().strip() == "8AC5B50C-7278-46F8-A164-9A75E310A466.39786789-9B56-475C-8F26-D04CE48EB206"
