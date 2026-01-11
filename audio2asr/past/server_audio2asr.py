#!/usr/bin/env python3
"""
ASR 语音识别服务 (仅 API 模式)
完全依赖 interaction.py 提供的识别接口,避免设备冲突
"""

import os
import sys
import time
import uvicorn
import requests
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

# ================= 日志配置 =================
class LocalFormatter(logging.Formatter):
    """强制使用 UTC+8 时间的日志格式化器"""
    def formatTime(self, record, datefmt=None):
        # 获取 UTC 时间戳
        ct = record.created
        # 强制加上 8 小时 (8 * 3600 秒)
        t = time.gmtime(ct + 28800)
        
        if datefmt:
            s = time.strftime(datefmt, t)
        else:
            s = time.strftime("%Y-%m-%d %H:%M:%S", t)
        return s

formatter = LocalFormatter(
    fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
handler = logging.StreamHandler()
handler.setFormatter(formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[handler]
)

logger = logging.getLogger("ASR")

# 屏蔽 httpx 和 urllib3 的详细日志
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# ================= 配置 =================
INTERACTION_API_URL = "http://localhost:8004"  # interaction.py 的 API 地址

# ================= 接口调用方法 =================
def recognize_via_interaction(duration: float = 5.0, wait_time: float = 5.0) -> tuple:
    """
    通过 interaction.py 的接口获取识别结果
    """
    try:
        # duration 设置为 wait_time + 1 秒缓冲,确保覆盖整个录音期间
        effective_duration = wait_time + 1.0
        
        logger.info(f"📡 调用 interaction.py 接口 (等待 {wait_time}秒, 提取 {effective_duration}秒内文本)...")
        response = requests.post(
            f"{INTERACTION_API_URL}/get_recognition",
            json={
                "duration": effective_duration,
                "wait_time": wait_time
            },
            timeout=wait_time + 5.0
        )
        
        if response.status_code == 200:
            data = response.json()
            text = data.get("text", "")
            success = data.get("success", False)
            error = data.get("error")
            
            if success:
                # 清理识别结果 (移除重复空格、特殊字符)
                text = " ".join(text.split())
                logger.info(f"✅ 接口返回成功: [{text}]")
            else:
                logger.warning(f"⚠️ 接口返回失败: {error}")
            
            return text, success, error
        else:
            error_msg = f"HTTP {response.status_code}"
            logger.error(f"❌ 接口请求失败: {error_msg}")
            return "", False, error_msg
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ 接口调用异常: {error_msg}")
        return "", False, error_msg

# ================= FastAPI 应用 =================
app = FastAPI(title="ASR Service (API Only)", description="语音识别服务 (依赖 interaction.py)")

class RecognizeLiveRequest(BaseModel):
    """实时录音请求"""
    duration: Optional[float] = 5.0
    wait_time: Optional[float] = None

class RecognizeResponse(BaseModel):
    """识别结果"""
    text: str
    success: bool
    duration_actual: Optional[float] = None
    error: Optional[str] = None
    method: Optional[str] = "interaction_api"

@app.on_event("startup")
async def startup_event():
    """服务启动时检查依赖"""
    logger.info("🔧 正在检查 interaction.py 服务...")
    
    max_retry = 5
    for i in range(max_retry):
        try:
            response = requests.get(f"{INTERACTION_API_URL}/status", timeout=2.0)
            if response.status_code == 200:
                logger.info("✅ interaction.py 服务连接成功")
                logger.info("✅ ASR 服务初始化完成 (API Only 模式)")
                return
        except Exception as e:
            logger.warning(f"⚠️ 第 {i+1}/{max_retry} 次尝试失败: {e}")
            time.sleep(2)
    
    # 🆕 如果 interaction.py 不可用,则启动失败
    logger.error("❌ 错误: 无法连接到 interaction.py 服务")
    logger.error(f"   请确保 interaction.py 已在 {INTERACTION_API_URL} 运行")
    import os
    os._exit(1)

@app.post("/recognize_live", response_model=RecognizeResponse)
async def recognize_live(request: RecognizeLiveRequest):
    """
    实时录音识别 (通过 interaction.py API)
    """
    # 参数优先级处理
    target_duration = request.duration
    target_wait_time = request.wait_time if request.wait_time is not None else target_duration
    
    try:
        text, success, error = recognize_via_interaction(
            duration=target_duration,
            wait_time=target_wait_time
        )
        
        if success:
            return RecognizeResponse(
                text=text,
                success=True,
                duration_actual=target_wait_time,
                method="interaction_api"
            )
        else:
            return RecognizeResponse(
                text="",
                success=False,
                error=error or "识别失败",
                method="interaction_api"
            )
    
    except Exception as e:
        logger.error(f"❌ 识别失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        return RecognizeResponse(
            text="",
            success=False,
            error=str(e),
            method="failed"
        )

@app.get("/health")
def health_check():
    """健康检查"""
    interaction_available = False
    try:
        response = requests.get(f"{INTERACTION_API_URL}/status", timeout=1.0)
        interaction_available = response.status_code == 200
    except:
        pass
    
    return {
        "status": "ok" if interaction_available else "degraded",
        "service": "ASR Service (API Only)",
        "interaction_api_available": interaction_available,
        "mode": "api_only",
        "message": "依赖 interaction.py 提供音频识别" if interaction_available else "interaction.py 不可用"
    }

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 启动 ASR 服务 (API Only 模式, Port: 8003)")
    logger.info("   依赖: interaction.py @ http://localhost:8004")
    logger.info("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8003)