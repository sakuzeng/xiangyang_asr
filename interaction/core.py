import sys
import os
import time
import logging
import threading
from pathlib import Path
import numpy as np
import torch
from asr.common import TTSClient, AgentClient, setup_logger
from asr.interaction.utils.buffer import recognition_buffer
from asr.interaction.utils.audio import get_audio_device, get_audio_config, create_input_stream
from asr.interaction.utils.wake_word import check_wake_word
from asr.interaction.context import set_system

# 配置日志
logger = setup_logger(__name__)

# 必须确保 sys.path 已由入口脚本设置好，才能导入以下模块
try:
    from asr.streaming_sensevoice_master.streaming_sensevoice import StreamingSenseVoice
    from pysilero import VADIterator
    from pypinyin import lazy_pinyin
except ImportError:
    pass # 由主程序处理

class InteractionSystem:
    # 状态定义
    STATE_WAIT_WAKE = "WAIT_WAKE"   # 等待唤醒
    STATE_LISTENING = "LISTENING"   # 正在倾听用户指令
    STATE_THINKING = "THINKING"     # 调用 Agent 思考中
    STATE_SPEAKING = "SPEAKING"     # TTS 播报中

    def __init__(self):
        # 注册自身到全局上下文
        set_system(self)
        
        self.wake_word = "小安"
        self.wake_word_pinyin = lazy_pinyin(self.wake_word) if lazy_pinyin else None
        
        self.state = self.STATE_WAIT_WAKE
        self.is_running = True
        
        # 唤醒控制
        self.wake_detection_paused = False
        
        # VAD & 识别状态
        self.is_speech_active = False
        self.last_speech_time = 0
        self.current_text_buffer = ""
        
        # 1. 初始化模型
        self._init_model()
        
        # 2. 初始化客户端
        self.agent = AgentClient()
        
        # 3. 初始化 VAD
        self.vad = VADIterator(min_silence_duration_ms=1000, speech_pad_ms=100)
        
        # 4. 唤醒暂停控制
        self.pause_source = None
        self.pause_lock = threading.Lock()
        
        print(f"✅ 系统初始化完成 (唤醒词: {self.wake_word})")

    def _init_model(self):
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🖥️  运行设备: {device.upper()}")
        
        # 本地微调模型路径
        local_model_dir = "/home/devuser/workspace/asr/FunASR-main/examples/industrial_data_pretraining/sense_voice/outputs/sensevoice_finetune_v3"
        model_id = local_model_dir if os.path.exists(local_model_dir) else "iic/SenseVoiceSmall"
        
        print(f"正在加载 StreamingSenseVoice 模型: {model_id}")
        contexts = [self.wake_word, "变"]
        
        self.model = StreamingSenseVoice(
            contexts=contexts,
            model=model_id,
            device=device,
        )
        print("✅ 模型加载成功")

    def set_wake_paused(self, paused: bool):
        """(已弃用) 请使用 pause_wake_detection / resume_wake_detection"""
        self.wake_detection_paused = paused
        if paused:
            self.model.reset()
            self.current_text_buffer = ""

    def pause_wake_detection(self, source: str) -> bool:
        """暂停唤醒检测 (带来源记录)"""
        with self.pause_lock:
            if self.wake_detection_paused:
                # 已经被暂停了
                if self.pause_source == source:
                    return True # 同一个源，视为成功
                else:
                    print(f"⚠️ 暂停失败: 已被 '{self.pause_source}' 暂停")
                    return False
            
            self.wake_detection_paused = True
            self.pause_source = source
            # 重置状态
            self.model.reset()
            self.current_text_buffer = ""
            return True

    def resume_wake_detection(self, source: str) -> bool:
        """恢复唤醒检测 (带来源验证)"""
        with self.pause_lock:
            if not self.wake_detection_paused:
                return True # 本来就没暂停
            
            if self.pause_source != source:
                print(f"⚠️ 恢复失败: 当前由 '{self.pause_source}' 暂停, '{source}' 无权恢复")
                return False
            
            self.wake_detection_paused = False
            self.pause_source = None
            return True

    def handle_wake_up(self):
        """处理唤醒事件"""
        print("💡 触发唤醒逻辑...")
        
        # 1. 切换状态 (先设为 SPEAKING 以忽略 "我在" 的声音)
        self.state = self.STATE_SPEAKING
        
        # 2. 启动交互线程，避免阻塞主循环音频读取
        threading.Thread(target=self._run_interaction, daemon=True).start()

    def _run_interaction(self):
        """交互流程执行线程 (支持连续对话)"""
        try:
            # 1. 唤醒后立即申请独占权，直到对话彻底结束才释放
            TTSClient.set_exclusive_mode(True, allowed_source="interaction")
            
            # 🆕 重置 Agent 会话 (Session ID)，开启新的对话上下文
            # 这样可以确保每次唤醒都是一次全新的对话，只有在本次连续交互中才保留记忆
            self.agent.reset_session()
            
            # 播放唤醒音效/语音
            TTSClient.speak("我在", wait=True, source="interaction")
            # time.sleep(0.2) # ⚡ 优化: 移除额外等待，加速进入监听状态
            
            # min_silence_duration_ms : 决定了 “等多久才算完”
            # speech_pad_ms : 决定了 “多保留多少声音”
            # 🆕 优化: 将 speech_pad_ms 从 1500ms 降低到 500ms，减少音频重叠导致的"变变"重复问题
            self.vad = VADIterator(min_silence_duration_ms=2000, speech_pad_ms=200)
            
            self.state = self.STATE_LISTENING
            
            # 进入连续对话循环
            while True:
                should_continue = self._process_one_turn()
                if not should_continue:
                    break
                # 每一轮结束后，稍微等待一下
                time.sleep(0.1)
                
        except Exception as e:
            print(f"❌ 交互循环异常: {e}")
        finally:
            # 退出交互，重置状态
            self.state = self.STATE_WAIT_WAKE
            self.is_speech_active = False
            self.model.reset()
            # 恢复默认 VAD 设置
            self.vad = VADIterator(min_silence_duration_ms=1000, speech_pad_ms=100)
            
            # 确保释放独占权
            TTSClient.set_exclusive_mode(False, allowed_source="interaction")
            print("💤 回到等待唤醒模式")

    def _process_one_turn(self) -> bool:
        """处理一轮对话，返回是否继续"""
        print("\n🎤 请说话...")
        
        # 录音参数
        listen_duration = 8.0  # 最大聆听时间
        silence_timeout = 2.0  # 沉默超时
        
        recognition_buffer.start_recording()
        
        final_query = ""
        try:
            start_time = time.time()
            last_speech_end = time.time()
            has_spoken = False
            
            while time.time() - start_time < listen_duration:
                # 检查是否超时（说完后沉默了一段时间）
                if has_spoken and (time.time() - last_speech_end > silence_timeout):
                    print("⚡ 说话结束判定")
                    break
                
                # 更新说话状态
                if self.is_speech_active:
                    has_spoken = True
                    last_speech_end = time.time()
                    # 如果正在说话，延长总聆听时间
                    if time.time() - start_time > listen_duration - 2.0:
                        listen_duration += 1.0
                
                time.sleep(0.1)
            
            # 获取识别结果
            # 注意: 在 start_recording() 状态下，get_recent 会自动获取从录音开始到现在的所有内容，duration 参数会被忽略
            final_query = recognition_buffer.get_recent()
            print(f"\n📝 识别结果: {final_query}")
            
        finally:
            recognition_buffer.stop_recording()

        # 1. 超时检测 (无语音)
        if not final_query:
            print("⌛ 交互超时 (无语音)")
            self.state = self.STATE_SPEAKING
            TTSClient.speak("再见", wait=True, source="interaction")
            return False

        # 2. 退出指令检测
        exit_keywords = ["结束对话", "退出", "停止交互", "关闭对话", "再见", "结束"]
        if any(kw in final_query for kw in exit_keywords):
            print(f"🛑 用户请求退出: {final_query}")
            self.state = self.STATE_SPEAKING # 🆕 防止听到自己的声音 (回声消除)
            TTSClient.speak("好的，再见", wait=True, source="interaction")
            return False

        # 3. Agent 交互
        self.state = self.STATE_THINKING
        try:
            response = self.agent.chat(final_query)
            print(f"🤖 Agent: {response}")
            # TODO 回答处理模块
            # 进入播报模式
            self.state = self.STATE_SPEAKING
            
            # 直接播报 (独占权已在 _run_interaction 统一管理)
            TTSClient.speak(response, wait=True, source="interaction")
            # TODO 根据识别到的语音增加 播放暂停模块
            time.sleep(0.5) # 等待尾音结束
                    
        except Exception as e:
            print(f"❌ 交互异常: {e}")
            TTSClient.speak("我出错了", wait=True, source="interaction")
        
        # 准备下一轮，切换回监听状态
        self.state = self.STATE_LISTENING
        return True

    def run(self):
        # 1. 获取音频设备
        target_device_idx = get_audio_device("Newmine Mic")

        # 2. 获取音频配置
        target_sample_rate = 16000
        chunk_duration = 0.1
        
        stream_sample_rate, samples_per_read, use_resample, resampler = get_audio_config(
            target_device_idx, 
            target_sample_rate, 
            chunk_duration
        )
        
        if use_resample and not resampler:
             from scipy import signal

        self.current_text_buffer = "" 
        self.is_speech_active = False 
        
        stream = create_input_stream(target_device_idx, stream_sample_rate)
        stream.start()
        print(f"\n🚀 系统就绪,请说 '{self.wake_word}' 唤醒")

        try:
            while True:
                # 统一读取音频
                samples, _ = stream.read(samples_per_read)
                audio_chunk = samples[:, 0]
                
                if use_resample:
                    if resampler:
                        audio_chunk = resampler.resample_chunk(audio_chunk)
                    else:
                        num_output = int(len(audio_chunk) * target_sample_rate / stream_sample_rate)
                        audio_chunk = signal.resample(audio_chunk, num_output)
                
                if self.state == self.STATE_WAIT_WAKE:
                    # ===== 等待唤醒模式 =====
                    # 即使暂停唤醒，也要继续处理音频以更新 Buffer，供旁路监听使用
                    # 但在暂停期间，不进行唤醒词匹配
                    
                    vad_outs = self.vad(audio_chunk)
                        
                    for speech_dict, speech_samples in vad_outs:
                        if "start" in speech_dict:
                            self.is_speech_active = True
                            self.model.reset()
                            self.current_text_buffer = ""
                            self.last_speech_time = time.time()
                        
                        text = ""
                        for res in self.model.streaming_inference(speech_samples * 32768, "end" in speech_dict):
                            text = res.get("text", "")
                            if text:
                                if len(text) < 2 or len(set(text)) == 1:
                                    continue
                            
                                if text != self.current_text_buffer:
                                    print(f"\r👂 识别中: {text}", end="", flush=True)
                                    self.current_text_buffer = text
                                    recognition_buffer.add(text)
                    
                        # 只有在未暂停唤醒检测时，才检查唤醒词
                        if not self.wake_detection_paused and text and check_wake_word(text, self.wake_word, self.wake_word_pinyin):
                            if not recognition_buffer.is_active:
                                print(f"\n🚀 检测到唤醒词！")
                                self.handle_wake_up()
                                self.current_text_buffer = ""
                                self.model.reset()
                                break
                            else:
                                print(f"\r👂 识别中: {text} (外部录音中,暂不响应唤醒)", end="", flush=True)
                        elif not recognition_buffer.is_active and "end" in speech_dict:
                            self.model.reset()
                            self.current_text_buffer = ""
                else:
                    # ===== 交互模式 =====
                    # 如果正在思考或播报，暂停识别以避免自回声
                    if self.state in [self.STATE_THINKING, self.STATE_SPEAKING]:
                        time.sleep(0.01)
                        continue

                    # VAD 仍然运行以检测说话结束
                    vad_outs = self.vad(audio_chunk)
                    for speech_dict, speech_samples in vad_outs:
                        if "start" in speech_dict:
                            self.is_speech_active = True
                            self.model.reset() # 🆕 修复: 新的一句开始时，必须重置模型状态
                            self.last_speech_time = time.time()
                        if "end" in speech_dict:
                            self.is_speech_active = False
                            self.last_speech_time = time.time()
                        
                        for res in self.model.streaming_inference(speech_samples * 32768, "end" in speech_dict):
                            text = res.get("text", "")
                            if text and text != self.current_text_buffer:
                                print(f"\r🎤 交互识别: {text}", end="", flush=True)
                                self.current_text_buffer = text
                                recognition_buffer.add(text)
                
                time.sleep(0.001)

        except KeyboardInterrupt:
            print("\n🛑 停止服务...")
            stream.stop()
            stream.close()
            # 🆕 仅在非等待唤醒状态下（即可能持有锁的状态）才尝试释放
            if self.state != self.STATE_WAIT_WAKE:
                TTSClient.set_exclusive_mode(False, allowed_source="interaction")
