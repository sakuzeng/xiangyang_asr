import time
import logging
from collections import deque
from threading import Lock
from asr.common import setup_logger

# 配置日志
logger = setup_logger("buffer")

class RecognitionBuffer:
    """识别结果缓冲区 (线程安全)"""
    def __init__(self, max_duration=60.0):
        # 🆕 将缓冲区大小增加到 60 秒，以支持旁路监听回溯
        self.max_duration = max_duration
        self.buffer = deque()
        self.lock = Lock()
        self.is_active = False
        self.active_lock = Lock()
        self.recording_start_time = None  # 🆕 记录开始时间
    
    def add(self, text: str):
        """添加识别结果"""
        with self.lock:
            current_time = time.time()
            self.buffer.append((current_time, text))
            
            # 清理过期数据 (物理删除)
            while self.buffer and (current_time - self.buffer[0][0] > self.max_duration):
                self.buffer.popleft()
    
    def get_recent(self, duration: float = 5.0, start_time: float = None) -> str:
        """
        获取识别文本
        
        Args:
            duration: 如果 start_time 为 None，则获取最近 duration 秒的内容
            start_time: 如果指定了 start_time，则获取该时间戳之后的所有内容(忽略 duration)
        """
        with self.lock:
            # 🆕 捕获当前的 start_time 到局部变量，防止并发修改导致 NoneType 错误
            current_start_time = self.recording_start_time
            
            # 优先使用传入的 start_time，否则使用 recording_start_time，最后回退到 duration
            target_start_time = start_time if start_time is not None else current_start_time
            
            result_texts = []
            current_time = time.time()
            
            for timestamp, text in self.buffer:
                if target_start_time is not None:
                    # 使用精确时间戳过滤 (允许 0.5s 误差以防边界丢失)
                    if timestamp >= target_start_time - 0.5:
                        result_texts.append(text)
                else:
                    # 使用 duration 回溯
                    if current_time - timestamp <= duration:
                        result_texts.append(text)
            
            # 🆕 智能合并策略 (Smart Merge)
            # 1. 增量合并 (Prefix Merge) - 消除流式识别的中间结果
            # 例如: "需要" -> "需要许可" -> "需要许可..."
            merged_texts = []
            if result_texts:
                current_phrase = result_texts[0]
                
                for i in range(1, len(result_texts)):
                    next_phrase = result_texts[i]
                    
                    # 如果 next_phrase 是 current_phrase 的延续 (包含关系)
                    if len(next_phrase) >= len(current_phrase) and next_phrase.startswith(current_phrase):
                        current_phrase = next_phrase
                    # 或者 current_phrase 是 next_phrase 的一部分 (修正/包含)
                    elif current_phrase in next_phrase:
                         current_phrase = next_phrase
                    else:
                        # 这是一个新的片段(或者完全不同的修正)，先保存旧的
                        merged_texts.append(current_phrase)
                        current_phrase = next_phrase
                
                merged_texts.append(current_phrase)
            
            # 2. 重叠拼接 (Overlap Stitching) - 消除 VAD 切分导致的重复
            # 例如: "需要许可" + "许可是" -> "需要许可是"
            final_text = ""
            if merged_texts:
                final_text = merged_texts[0]
                for i in range(1, len(merged_texts)):
                    next_t = merged_texts[i]
                    
                    # 尝试找到重叠部分
                    overlap_found = False
                    max_overlap = min(len(final_text), len(next_t))
                    
                    # 从最大重叠开始匹配，最小重叠 2 个字符
                    # for k in range(max_overlap, 1, -1): 
                    # 从最大重叠开始匹配，最小重叠 1 个字符
                    for k in range(max_overlap, 0, -1): 
                        if final_text.endswith(next_t[:k]):
                            final_text += next_t[k:]
                            overlap_found = True
                            break
                    
                    if not overlap_found:
                        final_text += " " + next_t
            
            # 🆕 升级为"软清理": 不再物理删除 Buffer 中的数据，而是依赖 max_duration 自动滚动淘汰。
            # 这样做的目的是：
            # 1. 允许 server_audio2asr.py 等旁路服务在主程序交互期间也能读取到完整的历史数据。
            # 2. 主程序通过 recording_start_time 依然可以准确获取本次会话的内容，不受旧数据干扰。
            
            return final_text.strip()
    
    def start_recording(self) -> bool:
        """标记开始录音 (互斥锁)"""
        with self.active_lock:
            if self.is_active:
                return False
            self.is_active = True
            self.recording_start_time = time.time()  # 🆕 记录开始时间,不清空缓冲区
            return True
    
    def stop_recording(self):
        """结束录音"""
        with self.active_lock:
            self.is_active = False
            self.recording_start_time = None

# 🆕 全局缓冲区实例
recognition_buffer = RecognitionBuffer(max_duration=10.0)