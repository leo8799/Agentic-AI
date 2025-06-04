from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncio
import subprocess
import json
import os
import uuid
import time
import logging
from typing import Dict, Optional, List
from datetime import datetime
import threading
from pathlib import Path
import zipfile
import io
import mimetypes

from config import settings, validate_settings

validate_settings()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="WebVoyager API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    userId: str

class TaskRequest(BaseModel):
    question: str
    website: str = "https://www.arxiv.org"
    max_iter: int = 5
    headless: bool = True
    text_only: bool = False
    rag: bool = True
    trajectory: bool = True
    EGA: bool = True

# 任務狀態管理
class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, Dict] = {}
        self.websocket_connections: Dict[str, WebSocket] = {}
        self.active_tasks_count = 0
        
    def create_task(self, task_id: str, request: TaskRequest, user_id: str):
        self.tasks[task_id] = {
            "id": task_id,
            "user_id": user_id,
            "status": "pending",
            "created_at": datetime.now(),
            "request": request,
            "process": None,
            "result": None,
            "error": None,
            "progress": "任務已創建",
            "logs": [],
            "current_iteration": 0
        }
        
    def update_task_status(self, task_id: str, status: str, **kwargs):
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = status
            self.tasks[task_id].update(kwargs)
            
    def get_task(self, task_id: str) -> Optional[Dict]:
        return self.tasks.get(task_id)
        
    def add_websocket(self, task_id: str, websocket: WebSocket):
        self.websocket_connections[task_id] = websocket
        
    def remove_websocket(self, task_id: str):
        if task_id in self.websocket_connections:
            del self.websocket_connections[task_id]
            
    async def broadcast_update(self, task_id: str, data: Dict):
        if task_id in self.websocket_connections:
            try:
                await self.websocket_connections[task_id].send_text(json.dumps(data))
            except Exception as e:
                logger.error(f"Error broadcasting to {task_id}: {e}")
                self.remove_websocket(task_id)
                
    def can_start_new_task(self) -> bool:
        return self.active_tasks_count < settings.MAX_CONCURRENT_TASKS
        
    def increment_active_tasks(self):
        self.active_tasks_count += 1
        
    def decrement_active_tasks(self):
        self.active_tasks_count = max(0, self.active_tasks_count - 1)

task_manager = TaskManager()

def validate_file_access(task_id: str, filename: str) -> tuple[bool, str]:
    """
    驗證文件訪問的安全性
    返回: (is_valid, file_path)
    """
    try:
        logger.info(f"Validating file access for task_id: {task_id}, filename: {filename}")
        
        task = task_manager.get_task(task_id)
        if not task:
            logger.warning(f"Task {task_id} not found in task_manager")
            return False, ""
            
        output_dir = f"{settings.OUTPUT_DIR}/{task_id}"
        logger.info(f"Searching in output_dir: {output_dir}")
        
        if not os.path.exists(output_dir):
            logger.warning(f"Output directory does not exist: {output_dir}")
            return False, ""
            
        safe_filename = os.path.basename(filename)
        logger.info(f"Looking for safe_filename: {safe_filename}")
        
        # 確保使用絕對路徑進行比較
        abs_output_dir = os.path.abspath(output_dir)
        
        for root, dirs, files in os.walk(output_dir):
            logger.info(f"Scanning directory: {root}, files: {files}")
            if safe_filename in files:
                file_path = os.path.join(root, safe_filename)
                abs_file_path = os.path.abspath(file_path)
                logger.info(f"Found file at: {file_path} (abs: {abs_file_path})")
                
                # 使用絕對路徑進行安全檢查
                if abs_file_path.startswith(abs_output_dir):
                    logger.info(f"File access validated successfully: {abs_file_path}")
                    return True, abs_file_path
                else:
                    logger.warning(f"File path security check failed: {abs_file_path} not under {abs_output_dir}")
        
        logger.warning(f"File {safe_filename} not found in any subdirectory")
        return False, ""
        
    except Exception as e:
        logger.error(f"File validation error: {e}")
        return False, ""

def get_mime_type(filename: str) -> str:
    """根據文件擴展名返回 MIME 類型"""
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type:
        return mime_type
    
    ext = filename.lower().split('.')[-1]
    mime_map = {
        'png': 'image/png',
        'jpg': 'image/jpeg', 
        'jpeg': 'image/jpeg',
        'pdf': 'application/pdf',
        'json': 'application/json',
        'md': 'text/markdown',
        'txt': 'text/plain',
        'log': 'text/plain'
    }
    return mime_map.get(ext, 'application/octet-stream')

def create_zip_stream(task_id: str) -> io.BytesIO:
    """創建任務所有文件的 ZIP 壓縮流"""
    try:
        output_dir = f"{settings.OUTPUT_DIR}/{task_id}"
        if not os.path.exists(output_dir):
            raise FileNotFoundError("Task directory not found")
            
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    if file == 'task.json':
                        continue
                        
                    file_path = os.path.join(root, file)
                    arc_name = file
                    zip_file.write(file_path, arc_name)
        
        zip_buffer.seek(0)
        return zip_buffer
        
    except Exception as e:
        logger.error(f"Error creating zip: {e}")
        raise HTTPException(status_code=500, detail="Failed to create zip file")

# API endpoints
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """處理聊天請求，判斷是否需要啟動自動化任務"""
    try:
        message = request.message.strip()
        user_id = request.userId
        
        automation_keywords = ["搜尋", "查詢", "找", "瀏覽", "下載", "PDF", "論文", "網站", "search", "find", "browse"]
        needs_automation = any(keyword in message.lower() for keyword in automation_keywords)
        
        if needs_automation:
            if not task_manager.can_start_new_task():
                return {
                    "message": f"目前有太多任務在執行中，請稍後再試。",
                    "taskId": None,
                    "status": "rejected"
                }
            
            task_id = str(uuid.uuid4())
            
            website = "https://arxiv.org"
            
            task_request = TaskRequest(
                question=message,
                website=website,
                max_iter=5,
                headless=settings.SELENIUM_HEADLESS,
                rag=True,
                trajectory=True,
                EGA=True
            )
            
            task_manager.create_task(task_id, task_request, user_id)
            
            asyncio.create_task(execute_automation_task(task_id))
            
            return {
                "message": f"我正在為您處理：{message}",
                "taskId": task_id,
                "status": "pending"
            }
        else:
            return {
                "message": f"您說：{message}。我是您的 AI 助手，可以幫您搜尋資訊和瀏覽網頁！試試說「搜尋 AI 論文」來開始。",
                "taskId": None,
                "status": "completed"
            }
            
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket 連接以提供即時更新"""
    await websocket.accept()
    task_manager.add_websocket(task_id, websocket)
    logger.info(f"WebSocket connected for task {task_id}")
    
    try:
        # 發送初始狀態
        task = task_manager.get_task(task_id)
        if task:
            await websocket.send_text(json.dumps({
                "status": task["status"],
                "progress": task["progress"],
                "currentIteration": task["current_iteration"]
            }))
        
        # 保持連接
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # 發送心跳包
                await websocket.send_text(json.dumps({"type": "heartbeat"}))
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for task {task_id}")
        task_manager.remove_websocket(task_id)
    except Exception as e:
        logger.error(f"WebSocket error for task {task_id}: {e}")
        task_manager.remove_websocket(task_id)

@app.get("/api/task/{task_id}")
async def get_task_status(task_id: str):
    """獲取任務狀態"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "id": task["id"],
        "status": task["status"],
        "progress": task["progress"],
        "current_iteration": task["current_iteration"],
        "result": task["result"],
        "error": task["error"],
        "logs": task["logs"][-10:]  # 只返回最後 10 條日誌
    }

@app.get("/api/files/{task_id}")
async def list_task_files(task_id: str):
    """獲取任務的所有文件列表"""
    try:
        output_dir = f"{settings.OUTPUT_DIR}/{task_id}"
        if not os.path.exists(output_dir):
            raise HTTPException(status_code=404, detail="Task directory not found")
        
        files = []
        for root, dirs, filenames in os.walk(output_dir):
            for filename in filenames:
                # 跳過任務配置文件
                if filename == 'task.json':
                    continue
                    
                file_path = os.path.join(root, filename)
                relative_path = os.path.relpath(file_path, output_dir)
                
                files.append({
                    "name": filename,
                    "path": relative_path,
                    "size": os.path.getsize(file_path),
                    "mime_type": get_mime_type(filename),
                    "download_url": f"/api/files/{task_id}/{filename}",
                    "preview_url": f"/api/preview/{task_id}/{filename}"
                })
        
        return {"files": files}
        
    except Exception as e:
        logger.error(f"Error listing files for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list files")

@app.get("/api/files/{task_id}/{filename}")
async def download_file(task_id: str, filename: str):
    """下載指定文件"""
    is_valid, file_path = validate_file_access(task_id, filename)
    if not is_valid:
        raise HTTPException(status_code=404, detail="File not found or access denied")
    
    mime_type = get_mime_type(filename)
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=mime_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "no-cache",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
    )

@app.get("/api/preview/{task_id}/{filename}")
async def preview_file(task_id: str, filename: str):
    """預覽文件內容"""
    is_valid, file_path = validate_file_access(task_id, filename)
    if not is_valid:
        raise HTTPException(status_code=404, detail="File not found or access denied")
    
    mime_type = get_mime_type(filename)
    
    # 對於文本文件，可以直接返回內容
    if filename.endswith(('.md', '.txt', '.json', '.log')):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if filename.endswith('.json'):
                # 格式化 JSON
                try:
                    parsed_json = json.loads(content)
                    content = json.dumps(parsed_json, indent=2, ensure_ascii=False)
                except:
                    pass
            
            return {
                "type": "text",
                "content": content,
                "mime_type": mime_type
            }
        except Exception as e:
            logger.error(f"Error reading text file {filename}: {e}")
            raise HTTPException(status_code=500, detail="Failed to read file content")
    
    # 對於圖片和 PDF，返回文件響應供前端直接顯示
    return FileResponse(
        path=file_path,
        media_type=mime_type,
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Disposition": f"inline; filename={filename}",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
    )

@app.get("/api/download/{task_id}/all")
async def download_all_files(task_id: str):
    """下載任務的所有文件（ZIP格式）"""
    try:
        # 檢查任務是否存在
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        zip_buffer = create_zip_stream(task_id)
        
        # 創建流式響應
        def iter_zip():
            while True:
                chunk = zip_buffer.read(8192)
                if not chunk:
                    break
                yield chunk
        
        filename = f"task_{task_id[:8]}_files.zip"
        
        return StreamingResponse(
            iter_zip(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(zip_buffer.getvalue())),
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )
        
    except Exception as e:
        logger.error(f"Error creating zip for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create zip file")

# 添加 CORS 預檢請求支持
@app.options("/api/preview/{task_id}/{filename}")
@app.options("/api/files/{task_id}/{filename}")
@app.options("/api/download/{task_id}/all")
async def cors_preflight():
    """處理 CORS 預檢請求"""
    from fastapi.responses import Response
    return Response(
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization"
        }
    )

async def execute_automation_task(task_id: str):
    """執行自動化任務"""
    task = task_manager.get_task(task_id)
    if not task:
        return
        
    try:
        # 增加活躍任務計數
        task_manager.increment_active_tasks()
        
        # 更新狀態為運行中
        task_manager.update_task_status(task_id, "running", progress="正在啟動自動化任務...")
        await task_manager.broadcast_update(task_id, {
            "status": "running",
            "progress": "正在啟動自動化任務...",
            "currentIteration": 0
        })
        
        # 準備輸出目錄
        output_dir = f"{settings.OUTPUT_DIR}/{task_id}"
        os.makedirs(output_dir, exist_ok=True)
        
        # 創建臨時任務文件
        temp_task_file = f"{output_dir}/task.json"
        task_data = {
            "id": 1,
            "web": task["request"].website,
            "ques": task["request"].question
        }
        
        # 修改為 JSONL 格式 (每行一個 JSON 物件)
        with open(temp_task_file, 'w', encoding='utf-8') as f:
            f.write(json.dumps(task_data, ensure_ascii=False) + '\n')
        
        # 構建命令行參數
        cmd = [
            "python3", "run.py",
            "--test_file", temp_task_file,
            "--max_iter", str(task["request"].max_iter),
            "--output_dir", output_dir,
            "--api_key", settings.GOOGLE_API_KEY,
            "--api_model", settings.API_MODEL,
            "--window_width", str(settings.SELENIUM_WINDOW_WIDTH),
            "--window_height", str(settings.SELENIUM_WINDOW_HEIGHT),
            "--download_dir", settings.DOWNLOAD_DIR
        ]
        
        # 添加可選參數
        if task["request"].headless:
            cmd.append("--headless")
        if task["request"].text_only:
            cmd.append("--text_only")
        if task["request"].rag:
            cmd.append("--rag")
        if task["request"].trajectory:
            cmd.append("--trajectory")
        if task["request"].EGA:
            cmd.append("--EGA")
        
        # 啟動進程
        logger.info(f"Starting automation task {task_id} with command: {' '.join(cmd)}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=os.getcwd()
        )
        
        task_manager.update_task_status(task_id, "running", process=process)
        
        # 監控進程輸出
        stdout_task = asyncio.create_task(monitor_process_output(task_id, process))
        
        # 等待進程完成（有超時）
        try:
            returncode = await asyncio.wait_for(process.wait(), timeout=settings.TASK_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning(f"Task {task_id} timed out, terminating process")
            process.terminate()
            await process.wait()
            raise Exception("Task execution timed out")
        
        if returncode == 0:
            # 任務成功完成
            result = await collect_task_results(task_id, output_dir)
            task_manager.update_task_status(
                task_id, 
                "completed", 
                result=result,
                progress="任務完成"
            )
            
            await task_manager.broadcast_update(task_id, {
                "status": "completed",
                "result": result,
                "progress": "任務完成",
                "final": True
            })
        else:
            # 任務失敗
            stderr_output = await process.stderr.read()
            error_msg = stderr_output.decode() if stderr_output else "Unknown error"
            
            task_manager.update_task_status(
                task_id,
                "error",
                error=error_msg,
                progress="任務執行失敗"
            )
            
            await task_manager.broadcast_update(task_id, {
                "status": "error",
                "error": error_msg,
                "progress": "任務執行失敗",
                "final": True
            })
            
    except Exception as e:
        logger.error(f"Error executing task {task_id}: {e}")
        task_manager.update_task_status(
            task_id,
            "error", 
            error=str(e),
            progress="任務執行出錯"
        )
        
        await task_manager.broadcast_update(task_id, {
            "status": "error",
            "error": str(e),
            "progress": "任務執行出錯",
            "final": True
        })
    finally:
        # 減少活躍任務計數
        task_manager.decrement_active_tasks()

async def monitor_process_output(task_id: str, process):
    """監控進程輸出並更新進度"""
    try:
        while True:
            line = await process.stdout.readline()
            if not line:
                break
                
            line_str = line.decode().strip()
            if line_str:
                # 解析日誌並更新進度
                task = task_manager.get_task(task_id)
                if task:
                    task["logs"].append(line_str)
                    
                    # 檢測迭代進度
                    if "Iter:" in line_str:
                        try:
                            iter_num = int(line_str.split("Iter:")[1].strip())
                            task_manager.update_task_status(
                                task_id,
                                "running",
                                current_iteration=iter_num,
                                progress=f"正在執行第 {iter_num} 次迭代..."
                            )
                            
                            await task_manager.broadcast_update(task_id, {
                                "status": "running",
                                "currentIteration": iter_num,
                                "progress": f"正在執行第 {iter_num} 次迭代...",
                                "logs": task["logs"][-5:]  # 最後 5 條日誌
                            })
                        except:
                            pass
                    
                    # 檢測其他進度信息
                    elif "finish!!" in line_str:
                        task_manager.update_task_status(
                            task_id,
                            "running",
                            progress="任務即將完成..."
                        )
                        await task_manager.broadcast_update(task_id, {
                            "status": "running",
                            "progress": "任務即將完成..."
                        })
                            
    except Exception as e:
        logger.error(f"Error monitoring output for task {task_id}: {e}")

async def collect_task_results(task_id: str, output_dir: str) -> Dict:
    """收集任務結果"""
    try:
        results = {
            "task_id": task_id,
            "output_directory": output_dir,
            "files": [],
            "summary": None,
            "iterations": 0
        }
        
        # 掃描輸出目錄（遞歸搜索所有子目錄）
        if os.path.exists(output_dir):
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    # 跳過任務配置文件
                    if file == 'task.json':
                        continue
                        
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, output_dir)
                    
                    results["files"].append({
                        "name": file,
                        "path": relative_path,
                        "size": os.path.getsize(file_path),
                        "mime_type": get_mime_type(file),
                        "download_url": f"/api/files/{task_id}/{file}",
                        "preview_url": f"/api/preview/{task_id}/{file}"
                    })
                    
                    # 讀取摘要文件
                    if file.endswith('.md') and 'summary' in file:
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                results["summary"] = f.read()
                        except:
                            pass
                    
                    # 計算迭代次數
                    if 'screenshot' in file and file.endswith('.png'):
                        try:
                            iter_num = int(file.replace('screenshot', '').replace('.png', ''))
                            results["iterations"] = max(results["iterations"], iter_num)
                        except:
                            pass
        
        return results
        
    except Exception as e:
        logger.error(f"Error collecting results for task {task_id}: {e}")
        return {"error": str(e)}

@app.get("/")
async def root():
    return {
        "message": "WebVoyager API is running",
        "version": "1.0.0",
        "active_tasks": task_manager.active_tasks_count,
        "max_concurrent_tasks": settings.MAX_CONCURRENT_TASKS
    }

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_tasks": task_manager.active_tasks_count
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT) 