from __future__ import annotations
import logging
from typing import Any
from datetime import datetime, timezone

from homeassistant.components.sensor import (
    SensorDeviceClass
)
from homeassistant.const import (
    UnitOfTemperature,
    PERCENTAGE,
    CONCENTRATION_PARTS_PER_MILLION,
    UnitOfTime,
)
from homeassistant.helpers.entity import Entity
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)

from .hub import Qingping
from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)

DC_STATUS = SensorDeviceClass.ENUM

# Глобальный реестр зарегистрированных MAC + sensor_class, чтобы не создавать дубликаты
REGISTERED_SENSORS = set()
ASYNC_ADD_ENTITIES = None

# See cover.py for more details.
# Note how both entities for each roller sensor (battry and illuminance) are added at
# the same time to the same list. This way only a single async_add_devices call is
# required.
async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add sensors for passed config_entry in HA."""
    global ASYNC_ADD_ENTITIES
    ASYNC_ADD_ENTITIES = async_add_entities  # Сохраняем для динамического добавления

    hub = hass.data[DOMAIN][config_entry.entry_id]
    for mac, qp in hub.devices.items():
        if qp.data and "sensor" in qp.data and qp.data.get("firmware_version") and qp.data.get("hardwareVersion"):
            add_qingping_sensors(qp) # Просто вызываем динамическую функцию для каждого

class QingpingBinarySensor(BinarySensorEntity):
    """Representation of a Qingping Binary Sensor."""
    _attr_should_poll = False
    
    def __init__(self, device: Qingping, device_class: BinarySensorDeviceClass):
        self._qp_device = device
        self._attr_device_class = device_class
        self._attr_unique_id = f"{self._qp_device.addr}_{self.device_class.value}"
        self._attr_name = f"{self._qp_device.name} {self.device_class.value.replace('_', ' ').title()}"

    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return {
            "identifiers": {(DOMAIN, self._qp_device.addr)}
        }

    @property
    def available(self) -> bool:
        return self._qp_device.data is not False

    @property
    def is_on(self) -> bool | None:
        if self.device_class == BinarySensorDeviceClass.PLUG:
            return self._qp_device.is_plugged_in
        if self.device_class == BinarySensorDeviceClass.PROBLEM:
            return self._qp_device.is_calibrating
        if self.device_class == BinarySensorDeviceClass.POWER:
            return self._qp_device.is_low_power_mode
        return None

    async def async_added_to_hass(self):
        self._qp_device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        self._qp_device.remove_callback(self.async_write_ha_state)

# Новый метод для динамического добавления сенсоров
def add_qingping_sensors(qp):
    """Динамически добавляет сенсоры для устройства Qingping."""
    entities = []

    # --- Стандартные сенсоры ---
    SENSORS_TO_CREATE = [
        (SensorDeviceClass.TEMPERATURE, qp.temperature),
        (SensorDeviceClass.HUMIDITY, qp.humidity),
        (SensorDeviceClass.CO2, qp.co2_ppm), # <-- Используем правильное свойство qp.co2_ppm
        (SensorDeviceClass.TIMESTAMP, qp.last_update_timestamp), # <-- Используем правильное свойство qp.last_update_timestamp
    ]
    # Проверяем, что значение свойства не None
    for device_class, is_supported in SENSORS_TO_CREATE:
        if is_supported is not None:
            unique_id = f"{qp.addr}_{device_class.value}"
            if unique_id not in REGISTERED_SENSORS:
                entities.append(SensorBase(qp, device_class))
                REGISTERED_SENSORS.add(unique_id)
    

    # --- Специальная обработка для BatterySensor ---
    unique_id = f"{qp.addr}_{SensorDeviceClass.BATTERY.value}"
    if qp.battery_level is not None and unique_id not in REGISTERED_SENSORS:
        entities.append(BatterySensor(qp))
        REGISTERED_SENSORS.add(unique_id)

    # --- Бинарные сенсоры ---
    BINARY_SENSORS_TO_CREATE = [
        (BinarySensorDeviceClass.PLUG, qp.is_plugged_in),
        (BinarySensorDeviceClass.PROBLEM, qp.is_calibrating),
        (BinarySensorDeviceClass.POWER, qp.is_low_power_mode),
    ]
    for device_class, is_supported in BINARY_SENSORS_TO_CREATE:
        if is_supported is not None:
            unique_id = f"{qp.addr}_{device_class.value}"
            if unique_id not in REGISTERED_SENSORS:
                entities.append(QingpingBinarySensor(qp, device_class))
                REGISTERED_SENSORS.add(unique_id)

    # --- Кастомный сенсор интервала ---
    unique_id = f"{qp.addr}_co2_measurement_interval"
    if qp.co2_measurement_interval is not None and unique_id not in REGISTERED_SENSORS:
        entities.append(SensorBase(qp, "co2_measurement_interval"))
        REGISTERED_SENSORS.add(unique_id)

    # --- Сенсор статуса ---
    unique_id = f"{qp.addr}_{DC_STATUS.value}"
    if unique_id not in REGISTERED_SENSORS:
        entities.append(SensorBase(qp, DC_STATUS))
        REGISTERED_SENSORS.add(unique_id)

    if entities and ASYNC_ADD_ENTITIES:
        ASYNC_ADD_ENTITIES(entities)
    # Строка qp.sensors_created = True убрана, чтобы разрешить добавление новых сенсоров в будущем

class SensorBase(Entity):
    should_poll  = False

    def __init__(self, qp_device: Qingping, device_class):
        """Initialize the sensor."""
        self._qp_device         = qp_device
        self._attr_device_class = device_class

        class_str = device_class.value if isinstance(device_class, SensorDeviceClass) else device_class
        self._attr_unique_id    = f"{qp_device.id}_{class_str}"
        self._attr_name         = f"{qp_device.name} {class_str.replace('_', ' ').title()}"

        if device_class == DC_STATUS:
            self._attr_name = f"{qp_device.name} Status"
        elif device_class == SensorDeviceClass.TIMESTAMP:
            self._attr_name = f"{qp_device.name} Last Update"
        elif device_class == "co2_measurement_interval":
            self._attr_name = f"{qp_device.name} CO2 Measurement Interval"

    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return {
            "identifiers": {(DOMAIN, self._qp_device.addr)}
        }

    @property
    def available(self) -> bool:
        if self.device_class == DC_STATUS:
            return True
        return self._qp_device.data is not False

    async def async_added_to_hass(self):
        self._qp_device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        self._qp_device.remove_callback(self.async_write_ha_state)

    @property
    def state(self):
        if self.device_class==SensorDeviceClass.BATTERY:
            return self._qp_device.battery_level
        elif self.device_class==SensorDeviceClass.TEMPERATURE:
            return self._qp_device.temperature
        elif self.device_class==SensorDeviceClass.HUMIDITY:
            return self._qp_device.humidity
        elif self.device_class==SensorDeviceClass.CO2:
            return self._qp_device.co2_ppm
        elif self.device_class==SensorDeviceClass.TIMESTAMP:
            if (ts := self._qp_device.last_update_timestamp) is not None:
                return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            return None
        elif self.device_class=="co2_measurement_interval":
            return self._qp_device.co2_measurement_interval
        elif self.device_class==DC_STATUS:
            if self._qp_device.is_calibrating:
                return 'calibrating'
            else:
                if self._qp_device.data:
                    return 'online'
                else:
                    return 'waiting for data'
        else:
            return None
    
    @property
    def unit_of_measurement(self) -> str | None:
        if self.device_class == SensorDeviceClass.TEMPERATURE:
            return UnitOfTemperature.CELSIUS
        if self.device_class == SensorDeviceClass.HUMIDITY:
            return PERCENTAGE
        if self.device_class == SensorDeviceClass.CO2:
            return CONCENTRATION_PARTS_PER_MILLION
        if self.device_class == SensorDeviceClass.BATTERY:
            return PERCENTAGE
        if self.device_class == "co2_measurement_interval":
            return UnitOfTime.SECONDS
        return None

    @property
    def icon(self) -> str | None:
        if self.device_class == "co2_measurement_interval":
            return "mdi:camera-timer"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.device_class!=DC_STATUS:
            return None

        attrs = {
            'info': self._qp_device.info,
            'data': self._qp_device.data,
            'history': {}
        }
        attrs.update(self._qp_device.extra_firmware_versions)

        attrs['history']['last_index'] = self._qp_device.history_last_index
        for k, v in self._qp_device.history_data.items():
            attrs['history'][k]=v

        return attrs

class BatterySensor(SensorBase):
    device_class = SensorDeviceClass.BATTERY

    def __init__(self, qp_device: Qingping):
        # Исправлена ошибка: super() теперь вызывается с правильными аргументами
        super().__init__(qp_device, SensorDeviceClass.BATTERY)
        # Эти строки теперь не нужны, так как имя и ID задаются в SensorBase
        # self._attr_unique_id = f"{qp_device.id}_battery"
        # self._attr_name = f"{qp_device.name} Battery"

    # Свойство state убрано, так как оно полностью дублировало логику
    # из родительского класса SensorBase.
