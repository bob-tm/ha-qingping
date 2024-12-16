"""A demonstration 'hub' that connects several devices."""
from __future__ import annotations

# In a real implementation, this would be in an external library that's on PyPI.
# The PyPI package needs to be included in the `requirements` section of manifest.json
# See https://developers.home-assistant.io/docs/creating_integration_manifest
# for more information.
# This dummy hub always returns 3 rollers.
import asyncio
import random

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_PASSWORD, CONF_USERNAME


from homeassistant.components.sensor import (
    SensorDeviceClass
)

import aiomqtt
from . import decode_mqqt_message
from .const import DOMAIN, PLATFORMS

async def TestConnection(host, port:int, user, pwd):
    try:
        async with aiomqtt.Client(
            hostname = host,
            port     = int(port),
            username = user,
            password = pwd) as client:

            await client.subscribe("test_topic")
            return True
    except:
        return False

class Hub:
    """Dummy hub for Hello World example."""

    manufacturer = "Demonstration Corp"

    def __init__(self, hass: HomeAssistant, entry_data, config_entry) -> None:
        """Init dummy hub."""
        self._host = entry_data[CONF_HOST]
        self._port = int(entry_data[CONF_PORT])
        self._user = entry_data[CONF_USERNAME]
        self._pass = entry_data[CONF_PASSWORD]
        self._hass = hass
        self._name = self._host
        self._id = self._host.lower()
        self.devices = {}
        self.config_entry = config_entry
        self.online = True

        hass.async_create_task(
            self.task_on_mqtt_message()
        )

    async def update_device(self, qp: Qingping):

        if qp.ready:
            if qp.sensors_created:
                # parent device is already registered. Just Update HA
                await qp.publish_updates()
            else:
                device_registry = dr.async_get(self._hass)

                device = device_registry.async_get_or_create(
                    config_entry_id = self.config_entry.entry_id,
                    connections     = {(qp.addr, DOMAIN)},
                    identifiers     = {(qp.addr, DOMAIN)},
                    manufacturer    = "Qingping",
                    name            = qp.name,
                    model           = qp.model,
                    sw_version      = qp.firmware_version,
                    hw_version      = qp.hardwareVersion,
                )

                await self._hass.config_entries.async_forward_entry_setups(self.config_entry, PLATFORMS)

                qp.sensors_created = True

    async def task_on_mqtt_message(self):
        topic = "qingping/+/up"
        async with aiomqtt.Client(
            hostname = self._host,
            port     = self._port,
            username = self._user,
            password = self._pass) as client:

            await client.subscribe(topic)
            async for message in client.messages:
                r = decode_mqqt_message.decode(message.topic, message.payload)
                print(f"MESSAGE {r}")
                if r:
                    a = r['addr']
                    if a not in self.devices:
                        self.devices[a]=Qingping(self, r['addr'])

                    qp = self.devices[a]
                    qp.update_from_mqtt(r['data'])
                    await self.update_device(qp)

        return True


    @property
    def hub_id(self) -> str:
        """ID for dummy hub."""
        print(f"hub_id {self._id}")
        return self._id

    async def test_connection(self) -> bool:
        """Test connectivity to the Dummy hub is OK."""
        await asyncio.sleep(1)
        print("test_connection")

        return True


class Qingping:
    """Dummy roller (device for HA) for Hello World example."""

    def __init__(self, hub: Hub, addr: str) -> None:
        self.addr  = addr
        self.hub   = hub
        self.name  = addr
        self._callbacks = set()

        self.info = False #General Info
        self.data = False #Sensors Data
        self.history_data   = {}
        self.history_index  = 0
        self.history_last_index  = 0
        self.history_max    = 10

        self.sensors_created = False

    def update_from_mqtt(self, data) -> None:
        if data['_header']=='CG9':
            self.info = data
            """
               '_header': 'CG9',
                'autoOffTime': 0,
                'co2ASC': True,
                'co2IsBeingCalibrated': False,
                'co2MeasurementInterval': 1800,
                'co2Offset': 0,
                'co2OffsetPercentage': 0.0,
                'humidityOffset': 0.0,
                'humidityOffsetPercentage': 0.0,
                'productId': '3\x00',
                'temperatureOffset': 0.0,
                'temperatureOffsetPercentage': 0.0,
                'temperatureUnit': 'celsius',
                'timeMode': '24h',
                'unk_key_04': b'<\x00',
                'unk_key_05': b'\x84\x03',
                'unk_key_06': b'\xe8\x03',
                'unk_key_19': b'\x00',
                'unk_key_44': b'\x01
            """
        elif data['_header']=='CG1':
            self.history_data[self.history_index] = data
            self.history_last_index = self.history_index


            if self.history_index >= self.history_max:
                self.history_index = 0
            else:
                self.history_index = self.history_index + 1

            """
                {'_header': 'CG1',
                'isGoingIntoLowPowerMode': True,
                'productId': '3\x00',
                'unk_key_03': b'\x1c\xc6\xd5e\x84\x03\xa4\x11+5\x03d\xd3\x81)\xa8'
                        b'\x02d'}}
            """
        elif data['_header']=='CG4':
            self.data = data

            """
                '_header': 'CG4',
                'battery': 100,
                'co2IsBeingCalibrated': False,
                'co2_ppm': 939,
                'firmware_version': '2.0.0',
                'hardwareVersion': '0000',
                'humidity': 46.9,
                'isGoingIntoLowPowerMode': True,
                'isPluggedInToPower': False,
                'mcuFirmwareVersion': '2.0.0',
                'productId': '3\x00',
                'temperature': 18.5,
                'timestamp': 1708434246,
                'unk_key_11': b'2.0.0',
                'unk_key_14': b'F\xa3\xd4e\xd5\xd1*\xab\x03d\xcd\x00',
                'unk_key_67': b'\x01\x00\x00\x00',
                'wirelessModuleFirmwareVersion': '1.9.5'
            """
        else:
            #print(data['_header'])
            pass

    def is_supported(self, device_class: SensorDeviceClass) -> bool:
        if 'sensor' not in self.data:
            return False

        if device_class==SensorDeviceClass.BATTERY:
            return 'battery' in self.data['sensor']
        elif device_class==SensorDeviceClass.TEMPERATURE:
            return 'temperature' in self.data['sensor']
        elif device_class==SensorDeviceClass.HUMIDITY:
            return 'humidity' in self.data['sensor']
        elif device_class==SensorDeviceClass.CO2:
            return 'co2_ppm' in self.data['sensor']
        else:
            return False

    @property
    def ready(self) -> bool:
        return self.data != False

    @property
    def id(self) -> str:
        """Return ID for roller."""
        return self.addr

    @property
    def model(self) -> str:
        if self.data:
            return f"{self.data['productId']} - {self.addr}",

    @property
    def firmware_version(self) -> str:
        if self.data:
            return self.data['firmware_version']

    @property
    def hardwareVersion(self) -> str:
        if self.data:
            return self.data['hardwareVersion']



    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register callback, called when Roller changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback: Callable[[], None]) -> None:
        """Remove previously registered callback."""
        self._callbacks.discard(callback)


    # In a real implementation, this library would call it's call backs when it was
    # notified of any state changeds for the relevant device.
    async def publish_updates(self) -> None:
        """Schedule call all registered callbacks."""
        for callback in self._callbacks:
            callback()

    @property
    def online(self) -> bool:
        return self.hub.online

    @property
    def battery_level(self) -> int:
        if self.data:
            return self.data['sensor']['battery']

    @property
    def temperature(self) -> float:
        if self.data:
            return self.data['sensor']['temperature']

    @property
    def co2IsBeingCalibrated(self):
        if self.data:
            return self.data['co2IsBeingCalibrated']

    @property
    def co2_ppm(self) -> int:
        if self.data:
            return self.data['sensor']['co2_ppm']


    @property
    def humidity(self) -> float:
        if self.data:
            return self.data['sensor']['humidity']