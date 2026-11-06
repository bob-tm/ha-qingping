"""Sensors for Qingping MQTT devices."""

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
)

try:
    from homeassistant.const import UnitOfRatio
except ImportError:
    # Home Assistant 2025.3 predates UnitOfRatio.
    from homeassistant.const import CONCENTRATION_PARTS_PER_MILLION as _PARTS_PER_MILLION
else:
    _PARTS_PER_MILLION = UnitOfRatio.PARTS_PER_MILLION

from .const import DOMAIN
from .hub import Qingping


_SENSOR_UNITS = {
    SensorDeviceClass.TEMPERATURE: UnitOfTemperature.CELSIUS,
    SensorDeviceClass.HUMIDITY: PERCENTAGE,
    SensorDeviceClass.CO2: _PARTS_PER_MILLION,
    SensorDeviceClass.BATTERY: PERCENTAGE,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up My integration from a config entry."""
    hub = config_entry.runtime_data

    def _check_device() -> None:
        new_devices = []
        for qp in hub.devices.values():
            if not qp.sensors_created:
                for s in qp.sensors:
                    if qp.sensors[s]['supported']:
                        new_devices.append(SensorBase(qp, s))
                qp.sensors_created = True

            if new_devices:
                async_add_entities(new_devices)

    _check_device()

    # Add Lisener only once
    if len(hub.devices)==1:
        hub.async_add_listener(_check_device)

class SensorBase(SensorEntity):
    'Descr.'
    should_poll  = False

    def __init__(self, qp_device: Qingping, sensor_name):
        """Initialize the sensor."""
        device_class            = qp_device.sensors[sensor_name].get('dc', None)
        self.sensor_diagnostic  = qp_device.sensors[sensor_name].get('diagnostic', False)
        self._qp_device         = qp_device
        self.sensor_name        = sensor_name

        self._attr_device_class = device_class
        if device_class in _SENSOR_UNITS:
            self._attr_native_unit_of_measurement = _SENSOR_UNITS[device_class]
            self._attr_state_class = SensorStateClass.MEASUREMENT

        name_postfix = sensor_name if device_class is None else device_class

        self._attr_unique_id    = f"{qp_device.id}_{name_postfix}"
        self._attr_name         = f"{qp_device.name} {name_postfix}"

        #print(f"Creating Sensor {self._attr_unique_id}")

        if sensor_name=='status':
            self._attr_name = f"{qp_device.name} Status"

    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return {"identifiers": {(self._qp_device.addr, DOMAIN)}}

    # This property is important to let HA know if this entity is online or not.
    # If an entity is offline (return False), the UI will refelect this.
    @property
    def available(self) -> bool:
        """Return True if roller and hub is available."""
        return self._qp_device.online

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        await super().async_added_to_hass()
        # Sensors should also register callbacks to HA when their state changes
        self._qp_device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self._qp_device.remove_callback(self.async_write_ha_state)
        await super().async_will_remove_from_hass()

    @property
    def entity_category(self):
        '''Category.'''
        if self.sensor_diagnostic:
            return EntityCategory.DIAGNOSTIC
        else:
            return None

    @property
    def native_value(self):
        """Return the decoder's value in its native unit (Celsius for temperature)."""
        if self.sensor_name=='status':
             return 'data in attributes'

        return self._qp_device.getValue(self.sensor_name)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        "Attributes added for debug."
        if self.sensor_name != 'status':
            return None

        Attr = {
            'info': self._qp_device.info,
            'data': self._qp_device.data,
            'history': {}
        }

        Attr['history']['last_index'] = self._qp_device.history_last_index
        for k, v in self._qp_device.history_data.items():
            Attr['history'][k]=v

        return Attr
