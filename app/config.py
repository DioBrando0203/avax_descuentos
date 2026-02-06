from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    
    # Tokens - 
    AVAX_TOKEN: str
    ZAP_TOKEN: str

    # URLs base
    AVAX_BASE_URL: str = "https://api.avax.pe/v1"
    ZAP_BASE_URL: str = "https://sap-a.back.ngrok.pizza"

    # Timer entre requests
    REQUEST_DELAY: int = 5

    # Scheduler
    SCHEDULER_HOUR: int = 5
    SCHEDULER_MINUTE: int = 0

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
