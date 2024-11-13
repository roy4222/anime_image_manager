# main.py
import asyncio
import sys
import json
import time
from datetime import datetime
from typing import Optional, Set
from tqdm import tqdm
from loguru import logger
from pathlib import Path
from core.firebase_handler import FirebaseHandler
from core.google_drive_handler import GoogleDriveHandler
from core.tracemoe_handler import TraceMoeHandler
from models.image_data import ImageData
from config.config import Config
import re

class AnimeImageManager:
    def __init__(self):
        """初始化管理器"""
        # 設定日誌
        self._setup_logger()
        
        # 初始化處理器
        try:
            self.firebase = FirebaseHandler()
            self.drive_handler = GoogleDriveHandler()
            self.tracemoe = TraceMoeHandler()
        except Exception as e:
            logger.error(f"Failed to initialize handlers: {e}")
            raise
        
        # 計數器和狀態
        self.processed_count = 0
        self.error_count = 0
        self.start_time = time.time()
        self.processed_files: Set[str] = set()  # 記錄已處理的檔案ID
        self.load_progress()  # 載入先前的進度
        
    def _setup_logger(self):
        """設定日誌系統"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        logger.add(
            log_dir / "anime_manager_{time}.log",
            rotation="500 MB",
            retention="10 days",
            level="INFO",
            encoding="utf-8"
        )
    
    def save_progress(self):
        """儲存處理進度"""
        try:
            progress_data = {
                'processed_files': list(self.processed_files),
                'processed_count': self.processed_count,
                'error_count': self.error_count,
                'last_update': datetime.now().isoformat()
            }
            
            with open('progress.json', 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"進度已保存: {len(self.processed_files)} 個檔案")
            
        except Exception as e:
            logger.error(f"保存進度失敗: {e}")

    def load_progress(self):
        """載入處理進度"""
        try:
            if Path('progress.json').exists():
                with open('progress.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.processed_files = set(data.get('processed_files', []))
                    self.processed_count = data.get('processed_count', 0)
                    self.error_count = data.get('error_count', 0)
                    logger.info(f"已載入先前進度: {len(self.processed_files)} 個檔案")
        except Exception as e:
            logger.error(f"載入進度失敗: {e}")
    
    def display_eta(self, pbar, remaining_count: int):
        """顯示預估剩餘時間"""
        elapsed_time = time.time() - self.start_time
        processed_per_second = self.processed_count / elapsed_time if elapsed_time > 0 else 0
        
        if processed_per_second > 0:
            eta_seconds = remaining_count / processed_per_second
            hours = int(eta_seconds // 3600)
            minutes = int((eta_seconds % 3600) // 60)
            
            pbar.set_postfix({
                'processed': self.processed_count,
                'errors': self.error_count,
                'ETA': f"{hours}h {minutes}m"
            })

    async def process_single_image(self, image: dict) -> Optional[ImageData]:
        """處理單張圖片"""
        try:
            # 檢查是否已處理
            if image['path'] in self.processed_files:
                logger.debug(f"跳過已處理的檔案: {image['name']}")
                return None
                
            logger.info(f"開始處理圖片: {image['name']}")
            
            # 使用 trace.moe 識別動畫
            result = await self.tracemoe.identify_image(image["content"])
            if not result:
                logger.warning(f"無法識別圖片: {image['name']}")
                self.error_count += 1
                return None
            
            # 建立新檔名
            new_name = f"{result['anime_title']}_Episode{result['episode']}_{result['timestamp']}.jpg"
            logger.info(f"新檔名: {new_name}")
            
            # 重命名 Google Drive 檔案
            if await self.drive_handler.rename_file(image["path"], new_name):
                # 儲存資訊到 Firebase
                image_data = ImageData(
                    path=image["path"],
                    name=new_name,
                    anime_title=result["anime_title"],
                    episode=result["episode"],
                    timestamp=result["timestamp"],
                    upload_time=datetime.now()
                )
                
                if await self.firebase.save_image_data(image_data):
                    self.processed_count += 1
                    self.processed_files.add(image["path"])  # 記錄已處理的檔案
                    self.save_progress()  # 儲存進度
                    logger.success(f"成功處理圖片: {new_name}")
                    return image_data
                else:
                    logger.error(f"儲存到 Firebase 失敗: {new_name}")
            else:
                logger.error(f"重命名失敗: {image['name']} -> {new_name}")
            
            self.error_count += 1
            return None
            
        except Exception as e:
            self.error_count += 1
            logger.exception(f"處理圖片時發生錯誤 {image['name']}: {e}")
            return None

    async def process_folder(self):
        """處理資料夾中的所有圖片"""
        try:
            folder_id = Config.FOLDER_ID
            logger.info(f"開始處理資料夾 ID: {folder_id}")
            
            if not await self.drive_handler.check_folder_exists(folder_id):
                logger.error(f"找不到資料夾: {folder_id}")
                await self.drive_handler.list_available_folders()
                return False
            
            start_index = 0
            total_processed = 0
            skipped_count = len(self.processed_files)  # 包含已處理的檔案
            
            with tqdm(desc="處理進度", unit="files") as pbar:
                while True:
                    # 取得所有圖片
                    images = await self.drive_handler.get_images_from_folder(folder_id, start_index)
                    if not images:
                        break
                    
                    # 過濾已處理的檔案
                    unprocessed_images = [
                        img for img in images 
                        if img['path'] not in self.processed_files and not self._is_already_processed(img['name'])
                    ]
                    
                    skipped_count += len(images) - len(unprocessed_images)
                    
                    if not unprocessed_images:
                        logger.info("所有檔案都已處理完成")
                        break
                    
                    # 限制並行處理數量
                    for i in range(0, len(unprocessed_images), Config.CONCURRENT_LIMIT):
                        batch = unprocessed_images[i:i + Config.CONCURRENT_LIMIT]
                        tasks = [self.process_single_image(image) for image in batch]
                        results = await asyncio.gather(*tasks)
                        
                        # 更新進度
                        processed = len([r for r in results if r is not None])
                        total_processed += processed
                        pbar.update(len(batch))
                        
                        # 顯示預估剩餘時間
                        remaining_count = len(unprocessed_images) - total_processed
                        self.display_eta(pbar, remaining_count)
                        
                        # API 請求限制
                        await asyncio.sleep(Config.TRACE_MOE_RATE_LIMIT)
                    
                    self.save_progress()  # 每批次儲存進度
                    start_index += Config.BATCH_SIZE
            
            self._print_summary(skipped_count)
            return True
            
        except Exception as e:
            logger.exception(f"處理資料夾時發生錯誤: {e}")
            return False

    def _is_already_processed(self, filename: str) -> bool:
        """檢查檔案是否已經處理過"""
        patterns = [
            r'.*_Episode\d+_\d{2}:\d{2}:\d{2}\.jpg$',
            r'Anime_\d+_Episode\d+_\d{2}:\d{2}:\d{2}\.jpg$'
        ]
        return any(re.match(pattern, filename) for pattern in patterns)

    def _print_summary(self, skipped_count: int):
        """輸出處理總結"""
        if self.processed_count > 0:
            success_rate = (self.processed_count - self.error_count) / self.processed_count * 100
        else:
            success_rate = 0
            
        elapsed_time = time.time() - self.start_time
        hours = int(elapsed_time // 3600)
        minutes = int((elapsed_time % 3600) // 60)
            
        summary = f"""
處理完成!
------------------------
總檔案數: {self.processed_count + skipped_count}
已處理檔案: {self.processed_count}
跳過檔案: {skipped_count}
成功處理: {self.processed_count - self.error_count}
錯誤數: {self.error_count}
成功率: {success_rate:.2f}%
處理時間: {hours}小時 {minutes}分鐘
------------------------
"""
        logger.info(summary)
        print(summary)

# main 函數保持不變...

async def main():
    """主程式"""
    try:
        # 驗證配置
        Config.validate_config()
        
        # 建立管理器實例
        manager = AnimeImageManager()
        logger.info("程式啟動")
        
        # 開始處理
        success = await manager.process_folder()
        
        if not success:
            logger.error("處理過程中發生錯誤")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.warning("\n程式被使用者中斷")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"發生意外錯誤: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # 使用 asyncio 運行主程式
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"程式執行失敗: {e}")
        sys.exit(1)