import time
import logging
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from asr.common import setup_logger
from asr.interaction.utils.buffer import recognition_buffer
from asr.interaction.context import get_system

# 配置日志
logger = setup_logger("api_server")

api_app = FastAPI(title="Interaction Recognition API")

class RecognitionRequest(BaseModel):
    duration: float = 5.0
    since_time: float = None # 🆕 支持指定起始时间戳

class RecognitionResponse(BaseModel):
    text: str
    success: bool
    error: str = None

class PauseRequest(BaseModel):
    source: str = "api"

class PauseResponse(BaseModel):
    success: bool
    message: str

@api_app.post("/listen_recent", response_model=RecognitionResponse)
async def listen_recent(request: RecognitionRequest):
    """
    非侵入式监听接口:
    仅获取 Buffer 中的最近文本，不开启录音模式，不占用互斥锁，不清除 Buffer。
    适用于旁路监听或调试，不影响主交互流程。
    """
    try:
        # 强制 clear=False, 避免影响主流程
        # 如果 request.since_time 存在，则忽略 duration，返回该时间点之后的内容
        text = recognition_buffer.get_recent(
            duration=request.duration, 
            start_time=request.since_time
        )
        return RecognitionResponse(text=text, success=True)
    except Exception as e:
        return RecognitionResponse(text="", success=False, error=str(e))


@api_app.get("/status")
def get_status():
    system = get_system()
    status = {
        "buffer_active": recognition_buffer.is_active,
        "system_state": system.state if system else "unknown",
        "wake_paused": system.wake_detection_paused if system else False,
        "pause_source": system.pause_source if system else None
    }
    return status

@api_app.post("/wake/pause", response_model=PauseResponse)
async def pause_wake_detection(request: PauseRequest):
    """暂停唤醒词检测"""
    system = get_system()
    if not system:
        return PauseResponse(success=False, message="System not initialized")
    
    success = system.pause_wake_detection(request.source)
    msg = "Wake detection paused" if success else f"Failed to pause (already paused by {system.pause_source})"
    
    logger.info(f"⏸️ 唤醒暂停请求 ({request.source}): {'成功' if success else '失败'}")
    return PauseResponse(success=success, message=msg)

@api_app.post("/wake/resume", response_model=PauseResponse)
async def resume_wake_detection(request: PauseRequest):
    """恢复唤醒词检测"""
    system = get_system()
    if not system:
        return PauseResponse(success=False, message="System not initialized")
        
    success = system.resume_wake_detection(request.source)
    msg = "Wake detection resumed" if success else f"Failed to resume (locked by {system.pause_source})"
    
    logger.info(f"▶️ 唤醒恢复请求 ({request.source}): {'成功' if success else '失败'}")
    return PauseResponse(success=success, message=msg)

def run_api_server():
    logger.info("🌐 启动 API 服务 (端口 8004)...")
    uvicorn.run(api_app, host="0.0.0.0", port=8004, log_level="error")