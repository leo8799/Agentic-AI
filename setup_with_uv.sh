#!/bin/bash

set -e 

echo "🚀 開始建構 WebVoyager API 專案..."

if ! command -v uv &> /dev/null; then
    echo "❌ 未找到 uv，正在安裝..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source ~/.local/bin/env
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "✓ uv 已安裝: $(uv --version)"

echo "📁 創建目錄結構..."
mkdir -p api_results downloads chroma_db data logs

echo "📦 安裝專案依賴..."
if [ -f "requirements.txt" ]; then
    echo "✓ 找到 requirements.txt，使用 uv 安裝完整依賴..."
    if [ ! -d ".venv" ]; then
        echo "🔧 創建 Python 虛擬環境..."
        uv venv --python 3.11
    fi
    
    echo "📥 安裝依賴套件..."
    uv pip install -r requirements.txt
    
    echo "✅ 依賴安裝完成！"
else
    echo "❌ 未找到 requirements.txt 檔案"
    echo "請確保 requirements.txt 存在於專案根目錄"
    exit 1
fi

echo "🌐 檢查瀏覽器環境..."
if command -v google-chrome &> /dev/null; then
    CHROME_VERSION=$(google-chrome --version)
    echo "✓ Google Chrome 已安裝: $CHROME_VERSION"
elif command -v chromium-browser &> /dev/null; then
    CHROMIUM_VERSION=$(chromium-browser --version)
    echo "✓ Chromium 已安裝: $CHROMIUM_VERSION"
else
    echo "   Ubuntu/Debian: sudo apt install google-chrome-stable"
    echo "   或下載: https://www.google.com/chrome/"
fi

if [ ! -f ".env" ]; then
    echo "📝 創建基本 .env 檔案..."
    cat > .env << 'EOF'
    # 請在此設定您的 Google API Key
    GOOGLE_API_KEY=your_google_api_key_here
EOF
    echo "✓ 已創建 .env 檔案，請編輯設定您的 GOOGLE_API_KEY"
else
    echo "✓ .env 檔案已存在"
fi

echo ""
echo "✅ WebVoyager API 專案建構完成！"
echo ""
echo "📋 接下來的步驟："
echo "1. 編輯 .env 檔案，填入您的 Google API 金鑰："
echo "   nano .env"
echo ""
echo "2. 啟動 API 服務器："
echo "   uv run python start_api.py"
echo ""
echo "🔗 API 將在 http://localhost:3001 啟動"
echo "📚 API 文檔: http://localhost:3001/docs" 