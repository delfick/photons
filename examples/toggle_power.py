#!/usr/bin/python3 -ci=__import__;o=i("os");s=i("sys");a=s.argv;p=o.path;y=p.join(p.dirname(a[1]),".python");o.execv(y,a)

from photons_app.executor import library_setup
from photons_app.special import FoundSerials

from photons_control.transform import PowerToggle

from delfick_project.logging import setup_logging


async def doit(collector):
    lan_target = collector.resolve_target("lan")
    await lan_target.send(PowerToggle(), FoundSerials())


if __name__ == "__main__":
    setup_logging()
    collector = library_setup()
    collector.run_coro_as_main(doit(collector))
