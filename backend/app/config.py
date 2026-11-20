from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI 3D Toy Studio"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    database_url: str = f"sqlite:///{(ROOT_DIR / 'storage' / 'toy_studio.db').as_posix()}"
    storage_root: Path = ROOT_DIR / "storage"

    blender_executable: str = r"D:\blander5.3\blender.exe"
    blender_timeout_seconds: int = 300
    blender_scripts_dir: Path = ROOT_DIR / "blender" / "scripts"

    bambu_studio_executable: str = ""

    ai_provider: str = "meshy"
    meshy_api_key: str = ""
    meshy_base_url: str = "https://api.meshy.ai"
    tripo_api_key: str = ""
    tripo_base_url: str = "https://api.tripo3d.ai"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    def ensure_storage(self) -> None:
        for name in (
            "projects",
            "source",
            "generated",
            "processed",
            "exports",
            "previews",
        ):
            (self.storage_root / name).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_storage()
    return settings
