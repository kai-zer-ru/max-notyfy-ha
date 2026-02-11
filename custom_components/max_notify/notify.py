"""Notify platform for Max Notify integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    API_BASE_URL,
    API_PATH_MESSAGES,
    CONF_ACCESS_TOKEN,
    CONF_CHAT_ID,
    CONF_RECIPIENT_TYPE,
    CONF_USER_ID,
    DOMAIN,
    RECIPIENT_TYPE_CHAT,
    RECIPIENT_TYPE_USER,
)

_LOGGER = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4000


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Max Notify notify entity from a config entry."""
    async_add_entities([MaxNotifyEntity(entry)])


class MaxNotifyEntity(NotifyEntity):
    """Representation of a Max Notify entity."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the notify entity."""
        self._entry = entry
        self._attr_unique_id = entry.entry_id
        suffix = "default"
        if entry.data.get(CONF_RECIPIENT_TYPE) == RECIPIENT_TYPE_USER and entry.data.get(CONF_USER_ID):
            suffix = f"user_{entry.data[CONF_USER_ID]}"
        elif entry.data.get(CONF_CHAT_ID):
            suffix = f"chat_{entry.data[CONF_CHAT_ID]}"
        self._attr_name = f"Max {suffix}"

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message to the Max chat/user."""
        text = f"{title}\n{message}" if title else message
        if len(text) > MAX_MESSAGE_LENGTH:
            _LOGGER.warning("Message truncated from %d to %d characters", len(text), MAX_MESSAGE_LENGTH)
            text = text[:MAX_MESSAGE_LENGTH]

        token = self._entry.data.get(CONF_ACCESS_TOKEN)
        if not token:
            _LOGGER.error("No access token in config entry")
            return

        params: dict[str, Any] = {}
        if self._entry.data.get(CONF_RECIPIENT_TYPE) == RECIPIENT_TYPE_USER:
            uid = self._entry.data.get(CONF_USER_ID)
            if uid is not None:
                params["user_id"] = uid
        else:
            cid = self._entry.data.get(CONF_CHAT_ID)
            if cid is not None:
                params["chat_id"] = cid

        if not params:
            _LOGGER.error("Neither user_id nor chat_id in config entry")
            return

        url = f"{API_BASE_URL}{API_PATH_MESSAGES}"
        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
        }
        payload = {"text": text}

        try:
            session = async_get_clientsession(self.hass)
            async with session.post(
                url,
                params=params,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    _LOGGER.error("Max API send failed: status=%s body=%s", resp.status, body[:500])
                    return
                _LOGGER.debug("Message sent successfully")
        except aiohttp.ClientError as e:
            _LOGGER.error("Max API request failed: %s", e)
        except Exception as e:
            _LOGGER.exception("Unexpected error sending Max message: %s", e)
