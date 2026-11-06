"""Regression tests against real Home Assistant, without an MQTT connection.

Run with:
mkdir -p .tmp
PYTHONDONTWRITEBYTECODE=1 uv run --python 3.14 \
    --with homeassistant==2026.10.4 --with pytest --with pytest-asyncio \
    --with aiomqtt python -m pytest -q tests --basetemp .tmp/pytest \
    -o asyncio_default_fixture_loop_scope=function
"""

from datetime import timedelta
from inspect import signature
import logging
from types import MappingProxyType, SimpleNamespace

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.const import (
    EntityCategory,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
import pytest
import pytest_asyncio

from custom_components.qingping_mqtt_parser.const import DOMAIN
from custom_components.qingping_mqtt_parser.hub import Qingping
from custom_components.qingping_mqtt_parser.sensor import SensorBase


# Synthetic, locally administered address; not a physical device identifier.
ADDRESS = "020000000001"
MEASUREMENTS = [
    ("temperature", SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, 21.5),
    ("humidity", SensorDeviceClass.HUMIDITY, "%", 42.5),
    ("co2_ppm", SensorDeviceClass.CO2, "ppm", 700),
    ("battery", SensorDeviceClass.BATTERY, "%", 75),
]


@pytest.fixture
def device():
    """Use the real decoded-value container, but never start the MQTT hub."""
    return Qingping(
        SimpleNamespace(online=True),
        ADDRESS,
        {
            "magic": "CG",
            "cmd": "0x34",
            "sensor": {name: value for name, _, _, value in MEASUREMENTS},
            "co2IsBeingCalibrated": False,
            "isPluggedInToPower": True,
        },
    )


@pytest_asyncio.fixture
async def platform(tmp_path):
    """Use HA's real registry, entity-add lifecycle and state machine."""
    hass = HomeAssistant(str(tmp_path))
    try:
        # Older HA creates the device registry in async_load instead.
        if hasattr(dr, "async_setup"):
            dr.async_setup(hass)
        for registry in (dr, er):
            load_options = (
                {"load_empty": True}
                if "load_empty" in signature(registry.async_load).parameters
                else {}
            )
            await registry.async_load(hass, **load_options)
        hass.config_entries = ConfigEntries(hass, {})
        entry = ConfigEntry(
            data={},
            discovery_keys=MappingProxyType({}),
            domain=DOMAIN,
            minor_version=1,
            options={},
            source="user",
            subentries_data=None,
            title="Qingping",
            unique_id=None,
            version=1,
        )
        # Register without async_add(), which would start the real MQTT hub.
        hass.config_entries._entries[entry.entry_id] = entry
        sensor_platform = EntityPlatform(
            hass=hass,
            logger=logging.getLogger(__name__),
            domain="sensor",
            platform_name=DOMAIN,
            platform=None,
            scan_interval=timedelta(seconds=30),
            entity_namespace=None,
        )
        sensor_platform.async_prepare()
        sensor_platform.config_entry = entry
        yield sensor_platform
        await sensor_platform.async_reset()
    finally:
        await hass.async_stop(force=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("name,device_class,unit,reading", MEASUREMENTS)
@pytest.mark.parametrize("sample", ["reading", "zero", "missing"])
async def test_measurement_native_values_and_published_attributes(
    platform, device, name, device_class, unit, reading, sample
):
    value = {"reading": reading, "zero": 0, "missing": None}[sample]
    device.data["sensor"][name] = value
    entity = SensorBase(device, name)
    assert isinstance(entity, SensorEntity)
    assert SensorBase.state is SensorEntity.state
    assert entity.native_value == value
    assert entity.native_unit_of_measurement == unit
    assert entity.state_class == SensorStateClass.MEASUREMENT
    assert entity.device_class == device_class
    assert entity.should_poll is False
    assert entity.entity_category is None
    assert entity.extra_state_attributes is None

    await platform.async_add_entities([entity])
    state = platform.hass.states.get(entity.entity_id)
    assert state is not None
    assert entity.state == value
    assert state.state == (STATE_UNKNOWN if value is None else str(value))
    assert state.attributes["state_class"] == "measurement"
    assert state.attributes["unit_of_measurement"] == unit
    assert state.attributes["device_class"] == device_class


@pytest.mark.asyncio
async def test_temperature_conversion_updates_and_removal(platform, device):
    platform.hass.config.units = US_CUSTOMARY_SYSTEM
    device.info = {"temperatureUnit": "fahrenheit"}
    device.data["sensor"]["temperature"] = 20
    entity = SensorBase(device, "temperature")
    await platform.async_add_entities([entity])

    state = platform.hass.states.get(entity.entity_id)
    assert entity.native_unit_of_measurement == UnitOfTemperature.CELSIUS
    assert entity.native_value == 20
    assert float(entity.state) == pytest.approx(68)
    assert float(state.state) == pytest.approx(68)
    assert state.attributes["unit_of_measurement"] == UnitOfTemperature.FAHRENHEIT
    assert state.attributes["state_class"] == "measurement"
    assert len(device._callbacks) == 1

    device.data["sensor"]["temperature"] = 25
    await device.publish_updates()
    assert float(platform.hass.states.get(entity.entity_id).state) == pytest.approx(77)
    device.data["sensor"]["temperature"] = -10
    await device.publish_updates()
    assert float(platform.hass.states.get(entity.entity_id).state) == pytest.approx(14)
    device.hub.online = False
    await device.publish_updates()
    assert platform.hass.states.get(entity.entity_id).state == STATE_UNAVAILABLE

    await entity.async_remove()
    assert not device._callbacks
    removed_state = platform.hass.states.get(entity.entity_id)
    assert removed_state.state == STATE_UNAVAILABLE
    assert removed_state.attributes["restored"] is True
    device.hub.online = True
    device.data["sensor"]["temperature"] = 30
    await device.publish_updates()
    assert platform.hass.states.get(entity.entity_id) is removed_state


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["co2IsBeingCalibrated", "isPluggedInToPower"])
@pytest.mark.parametrize("value", [False, True])
async def test_boolean_diagnostics_remain_non_statistical(platform, device, name, value):
    device.data[name] = value
    entity = SensorBase(device, name)
    await platform.async_add_entities([entity])

    assert entity.native_value is value
    assert entity.state is value
    assert entity.entity_category == EntityCategory.DIAGNOSTIC
    assert entity.native_unit_of_measurement is None
    assert entity.state_class is None
    assert entity.device_class is None
    state = platform.hass.states.get(entity.entity_id)
    assert state.state == str(value)
    assert not {"state_class", "unit_of_measurement", "device_class"} & state.attributes.keys()


@pytest.mark.asyncio
async def test_status_preserves_debug_attributes(platform, device):
    device.info = {"temperatureUnit": "celsius"}
    device.history_last_index = 3
    device.history_data = {3: {"sensor": {"temperature": 19.5}}}
    entity = SensorBase(device, "status")
    await platform.async_add_entities([entity])

    assert entity.name == f"{ADDRESS} Status"
    assert entity.native_value == "data in attributes"
    assert entity.entity_category == EntityCategory.DIAGNOSTIC
    assert entity.native_unit_of_measurement is None
    assert entity.state_class is None
    state = platform.hass.states.get(entity.entity_id)
    assert state.state == "data in attributes"
    assert state.attributes["info"] == device.info
    assert state.attributes["data"] == device.data
    assert state.attributes["history"] == {
        "last_index": 3,
        3: {"sensor": {"temperature": 19.5}},
    }
    assert "last_index" not in device.history_data
    assert not {"state_class", "unit_of_measurement", "device_class"} & state.attributes.keys()


@pytest.mark.asyncio
async def test_existing_registry_identity_and_device_association(platform, device):
    registry = er.async_get(platform.hass)
    entities = []
    expected_ids = {}
    for name, description in device.sensors.items():
        suffix = description.get("dc", name)
        unique_id = f"{ADDRESS}_{suffix}"
        entity_id = f"sensor.{unique_id.lower()}"
        # Seed the IDs created by the pre-migration integration.
        registered = registry.async_get_or_create(
            "sensor",
            DOMAIN,
            unique_id,
            config_entry=platform.config_entry,
            suggested_object_id=unique_id,
        )
        assert registered.entity_id == entity_id
        expected_ids[name] = entity_id
        entity = SensorBase(device, name)
        assert entity.unique_id == unique_id
        assert entity.device_info == {"identifiers": {(ADDRESS, DOMAIN)}}
        entities.append(entity)

    await platform.async_add_entities(entities)
    assert len(platform.entities) == len(device.sensors)
    assert expected_ids["co2_ppm"] == f"sensor.{ADDRESS}_carbon_dioxide"
    assert {entity.entity_id for entity in entities} == set(expected_ids.values())
    assert len({entity.device_entry.id for entity in entities}) == 1
    for entity in entities:
        assert entity.device_entry.identifiers == {(ADDRESS, DOMAIN)}
        assert platform.hass.states.get(entity.entity_id) is not None
