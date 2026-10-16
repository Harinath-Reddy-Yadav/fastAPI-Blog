from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    secret_key: SecretStr
    algorithm: str = "HS256"

    access_token_expire: int = 30

    max_upload_size_bytes: int = 10 * 1024 * 1024   #10MB

    posts_per_page: int = 10   #default page size


settings = Settings() #Loads from .env   
    
    