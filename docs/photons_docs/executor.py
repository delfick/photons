import json
import logging

from photons_app import helpers as hp
from photons_app.executor import App

log = logging.getLogger("photons_docs.executor")


class App(App):
    cli_description = "Documentation!"

    def execute(self, args_obj, args_dict, extra_args, logging_handler):
        data = {"for_docs": True, "photons_app": {"addons": {"lifx.photons": ["__all__"]}}}

        with hp.a_temp_file() as fle:
            fle.write(json.dumps(data).encode())
            fle.flush()
            return super(App, self).execute(
                args_obj, args_dict, extra_args, logging_handler, extra_files=[fle.name]
            )


main = App.main
if __name__ == "__main__":
    main()
