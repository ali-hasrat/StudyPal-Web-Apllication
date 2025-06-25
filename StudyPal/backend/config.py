from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "StudyPal Backend"
    admin_email: str = "admin@studypal.com"
    chroma_db_path: str = "./chroma_db"
    openai_api_key: str = ""
    model_name: str = "gpt-3.5-turbo"
    embedding_model: str = "text-embedding-3-small"

    class Config:
        env_file = ".env"


settings = Settings()