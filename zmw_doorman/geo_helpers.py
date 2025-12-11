""" Helpers depending on location (eg to determine sunries) """

from astral.sun import sun as astral_sun
import astral
import datetime


def is_sun_out(lat, lon, tolerance_mins=45):
    """ Returns true if there is plenty of light outside """
    day = astral_sun(astral.Observer(lat, lon), date=datetime.date.today())
    tolerance = datetime.timedelta(minutes=tolerance_mins)
    sunrise = day['sunrise'] + tolerance
    sunset = day['sunset'] - tolerance
    ahora = datetime.datetime.now(day['sunset'].tzinfo)
    sun_out = sunrise < ahora < sunset
    return sun_out


def late_night(latlon, late_night_start_hour):
    """ Returns true if it's dark outside, and also it's late at night """
    day = astral_sun(astral.Observer(*latlon), date=datetime.date.today())
    sunset = day['dusk']
    next_sunrise = day['sunrise'] + datetime.timedelta(hours=24)
    ahora = datetime.datetime.now(day['sunset'].tzinfo)
    if ahora < sunset:
        return False
    if sunset < ahora < next_sunrise:
        local_hour = datetime.datetime.now().hour  # no tz, just local hour
        if local_hour >= late_night_start_hour or local_hour <= next_sunrise.hour:
            return True
    return False

