"""A demonstration 'hub' that connects several devices."""
from __future__ import annotations

import asyncio
import logging
from typing import Callable

import aiomqtt

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from . import decode_mqqt_message
from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def TestConnection(host, port:int, user, pwd):
    "Test code."
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

    def __init__(self, hass: HomeAssistant, entry_data, config_entry) -> None:
        """Init hub."""
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
        self.unloading = False

        self._listeners: dict[int, tuple[CALLBACK_TYPE, object | None]] = {}
        self._last_listener_id: int = 0

        self.looptask = hass.async_create_task(
            self.task_on_mqtt_message()
        )

    async def task_stop(self):
        _LOGGER.debug("Start task stopping ...")

        self.unloading = True
        await self.client.__aexit__(None, None, None)
        await asyncio.sleep(5)
        self.looptask.cancel()

        try:
            _LOGGER.debug("Waiting for task_stop")
            await self.looptask
            _LOGGER.debug("Stopped")
        except asyncio.CancelledError:
            _LOGGER.error("Task Stop Error ...")

    async def task_on_mqtt_message(self):
        "Parse device sensors."
        interval = 15  # Seconds
        topic    = "qingping/+/up"
        client   = aiomqtt.Client(
                hostname = self._host,
                port     = self._port,
                username = self._user,
                password = self._pass)

        self.client = client

        while not self.unloading:
            #_LOGGER.debug("Start new Loop ...")
            try:
                async with client:
                    _LOGGER.info(f"Connected to MQTT Server")

                    await client.subscribe(topic)

                    _LOGGER.debug(f"Subscribed to {topic}")

                    async for message in client.messages:
                        await self.parse_message(message)
            except aiomqtt.MqttError:
                if not self.unloading:
                    _LOGGER.error(f"Connection lost; Reconnecting in {interval} seconds ...")
                    await asyncio.sleep(interval)

        _LOGGER.debug("Loop stopped")

        return True

    async def parse_message(self, message):
        "Parse MQTT Message."
        try:
            _LOGGER.debug(f"Received MQTT message on topic: {message.topic}")
            r = decode_mqqt_message.decode(message.topic, message.payload)
            if r:
                _LOGGER.debug(f"Decoded MQTT message: {r}")
                a = r['addr']
                if a not in self.devices:
                    # skip no data messages
                    if 'firmware_version' not in r['data']:
                        return True

                    _LOGGER.debug(f"Creating new Qingping device for address: {a}")
                    qp =Qingping(self, r['addr'], r['data'])
                    self.devices[a] = qp

                    _LOGGER.debug(f"Creating device {qp.id} in Home Assistant.")
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

                    # HA Do not support runtime reconfig. So Uplaod everything and start again
                    if len(self.devices)>1:
                        _LOGGER.debug("async_update_listeners")
                        self.async_update_listeners()
                    else:
                        _LOGGER.debug("async_forward_entry_setups")
                        await self._hass.config_entries.async_forward_entry_setups(self.config_entry, PLATFORMS)
                else:
                    qp = self.devices[a]
                    qp.update_from_mqtt(r['data'])
                    if qp.ready:
                        await qp.publish_updates()

        except Exception as e:  # noqa: BLE001
            _LOGGER.error(f"Parse_message Error: {str(e)}")

        return True

    @callback
    def async_add_listener(self, update_callback, context=None):
        "Callback to register callback to add new devices."
        _LOGGER.debug('async_add_listener')

        self._last_listener_id += 1
        self._listeners[self._last_listener_id] = (update_callback, context)

    @callback
    def async_update_listeners(self) -> None:
        """Update all registered listeners."""
        _LOGGER.debug('async_update_listeners')

        for update_callback, _ in list(self._listeners.values()):
            update_callback()

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
    """CGP22C."""

    def __init__(self, hub: Hub, addr: str, data) -> None:
        "Init."
        self.addr  = addr
        self.hub   = hub
        self.name  = addr
        self._callbacks = set()

        self.info = False #General Info
        self.data = False #Sensors Data
        self.history_data   = {}
        self.history_index  = 0
        self.history_last_index = 0
        self.history_max        = 10
        self.sensors_created    = False
        self.sensors = {
            'battery'             : {'dc': SensorDeviceClass.BATTERY},
            'temperature'         : {'dc': SensorDeviceClass.TEMPERATURE},
            'humidity'            : {'dc': SensorDeviceClass.HUMIDITY},
            'co2_ppm'             : {'dc': SensorDeviceClass.CO2},
            'co2IsBeingCalibrated': {'diagnostic': True},
            'isPluggedInToPower'  : {'diagnostic': True},
            'status'              : {'diagnostic': True}
        }

        self.update_from_mqtt(data)

        for s in self.sensors:
            self.sensors[s]['supported'] = self.getValue(s) is not None

        self.sensors['status']['supported'] = True

    def update_from_mqtt(self, data) -> None:
        "Assing data to sensors."
        _LOGGER.debug(f"Processing : {data}")

        if data['magic'] == 'CG':
            # 0x32 Configuration sending. Server -> Device
            # 0x33 Firmware upgrade (Wi-Fi). Server -> Device
            # 0x3A Network access setting. Server -> Device
            # 0x3B Real-time data uploading. Device -> Server

            if data['cmd'] in ['0x35']:
                # {'header_old': 'CG5', 'magic': 'CG', 'cmd': '0x35', 'productId': '5d 00', 'timestamp': 1640995213}
                pass
            elif data['cmd'] in ['0x39']: #CG9
                # 0x39 Configuration reporting. Device -> Server
                self.info = data
            elif data['cmd'] in ['0x34', '0x41']: #CG4, CGA
                # 0x34 Event reporting. Device -> Server
                # 0x41 ???
                self.data = data
            elif data['cmd'] in ['0x31', '0x42']: #CG1, CGB
                # 0x31 Data uploading.  Device -> Server
                # 0x42 ???
                self.history_data[self.history_index] = data
                self.history_last_index = self.history_index

                if self.history_index >= self.history_max:
                    self.history_index = 0
                else:
                    self.history_index = self.history_index + 1
            else:
                _LOGGER.debug(f"Unknown cmd: {data}")

    @property
    def ready(self) -> bool:
        "Init is done."
        return self.data != False

    @property
    def id(self) -> str:
        """Return ID for roller."""
        return self.addr

    @property
    def online(self) -> bool:
        "Online."
        return self.hub.online

    def getValue(self, s):
        "Check if sensor present in json."
        if self.data:
            if s in self.data:
                return self.data[s] # type: ignore

            if s in self.data['sensor']: # type: ignore
                return self.data['sensor'][s] # type: ignore

        return None

    @property
    def model(self) -> str:
        "Mode for ha."
        return self.addr

    @property
    def firmware_version(self):
        "Firmware ver."
        return self.getValue('firmware_version')

    @property
    def hardwareVersion(self):
        "HardwareVersion."
        return self.getValue('hardwareVersion')

    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register callback, called when Roller changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback: Callable[[], None]) -> None:
        """Remove previously registered callback."""
        self._callbacks.discard(callback)

    async def publish_updates(self) -> None:
        """Schedule call all registered callbacks."""
        for callback in self._callbacks:
            callback()