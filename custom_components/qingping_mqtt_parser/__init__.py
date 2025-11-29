from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import hub
from .const import PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Create Hub for entry."""
    entry.runtime_data = hub.Hub(hass, entry.data, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    hub = entry.runtime_data
    await hub.task_stop()

    if (unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS)):
        #entry.runtime_data.listener()
        pass

    return unload_ok