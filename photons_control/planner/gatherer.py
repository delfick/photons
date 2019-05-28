from photons_control.planner.plans import pktkey, Skip, NoMessages
from photons_control.planner.script import WithSender

from photons_app.errors import RunErrors, BadRunWithResults
from photons_app import helpers as hp

from photons_transport.errors import FailedToFindDevice
from photons_transport.base.item import throw_error
from photons_control.script import find_serials

from input_algorithms import spec_base as sb
from collections import defaultdict
import asyncio
import time
import uuid

class PlanInfo:
    """
    Represents an instance of a plan
    """
    def __init__(self, plan, plankey, instance, completed):
        self.plan = plan
        self.plankey = plankey
        self.instance = instance
        self.completed = completed

        self.done = self.completed is not None

    def mark_done(self):
        """Mark this plan as done"""
        self.done = True

    @hp.memoized_property
    def messages(self):
        """
        Get messages from the instance, or if that has no messages, get them
        from the plan
        """
        messages = self.instance.messages
        if not messages:
            messages = self.plan.messages
        return messages

    @property
    def not_done_messages(self):
        """
        Yield messages unless we are already done or have no messages.
        """
        if not self.done:
            messages = self.messages
            if messages and messages not in (Skip, NoMessages):
                yield from messages

class Planner:
    """
    A class for managing getting results from our plans for this serial
    """
    def __init__(self, session, plans, depinfo, serial, error_catcher):
        self.plans = plans
        self.serial = serial
        self.session = session
        self.depinfo = depinfo
        self.error_catcher = error_catcher

    def find_msgs_to_send(self):
        """
        Yield WithSender items for any messages that we need to send to this
        device. We take into account the refresh on the plans to remove any
        cached results. If there are no cached results after this, then we need
        to send this message to the device.

        Note that Planner.completed must not be called before this method.
        """
        sent = set()

        for label, info in sorted(self._by_label.items()):
            for message in info.not_done_messages:
                key = pktkey(message)
                self.session.refresh_received(key, self.serial, info.instance.refresh)

                if not self.session.has_received(key, self.serial) and key not in sent:
                    sent.add(key)
                    yield WithSender(message, key, self.serial)

    async def completed(self):
        """
        Must be used after find_msgs_to_send()

        For each plan:

        * If we already have completed information then yield that
          completed information.
        * If the plan's messages is the NoMessages class then we process it as
          if it's done.

        Finally we pass all known packets into all plans and yield any completed
        results from doing this.
        """
        for label, info in sorted(self._by_label.items()):
            if info.done:
                yield info.completed
            elif info.messages is NoMessages:
                yield await self._process_pkt(NoMessages, label, info)

        async for thing in self._process(self.session.known_packets(self.serial)):
            yield thing

    async def add(self, key, pkt):
        """Add a packet to known packets and process it against all plans"""
        self.session.receive(key, pkt)
        async for thing in self._process([pkt]):
            yield thing

    async def ended(self):
        """
        For all plans that aren't done yet but should be considered done
        after no more messages, we process as if it's done and yield results
        """
        for label, info in sorted(self._by_label.items()):
            if not info.done and info.instance.finished_after_no_more_messages:
                yield await self._process_pkt(NoMessages, label, info)

    @hp.memoized_property
    def _by_label(self):
        """
        Memoize a dictionary of ``{<label>: <PlanInfo instance>}`` for our plans.

        Each PlanInfo is given:

        * plan - the original plan instance
        * instance - the instance of plan.Instance
        * plankey - the result of instance.key
        * completed - The completed result for this plan if we have one

          * If we have cached result for this plan key and serial, then we give
            completed as (serial, label, completed)
          * If the messages for the plan or instance is Skip then this
            will be Skip.
          * Othwerwise it is not completed and we say None.
        """
        by_label = {}

        for label, plan, instance in self._instances():
            plankey = instance.key()
            self.session.refresh_filled(plankey, self.serial, instance.refresh)

            completed = self.session.completed(plankey, self.serial)
            if completed is not None:
                by_label[label] = PlanInfo(plan, plankey, instance, (self.serial, label, completed))
                continue

            if plan.messages is Skip or instance.messages is Skip:
                by_label[label] = PlanInfo(plan, plankey, instance, (self.serial, label, Skip))
                continue

            by_label[label] = PlanInfo(plan, plankey, instance, None)

        return by_label

    def _instances(self):
        """
        Yield (label, plan, instance) tuples for our plans. We take into acount
        depinfo from this Planner instance when we create the plan.Instance
        """
        for label, plan in sorted(self.plans.items()):
            instance = None

            if plan in self.depinfo:
                if self.depinfo[plan]:
                    instance = plan.Instance(self.serial, plan, self.depinfo[plan])
            else:
                instance = plan.Instance(self.serial, plan, None)

            if instance is not None:
                yield label, plan, instance

    async def _process(self, pkts):
        """
        For each packet and for each plan. If the plan is done, ignore the packet
        for that plan, otherwise provide the packet to the plan and if it's done,
        yield (serial, label, result)
        """
        for pkt in pkts:
            for label, info in sorted(self._by_label.items()):
                if info.done:
                    continue

                result = await self._process_pkt(pkt, label, info)

                if result is not None:
                    yield result

    async def _process_pkt(self, pkt, label, info):
        """
        Actually process a packet for this PlanInfo. If instance.process(pkt)
        returns True or if pkt is NoMessages then use instance.info() to get a
        result.

        We then mark the plan as done, cache the result, and return it.
        """
        plankey = info.plankey
        instance = info.instance

        if pkt is NoMessages or instance.process(pkt):
            info.mark_done()

            try:
                result = await instance.info()
            except asyncio.CancelledError:
                raise
            except Exception as error:
                hp.add_error(self.error_catcher, error)
                return

            if plankey is not None:
                self.session.fill(plankey, instance.serial, result)

            return instance.serial, label, result

class Session:
    """
    The cache of results from the Gatherer. It caches the replies to individual
    messages and the final results from plans. It caches per plan/serial.
    """
    def __init__(self):
        self.received = defaultdict(lambda: defaultdict(list))
        self.filled = defaultdict(dict)

    def planner(self, plans, depinfo, serial, error_catcher):
        """Return a Planner instance for managing packets and results"""
        return Planner(self, plans, depinfo, serial, error_catcher)

    def receive(self, key, pkt):
        """
        Cache this reply packet for this key. We use pkt.serial
        for determining what serial this packet came from.

        We also record the current time to use later for determining refreshes
        """
        self.received[pkt.serial][key].append((time.time(), pkt))

    def fill(self, plankey, serial, result):
        """
        Cache the result for this plankey for this serial

        We also record the current time to use later for determining refreshes
        """
        self.filled[plankey][serial] = (time.time(), result)

    def completed(self, plankey, serial):
        """
        If this plan has a cached final result, then return it.

        Otherwise, return None
        """
        if plankey in self.filled and serial in self.filled[plankey]:
            return self.filled[plankey][serial][1]

    def has_received(self, key, serial):
        """Return whether this serial has received results for this key"""
        return bool(self.received[serial].get(key))

    def known_packets(self, serial):
        """Yield all the known reply packets from this serial"""
        for s, pkts in self.received.items():
            if s == serial:
                for ps in pkts.values():
                    for _, p in ps:
                        yield p

    def refresh_received(self, key, serial, refresh):
        """
        Remove received packets given the provided refresh.

        * refresh == 0 - delete the information
        * refresh == True - Delete the information
        * refresh == False - Don't delete anything
        * refresh == integer - Look at the time the packet was received
          if it's been refresh seconds, then remove the result.
        """
        if refresh is False:
            return

        now = time.time()

        for s, infos in self.received.items():
            if s == serial and key in infos:
                if refresh is True:
                    del infos[key]
                else:
                    infos[key] = [(ts, i) for ts, i in infos[key] if now - ts < refresh]
                    if not infos[key]:
                        del infos[key]

    def refresh_filled(self, plankey, serial, refresh):
        """
        Remove the result for this plan given the refresh

        * refresh == 0 - delete the information
        * refresh == True - Delete the information
        * refresh == False - Don't delete anything
        * refresh == integer - Look at the time the result was recorded
          if it's been refresh seconds, then remove the result.
        """
        if refresh is False or plankey not in self.filled or serial not in self.filled[plankey]:
            return

        now = time.time()
        ts, _ = self.filled[plankey][serial]

        if refresh is True or now - ts >= refresh:
            del self.filled[plankey][serial]

        if not self.filled[plankey]:
            del self.filled[plankey]

class Gatherer:
    """
    This class is used by users to gather information from your devices.

    Usage looks like:

    .. code-block:: python

        from photons_control.planner import Gatherer, make_plans

        g = Gatherer(target)
        plans = make_plans("label", "power")

        async for serial, label, info in g.gather(plans, ["d073d5000001", "d073d5000002"]):
            # label will be "label" or "power"
            # serial will be the serial of the device
            # info will be the information associated with that plan
            # Information is sent to you as it is received.

    If you already have an afr, you can provide it when gathering information:

    .. code-block:: python

        async for serial, label, info in g.gather(plans, ["d073d5000001", "d073d5000002"], afr):
            ...

    If you don't supply an afr, one will be created and cleaned up for you.

    If you supply limit as a number to any gather method, then it will be
    converted into a semaphore for you that is shared by all run_with calls.

    There are three methods on this for gathering information:

    * gather - yield (serial, label, info) tuples for each plan as they are
      completed per device
    * gather_all - return {serial: (completed, info)} dictionary where completed
      is a boolean that is True if we received all information for this device
      and info is a dictionary of {label: <information from plan>}
    * gather_per_serial - yield (serial, completed, info) for each device where
      completed and info is the same as for gather_all, but per device.

    All these methods take in the same arguments as run_with, but with an extra
    positional argument before reference which is a dictionary of labels to plan
    instances. You may use the make_plans function to create this dictionary of
    plans.

    For example, the following is the same:

    .. code-block:: python

        from photons_control.planner import make_plans

        # Use the registered power plan
        plans = make_plans("power")

        # Use the power plan manually
        from photons_control.planner.plans import PowerPlan
        plans = make_plans(power=PowerPlan())

    The first form is easier because you don't have to import the plan, but does
    require the plan has been registered. The second form is more flexible as you
    may define a custom refresh when you instantiate the plan and you may also
    give the plan a different label.

    Note that results from gathering will be cached and you may remove this cache
    by calling gatherer.clear_cache()
    """
    def __init__(self, target):
        self.target = target

    @hp.memoized_property
    def session(self):
        return Session()

    def clear_cache(self):
        """Remove all cached results"""
        if hasattr(self, "_session"):
            del self.session

    async def gather(self, plans, reference, args_for_run=sb.NotSpecified, limit=30, error_catcher=None, **kwargs):
        """
        Yield (serial, label, info) information as we get it
        """
        if not plans:
            return

        do_raise = error_catcher is None
        error_catcher = [] if do_raise else error_catcher
        kwargs["error_catcher"] = error_catcher

        if isinstance(limit, int):
            limit = asyncio.Semaphore(limit)
        kwargs["limit"] = limit

        async with self._ensure_afr(self.target, args_for_run) as afr:
            serials, missing = await find_serials(reference, afr, timeout=kwargs.get("find_timeout", 20))

            for serial in missing:
                hp.add_error(error_catcher, FailedToFindDevice(serial=serial))

            class Done:
                pass

            ts = []
            queue = asyncio.Queue()

            for serial in serials:
                ts.append(hp.async_as_background(self._follow(plans, serial, afr, queue, **kwargs)))

            def on_finish(res):
                hp.async_as_background(queue.put(Done))

            if not ts:
                on_finish(None)
            else:
                t = hp.async_as_background(asyncio.wait(ts))
                t.add_done_callback(on_finish)

            while True:
                nxt = await queue.get()
                if nxt is Done:
                    break
                yield nxt

            if do_raise:
                throw_error(serials, error_catcher)

    async def gather_all(self, plans, reference, args_for_run=sb.NotSpecified, **kwargs):
        """Return {serial: (completed, info)} dictionary with all information"""
        results = defaultdict(dict)

        try:
            async for serial, completed, info in self.gather_per_serial(plans, reference, args_for_run, **kwargs):
                results[serial] = (completed, info)
        except asyncio.CancelledError:
            raise
        except RunErrors as error:
            raise BadRunWithResults(results=results, _errors=error.errors)
        except Exception as error:
            raise BadRunWithResults(results=results, _errors=[error])
        else:
            return results

    async def gather_per_serial(self, plans, reference, args_for_run=sb.NotSpecified, **kwargs):
        """yield (serial, completed, info) with all information for each serial"""
        done = set()
        wanted = set(plans)

        result = defaultdict(dict)

        try:
            async for serial, label, info in self.gather(plans, reference, args_for_run, **kwargs):
                result[serial][label] = info

                if set(result[serial]) == wanted:
                    done.add(serial)
                    yield serial, True, result[serial]
                    del result[serial]
        finally:
            for serial, info in sorted(result.items()):
                if serial not in done:
                    yield serial, False, info

    async def _follow(self, plans, serial, afr, queue, **kwargs):
        """
        * get dependency information
        * Determine messages to be sent to devices
        * Yield any completed results we already have
        * Send messages to devices, process results and yield any completed results
        * Complete any plans that are finished after no more messages and yield
          completed results.
        """
        depinfo = await self._deps(plans, serial, afr, **kwargs)
        planner = self.session.planner(plans, depinfo, serial, kwargs["error_catcher"])

        msgs_to_send = list(planner.find_msgs_to_send())

        # Must call completed after getting msgs_to_send
        # to make sure refreshes are taken into account
        # But we'll return them before we send those messages
        # So that those results are immediately available
        async for complete in planner.completed():
            await queue.put(complete)

        if msgs_to_send:
            async for key, pkt in self.target.script(msgs_to_send).run_with(None, afr, **kwargs):
                async for complete in planner.add(key, pkt):
                    await queue.put(complete)

        async for complete in planner.ended():
            await queue.put(complete)

    async def _deps(self, plans, serial, afr, **kwargs):
        """
        Determine if any of the plans have dependent plans and get that information
        and return {plan: {label: information}} so that it may be used by
        _follow to instantiate plan instances with required dependencies.
        """
        deps = {}
        depplan = {}
        depinfo = {}

        for _, plan in sorted(plans.items()):
            d = plan.dependant_info
            if d:
                for l, p in d.items():
                    uid = str(uuid.uuid4())
                    deps[uid] = (plan, l)
                    depplan[uid] = p
                depinfo[plan] = None

        if depplan:
            g = await self.gather_all(depplan, serial, afr, **kwargs)
            if serial in g:
                completed, i = g[serial]
                if completed:
                    for uid, info in i.items():
                        if uid in deps:
                            plan, l = deps[uid]
                        if depinfo.get(plan) is None:
                            depinfo[plan] = {}
                        depinfo[plan][l] = info

        return depinfo

    class _ensure_afr:
        """Used to make sure we have an afr"""
        def __init__(self, target, afr):
            self.afr = afr
            self.target = target

        async def __aenter__(self):
            if self.afr is sb.NotSpecified:
                self.own_afr = True
                self.afr = await self.target.args_for_run()
            return self.afr

        async def __aexit__(self, exc_type, exc, tb):
            if hasattr(self, "own_afr") and self.afr is not sb.NotSpecified:
                await self.target.close_args_for_run(self.afr)
