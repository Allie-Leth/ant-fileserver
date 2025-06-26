import json
from typing import Dict, Any
from ._env import get_config

class ConfigurationError(Exception):
    """Raised when a required configuration is missing or invalid."""
    pass

class BaseConfig:
    # STORAGE Settings
    _CONFIG_SPEC = {
        "STORAGE_ENDPOINT":       ("STORAGE_ENDPOINT",       None,                               True,  False),
        "STORAGE_BUCKET":         ("STORAGE_BUCKET",         None,                               True,  False),
        "STORAGE_REGION":         ("STORAGE_REGION",         "us-east-1",                        False, False),
        "STORAGE_ACCESS_KEY_ID":  ("STORAGE_ACCESS_KEY_ID",  None,                               True,  False),
        "STORAGE_SECRET_ACCESS_KEY":("STORAGE_SECRET_ACCESS_KEY", None,                          True,  False),
        "JWT_SECRET_KEY":         ("JWT_SECRET_KEY",         None,                               True,  False),
        "API_KEY_ROLES":          ("API_KEY_ROLES",          '{"dev-key":["admin","uploader"]}', False, True),
        "LOG_LEVEL":              ("LOG_LEVEL",              "INFO",                               False, False),
        "DEBUG":                  ("DEBUG",                  "False",                            False, False),
    }

    @classmethod
    def init_app(cls, app):
        """
        Called at runtime after Flask has loaded the class into the app.config
        All get_config calls and validations should be done here.
        """
        for env_var, (conf_key, default, required, is_json) in cls._CONFIG_SPEC.items():
            raw = get_config(env_var, default=default, required=required)
            if is_json:
                try:
                    val: Any = json.loads(raw)
                except json.JSONDecodeError as e:
                    raise ConfigurationError(f"Invalid JSON in {env_var}: {e}")
            elif conf_key == "DEBUG":
                # coerce boolean-ish strings
                val = str(raw).lower() in ("1","true","yes","on")
            else:
                val = raw

            app.config[conf_key] = val
        
        app.logger.info(
            "[Config %s] endpoint=%r bucket=%r API-keys=%d debug=%s",
            cls.__name__,
            app.config["STORAGE_ENDPOINT"],
            app.config["STORAGE_BUCKET"],
            len(app.config["API_KEY_ROLES"]),
            app.config["DEBUG"],
            )


class DevelopmentConfig(BaseConfig):
    pass

class ProductionConfig(BaseConfig):
    pass

config_map: Dict[str, type[BaseConfig]] = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,  # Fallback if no env var set
}