# Qingping custom integration for Home Assistant

Tested with Qingping CO2 Temp & RH Sensor (CGP22C) via it's private cloud


## Enabling private cloud
https://github.com/GreyEarl/qingping-air-monitor-mqtt

## HACS Installation

1. Go to http://homeassistant.local:8123/hacs/integrations
1. Add `https://github.com/bob-tm/ha-qingping` custom integration repository
1. Download the Qingping repository
1. Go to http://homeassistant.local:8123/config/integrations and add new integration
1. Choose "Qingping MQTT Parser" from the list and follow the config flow steps
1. Press button on Qingping device to publish data over wifi
2. Sensors will be added automaticaly
3. Sensor Status has extended attributes for debuging and inverstigating.   


Parsing code converted to python from @niklasarnitz
https://github.com/niklasarnitz/qingping-co2-temp-rh-sensor-mqtt-parser
