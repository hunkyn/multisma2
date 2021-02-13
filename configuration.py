# Site location details for solar time calculations
SITE_NAME = "Solar SMA"
SITE_REGION = "New York"
TIMEZONE = 'America/New_York'
SITE_LATITUDE = 28.160046
SITE_LONGITUDE = -82.310636

# Solar array information for predictions, SITE_AZIMUTH and SITE_TILT are degrees,
# SITE_PANEL_AREA is square meters, and SITE_PANEL_EFFICIENCY is a percentage.
SITE_AZIMUTH = 180
SITE_TILT = 30
SITE_PANEL_AREA = 100
SITE_PANEL_EFFICIENCY = 0.15

# Application log file customization
APPLICATION_LOG_FILE = 'log/multisma2'
APPLICATION_LOG_FORMAT = '[%(asctime)s] [%(module)s] [%(levelname)s] %(message)s'
APPLICATION_LOG_LOGGER_NAME = 'multisma2'

# Production fuel mix factor (kgCO2e per kWh) which is an estimate of local utility KgCO2e/kWh
# You can get these estimates from the EPA, your utility company
# or from https://www.carbonfootprint.com/international_electricity_factors.html
CO2_AVOIDANCE = 0.44000

# The InfluxDB interface uses the newer 2.0 client which supports both the 2.0 and 1.8.x InfluxDB versions
# with just minor changes in the configuration making a future upgrade to v2 a simple change of options.
#
# Influxdb configuration options:
#  INFLUXDB_ENABLE            set to True to enable InfluxDB usage
#  INFLUXDB_BUCKET            set to the InfluxDB bucket (v2) or 'database/retention_policy' (v1.8)
#  INFLUXDB_URL               set to the InfluxDB server URL and port
#  INFLUXDB_ORG               set to the v2 organization or '-' if using v1.8
#  INFLUXDB_TOKEN             set to a valid v2 token or v1.8 'username:password'
INFLUXDB_ENABLE = True
INFLUXDB_BUCKET = 'multisma2/autogen'
INFLUXDB_URL = 'http://a0d7b954-influxdb:8086'
INFLUXDB_ORG = '-'
INFLUXDB_TOKEN = 'homeassistant:jun61978'

# MQTT configuration options:
#  MQTT_ENABLE            set to True to enable sending messages to the broker
#  MQTT_CLIENT            set to a unique broker client name and used as top level topic
#  MQTT_BROKER_IPADDR     set to the fully qualified domain name or IP address of the broker
#  MQTT_BROKER_PORT       set to port (default to 1883 if set to 0)
#  MQTT_USERNAME          set to the username if authentication is used
#  MQTT_PASSWORD          set to the password port if authentication is used
MQTT_ENABLE = False
MQTT_CLIENT = 'multisma2'
MQTT_BROKER_IPADDR = 'broker.mqtt.com'
MQTT_BROKER_PORT = 0
MQTT_USERNAME = 'username'
MQTT_PASSWORD = 'password'

# Inverter login information
INVERTER_USERNAME = installer
INVERTER_PASSWORD = sma12345

# Inverter configuration
# Supply the IP address and login credentials for each inverter.  The inverter names are used
# in MQTT messages for the individual inverter sensors, :
# multisma2/production_lifetime {"unit": "kWh", "inv0": 3287.216, "total": 8966.242, "inv1": 2417.215}
INVERTERS = [
   {'ip': 'https://192.168.30.20', 'SMA': 'inv1', 'user': installer, 'password': sma12345},
]
