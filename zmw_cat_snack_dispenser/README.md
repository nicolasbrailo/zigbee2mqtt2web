# Cat Snack Dispenser

Ensures cats don't go hungry. Integrates with Aqara ZNCWWSQ01LM aqara.feeder.acn001.

![](README_screenshot.png)

Cat feeder service will

* Integrate with Telegram, and create a bot command; sending /DispenseCatSnacks will feed your cats
* Send a Telegram notification when food is being dispensed: get a notice when the feeding schedule triggers
* Send a Telegram notification when food is being dispensed when food is dispensed out of schedule: get an alarm if your cats have discovered how to press a button in the unit to get food
* Receive alarms if the unit reports errors, or if the feeding schedule isn't triggering the dispensing of snacks

This service will read a schedule from its config file, and then upload the schedule to the unit, so that this service dies snack dispensing isn't affected. It will also monitor that the unit is respecting the schedule, to ensure that, as a fallback, it can trigger automatic dispensing. If the unit doesn't report any feeding, it will notify you, so that you can manually feed your pets.

