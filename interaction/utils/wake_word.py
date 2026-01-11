import logging
import time
from asr.common import setup_logger

# 配置日志
logger = setup_logger(__name__)

try:
    from pypinyin import lazy_pinyin
except ImportError:
    lazy_pinyin = None

def check_wake_word(text, wake_word, wake_word_pinyin=None):
    """检查文本中是否包含唤醒词，支持文本直接匹配和拼音匹配"""
    if wake_word in text:
        return True
    
    if lazy_pinyin and wake_word_pinyin:
        try:
            text_pinyin = lazy_pinyin(text)
            n = len(wake_word_pinyin)
            if len(text_pinyin) >= n:
                for i in range(len(text_pinyin) - n + 1):
                    if text_pinyin[i:i+n] == wake_word_pinyin:
                        return True
        except Exception:
            pass
    return False