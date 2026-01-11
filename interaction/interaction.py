import sys
import os
import threading
import importlib.util
from pathlib import Path
import logging
import time

# 设置离线模式
os.environ['MODELSCOPE_OFFLINE'] = '1'

# ================= 路径适配 =================
project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 必须先设置路径才能导入 asr.common
from asr.common import setup_logger

# 配置日志
logger = setup_logger("Interaction")

# ================= 依赖修复 =================
# 尝试修复 pysilero 路径问题，必须在导入 core 之前执行
try:
    spec = importlib.util.find_spec("pysilero")
    if spec and spec.submodule_search_locations:
        pkg_path = spec.submodule_search_locations[0]
        if pkg_path not in sys.path:
            sys.path.insert(0, pkg_path)
except Exception:
    pass

# ================= 模块导入 =================
from asr.interaction.core import InteractionSystem
from asr.interaction.api_server import run_api_server

if __name__ == "__main__":
    # 启动 API 服务 (后台线程)
    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()
    
    # 启动交互系统 (主线程)
    system = InteractionSystem()
    system.run()