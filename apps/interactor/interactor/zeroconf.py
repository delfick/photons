import logging
import socket

from delfick_project.norms import dictobj, sb
from interactor import VERSION, ZEROCONF_TYPE
from photons_app import helpers as hp
from zeroconf import IPVersion
from zeroconf.asyncio import AsyncServiceInfo, AsyncZeroconf

log = logging.getLogger("interactor.zeroconf")


class ZeroconfRegisterer(hp.AsyncCMMixin):
    def __init__(self, options, ts, host, port, sender, finder):
        self.ts = ts
        self.host = host
        self.port = port
        self.sender = sender
        self.finder = finder
        self.options = options

    async def start(self):
        if self.options.enabled:
            log.info(
                hp.lc(
                    "Enabling Zeroconf service discovery",
                    hostname=f"{socket.getfqdn()}.",
                    ipaddress=self.options.ip_address,
                    port=self.port,
                    sd=self.options.name,
                )
            )
            self.zeroconf = AsyncZeroconf(ip_version=IPVersion.V4Only)
            await self.zeroconf.async_register_service(await self.get_interactor_service_info())

    async def finish(self, exc_typ=None, exc=None, tb=None):
        if not hasattr(self, "zeroconf"):
            return

        # Ensure they both run and aren't interrupted by errors
        t1 = self.ts.add(self.zeroconf.async_unregister_all_services())
        await hp.wait_for_all_futures(t1, name="ZeroConfRegisterer::finish")
        t2 = self.ts.add(self.zeroconf.async_close())
        await hp.wait_for_all_futures(t2, name="ZeroConfRegisterer::finish")

        # Raise any exceptions
        await t1
        await t2

    async def get_interactor_service_info(self):
        return AsyncServiceInfo(
            ZEROCONF_TYPE,
            f"{self.options.name}.{ZEROCONF_TYPE}",
            addresses=[socket.inet_aton(self.options.ip_address)],
            port=self.port,
            server=f"{socket.getfqdn()}.",
            properties={"version": VERSION, "md": "Photons Interactor"},
        )


class ip_address_spec(sb.Spec):
    def normalise(self, meta, val):
        if val is sb.NotSpecified:
            """Get the currently active/routing IP address of the local machine."""
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("10.255.255.255", 1))
                val = s.getsockname()[0]
            except Exception:
                val = "127.0.0.1"
            finally:
                s.close()

        return sb.string_spec().normalise(meta, val)


class Zeroconf(dictobj.Spec, hp.AsyncCMMixin):
    enabled = dictobj.Field(sb.boolean, default=False, help="Whether zeroconf is enabled")

    ip_address = dictobj.Field(
        format_into=ip_address_spec,
        help="The IP address of this computer. Defaults to automatic discovery.",
    )

    name = dictobj.Field(
        format_into=sb.string_spec,
        default=socket.getfqdn().split(".")[0],
        help="The name of this Photons Interactor instance. Defaults to the hostname.",
    )

    async def start(self, ts, host, port, sender, finder):
        self.register = ZeroconfRegisterer(self, ts, host, port, sender, finder)
        await self.register.start()

    async def finish(self, exc_typ=None, exc=None, tb=None):
        if hasattr(self, "register"):
            await self.register.finish()
            del self.register
