"""Config flow for Max Notify integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    API_BASE_URL,
    API_PATH_ME,
    CONF_ACCESS_TOKEN,
    CONF_CHAT_ID,
    CONF_RECIPIENT_TYPE,
    CONF_USER_ID,
    DOMAIN,
    RECIPIENT_TYPE_CHAT,
    RECIPIENT_TYPE_USER,
)

_LOGGER = logging.getLogger(__name__)


async def _validate_token(hass: HomeAssistant, token: str) -> str | None:
    """Validate the access token by calling GET /me. Returns error string or None."""
    url = f"{API_BASE_URL}{API_PATH_ME}"
    headers = {"Authorization": token}
    try:
        session = async_get_clientsession(hass)
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                return None
            if resp.status == 401:
                return "invalid_auth"
            text = await resp.text()
            _LOGGER.warning("Max API /me failed: status=%s body=%s", resp.status, text[:200])
            return "cannot_connect"
    except aiohttp.ClientError as e:
        _LOGGER.warning("Max API request failed: %s", e)
        return "cannot_connect"
    except Exception as e:
        _LOGGER.exception("Unexpected error validating Max token: %s", e)
        return "unknown"


class MaxNotifyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Max Notify."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._token: str | None = None
        self._recipient_type: str | None = None
        self._user_id: str | None = None
        self._chat_id: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step (token)."""
        if user_input is not None:
            self._token = user_input[CONF_ACCESS_TOKEN].strip()
            if not self._token:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._schema_token(),
                    errors={"base": "invalid_token"},
                )
            err = await _validate_token(self.hass, self._token)
            if err:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._schema_token(),
                    errors={"base": err},
                )
            return await self.async_step_recipient()

        return self.async_show_form(step_id="user", data_schema=self._schema_token())

    def _schema_token(self):
        return self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    vol.Required(CONF_ACCESS_TOKEN): str,
                }
            ),
            {CONF_ACCESS_TOKEN: self._token or ""},
        )

    async def async_step_recipient(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Ask for recipient type and user_id or chat_id."""
        if user_input is not None:
            self._recipient_type = user_input[CONF_RECIPIENT_TYPE]
            if self._recipient_type == RECIPIENT_TYPE_USER:
                raw = user_input.get(CONF_USER_ID, "").strip()
                if not raw:
                    return self.async_show_form(
                        step_id="recipient",
                        data_schema=self._schema_recipient(),
                        errors={"base": "user_id_required"},
                    )
                try:
                    uid = int(raw)
                    if uid <= 0:
                        raise ValueError("user_id must be positive")
                except ValueError:
                    return self.async_show_form(
                        step_id="recipient",
                        data_schema=self._schema_recipient(),
                        errors={"base": "invalid_user_id"},
                    )
                self._user_id = str(uid)
                self._chat_id = None
            else:
                raw = user_input.get(CONF_CHAT_ID, "").strip()
                if not raw:
                    return self.async_show_form(
                        step_id="recipient",
                        data_schema=self._schema_recipient(),
                        errors={"base": "chat_id_required"},
                    )
                try:
                    cid = int(raw)
                    if cid <= 0:
                        raise ValueError("chat_id must be positive")
                except ValueError:
                    return self.async_show_form(
                        step_id="recipient",
                        data_schema=self._schema_recipient(),
                        errors={"base": "invalid_chat_id"},
                    )
                self._chat_id = str(cid)
                self._user_id = None

            return await self._create_entry()

        return self.async_show_form(step_id="recipient", data_schema=self._schema_recipient())

    def _schema_recipient(self):
        return self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    vol.Required(CONF_RECIPIENT_TYPE): vol.In([RECIPIENT_TYPE_USER, RECIPIENT_TYPE_CHAT]),
                    vol.Optional(CONF_USER_ID, default=""): str,
                    vol.Optional(CONF_CHAT_ID, default=""): str,
                }
            ),
            {
                CONF_RECIPIENT_TYPE: self._recipient_type or RECIPIENT_TYPE_USER,
                CONF_USER_ID: self._user_id or "",
                CONF_CHAT_ID: self._chat_id or "",
            },
        )

    async def _create_entry(self) -> FlowResult:
        """Create the config entry."""
        data: dict[str, Any] = {
            CONF_ACCESS_TOKEN: self._token,
            CONF_RECIPIENT_TYPE: self._recipient_type,
        }
        if self._user_id:
            data[CONF_USER_ID] = int(self._user_id)
        else:
            data[CONF_CHAT_ID] = int(self._chat_id)

        unique_suffix = self._user_id or self._chat_id or "default"
        await self.async_set_unique_id(f"max_notify_{unique_suffix}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"Max Notify ({unique_suffix})",
            data=data,
        )
