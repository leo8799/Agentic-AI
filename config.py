import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Settings:
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY")
    API_MODEL: str = os.getenv("API_MODEL", "gemini-2.0-flash")
    
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "3001"))
    
    ALLOWED_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5173",
        "http://140.115.126.192:3000",
        "http://140.115.126.192:3001"
    ]
    
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "api_results")
    DOWNLOAD_DIR: str = os.getenv("DOWNLOAD_DIR", "downloads")
    
    MAX_CONCURRENT_TASKS: int = int(os.getenv("MAX_CONCURRENT_TASKS", "3"))
    TASK_TIMEOUT: int = int(os.getenv("TASK_TIMEOUT", "1800"))  # 30分鐘
    
    SELENIUM_HEADLESS: bool = os.getenv("SELENIUM_HEADLESS", "true").lower() == "true"
    SELENIUM_WINDOW_WIDTH: int = int(os.getenv("SELENIUM_WINDOW_WIDTH", "1920"))
    SELENIUM_WINDOW_HEIGHT: int = int(os.getenv("SELENIUM_WINDOW_HEIGHT", "1068"))
    
    CHROMA_DB_PATH: str = os.getenv("CHROMA_DB_PATH", "chroma_db")
    PDF_CHUNK_SIZE: int = int(os.getenv("PDF_CHUNK_SIZE", "1000"))
    PDF_CHUNK_OVERLAP: int = int(os.getenv("PDF_CHUNK_OVERLAP", "200"))

settings = Settings()

def validate_settings():
    """驗證必要的配置是否正確設置"""
    if not settings.GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY is required")
    
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    os.makedirs(settings.DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(settings.CHROMA_DB_PATH, exist_ok=True)

if __name__ == "__main__":
    validate_settings()
    print("Configuration validated successfully!")
    print(f"API Key: {settings.GOOGLE_API_KEY[:10]}...")
    print(f"Output Directory: {settings.OUTPUT_DIR}")
    print(f"Server will run on: {settings.HOST}:{settings.PORT}") 