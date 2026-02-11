"""Constants for the Max Notify integration."""

DOMAIN = "max_notify"

CONF_ACCESS_TOKEN = "access_token"
CONF_RECIPIENT_TYPE = "recipient_type"
CONF_USER_ID = "user_id"
CONF_CHAT_ID = "chat_id"

RECIPIENT_TYPE_USER = "user"
RECIPIENT_TYPE_CHAT = "chat"

API_BASE_URL = "https://platform-api.max.ru"
API_PATH_ME = "/me"
API_PATH_MESSAGES = "/messages"
# Версия API: в Go-клиенте добавляется query-параметр "v" к каждому запросу (api.go: version = "1.2.5")
API_VERSION = "1.2.5"
