"""Code to interface with the SMA inverters and return the results."""

import asyncio
import datetime
import logging

from pprint import pprint

from inverter import Inverter
from influx import InfluxDB

from configuration import INVERTERS
from configuration import APPLICATION_LOG_LOGGER_NAME


logger = logging.getLogger(APPLICATION_LOG_LOGGER_NAME)


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

    async def run(self):
        month = 6
        year = 2020

        now = datetime.datetime.now()
        yesterday = now - datetime.timedelta(days=1)
        start = datetime.datetime.combine(datetime.date.today().replace(year=year, month=month, day=1), datetime.time(23, 0)) - datetime.timedelta(days=1)
        stop = datetime.datetime.combine(yesterday.date(), datetime.time(23, 0))
        histories = await asyncio.gather(*(inverter.read_history(int(start.timestamp()), int(stop.timestamp())) for inverter in self._inverters))
        total = {}
        for inverter in histories:
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
        histories.append(site_total)
        self._influx.write_history(histories)
