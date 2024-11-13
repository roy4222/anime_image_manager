# Anime Image Manager

這是一個自動化的動畫截圖管理工具，能夠自動識別動畫截圖並進行重命名和管理。整合了 Google Drive、Firebase 和 trace.moe API，提供完整的檔案管理解決方案。

## 功能特點

- 🔍 自動識別動畫截圖（使用 trace.moe API）
- 📝 智能重命名（包含日文動畫名稱、集數和時間戳記）
- 🔄 Google Drive 整合
- 🗄️ Firebase 資料庫儲存
- 📦 支援批次處理
- ⏸️ 斷點續傳功能
- 📊 詳細的進度追蹤和統計
- 🚀 非同步處理提升效能
- 📝 完整的日誌記錄

##架構 

anime_image_manager/
├── config/ # 配置相關
│ └── config.py # 環境變數和系統配置
│ ├── Google Drive 設定
│ ├── Firebase 設定
│ ├── Trace.moe 設定
│ └── 效能參數設定
├── core/ # 核心功能模組
│ ├── init.py
│ ├── google_drive_handler.py # Google Drive 操作
│ │ ├── 檔案上傳/下載
│ │ ├── 檔案重命名
│ │ └── 資料夾管理
│ ├── tracemoe_handler.py # Trace.moe API 操作
│ │ ├── 動畫識別
│ │ ├── 日文標題獲取
│ │ └── API 請求管理
│ └── firebase_handler.py # Firebase 資料庫操作
│ ├── 資料儲存
│ └── 資料查詢
├── models/ # 資料模型
│ └── image_data.py # 圖片資料結構定義
├── utils/ # 工具函數
│ ├── init.py
│ └── helpers.py # 通用輔助函數
├── logs/ # 日誌檔案
│ └── anime_manager_{time}.log
├── main.py # 主程式入口
│ ├── 初始化各個處理器
│ ├── 處理流程控制
│ ├── 進度追蹤
│ └── 錯誤處理
├── requirements.txt # 依賴套件清單
├── .env # 環境變數（本地）
├── .env.example # 環境變數範例
├── .gitignore # Git 忽略清單
├── credentials.json # Google Drive API 憑證
├── token.json # Google Drive 存取令牌
└── README.md # 專案說明文件
## 核心模組功能說明

### 1. config/config.py
- 環境變數管理和驗證
- API 金鑰和資料庫 URL 設定
- 批次處理和效能參數配置
- 檔案路徑管理

### 2. core/google_drive_handler.py
- Google Drive API 認證和連接
- 檔案上傳和下載功能
- 檔案重命名操作
- 資料夾存取和管理
- 分頁處理和快取機制

### 3. core/tracemoe_handler.py
- Trace.moe API 整合
- 動畫識別和標題提取
- 日文標題獲取（Anilist API）
- API 請求限制控制
- 結果快取管理

### 4. core/firebase_handler.py
- Firebase 資料庫連接
- 資料儲存和更新
- 查詢功能實作
- 即時資料同步

### 5. models/image_data.py
- 圖片資料模型定義
- 資料驗證邏輯
- 資料格式轉換
- 序列化功能

### 6. main.py
- 程式進入點
- 處理器初始化
- 流程控制邏輯
- 進度追蹤和顯示
- 錯誤處理機制
- 斷點續傳功能

## 安裝需求

1. Python 3.9+
2. 必要的 Python 套件：

