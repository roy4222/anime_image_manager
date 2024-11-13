 # models/image_data.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ImageData:
    """圖片資料模型"""
    path: str          # 檔案路徑或 ID
    name: str          # 檔案名稱
    anime_title: str   # 動畫標題
    episode: str       # 集數
    timestamp: str     # 時間戳記
    upload_time: datetime  # 上傳/處理時間
    
    def to_dict(self):
        """轉換為字典格式"""
        return {
            "path": self.path,
            "name": self.name,
            "anime_title": self.anime_title,
            "episode": self.episode,
            "timestamp": self.timestamp,
            "upload_time": self.upload_time.isoformat() + 'Z'
        }
    
    @staticmethod
    def from_dict(data: dict):
        """從字典建立實例"""
        return ImageData(
            path=data["path"],
            name=data["name"],
            anime_title=data["anime_title"],
            episode=data["episode"],
            timestamp=data["timestamp"],
            upload_time=datetime.fromisoformat(data["upload_time"].rstrip('Z'))
        )