"""A demonstration 'hub' that connects several devices."""
from __future__ import annotations

import logging
_LOGGER = logging.getLogger(__name__)

# In a real implementation, this would be in an external library that's on PyPI.
# The PyPI package needs to be included in the `requirements` section of manifest.json
# See https://developers.home-assistant.io/docs/creating_integration_manifest
# for more information.
# This dummy hub always returns 3 rollers.
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
        self._platforms_loaded = False  # Флаг чтобы не вызывать async_forward_entry_setups много раз
        self.online = True
        
        # Добавляем callback для добавления новых сенсоров
        self._add_entities_callback = None

        hass.async_create_task(
            self.task_on_mqtt_message()
        )

    def set_add_entities_callback(self, callback):
        """Устанавливаем callback для добавления новых сенсоров."""
        self._add_entities_callback = callback

    async def update_device(self, qp: Qingping):
        # Проверяем, есть ли у нас основные данные из CG4
        if not qp.data or not isinstance(qp.data, dict):
            return # Выходим, если нет данных CG4

        # Вызываем setup платформы только один раз (при первом валидном устройстве)
        if not getattr(self, "_platforms_loaded", False):
            await self._hass.config_entries.async_forward_entry_setups(self.config_entry, PLATFORMS)
            self._platforms_loaded = True

        # 1. Блок создания УСТРОЙСТВА (выполняется один раз)
        if not qp.device_registered:
            # Теперь safe: все поля есть, устройство регистрируем полностью
            device_registry = dr.async_get(self._hass)
            device = device_registry.async_get_or_create(
                config_entry_id=self.config_entry.entry_id,
                connections={(dr.CONNECTION_NETWORK_MAC, qp.addr)}, # Используем стандартный тип соединения
                identifiers={(DOMAIN, qp.addr)},
                manufacturer="Qingping",
                name=f"Qingping {qp.addr}",
                model=qp.model,
                sw_version=qp.firmware_version,
                hw_version=qp.hardwareVersion,
            )
            qp.device_registered = True # Устанавливаем флаг, что устройство создано


        # Импортируем и создаём сенсоры только сейчас!
        from .sensor import add_qingping_sensors

        # Вызываем функцию добавления. Она сама проверит, что уже создано, а что нет.
        # Это позволяет добавлять сенсоры, которые появились в новых пакетах.
        add_qingping_sensors(qp)

        # 3. Публикуем обновления для всех существующих сенсоров
        await qp.publish_updates()


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
                if r:
                    mac = r['addr']
                    if mac not in self.devices:
                        self.devices[mac]=Qingping(self, mac)

                    qp = self.devices[mac]
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
        self.name  = f"Qingping {qp.addr}"  # Имя по умолчанию
        self._callbacks = set()

        self.info = False #General Info
        self.data = False #Sensors Data
        self.history_data   = {}
        self.history_index  = 0
        self.history_last_index  = 0
        self.history_max    = 10

        # Разделяем флаги для большей ясности
        self.device_registered = False # Флаг, что само устройство создано в HA
        self.sensors_created = False # Этот флаг можно даже убрать, но оставим для обратной совместимости

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
            return f'Air Monitor (productId: {self.data.get("productId", "")}) - {self.addr}'
        return "Unknown"

    @property
    def firmware_version(self) -> str:
        if self.data:
            return self.data['firmware_version']
        return "Unknown"

    @property
    def hardwareVersion(self) -> str:
        if self.data:
            return self.data['hardwareVersion']
        return "Unknown"

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
        return 0

    @property
    def temperature(self) -> float:
        if self.data:
            return self.data['sensor']['temperature']
        return 0.0

    @property
    def co2_ppm(self) -> int:
        if self.data:
            return self.data['sensor']['co2_ppm']
        return 0

    @property
    def humidity(self) -> float:
        if self.data:
            return self.data['sensor']['humidity']
        return 0.0

    @property
    def is_plugged_in(self) -> bool | None:
        """Return True if the device is plugged in to power."""
        if self.data:
            return self.data.get("isPluggedInToPower")
        return None

    @property
    def is_calibrating(self) -> bool | None:
        """Return True if CO2 sensor is being calibrated."""
        if self.data:
            return self.data.get("co2IsBeingCalibrated")
        return None

    @property
    def is_low_power_mode(self) -> bool | None:
        """Return True if the device is in low power mode."""
        if self.data:
            return self.data.get("isGoingIntoLowPowerMode")
        return None

    @property
    def last_update_timestamp(self) -> int | None:
        """Return the timestamp of the last update from the device."""
        if self.data:
            return self.data.get("timestamp")
        return None
    
    @property
    def co2_measurement_interval(self) -> int | None:
        """Return the CO2 measurement interval in seconds from device config."""
        # Эти данные приходят в пакете CG9 (self.info)
        if self.info:
            return self.info.get("co2MeasurementInterval")
        return None

    @property
    def extra_firmware_versions(self) -> dict:
        """Return a dict of other firmware versions."""
        versions = {}
        if self.data:
            if "wirelessModuleFirmwareVersion" in self.data:
                versions["Wireless FW"] = self.data["wirelessModuleFirmwareVersion"]
            if "mcuFirmwareVersion" in self.data:
                versions["MCU FW"] = self.data["mcuFirmwareVersion"]
        return versions
