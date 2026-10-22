from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    storage_dir: Path = ROOT / "storage"
    database_path: Path = ROOT / "storage" / "app.db"

    tts_provider: str = "openai"
    openai_api_key: str = ""
    elevenlabs_api_key: str = ""
    google_tts_api_key: str = ""
    pexels_api_key: str = ""
    pixabay_api_key: str = ""
    image_gen_api_key: str = ""


settings = Settings()
