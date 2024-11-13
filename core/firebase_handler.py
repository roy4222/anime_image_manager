# core/firebase_handler.py
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime
from typing import Optional, List
from loguru import logger
from models.image_data import ImageData
from config.config import Config

class FirebaseHandler:
    """處理 Firebase 資料庫操作"""
    
    def __init__(self):
        """初始化 Firebase 處理器"""
        try:
            # 初始化 Firebase
            cred = credentials.Certificate(Config.FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred, {
                'databaseURL': Config.FIREBASE_DATABASE_URL
            })
            
            # 獲取資料庫參考
            self.db = db.reference()
            self.images_ref = self.db.child('images')
            self.anime_ref = self.db.child('anime_titles')
            
            logger.info("Successfully connected to Firebase")
            
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            raise
    
    async def save_image_data(self, image_data: ImageData) -> bool:
        """儲存圖片資料到 Firebase"""
        try:
            # 準備資料
            data = {
                'path': image_data.path,
                'name': image_data.name,
                'anime_title': image_data.anime_title,
                'episode': image_data.episode,
                'timestamp': image_data.timestamp,
                'upload_time': image_data.upload_time.isoformat() + 'Z'
            }
            
            # 儲存資料
            new_image_ref = self.images_ref.push(data)
            
            # 更新動畫標題索引
            await self._update_anime_titles(image_data.anime_title)
            
            logger.info(f"Successfully saved image data with ID: {new_image_ref.key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save image data: {e}")
            return False
    
    async def _update_anime_titles(self, title: str):
        """更新動畫標題索引"""
        try:
            sanitized_title = self._sanitize_key(title)
            self.anime_ref.child(sanitized_title).set({
                'title': title,
                'last_updated': datetime.now().isoformat() + 'Z'
            })
        except Exception as e:
            logger.warning(f"Failed to update anime titles index: {e}")
    
    def _sanitize_key(self, key: str) -> str:
        """清理 Firebase key"""
        return ''.join(c for c in key if c.isalnum() or c in '_-')
    
    async def get_image_by_anime(self, anime_title: str) -> List[ImageData]:
        """根據動畫標題獲取圖片資料"""
        try:
            images = self.images_ref\
                .order_by_child('anime_title')\
                .equal_to(anime_title)\
                .get()
            
            return [ImageData.from_dict(data) for data in images.values()] if images else []
            
        except Exception as e:
            logger.error(f"Failed to get images for anime {anime_title}: {e}")
            return []
    
    async def get_all_anime_titles(self) -> List[str]:
        """獲取所有動畫標題"""
        try:
            titles = self.anime_ref.get()
            return [data['title'] for data in titles.values()] if titles else []
            
        except Exception as e:
            logger.error(f"Failed to get anime titles: {e}")
            return []