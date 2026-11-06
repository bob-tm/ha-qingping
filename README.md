# Qingping custom integration for Home Assistant

Tested with Qingping CO2 Temp & RH Sensor (CGP22C) via it's private cloud


## Enabling private cloud
https://github.com/GreyEarl/qingping-air-monitor-mqtt

## History Data

Currently there is no much sence in history data (sesnor take measurment each 15 minutes, but uploads data once a hour)
History data is fully parsed since version 0.2, but I can not find any Api in HA to put that data in ha entity history. Currently it's avaible in extended attributes for status sensor. 


## HACS Installation

1. Go to http://homeassistant.local:8123/hacs/integrations
1. Add `https://github.com/bob-tm/ha-qingping` custom integration repository
1. Download the Qingping repository
1. Go to http://homeassistant.local:8123/config/integrations and add new integration
1. Choose "Qingping MQTT Parser" from the list and follow the config flow steps
1. Press button on Qingping device to publish data over wifi
2. Sensors will be added automaticaly
3. Sensor Status has extended attributes for debuging and inverstigating. Use ha /developer-tools/state to view what sensor sends. 


## HA 
After HA Rebot sensors will be unavailable until first fresh data from qingping device. 
Currenty unavailable status not tracked.

Credits to 
https://github.com/niklasarnitz/qingping-co2-temp-rh-sensor-mqtt-parser for payload parsing code

## MQTT startup scheduling tests

The long-running MQTT listener uses a Home Assistant background task so it does
not block startup while waiting for messages or reconnecting. This is a
startup-only change: entry unload is unchanged, including its existing manual
context exit and five-second delay. It does not fix MQTT lifecycle or transport
cleanup issues during connection setup or shutdown.

These tests use real Home Assistant scheduling and a fake MQTT client. They do
not connect to a broker or validate real transport cleanup or device payloads.

```sh
mkdir -p .tmp
PYTHONDONTWRITEBYTECODE=1 uv run --python 3.14 \
  --with homeassistant==2026.10.4 --with pytest --with pytest-asyncio \
  --with aiomqtt python -m pytest -q tests/test_hub.py --basetemp .tmp/pytest \
  -o asyncio_default_fixture_loop_scope=function
```

To test the minimum supported release, use `--python 3.13` and
`--with homeassistant==2025.3.0 --with aiohttp==3.11.13` instead. The explicit
aiohttp pin lets uv install that release's now-yanked required dependency.
