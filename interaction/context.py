import logging
import time
from asr.common import setup_logger

# 配置日志
logger = setup_logger(__name__)

# 全局系统实例持有者，用于解决循环引用
_system_instance = None

def set_system(system):
    global _system_instance
    _system_instance = system

def get_system():
    return _system_instance