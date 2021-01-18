"""Code to interface with the SMA inverters and return the results."""

import asyncio
import logging
import dateutil
from dateutil.rrule import rrule, MONTHLY
import datetime
import copy
import clearsky

from pprint import pprint

from inverter import Inverter
from influx import InfluxDB

from astral.sun import sun
from astral import LocationInfo

from configuration import INVERTERS
from configuration import SITE_LATITUDE, SITE_LONGITUDE, TIMEZONE, SITE_NAME, SITE_REGION
from configuration import SITE_AZIMUTH, SITE_TILT, SITE_PANEL_AREA, SITE_PANEL_EFFICIENCY
from configuration import APPLICATION_LOG_LOGGER_NAME


logger = logging.getLogger(APPLICATION_LOG_LOGGER_NAME)

START_MONTH = 1
START_YEAR  = 2020


def diff_month(d1, d2):
    return (d1.year - d2.year) * 12 + d1.month - d2.month


class Site:
    """Class to describe a PV site with one or more inverters."""
    def __init__(self, session):
        """Create a new Site object."""
        self._influx = InfluxDB()
        self._inverters = []
        for inverter in INVERTERS:
            self._inverters.append(Inverter(inverter["name"], inverter["ip"], inverter["user"], inverter["password"], session))

    async def start(self):
        """Initialize the Site object."""
        self._influx.start()
        results = await asyncio.gather(*(inverter.initialize() for inverter in self._inverters))
        return False not in results

    async def stop(self):
        """Shutdown the Site object."""
        await asyncio.gather(*(inverter.close() for inverter in self._inverters))
        self._influx.stop()

    async def populate_months(self):
        today = datetime.datetime.now()
        start_date = datetime.datetime(START_YEAR, START_MONTH, 1)
        inverters = await asyncio.gather(*(inverter.read_history(int(start_date.timestamp()), int(today.timestamp())) for inverter in self._inverters))
        first = inverters[0][1]
        last = datetime.datetime.fromtimestamp(first.get('t'))
        months = list(rrule(freq=MONTHLY, count=diff_month(last, start_date) + 1, dtstart=start_date, bymonthday=(1,)))

        results = []
        for inverter in inverters:
            inv = [{'inverter': inverter[0]['inverter']}]
            for month in months:
                t = int(month.timestamp())
                inv.append({'t': t, 'v': 0})
            results.append(inv)

        site = copy.deepcopy(results[0])
        site[0]['inverter'] = 'site'        
        results.append(site)
        self._influx.write_history(results)

    async def populate_days(self):
        now = datetime.datetime.now()
        start = datetime.datetime.combine(datetime.date.today().replace(year=START_YEAR, month=START_MONTH, day=1), datetime.time(0, 0)) - datetime.timedelta(days=1)
        stop = datetime.datetime.combine(now.date(), datetime.time(0, 0))
        inverters = await asyncio.gather(*(inverter.read_history(int(start.timestamp()), int(stop.timestamp())) for inverter in self._inverters))
        total = {}
        for inverter in inverters:
            for i in range(1, len(inverter)):
                t = inverter[i]['t']
                v = inverter[i]['v']
                if v is None:
                    if i > 1:
                        inverter[i]['v'] = inverter[i-1]['v']
                    else:
                        inverter[i]['v'] = inverter[i+1]['v']
                    v = inverter[i]['v']
                if t in total:
                    total[t] += v
                else:
                    total[t] = v

        site_total = []
        for t, v in total.items():
            site_total.append({'t': t, 'v': v})
        site_total.insert(0, {'inverter': 'site'})
        inverters.append(site_total)
        self._influx.write_history(inverters)
    
    async def irradiance_today(self):
        # Create location object to store lat, lon, timezone
        site = clearsky.site_location(SITE_LATITUDE, SITE_LONGITUDE, tz=TIMEZONE)
        siteinfo = LocationInfo(SITE_NAME, SITE_REGION, TIMEZONE, SITE_LATITUDE, SITE_LONGITUDE)
        tzinfo = dateutil.tz.gettz(TIMEZONE)
        astral = sun(observer=siteinfo.observer, tzinfo=tzinfo)
        dawn = astral['dawn']
        dusk = astral['dusk'] + datetime.timedelta(minutes=10)
        start = datetime.datetime(dawn.year, dawn.month, dawn.day, dawn.hour, int(int(dawn.minute/10)*10))
        stop = datetime.datetime(dusk.year, dusk.month, dusk.day, dusk.hour, int(int(dusk.minute/10)*10))

        # Get irradiance data for today and convert to InfluxDB line protocol
        irradiance = clearsky.get_irradiance(site=site, start=start.strftime("%Y-%m-%d %H:%M:00"), end=stop.strftime("%Y-%m-%d %H:%M:00"), tilt=SITE_TILT, azimuth=SITE_AZIMUTH, freq='10min')
        lp_points = []
        for point in irradiance:
            t = point['t']
            v = point['v'] * SITE_PANEL_AREA * SITE_PANEL_EFFICIENCY
            lp = f'prediction,inverter="site" production={round(v, 1)} {t}'
            lp_points.append(lp)
        self._influx.write_points(lp_points)

    async def run(self):
        await asyncio.gather(
            self.populate_months(),
            self.populate_days(),
            self.irradiance_today(),
        )
