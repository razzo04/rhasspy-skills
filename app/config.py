from pydantic import BaseSettings


class Settings(BaseSettings):
    store_directory: str = r"/data"
    rhasspy_url: str = "http://localhost:12101/api/"


settings = Settings()
