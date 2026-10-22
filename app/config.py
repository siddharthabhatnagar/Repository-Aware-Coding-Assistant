import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "RepoPulse - Repository-Aware Coding Assistant"
    APP_VERSION: str = "1.0.0"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    
    # Base workspace directory
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DEFAULT_REPO_PATH: str = str(BASE_DIR / "sample_repo")
    
    # Safe limits for untrusted repositories
    MAX_FILE_SIZE_BYTES: int = 1_000_000  # 1 MB max single file size
    MAX_REPO_FILES: int = 2000            # Max files to index to prevent DoS
    MAX_FILE_LINES: int = 10_000          # Max lines to read
    SAFE_MODE: bool = True                # Prevent dangerous writes/symlinks
    
    # Supported file extensions for code parsing
    SUPPORTED_EXTENSIONS: set = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".md",
        ".yaml", ".yml", ".toml", ".html", ".css", ".sql", ".sh"
    }
    
    # Ignore patterns
    IGNORE_DIRS: set = {
        ".git", ".svn", ".hg", "node_modules", "venv", ".venv",
        "env", "__pycache__", ".pytest_cache", ".mypy_cache",
        "dist", "build", ".next", ".nuxt", "coverage", ".idea", ".vscode"
    }
    
    # Embedding and LLM settings
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    LLM_PROVIDER: str = "auto" # 'auto', 'openai', 'groq', 'gemini', 'mock'
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
