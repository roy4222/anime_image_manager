# core/google_drive_handler.py
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import pickle
import os
from typing import List, Dict, Optional
from loguru import logger
from config.config import Config
import asyncio
import aiohttp

class GoogleDriveHandler:
    """處理 Google Drive 相關操作"""
    
    def __init__(self):
        """初始化 Google Drive 處理器"""
        self.SCOPES = [
            'https://www.googleapis.com/auth/drive',  # 完整的 Drive 存取權限
        ]
        self.service = self._get_drive_service()
    
    async def check_folder_exists(self, folder_id: str) -> bool:
        """檢查資料夾是否存在且可訪問"""
        try:
            file = self.service.files().get(
                fileId=folder_id,
                fields='id, name, mimeType'
            ).execute()
            
            # 檢查是否為資料夾
            is_folder = file.get('mimeType') == 'application/vnd.google-apps.folder'
            if not is_folder:
                logger.error(f"ID {folder_id} 不是資料夾")
                await self.list_available_folders()  # 列出可用的資料夾
                return False
                
            logger.info(f"成功找到資料夾：{file.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"檢查資料夾時發生錯誤: {str(e)}")
            await self.list_available_folders()  # 列出可用的資料夾
            return False
    
    def _get_drive_service(self):
        """取得 Google Drive 服務實例"""
        try:
            creds = None
            # 檢查是否存在 token
            if os.path.exists(Config.TOKEN_PATH):
                with open(Config.TOKEN_PATH, 'rb') as token:
                    creds = pickle.load(token)
            
            # 如果沒有憑證或憑證無效
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        Config.GOOGLE_CREDENTIALS_PATH, self.SCOPES)
                    creds = flow.run_local_server(port=0)
                
                # 保存憑證
                with open(Config.TOKEN_PATH, 'wb') as token:
                    pickle.dump(creds, token)
            
            # 建立服務
            service = build('drive', 'v3', credentials=creds)
            logger.info("Successfully connected to Google Drive")
            return service
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {e}")
            raise
    
    async def get_images_from_folder(self, folder_id: str, start_index: int = 0) -> List[Dict]:
        """從指定資料夾獲取圖片"""
        try:
            query = f"'{folder_id}' in parents and (mimeType contains 'image/') and trashed=false"
            page_token = self._get_page_token(start_index) if start_index > 0 else None
            
            results = self.service.files().list(
                q=query,
                pageSize=Config.BATCH_SIZE,
                pageToken=page_token,
                fields="nextPageToken, files(id, name, mimeType)",
                orderBy="name",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            
            files = results.get('files', [])
            if not files:
                return []
            
            # 使用 asyncio.gather 並行下載檔案
            tasks = [self._download_file_async(file) for file in files]
            image_items = await asyncio.gather(*tasks)
            
            # 過濾掉下載失敗的項目
            return [item for item in image_items if item is not None]
            
        except Exception as e:
            logger.exception(f"Error fetching images from folder {folder_id}: {e}")
            return []
    
    async def _download_file_async(self, file: Dict) -> Optional[Dict]:
        """非同步下載檔案"""
        for retry in range(Config.MAX_RETRIES):
            try:
                # 使用 service.files().get() 獲取檔案資訊
                request = self.service.files().get(
                    fileId=file['id'],
                    fields='id, name, webContentLink'
                ).execute()
                
                # 使用 aiohttp 下載檔案
                async with aiohttp.ClientSession() as session:
                    async with session.get(request['webContentLink']) as response:
                        if response.status == 200:
                            content = await response.read()
                            return {
                                "path": file['id'],
                                "name": file['name'],
                                "content": content
                            }
                        else:
                            logger.error(f"Failed to download {file['name']}: HTTP {response.status}")
                            
            except Exception as e:
                if retry == Config.MAX_RETRIES - 1:
                    logger.error(f"Failed to download {file['name']} after {Config.MAX_RETRIES} retries: {e}")
                await asyncio.sleep(1)  # 重試前等待
        return None
    
    def _download_file_with_chunks(self, file_id: str) -> Optional[bytes]:
        """使用分塊下載檔案（備用方法）"""
        try:
            request = self.service.files().get_media(fileId=file_id)
            file = io.BytesIO()
            downloader = MediaIoBaseDownload(
                file, 
                request, 
                chunksize=Config.DOWNLOAD_CHUNK_SIZE
            )
            
            done = False
            while not done:
                try:
                    _, done = downloader.next_chunk()
                except Exception as chunk_error:
                    logger.error(f"Chunk download error: {chunk_error}")
                    break
            
            if done:
                return file.getvalue()
            return None
            
        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {e}")
            return None
    
    async def rename_file(self, file_id: str, new_name: str) -> bool:
        """重命名檔案"""
        try:
            file = self.service.files().update(
                fileId=file_id,
                body={'name': new_name},
                fields='id, name'
            ).execute()
            
            logger.info(f"Successfully renamed file to: {file.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"Error renaming file {file_id} to {new_name}: {e}")
            return False
    
    def _get_page_token(self, start_index: int) -> Optional[str]:
        """獲取分頁 token"""
        try:
            if start_index == 0:
                return None
            
            pages_to_skip = start_index // Config.BATCH_SIZE
            query = f"'{Config.FOLDER_ID}' in parents and (mimeType contains 'image/') and trashed=false"
            
            page_token = None
            for _ in range(pages_to_skip):
                results = self.service.files().list(
                    q=query,
                    pageSize=Config.BATCH_SIZE,
                    pageToken=page_token,
                    fields="nextPageToken"
                ).execute()
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            return page_token
            
        except Exception as e:
            logger.error(f"Error getting page token: {e}")
            return None
    
    async def list_available_folders(self):
        """列出可訪問的資料夾"""
        try:
            # 查詢資料夾
            results = self.service.files().list(
                q="mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces='drive',
                fields='files(id, name)',
                pageSize=10
            ).execute()
            
            folders = results.get('files', [])
            
            if not folders:
                logger.warning("沒有找到任何資料夾")
                return
            
            logger.info("可用的資料夾：")
            for folder in folders:
                logger.info(f"資料夾名稱: {folder['name']}, ID: {folder['id']}")
                
        except Exception as e:
            logger.error(f"列出資料夾時發生錯誤: {str(e)}")

    async def check_folder_exists(self, folder_id: str) -> bool:
        """檢查資料夾是否存在"""
        try:
            self.service.files().get(fileId=folder_id).execute()
            return True
        except Exception:
            return False