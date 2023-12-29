VERSION = "0.7.1"


def run_pytest():
    import sys

    import pytest

    class EditConfig:
        @pytest.hookimpl(hookwrapper=True)
        def pytest_cmdline_parse(pluginmanager, args):
            args.extend(
                [
                    "--tb=short",
                    "-o",
                    "console_output_style=classic",
                    "-o",
                    "default_alt_async_timeout=1",
                ]
            )
            yield

    sys.exit(pytest.main(plugins=[EditConfig()]))
