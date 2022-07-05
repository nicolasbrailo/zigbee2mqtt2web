from astral.sun import sun as astral_sun
import astral
import datetime
import time

def light_outside(lat, lon):
    t = astral_sun(astral.Observer(lat, lon), date=datetime.date.today())
    tolerance = datetime.timedelta(minutes=45)
    sunrise = t['sunrise'] + tolerance
    sunset = t['sunset'] - tolerance
    ahora = datetime.datetime.now(t['sunset'].tzinfo)
    sun_out = ahora > sunrise and ahora < sunset
    return sun_out

def late_night(lat, lon, late_night_start_hour):
    t = astral_sun(astral.Observer(lat, lon), date=datetime.date.today())
    sunset = t['dusk']
    next_sunrise = t['sunrise'] + datetime.timedelta(hours=24)
    ahora = datetime.datetime.now(t['sunset'].tzinfo)
    if ahora < sunset:
        return False
    if ahora > sunset and ahora < next_sunrise:
        local_hour = datetime.datetime.now().hour # no tz, just local hour
        if local_hour >= late_night_start_hour or local_hour <= next_sunrise.hour:
            return True
    return False

