"Sensors for QP."

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
)

from .const import DOMAIN
from .hub import Qingping

SENSOR_UNITS = {
    SensorDeviceClass.TEMPERATURE: UnitOfTemperature.CELSIUS,
    SensorDeviceClass.HUMIDITY:    PERCENTAGE,
    SensorDeviceClass.BATTERY:     PERCENTAGE,
    SensorDeviceClass.CO2:         CONCENTRATION_PARTS_PER_MILLION,
}

SENSOR_STATE_CLASSES = {
    SensorDeviceClass.TEMPERATURE: SensorStateClass.MEASUREMENT,
    SensorDeviceClass.HUMIDITY:    SensorStateClass.MEASUREMENT,
    SensorDeviceClass.BATTERY:     SensorStateClass.MEASUREMENT,
    SensorDeviceClass.CO2:         SensorStateClass.MEASUREMENT,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Qingping integration from a config entry."""
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

    # Add Listener only once
    if len(hub.devices) == 1:
        hub.async_add_listener(_check_device)


class SensorBase(SensorEntity):
    """Qingping sensor entity."""

    should_poll = False

    def __init__(self, qp_device: Qingping, sensor_name):
        """Initialize the sensor."""
        device_class                = qp_device.sensors[sensor_name].get('dc', None)
        self.sensor_diagnostic      = qp_device.sensors[sensor_name].get('diagnostic', False)
        self._qp_device             = qp_device
        self.sensor_name            = sensor_name

        self._attr_device_class               = device_class
        self._attr_native_unit_of_measurement = SENSOR_UNITS.get(device_class)
        self._attr_state_class                = SENSOR_STATE_CLASSES.get(device_class)

        name_postfix = sensor_name if device_class is None else device_class

        self._attr_unique_id = f"{qp_device.id}_{name_postfix}"
        self._attr_name      = f"{qp_device.name} {name_postfix}"

        if sensor_name == 'status':
            self._attr_name = f"{qp_device.name} Status"

    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return {"identifiers": {(self._qp_device.addr, DOMAIN)}}

    @property
    def available(self) -> bool:
        """Return True if device and hub are available."""
        return self._qp_device.online

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        self._qp_device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        self._qp_device.remove_callback(self.async_write_ha_state)

    @property
    def entity_category(self):
        """Category."""
        if self.sensor_diagnostic:
            return EntityCategory.DIAGNOSTIC
        return None

    @property
    def native_value(self):
        """Return the sensor value."""
        if self.sensor_name == 'status':
            return 'data in attributes'

        return self._qp_device.getValue(self.sensor_name)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Attributes added for debug (status sensor only)."""
        if self.sensor_name != 'status':
            return None

        attr = {
            'info': self._qp_device.info,
            'data': self._qp_device.data,
            'history': {}
        }

        attr['history']['last_index'] = self._qp_device.history_last_index
        for k, v in self._qp_device.history_data.items():
            attr['history'][k] = v

        return attr