from datetime import datetime
import json
import logging
import os

from .schedule import Schedule, ShouldBeOn

log = logging.getLogger(__name__)

def _ignore_template_change_cb(new, old):
    # This may be invoked when a template schedule is built, or when there is a slot change
    # that coincides with whatever slot the template thinks is active
    pass

class ScheduleBuilder:
    def __init__(self, state_change_cb, persist_file, clock=None):
        self._active = Schedule(state_change_cb, clock)
        self._persist_file = persist_file

        class _NoClock:
            def __init__(self):
                self._now = datetime.now()
                self._now = self._now.replace(hour=0)
                self._now = self._now.replace(minute=0)
            def now(self):
                return self._now

        self._template = Schedule(_ignore_template_change_cb, _NoClock())

        if self._persist_file is None:
            log.warning("No persist file specified, changes to schedule are ephemeral")
            self.reset_template_to_default()
        elif not os.path.exists(self._persist_file):
            log.info("No schedule persisted, creating new one at %s", self._persist_file)
            self.reset_template_to_default()
        elif not os.path.isfile(self._persist_file):
            log.error("Specified persist path %s exists, but isn't a file. Changes to schedule won't be saved.", self._persist_file)
            self._persist_file = None
        else:
            # persist_file exists, and is a file
            log.info("Reading active schedule and template from %s", self._persist_file)
            with open(self._persist_file, "r") as fp:
                self.from_json(fp.read())

    def active(self):
        return self._active

    def get_slot(self, *a, **kv):
        return self._template.get_slot(*a, **kv)

    def set_slot(self, hour, minute, should_be_on, reason="Scheduled"):
        ret = self._template.set_slot(hour, minute, should_be_on, reason)
        self.save_state()
        return ret

    def tick(self, *a, **kv):
        slots_changed = self._active.tick(*a, **kv)
        if slots_changed > 1:
            log.error("Tick() advanced more than one slot. Template may not be applied correctly now.")
        if slots_changed > 0:
            hr, mn = self._active.get_last_slot_hr_mn()
            slot = self._template.get_slot(hr, mn)
            self._active.set_slot(hr, mn, slot.should_be_on, slot.reason)
        self.save_state()
        return slots_changed

    def reset_template_to_default(self):
        for hr in range(0, 24):
            for mn in range(0, 60, 15):
                self.set_slot(hr, mn, ShouldBeOn.Never, "Scheduled")
        self.save_state()

    def apply_template_to_today(self):
        for hr in range(0, 24):
            for mn in range(0, 60, 15):
                tmpl = self.get_slot(hr, mn)
                self._active.set_slot(hr, mn, tmpl.should_be_on, tmpl.reason)
        self.save_state()

    def save_state(self):
        if self._persist_file is None:
            return
        with open(self._persist_file, "w") as fp:
            fp.write(self.as_json())

    def as_json(self):
        return json.dumps({
            'active': list(map(lambda o: o.dictify(), self._active._sched)),
            'template': list(map(lambda o: o.dictify(), self._template._sched)),
        })

    def from_json(self, tjson):
        try:
            tdict = json.loads(tjson)
        except json.decoder.JSONDecodeError:
            log.error("Can't parse supplied serialized schedule, ignoring")
            self._template = Schedule(_ignore_template_change_cb)
            return None

        def _apply(serialized, restore):
            for serslot in serialized:
                try:
                    hr, mn, should_be_on, reason = serslot['hour'], serslot['minute'], serslot['should_be_on'], serslot['reason']
                    restore.set_slot(hr, mn, should_be_on, reason)
                except KeyError:
                    log.warning("Ignoring invalid template slot: %s", serslot)

        if 'active' in tdict and type(tdict['active']) == list:
            _apply(tdict['active'], self._active)
        else:
            log.error("Serialized schedule has no active schedule to deserialize")

        if 'template' in tdict and type(tdict['template']) == list:
            _apply(tdict['template'], self._template)
        else:
            log.error("Serialized schedule has no active template to deserialize")

        # We should save the state, but if something fails this may start a crashloop. If loading
        # succeeds, though, tick() will be called in a few minutes, and the state will be saved
        # then. If something makes the app crash before 5 minutes, losing the active schedule is
        # probably a comparatively minor problem.
        # self.save_state()
