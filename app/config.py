from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    
    # Tokens - 
    AVAX_TOKEN: str
    ZAP_TOKEN: str

    # URLs base
    #AVAX_BASE_URL=https://api.avax.com
    AVAX_BASE_URL: str = "http://127.0.0.1:5000/v1"
    ZAP_BASE_URL: str = "https://zapi.avax.pe"

    # Timer entre requests
    REQUEST_DELAY: int = 3

    # Scheduler
    SCHEDULER_HOUR: int = 5
    SCHEDULER_MINUTE: int = 0

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
