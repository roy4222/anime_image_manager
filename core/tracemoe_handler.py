# core/tracemoe_handler.py
import aiohttp
import asyncio
from typing import Optional, Dict
from loguru import logger
from config.config import Config
import re

class TraceMoeHandler:
    """處理 trace.moe API 請求"""
    
    def __init__(self):
        """初始化 trace.moe 處理器"""
        self.base_url = "https://api.trace.moe/search"
        self.anilist_url = "https://graphql.anilist.co"
        self.api_key = Config.TRACE_MOE_API_KEY
        self._last_request_time = 0
        self._title_cache = {}  # 快取已查詢過的標題
        self._session = None
        self._anilist_session = None
    
    async def _get_session(self):
        """取得或創建 session"""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def _get_anilist_session(self):
        """取得或創建 anilist session"""
        if self._anilist_session is None:
            self._anilist_session = aiohttp.ClientSession()
        return self._anilist_session
    
    async def _get_anilist_title(self, anilist_id: int) -> Optional[str]:
        """從 Anilist 獲取日文標題"""
        if anilist_id in self._title_cache:
            return self._title_cache[anilist_id]
            
        query = '''
        query ($id: Int) {
            Media (id: $id, type: ANIME) {
                title {
                    native
                    romaji
                }
            }
        }
        '''
        
        try:
            session = await self._get_anilist_session()
            async with session.post(
                self.anilist_url,
                json={'query': query, 'variables': {'id': anilist_id}}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    media = data.get('data', {}).get('Media', {})
                    titles = media.get('title', {})
                    
                    # 優先使用日文標題，如果沒有則使用羅馬拼音
                    title = titles.get('native') or titles.get('romaji')
                    if title:
                        self._title_cache[anilist_id] = title
                        return title
                        
                logger.warning(f"Failed to get title from Anilist for ID {anilist_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching Anilist title: {e}")
            return None
    
    def _clean_title(self, title: str) -> str:
        """清理標題，移除不合法的檔案名稱字符"""
        try:
            # 移除不合法的檔案名稱字符
            illegal_chars = '<>:"/\\|?*'
            for char in illegal_chars:
                title = title.replace(char, '_')
            
            # 限制標題長度
            if len(title) > 100:
                title = title[:97] + "..."
                
            return title.strip()
            
        except Exception as e:
            logger.error(f"Error cleaning title: {e}")
            return "Unknown"
    
    async def _get_japanese_title(self, match_data: Dict) -> str:
        """獲取日文標題"""
        try:
            # 從 anilist ID 獲取標題
            anilist_id = match_data.get('anilist')
            if isinstance(anilist_id, (int, str)):
                title = await self._get_anilist_title(int(anilist_id))
                if title:
                    return self._clean_title(title)
            
            # 如果無法獲取 Anilist 標題，使用檔案名稱
            if isinstance(match_data.get('filename'), str):
                filename = match_data['filename']
                clean_title = self._clean_filename(filename)
                if clean_title and clean_title != "Unknown":
                    return clean_title
            
            return "Unknown"
            
        except Exception as e:
            logger.error(f"Error getting title: {e}")
            logger.debug(f"Match data: {match_data}")
            return "Unknown"
    
    async def identify_image(self, image_data: bytes) -> Optional[Dict]:
        """識別動畫圖片"""
        try:
            await self._rate_limit()
            session = await self._get_session()
            
            data = aiohttp.FormData()
            data.add_field('image', image_data)
            
            headers = {}
            if hasattr(Config, 'TRACE_MOE_API_KEY') and Config.TRACE_MOE_API_KEY:
                headers['x-trace-key'] = Config.TRACE_MOE_API_KEY
            
            async with session.post(self.base_url, data=data, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    if not result.get("result"):
                        logger.warning("No matches found by trace.moe")
                        return None
                    
                    best_match = result["result"][0]
                    logger.debug(f"API Response: {best_match}")
                    
                    if not self._validate_match_data(best_match):
                        logger.warning("Invalid match data received from trace.moe")
                        return None
                    
                    title = await self._get_japanese_title(best_match)
                    logger.debug(f"Got title: {title}")  # 添加日誌以追蹤標題
                    
                    return {
                        "anime_title": title,
                        "episode": self._get_episode(best_match),
                        "timestamp": self._format_timestamp(best_match.get("from")),
                        "similarity": round(best_match.get("similarity", 0) * 100, 2)
                    }
                elif response.status == 402:
                    logger.error("Trace.moe API 需要付費或超出免費配額限制")
                    return None
                else:
                    logger.error(f"Trace.moe API returned status code: {response.status}")
                    return None
                    
        except Exception as e:
            logger.exception(f"Error in trace.moe API call: {e}")
            return None
    
    async def _rate_limit(self):
        """實施請求限制"""
        current_time = asyncio.get_event_loop().time()
        time_since_last_request = current_time - self._last_request_time
        
        if time_since_last_request < Config.TRACE_MOE_RATE_LIMIT:
            delay = Config.TRACE_MOE_RATE_LIMIT - time_since_last_request
            logger.debug(f"Rate limiting: waiting {delay:.2f} seconds")
            await asyncio.sleep(delay)
        
        self._last_request_time = asyncio.get_event_loop().time()
    
    def _validate_match_data(self, match_data: Dict) -> bool:
        """驗證匹配資料的有效性"""
        try:
            # 檢查基本結構
            if not isinstance(match_data, dict):
                logger.warning("Match data is not a dictionary")
                return False
            
            # 檢查必要欄位
            required_fields = ['anilist', 'filename', 'episode', 'similarity']
            if not all(field in match_data for field in required_fields):
                logger.warning("Missing required fields in match data")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating match data: {e}")
            return False
    
    def _get_episode(self, match_data: Dict) -> str:
        """獲取集數資訊"""
        episode = match_data.get("episode")
        if isinstance(episode, list):
            return f"{episode[0]:02d}" if episode else "00"
        return f"{episode:02d}" if episode is not None else "00"
    
    def _format_timestamp(self, seconds: Optional[float]) -> str:
        """將秒數轉換為 HH:MM:SS 格式"""
        try:
            if seconds is None:
                return "00:00:00"
            
            total_seconds = int(seconds)
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
        except (TypeError, ValueError):
            logger.warning(f"Invalid timestamp value: {seconds}")
            return "00:00:00"
    
    def _clean_filename(self, filename: str) -> str:
        """清理檔案名稱，移除不需要的標記"""
        try:
            # 移除常見的發布組標記
            patterns = [
                r'\[New-raws\]',
                r'\[raw\]',
                r'\[\d+x\d+\]',  # 解析度標記
                r'\[1080p\]',
                r'\[720p\]',
                r'\[NF\]',
                r'\[CR\]',
                r'\[BD\]',
                r'\[DVD\]',
                r'\[WEB\]',
                r'\[\d+~\d+\]',  # 集數範圍
                r'\s*-\s*\d+~\d+\s*'  # 集數範圍（無括號）
            ]
            
            for pattern in patterns:
                filename = re.sub(pattern, '', filename, flags=re.IGNORECASE)
            
            # 移除多餘的空格和破折號
            filename = re.sub(r'\s+', ' ', filename)
            filename = re.sub(r'\s*-\s*', ' ', filename)
            
            # 移除開頭和結尾的空格和破折號
            clean_title = filename.strip(' -')
            
            # 如果清理後的標題為空，返回 Unknown
            return clean_title if clean_title else "Unknown"
            
        except Exception as e:
            logger.error(f"Error cleaning filename: {e}")
            return "Unknown"