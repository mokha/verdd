from .base import *

# Database
# https://docs.djangoproject.com/en/2.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": config("DB_ENGINE"),
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST"),
        "PORT": config("DB_PORT"),
        "CHARSET": "utf8mb4",
        "COLLATION": "utf8mb4_bin",
    }
}

if DATABASES["default"]["ENGINE"] == "django.db.backends.mysql":
    DATABASES["default"]["OPTIONS"] = {
        "init_command": "SET character_set_connection=utf8mb4, collation_connection=utf8mb4_bin, default_storage_engine=INNODB",
        "charset": "utf8mb4",
    }
