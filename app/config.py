from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    gigachat_auth_token: str
    reports_dir: str = "./reports"

    admin_username: str = "admin"
    admin_password: str = "changeme"

    bitrix_portal: str = ""
    bitrix_user_id: str = ""
    bitrix_webhook_token: str = ""

    @property
    def bitrix_configured(self) -> bool:
        return bool(self.bitrix_portal and self.bitrix_webhook_token)


settings = Settings()