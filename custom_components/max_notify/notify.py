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
    API_VERSION,
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
    entity = MaxNotifyEntity(entry)
    _LOGGER.debug("Setting up notify entity: %s (entry_id=%s)", entity.name, entry.entry_id)
    async_add_entities([entity])


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
        _LOGGER.debug("MaxNotifyEntity created: name=%s, recipient_type=%s", self._attr_name, entry.data.get(CONF_RECIPIENT_TYPE))

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message to the Max chat/user."""
        text = f"{title}\n{message}" if title else message
        _LOGGER.debug("Preparing message: title=%s, len(message)=%d", title or "(none)", len(message))
        if len(text) > MAX_MESSAGE_LENGTH:
            _LOGGER.warning("Message truncated from %d to %d characters", len(text), MAX_MESSAGE_LENGTH)
            text = text[:MAX_MESSAGE_LENGTH]

        token = self._entry.data.get(CONF_ACCESS_TOKEN)
        if not token:
            _LOGGER.error("No access token in config entry")
            return

        # Как в max-bot-api-client-ts и max-bot-api-client-go: получатель в query, body — NewMessageBody.
        # Go-клиент добавляет query-параметр "v" (версия API) к каждому запросу — без него возможен 403.
        uid = self._entry.data.get(CONF_USER_ID)
        cid = self._entry.data.get(CONF_CHAT_ID)
        if uid is not None and int(uid) != 0:
            url = f"{API_BASE_URL}{API_PATH_MESSAGES}?user_id={int(uid)}&v={API_VERSION}"
            payload = {"text": text}
            _LOGGER.debug("Recipient: user_id=%s", uid)
        elif cid is not None and int(cid) != 0:
            url = f"{API_BASE_URL}{API_PATH_MESSAGES}?chat_id={int(cid)}&v={API_VERSION}"
            payload = {"text": text}
            _LOGGER.debug("Recipient: chat_id=%s", cid)
        else:
            _LOGGER.error(
                "Config must have non-zero user_id or chat_id (user_id=%s, chat_id=%s)",
                uid,
                cid,
            )
            return

        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
        }
        _LOGGER.debug("Request: POST %s, body len=%d", url, len(text))

        try:
            session = async_get_clientsession(self.hass)
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                body = await resp.text()
                if resp.status >= 400:
                    _LOGGER.error(
                        "Max API send failed: status=%s body=%s request_url=%s",
                        resp.status,
                        body[:500],
                        url,
                    )
                    if resp.status == 403 and "chatId" in body and "user_id=" in url:
                        _LOGGER.info(
                            "Подсказка: при 403 для личного сообщения получатель должен первым "
                            "начать диалог с ботом в Max (например, нажать «Начать» или написать боту)."
                        )
                    return
                _LOGGER.info("Message sent successfully (status=%s)", resp.status)
        except aiohttp.ClientError as e:
            _LOGGER.error("Max API request failed: %s", e)
        except Exception as e:
            _LOGGER.exception("Unexpected error sending Max message: %s", e)
