#!/usr/bin/env python3
import os
import sys
import subprocess
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_dependencies():
    """檢查必要的依賴"""
    try:
        import fastapi
        import uvicorn
        import selenium
        import chromadb
        logger.info("✓ 所有依賴已安裝")
        return True
    except ImportError as e:
        logger.error(f"✗ 缺少依賴: {e}")
        logger.info("請運行: pip install -r requirements_api.txt")
        return False

def check_environment():
    """檢查環境設定"""
    env_file = Path(".env")
    
    if not env_file.exists():
        logger.error("✗ 未找到 .env 文件")
        logger.info("請運行 ./setup_with_uv.sh 來創建 .env 文件")
        return False
    
    # 檢查 Google API Key
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key or api_key == "your_google_api_key_here":
        logger.error("✗ 請在 .env 文件中設定有效的 GOOGLE_API_KEY")
        return False
    
    logger.info("✓ 環境設定完成")
    return True

def check_chrome_driver():
    """檢查 Chrome 和 ChromeDriver"""
    try:
        result = subprocess.run(["google-chrome", "--version"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"✓ Chrome: {result.stdout.strip()}")
        else:
            logger.warning("⚠️  未找到 Chrome 瀏覽器")
    except FileNotFoundError:
        logger.warning("⚠️  未找到 Chrome 瀏覽器")
    
    logger.info("✓ ChromeDriver 將由 Selenium 自動管理")
    return True

def create_directories():
    """創建必要的目錄"""
    directories = ["api_results", "downloads", "chroma_db", "logs"]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        logger.info(f"✓ 創建目錄: {directory}")

def start_server():
    """啟動 FastAPI 服務器"""
    try:
        logger.info("🚀 啟動 WebVoyager API 服務器...")
        
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "main_api:app",
            "--host", "0.0.0.0",
            "--port", "3001",
            "--reload",
            "--log-level", "info"
        ])
        
    except KeyboardInterrupt:
        logger.info("🛑 服務器已停止")
    except Exception as e:
        logger.error(f"✗ 啟動服務器時發生錯誤: {e}")

def main():
    """主函數"""
    logger.info("=== WebVoyager API 啟動檢查 ===")
    
    if not check_dependencies():
        sys.exit(1)
    
    if not check_environment():
        sys.exit(1)
    
    check_chrome_driver()
    
    create_directories()
    
    start_server()

if __name__ == "__main__":
    main() 