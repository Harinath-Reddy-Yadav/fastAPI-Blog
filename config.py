from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    #Databse url connection
    # postgresql+psycopg://user:password@host:port/dbname
    database_url: str
    
    secret_key: SecretStr
    algorithm: str = "HS256"

    access_token_expire: int = 30

    max_upload_size_bytes: int = 10 * 1024 * 1024   #10MB

    posts_per_page: int = 10   #default page size

    # Email Settings for reset password
    reset_token_expire_minutes: int = 60   #in minutes
    mail_server: str = "localhost"
    mail_port: int = 587   #default port for local
    mail_username: str = ""
    mail_password: SecretStr = SecretStr("")
    mail_from: str = "noreply@example.com"
    mail_use_tls: bool = True


    frontend_url: str = "http://localhost:8000"

    #S3 Configuration
    S3_BUCKET_NAME: str
    S3_REGION: str = "us-east-1"
    S3_ACCESS_KEY_ID: SecretStr | None = None    #For local we need accesskey and secret key but if we deploy within AWS ecosystem then boto3 library will automatically take it using IAM role
    S3_SECRET_ACCESS_KEY: SecretStr | None = None
    s3_endpoint_url: str | None = None    #Thera are S3 compatabile service that runs locally for testing  we need s3_endpoint_url but for real s3 endpoint from AWS its Non



settings = Settings() #Loads from .env   
    
    