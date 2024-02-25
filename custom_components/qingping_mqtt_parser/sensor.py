from homeassistant.components.sensor import (
    SensorDeviceClass
)

from homeassistant.const import (
    UnitOfTemperature
)

from homeassistant.helpers.entity import Entity
from .hub import Qingping
from .const import DOMAIN
from typing import Any
from homeassistant.util.unit_system import TEMPERATURE_UNITS

DC_STATUS = SensorDeviceClass.ENUM

# See cover.py for more details.
# Note how both entities for each roller sensor (battry and illuminance) are added at
# the same time to the same list. This way only a single async_add_devices call is
# required.
async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add sensors for passed config_entry in HA."""
    hub = hass.data[DOMAIN][config_entry.entry_id]

    new_devices = []
    for mac, qp in hub.devices.items():

        if not qp.sensors_created:
            sdc = [SensorDeviceClass.BATTERY, SensorDeviceClass.TEMPERATURE, SensorDeviceClass.HUMIDITY, SensorDeviceClass.CO2]

            for c in sdc:
                if qp.is_supported(c):
                    new_devices.append(SensorBase(qp, c))

            # debug thing
            new_devices.append(SensorBase(qp, DC_STATUS))

    if new_devices:
        async_add_entities(new_devices)


# This base class shows the common properties and methods for a sensor as used in this
# example. See each sensor for further details about properties and methods that
# have been overridden.
class SensorBase(Entity):
    should_poll  = False

    def __init__(self, qp_device: Qingping, device_class):
        """Initialize the sensor."""
        self._qp_device         = qp_device

        self._attr_device_class = device_class
        self._attr_unique_id    = f"{qp_device.id}_{device_class}"
        self._attr_name         = f"{qp_device.name} {device_class}"

        if device_class==DC_STATUS:
            self._attr_name = f"{qp_device.name} Status"

        #if device_class==SensorDeviceClass.TEMPERATURE:
        #    self._attr_unit_of_measurement

    # never called
    # @property
    # def native_unit_of_measurement(self):
    #    if self.device_class==SensorDeviceClass.TEMPERATURE:
    #        if self._qp_device.info:
    #            if 'temperatureUnit' in self._qp_device.info:
    #                if self._qp_device.info['temperatureUnit']=='celsius':
    #                    return UnitOfTemperature.CELSIUS
    #                else:
    #                    return UnitOfTemperature.FAHRENHEIT

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
        # Sensors should also register callbacks to HA when their state changes
        self._qp_device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
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
        elif self.device_class==DC_STATUS:
            return 'data in attributes'
        else:
            return False


    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.device_class!=DC_STATUS:
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

class BatterySensor(SensorBase):
    device_class = SensorDeviceClass.BATTERY

    def __init__(self, qp_device: Qingping):
        super().__init__(qp_device)
        self._attr_unique_id = f"{qp_device.id}_battery"
        self._attr_name = f"{qp_device.name} Battery"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._qp_device.battery_level
