# config/config.py
from pathlib import Path
from dotenv import load_dotenv
import os
import sys
from loguru import logger

# 載入環境變數
load_dotenv()

class Config:
    # 基本路徑設定
    BASE_DIR = Path(__file__).parent.parent
    
    @staticmethod
    def _get_env_or_exit(key: str, default: str = None) -> str:
        """獲取環境變數，如果不存在則退出程式"""
        value = os.getenv(key, default)
        if value is None:
            logger.error(f"環境變數 {key} 未設定")
            sys.exit(1)
        return value
    
    # Google Drive configuration
    GOOGLE_CREDENTIALS_PATH = str(BASE_DIR / "credentials.json")
    TOKEN_PATH = str(BASE_DIR / "token.json")
    FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
    
    # Firebase configuration
    FIREBASE_CREDENTIALS_PATH = str(BASE_DIR / "anime-picture1-firebase-adminsdk-zzgqj-cd8d4db203.json")
    FIREBASE_DATABASE_URL = os.getenv('FIREBASE_DATABASE_URL')
    
    # Batch processing configuration
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', '100'))
    CONCURRENT_LIMIT = int(os.getenv('CONCURRENT_LIMIT', '5'))
    
    # API Rate Limiting
    TRACE_MOE_RATE_LIMIT = int(os.getenv('TRACE_MOE_RATE_LIMIT', '10'))
    
    # Performance optimization
    DOWNLOAD_CHUNK_SIZE = 1024 * 1024  # 1MB
    MAX_RETRIES = 3
    
    # Trace.moe configuration
    TRACE_MOE_API_KEY = os.getenv('TRACE_MOE_API_KEY', '')

    @classmethod
    def validate_config(cls):
        """驗證配置是否完整"""
        # 驗證必要的環境變數
        required_env_vars = {
            'GOOGLE_DRIVE_FOLDER_ID': cls.FOLDER_ID,
            'FIREBASE_DATABASE_URL': cls.FIREBASE_DATABASE_URL
        }
        
        for var_name, value in required_env_vars.items():
            if not value:
                logger.error(f"環境變數 {var_name} 未設定")
                sys.exit(1)
        
        # 驗證必要的檔案
        required_files = [
            (cls.GOOGLE_CREDENTIALS_PATH, "Google Drive credentials"),
            (cls.FIREBASE_CREDENTIALS_PATH, "Firebase credentials")
        ]
        
        for file_path, description in required_files:
            if not Path(file_path).exists():
                logger.error(f"找不到 {description} 檔案: {file_path}")
                sys.exit(1)