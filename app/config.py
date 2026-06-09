from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "DisciPlan API"
    app_env: str = "development"
    debug: bool = True
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:8080"

    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "disciplan"
    db_ssl: bool = False
    db_ssl_ca_path: str = ""
    # Paste full Aiven CA PEM in Render/Vercel env when ca.pem file is not on disk
    db_ssl_ca: str = ""
    db_pool_min: int = 2
    db_pool_max: int = 10

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7

    otp_expire_minutes: int = 10
    otp_demo_mode: bool = True
    otp_demo_code: str = "123456"

    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    cloudinary_folder: str = "disciplan"

    notification_poll_interval_sec: int = 8
    chat_poll_interval_sec: int = 3

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
