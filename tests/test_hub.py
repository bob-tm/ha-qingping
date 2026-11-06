"""Startup scheduling tests with real HA and a no-network MQTT client.

These tests do not exercise entry unload or real MQTT transport cleanup.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import aiomqtt
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import CoreState, HomeAssistant
import pytest
import pytest_asyncio

from custom_components import qingping_mqtt_parser as integration
from custom_components.qingping_mqtt_parser import hub as hub_module


class MQTTClient:
    """Expose deterministic message and connection-failure boundaries."""

    def __init__(self):
        self.read_started = asyncio.Event()
        self.queue = asyncio.Queue()
        self.connect_error = None
        self.subscriptions = []
        self.exit_types = []
        self.messages = self

    async def __aenter__(self):
        if self.connect_error is not None:
            raise self.connect_error
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        self.exit_types.append(exc_type)

    async def subscribe(self, topic):
        self.subscriptions.append(topic)

    def __aiter__(self):
        return self

    async def __anext__(self):
        self.read_started.set()
        message = await self.queue.get()
        if isinstance(message, Exception):
            raise message
        return message


@pytest_asyncio.fixture
async def environment(tmp_path, monkeypatch):
    """Use HA's actual task tracking, startup and shutdown implementation."""
    hass = HomeAssistant(str(tmp_path))
    entry = SimpleNamespace(data={
        CONF_HOST: "mqtt.example.test",
        CONF_PORT: 1883,
        CONF_USERNAME: "test-user",
        CONF_PASSWORD: "test-password",
    })
    client = MQTTClient()
    factory = Mock(return_value=client)
    monkeypatch.setattr(hub_module.aiomqtt, "Client", factory)
    try:
        yield SimpleNamespace(hass=hass, entry=entry, client=client, factory=factory)
    finally:
        # Also clean up an ordinary task if the startup regression test failed.
        if hasattr(entry, "runtime_data"):
            task = entry.runtime_data.looptask
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if hass.state is not CoreState.stopped:
            await hass.async_stop(force=True)


async def wait_for(event):
    """Use an event for synchronization and a timeout only as a failure guard."""
    await asyncio.wait_for(event.wait(), timeout=1)


async def start_hub(environment):
    assert await integration.async_setup_entry(environment.hass, environment.entry)
    return environment.entry.runtime_data


async def assert_startup_completes(hass, hub):
    await asyncio.wait_for(hass.async_start(), timeout=1)
    assert hass.state is CoreState.running
    await asyncio.wait_for(hass.async_block_till_done(), timeout=1)
    assert not hub.looptask.done()


@pytest.mark.asyncio
async def test_idle_listener_does_not_block_startup(environment):
    hub = await start_hub(environment)
    await wait_for(environment.client.read_started)
    await assert_startup_completes(environment.hass, hub)
    assert hub.looptask.get_name() == "Qingping MQTT listener"
    assert environment.client.subscriptions == ["qingping/+/up"]
    environment.factory.assert_called_once_with(
        hostname="mqtt.example.test", port=1883,
        username="test-user", password="test-password",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["connect", "read"])
async def test_reconnect_backoff_does_not_block_startup(environment, monkeypatch, failure):
    client = environment.client
    if failure == "connect":
        client.connect_error = aiomqtt.MqttError("test connection failure")
    else:
        client.queue.put_nowait(aiomqtt.MqttError("test disconnection"))
    backoff_started = asyncio.Event()
    release_backoff = asyncio.Event()
    delays = []

    async def backoff(delay):
        delays.append(delay)
        backoff_started.set()
        await release_backoff.wait()

    # Keep HA's own asyncio.sleep intact.
    monkeypatch.setattr(hub_module, "asyncio", SimpleNamespace(sleep=backoff))
    hub = await start_hub(environment)
    await wait_for(backoff_started)
    assert delays == [15]
    await assert_startup_completes(environment.hass, hub)


@pytest.mark.asyncio
async def test_background_listener_still_dispatches_messages(environment, monkeypatch):
    hub = await start_hub(environment)
    await wait_for(environment.client.read_started)
    await assert_startup_completes(environment.hass, hub)
    received = asyncio.Event()
    message = SimpleNamespace(topic="qingping/020000000001/up", payload=b"test")

    async def parse_message(value):
        assert value is message
        received.set()

    monkeypatch.setattr(hub, "parse_message", parse_message)
    environment.client.queue.put_nowait(message)
    await wait_for(received)
    await asyncio.wait_for(environment.hass.async_block_till_done(), timeout=1)
    assert not hub.looptask.done()


@pytest.mark.asyncio
async def test_ha_shutdown_cancels_connected_background_listener(environment):
    hub = await start_hub(environment)
    await wait_for(environment.client.read_started)
    await assert_startup_completes(environment.hass, hub)
    await asyncio.wait_for(environment.hass.async_stop(), timeout=1)
    assert environment.hass.state is CoreState.stopped
    assert hub.looptask.cancelled()
    assert environment.client.exit_types == [asyncio.CancelledError]
