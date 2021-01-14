"""Code to interface with the SMA inverters and return the results."""

import asyncio
import logging
#from dateutil.relativedelta import *
from dateutil.rrule import rrule, MONTHLY
import datetime
import copy

from pprint import pprint

from inverter import Inverter
from influx import InfluxDB

from configuration import INVERTERS
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
    
    async def run(self):
        await self.populate_months()
        await self.populate_days()
