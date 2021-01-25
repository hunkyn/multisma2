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

    async def populate_days(self):
        now = datetime.datetime.now()
        start = datetime.datetime.combine(datetime.date.today().replace(year=START_YEAR, month=START_MONTH, day=1), datetime.time(0, 0)) - datetime.timedelta(days=1)
        stop = datetime.datetime.combine(now.date(), datetime.time(0, 0))
        inverters = await asyncio.gather(*(inverter.read_history(int(start.timestamp()), int(stop.timestamp())) for inverter in self._inverters))

        for inverter in inverters:
            t = inverter[1]['t']
            dt = datetime.datetime.fromtimestamp(t)
            date = datetime.date(year=START_YEAR, month=START_MONTH, day=1)
            end_date = datetime.date(year=dt.year, month=dt.month, day=dt.day)
            delta = datetime.timedelta(days=1)
            while date < end_date:
                newtime = datetime.datetime.combine(date, datetime.time(0, 0))
                inverter.append({'t': int(newtime.timestamp()), 'v': 0})
                date += delta

        total = {}
        count = {}
        for inverter in inverters:
            last_non_null = None
            for i in range(1, len(inverter)):
                t = inverter[i]['t']
                v = inverter[i]['v']
                if not v:
                    if not last_non_null:
                        continue
                    v = last_non_null
                total[t] = v + total.get(t, 0)
                count[t] = count.get(t, 0) + 1
                last_non_null = v

        site_total = []
        for t, v in total.items():
            if count[t] == len(inverters):
                site_total.append({'t': t, 'v': v})
        site_total.insert(0, {'inverter': 'site'})
        inverters.append(site_total)
        self._influx.write_history(inverters, 'production/today')
    
    async def populate_irradiance(self):
        # Create location object to store lat, lon, timezone
        site = clearsky.site_location(SITE_LATITUDE, SITE_LONGITUDE, tz=TIMEZONE)
        siteinfo = LocationInfo(SITE_NAME, SITE_REGION, TIMEZONE, SITE_LATITUDE, SITE_LONGITUDE)
        tzinfo = dateutil.tz.gettz(TIMEZONE)

        delta = datetime.timedelta(days=1)
        date = datetime.date(year=2021, month=1, day=1)
        end_date = datetime.date.today() + delta

        lp_points = []
        while date < end_date:
            astral = sun(date=date, observer=siteinfo.observer, tzinfo=tzinfo)
            dawn = astral['dawn']
            dusk = astral['dusk'] + datetime.timedelta(minutes=10)
            start = datetime.datetime(dawn.year, dawn.month, dawn.day, dawn.hour, int(int(dawn.minute/10)*10))
            stop = datetime.datetime(dusk.year, dusk.month, dusk.day, dusk.hour, int(int(dusk.minute/10)*10))

            # Get irradiance data for today and convert to InfluxDB line protocol
            irradiance = clearsky.get_irradiance(site=site, start=start.strftime("%Y-%m-%d %H:%M:00"), end=stop.strftime("%Y-%m-%d %H:%M:00"), tilt=SITE_TILT, azimuth=SITE_AZIMUTH, freq='10min')
            for point in irradiance:
                t = point['t']
                v = point['v'] * SITE_PANEL_AREA * SITE_PANEL_EFFICIENCY
                lp = f'production,inverter=site irradiance={round(v, 1)} {t}'
                lp_points.append(lp)
            date += delta

        self._influx.write_points(lp_points)

    # Need to total points for which we have data from all inverters
    async def populate_production(self):
        delta = datetime.timedelta(days=1)
        date = datetime.date(year=2021, month=1, day=1)
        end_date = datetime.date.today() + delta

        while date < end_date:
            start = datetime.datetime.combine(date, datetime.time(0, 0)) - datetime.timedelta(minutes=5)
            stop = start + delta
            inverters = await asyncio.gather(*(inverter.read_fine_history(int(start.timestamp()), int(stop.timestamp())) for inverter in self._inverters))
            total = {}
            count = {}
            for inverter in inverters:
                last_non_null = None
                for i in range(1, len(inverter)):
                    t = inverter[i]['t']
                    v = inverter[i]['v']
                    if not v:
                        if not last_non_null:
                            continue
                        v = last_non_null
                    total[t] = v + total.get(t, 0)
                    count[t] = count.get(t, 0) + 1
                    last_non_null = v

            site_total = []
            for t, v in total.items():
                if count[t] == len(inverters):
                    site_total.append({'t': t, 'v': v})
            site_total.insert(0, {'inverter': 'site'})
            inverters.append(site_total)
            self._influx.write_history(inverters, 'production/total')
            date += delta


    async def run(self):
        await asyncio.gather(
            self.populate_days(),
            self.populate_production(),
            self.populate_irradiance(),
        )
