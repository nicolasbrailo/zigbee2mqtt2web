from zzmw_lib.logs import build_logger

log = build_logger("DispenseTracking")

class DispenseTracking:
    def __init__(self, snack_history, schedule):
        self._last_portions_per_day = None
        self._last_weight_per_day = None
        self._snack_history = snack_history
        self._schedule = schedule

    def get_schedule(self):
        return self._schedule.get_schedule()

    def get_history(self):
        return self._snack_history.get_history()

    def check_dispensing(self, cat_feeder):
        """ Checks if cat_feeder is dispensing food.
        Behaviour:
        * When someone presses the button in the unit, it will broadcast a message with feeding_source=manual
        * When someone triggers the unit remotely (eg through z2m) it will broadcast feeding_source=remote
        * When the unit triggers due to a schedule it will broadcast feeding_source=schedule
        * Once dispensing, the unit will broadcast messages until serving is complete. This seems to be:
          until portions_per_day and weight_per_day increases:
          - portions should increase by feeding_size
          - weight_per_day should increase by feeding_size * portion_weight
          - EG: if portion_weight was configured by the user to be 7, and feeding_size was configured to 2,
            then portions_per_day+=2 and weight_per_day+=14
        """
        any_unset = (self._last_weight_per_day is None) or (self._last_portions_per_day is None)
        any_set = (self._last_weight_per_day is not None) or (self._last_portions_per_day is not None)
        if any_unset and any_set:
            # Something weird happened if weight and portions are not in sync, but we can't do much other than log
            log.error("Error: last_portions_per_day unset, last_weight_per_day is %s: "
                      "these should always be in sync", self._last_weight_per_day)

        if cat_feeder.get('portions_per_day') is None or cat_feeder.get('weight_per_day') is None:
            if any_unset:
                # This service is probably booting up, so we don't have a previous value for the unit state, and we
                # haven't received an updated value from Z2M yet either.
                pass
            else:
                log.debug("Message to/from '%s' missing portions_per_day or weight_per_day; "
                          "this message is likely not from the unit, will ignore.",
                          cat_feeder.name)
            return

        day_changed = self._last_portions_per_day is not None and \
                          cat_feeder.get('portions_per_day') < self._last_portions_per_day
        if any_unset or day_changed:
            # Service just started and unit is reporting for the first time, or first report of the day
            self._last_portions_per_day = cat_feeder.get('portions_per_day')
            self._last_weight_per_day = cat_feeder.get('weight_per_day')
            log.info("Received first report from '%s', last_portions_per_day=%s last_weight_per_day=%s",
                     cat_feeder.name, self._last_portions_per_day, self._last_weight_per_day)
            return

        if cat_feeder.get('portions_per_day') == self._last_portions_per_day:
            # Unit bcasted a message, but it's not dispensing food. Keep weight in sync
            # in case it resets separately from portions (e.g., during day change).
            self._last_weight_per_day = cat_feeder.get('weight_per_day')
            return

        portions_dispensed = cat_feeder.get('portions_per_day') - self._last_portions_per_day
        self._last_portions_per_day += portions_dispensed
        weight_dispensed = cat_feeder.get('weight_per_day') - self._last_weight_per_day
        self._last_weight_per_day = cat_feeder.get('weight_per_day')

        # Sanity check: negative weight indicates a missed day reset
        if weight_dispensed < 0:
            log.warning("Detected negative weight_dispensed (%s), likely missed day reset. "
                        "Resetting weight tracking.", weight_dispensed)
            weight_dispensed = None

        if cat_feeder.get('feeding_source') == 'remote':
            # Someone requested dispensing over Z2M. If it's us, ACK the request in the history. If it's not us,
            # log it as an unauthorized food dispensing attempt.
            self._snack_history.register_zigbee_dispense(portions_dispensed, weight_dispensed)
            return

        if cat_feeder.get('feeding_source') == 'schedule':
            self._schedule.register_schedule_triggered(portions_dispensed, weight_dispensed)
            return

        if cat_feeder.get('feeding_source') == 'manual':
            # Someone pressed the unit to manually trigger dispensing.
            source = 'Unit button'
        else:
            # Something unknown triggered feeding
            source = 'Mystery!'
        self._snack_history.register_dispense(source, portions_dispensed, weight_dispensed)

    def request_feed_now(self, source, cat_feeder, serving_size):
        """ Start a feed request, which needs to be fulfilled later via check_dispensing. Returns True if the
        dispense request shouldn't be started (eg there is one in flight """
        if cat_feeder is None:
            self._snack_history.register_error(source, "Snack dispensing unit not discovered yet")
            return False

        if not self._snack_history.register_request(source, serving_size):
            return False

        # Set or get serving size
        if serving_size is not None:
            cat_feeder.set("serving_size", serving_size)
        else:
            log.warning("'%s' will dispense food using an unknown serving size", cat_feeder.name)
        cat_feeder.set("feed", "START")

        return True
