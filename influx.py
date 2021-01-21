# Interface to InfluxDB multisma2 database
#
# InfluxDB Line Protocol Reference
# https://docs.influxdata.com/influxdb/v2.0/reference/syntax/line-protocol/

import logging
from pprint import pprint

from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBServerError, InfluxDBClientError

from configuration import APPLICATION_LOG_LOGGER_NAME
from configuration import INFLUXDB_ENABLE, INFLUXDB_DATABASE, INFLUXDB_IPADDR, INFLUXDB_PORT

logger = logging.getLogger(APPLICATION_LOG_LOGGER_NAME)


LP_LOOKUP = {
    'ac_measurements/power': {'measurement': 'ac_measurements', 'field': 'power'},
    'ac_measurements/voltage': {'measurement': 'ac_measurements', 'field': 'voltage'},
    'ac_measurements/current': {'measurement': 'ac_measurements', 'field': 'current'},
    'ac_measurements/efficiency': {'measurement': 'ac_measurements', 'field': 'efficiency'},
    'dc_measurements/power': {'measurement': 'dc_measurements', 'field': 'power'},
    'status/reason_for_derating': {'measurement': 'status', 'field': 'derating'},
    'status/general_operating_status': {'measurement': 'status', 'field': 'operating_status'},
    'status/grid_relay': {'measurement': 'status', 'field': 'grid_relay'},
    'status/condition': {'measurement': 'status', 'field': 'condition'},
    'production/total': {'measurement': 'production', 'field': 'total'},
    'production/today': {'measurement': 'production', 'field': 'today'},
}


class InfluxDB():
    def __init__(self):
        self._client = None

    def start(self):
        if INFLUXDB_ENABLE:
            self._client = InfluxDBClient(host=INFLUXDB_IPADDR, port=INFLUXDB_PORT, database=INFLUXDB_DATABASE)
            if self._client:
                logger.info(f"Opened the InfluxDB database '{INFLUXDB_DATABASE}' for output")
            else:
                logger.error(f"Failed to open the InfluxDB database '{INFLUXDB_DATABASE}'")

    def stop(self):
        if self._client:
            self._client.close()
            logger.info(f"Closed the InfluxDB database '{INFLUXDB_DATABASE}'")

    def write_history(self, site, topic):
        if not self._client:
            return False

        lookup = LP_LOOKUP.get(topic)
        measurement = lookup.get('measurement')
        field = lookup.get('field')
        lps = []
        for inverter in site:
            inverter_name = inverter.pop(0)
            name = inverter_name['inverter']
            for history in inverter:
                t = history['t']
                v = history['v']
                if isinstance(v, int):
                    lp = f'{measurement},inverter={name} {field}={v}i {t}'
                    lps.append(lp)

        try:
            result = self._client.write_points(points=lps, time_precision='s', protocol='line')
            logger.info(f"Wrote {len(lps)} history points")
        except (InfluxDBClientError, InfluxDBServerError):
            logger.error(f"Database write_history() failed")
            result = False
        return result

    def write_points(self, points):
        if not self._client:
            return False

        try:
            result = self._client.write_points(points=points, time_precision='s', protocol='line')
            logger.info(f"Wrote {len(points)} line protocol points")
        except (InfluxDBClientError, InfluxDBServerError):
            logger.error(f"Database write_points() failed")
            result = False
        return result
