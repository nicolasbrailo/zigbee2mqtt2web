""" Helpers depending on location (eg to determine sunries) """

from astral.sun import sun as astral_sun
import astral
import datetime


def light_outside(latlon):
    """ Returns true if there is plenty of light outside """
    day = astral_sun(astral.Observer(*latlon), date=datetime.date.today())
    tolerance = datetime.timedelta(minutes=45)
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

# How many discrete steps the redshift process will have
REDSHIFT_STEPS_CNT = 5
# Redshfit is done from sunset to dusk * mult. Eg if dusk-sunset = 1h and mult=2, then redshift
# will be done in a period of 2 hours
REDSHIFT_DURATION_MULT = 2
# Redshift will start at sunset-(duration*offset). Eg if sunset=17.00, duration=1h and offset=.5,
# then redshift will start at 16.30 and last until 17.30
REDSHIFT_START_OFFSET = .7

# Offer a redshift % range, to allow excluding way too bright settings
REDSHIFT_START_PCT = 20
REDSHIFT_END_PCT = 80

def todays_redshift_steps(latlon, on_date=datetime.date.today()):
    """ Return a list of times and %s to gradually redshift ligths as sun goes down """
    # The time in the evening when the sun is about to disappear below the horizon (asuming a location with no obscuring features)
    sunset = astral_sun(astral.Observer(*latlon), date=on_date)['sunset']
    # The time in the evening when the sun is a specific number of degrees below the horizon.
    dusk = astral_sun(astral.Observer(*latlon), date=on_date)['dusk']

    redshift_duration = REDSHIFT_DURATION_MULT * (dusk - sunset)
    redshift_start = sunset - (REDSHIFT_START_OFFSET * redshift_duration)
    step_duration = redshift_duration / REDSHIFT_STEPS_CNT
    redshift_range = REDSHIFT_END_PCT - REDSHIFT_START_PCT
    redshift_steps = []
    for i in range(1, REDSHIFT_STEPS_CNT+1):
        red_pct = REDSHIFT_START_PCT + (redshift_range * i / REDSHIFT_STEPS_CNT)
        t = redshift_start + i*step_duration
        redshift_steps.append((t, red_pct))
    return redshift_steps
