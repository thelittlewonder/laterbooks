from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

LoginMethod = Literal["goodreads", "amazon"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    goodreads_email: str = ""
    goodreads_password: str = ""
    goodreads_storage_state: str = ""
    goodreads_login_method: LoginMethod = "goodreads"
    max_photos: int = 10
    playwright_headless: bool = True
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
