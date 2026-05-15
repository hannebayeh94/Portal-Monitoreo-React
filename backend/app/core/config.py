from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    database_url: str = "mysql+aiomysql://root:123456789@localhost:3306/react"
    secret_key: str = "super_secreta_llave_portal_ti_2024"
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = "hannejosebayehvillarreal@gmail.com"
    smtp_password: str = "etbn ebyl ulet oqgh"
    cors_origins: str = "http://localhost:3000"
    access_token_expire_minutes: int = 480

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()
