VERSION = "0.5.11"


def run_pytest():
    import pytest
    import sys

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
