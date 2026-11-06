# Qingping custom integration for Home Assistant

Tested with Qingping CO2 Temp & RH Sensor (CGP22C) via it's private cloud


## Enabling private cloud
https://github.com/GreyEarl/qingping-air-monitor-mqtt

## History Data

Currently there is no much sence in history data (sesnor take measurment each 15 minutes, but uploads data once a hour)
History data is fully parsed since version 0.2, but I can not find any Api in HA to put that data in ha entity history. Currently it's avaible in extended attributes for status sensor. 

## Sensor statistics

Temperature, humidity, CO2 and battery sensors expose native units and the
`measurement` state class through Home Assistant's `SensorEntity` API:

| Sensor | Native unit |
| --- | --- |
| Temperature | Celsius |
| Humidity | Percent (`%`) |
| CO2 | Parts per million (`ppm`) |
| Battery | Percent (`%`) |

These measurements are eligible for Home Assistant recorder statistics when
recorder is enabled and includes the entities. Home Assistant handles display-unit
conversion, including Celsius to Fahrenheit. The native Celsius unit follows the
existing decoder; the device's reported display preference does not change it.
Boolean diagnostics and the Status sensor remain non-statistical. Existing entity
unique IDs, names and device associations are preserved.

This does not backfill historical packets from the Status attributes into
recorder. Statistics start from states recorded after the change. Per-device
stale-reading detection is not implemented: the last reported value can remain
available while the MQTT hub is online, even if a device has not sent fresh data.


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

## Testing

The regression tests use real Home Assistant sensor entities, registries and state
machines without starting an MQTT connection. They cover measurement metadata,
zero and missing values, temperature conversion, diagnostic sensors, callback
cleanup and preservation of existing entity/device identities. Test payloads and
the locally administered device address are synthetic.

Run from the repository root with [uv](https://docs.astral.sh/uv/):

```sh
mkdir -p .tmp
PYTHONDONTWRITEBYTECODE=1 uv run --python 3.14 \
    --with homeassistant==2026.10.4 --with pytest --with pytest-asyncio \
    --with aiomqtt python -m pytest -q tests --basetemp .tmp/pytest-ha-2026.10.4 \
    -o asyncio_default_fixture_loop_scope=function
```

To check the minimum Home Assistant version declared in `hacs.json`:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --python 3.13 \
    --with homeassistant==2025.3.0 --with aiohttp==3.11.13 \
    --with pytest --with pytest-asyncio \
    --with aiomqtt python -m pytest -q tests --basetemp .tmp/pytest-ha-2025.3.0 \
    -o asyncio_default_fixture_loop_scope=function
```

Home Assistant 2025.3.0 pins the yanked `aiohttp==3.11.13` release. The explicit
pin above allows uv to use that exact dependency for this isolated compatibility
test; it is not a recommendation to deploy that aiohttp version.

uv may download the requested Python version and dependencies. These tests do not
verify live MQTT traffic or persisted recorder statistics; those require a
separate Home Assistant runtime check.

Credits to 
https://github.com/niklasarnitz/qingping-co2-temp-rh-sensor-mqtt-parser for payload parsing code
