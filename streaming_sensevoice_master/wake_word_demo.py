import sys
import os
import importlib.util

# [路径适配] 自动查找并添加 streaming-sensevoice 依赖路径
# 使得脚本可以在 integrated 目录或原始目录下运行
current_dir = os.path.dirname(os.path.abspath(__file__))
# 定义可能的依赖包路径: 
# 1. 上级目录的 streaming-sensevoice-master (当脚本在 integrated 目录时)
# 2. 当前目录 (当脚本在 streaming-sensevoice-master 目录时)
dependency_paths = [
    os.path.join(os.path.dirname(current_dir), "streaming-sensevoice-master"),
    current_dir
]

for path in dependency_paths:
    # 检查该路径下是否存在 streaming_sensevoice 包
    if os.path.exists(os.path.join(path, "streaming_sensevoice")):
        if path not in sys.path:
            sys.path.insert(0, path)
            print(f"[INFO] 自动添加依赖路径: {path}")
        break

# [优化] 强制设置 ModelScope 为离线模式，防止每次启动都尝试联网检查更新
# 这可以解决启动卡顿和重复下载 Silero VAD 的问题
os.environ['MODELSCOPE_OFFLINE'] = '1'

import sounddevice as sd
import numpy as np
import torch

# [自动修复] 尝试修复 pysilero 库的 frame_queue 导入错误
# pysilero 0.0.x 版本存在相对导入 bug，需要将其目录加入 sys.path 才能找到 frame_queue
try:
    spec = importlib.util.find_spec("pysilero")
    if spec and spec.submodule_search_locations:
        pkg_path = spec.submodule_search_locations[0]
        if pkg_path not in sys.path:
            sys.path.insert(0, pkg_path) # 插入到最前面以确保优先搜索
except Exception as e:
    print(f"[WARN] pysilero 路径修复失败: {e}")

from pysilero import VADIterator
from streaming_sensevoice import StreamingSenseVoice

try:
    from pypinyin import lazy_pinyin
except ImportError:
    lazy_pinyin = None
    print("[WARN] 未找到 pypinyin 库，将仅使用文本匹配。建议安装: pip install pypinyin")

def check_wake_word(text, wake_word, wake_word_pinyin=None):
    """检查文本中是否包含唤醒词，支持文本直接匹配和拼音匹配"""
    # 1. 直接文本匹配
    if wake_word in text:
        return True
    
    # 2. 拼音匹配 (如果启用了 pypinyin)
    # 这可以处理同音字的情况 (例如: "消安" -> "xiao an")
    if lazy_pinyin and wake_word_pinyin:
        try:
            text_pinyin = lazy_pinyin(text)
            # 简单的子序列匹配
            n = len(wake_word_pinyin)
            if len(text_pinyin) >= n:
                for i in range(len(text_pinyin) - n + 1):
                    if text_pinyin[i:i+n] == wake_word_pinyin:
                        return True
        except Exception:
            pass # 忽略拼音转换错误
            
    return False


def main():
    # 唤醒词配置
    wake_word = "小安"
    contexts = [wake_word]
    
    # 预计算唤醒词拼音
    wake_word_pinyin = None
    if lazy_pinyin:
        wake_word_pinyin = lazy_pinyin(wake_word)
        print(f"启用拼音辅助检测: {wake_word} -> {wake_word_pinyin}")
    
    # 模型路径配置 (参考 asr.py)
    # 指定本地微调模型路径
    local_model_dir = "/home/devuser/workspace/asr/FunASR-main/examples/industrial_data_pretraining/sense_voice/outputs/sensevoice_finetune_v1"
    model_id = "iic/SenseVoiceSmall" # 默认模型
    
    # 自动检测设备 (优先使用 GPU)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🖥️  运行设备: {device.upper()}")
    
    if os.path.exists(local_model_dir):
        model_id = local_model_dir
        print(f"📂 使用本地微调模型: {model_id}")
    else:
        print(f"⚠️ 本地模型不存在: {local_model_dir}")
        print(f"🔄 使用默认模型: {model_id}")

    print("正在加载 StreamingSenseVoice 模型...")
    # 初始化模型，传入 contexts 以增强唤醒词的识别权重，并指定模型路径
    # 注意: StreamingSenseVoice 不支持 disable_update 和 local_files_only 参数
    # 我们通过设置 os.environ['MODELSCOPE_OFFLINE'] = '1' 来实现离线模式
    model = StreamingSenseVoice(
        contexts=contexts, 
        model=model_id, 
        device=device,
    )
    print("模型加载完成。")

    # 初始化 VAD (语音活动检测)
    vad_iterator = VADIterator(speech_pad_ms=300)

    # 音频设备查找逻辑
    print("\n正在查找音频设备...")
    devices = sd.query_devices()
    target_device_idx = None
    
    # 尝试自动匹配设备
    # 优先级: 用户指定(Wireless microphone) > 板载声卡 > 其他USB设备
    target_names = ["Wireless microphone", "microphone", "ALC897", "PCH", "Intel", "B600", "USB Audio", "BTD 600"]
    
    for i, device in enumerate(devices):
        # 仅检查输入设备
        if device['max_input_channels'] > 0:
            dev_name = device['name']
            print(f"  Device {i}: {dev_name}")
            for target in target_names:
                if target in dev_name:
                    # 只有当找到更高优先级的设备时才更新 (通过列表索引判断优先级)
                    current_priority = target_names.index(target)
                    # 如果还没有选中设备，或者找到了优先级更高的设备
                    # (注意: 这里逻辑简化为找到第一个匹配的就作为候选，因为 target_names 是有序的)
                    # 为了严格匹配优先级，我们应该按 target_names 的顺序去遍历 devices，或者记录 best_priority
                    
                    # 简单策略: 直接匹配到最高优先级的就停止? 
                    # 不行，devices 列表顺序不确定。
                    # 改进策略: 记录当前匹配到的最高优先级
                    
                    # 这里为了简单有效，我们用一个临时变量存储最佳匹配
                    pass

    # 重新实现查找逻辑: 按 target_names 的优先级顺序去遍历设备列表
    target_device_idx = None
    found_target = None
    
    for target in target_names:
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                if target in device['name']:
                    target_device_idx = i
                    found_target = target
                    print(f"\n[INFO] 自动选择设备: {device['name']} (Index: {i}) [匹配关键词: {target}]")
                    break
        if target_device_idx is not None:
            break
    
    # 如果没找到特定设备，回退到默认设备
    if target_device_idx is None:
        if len(devices) > 0:
            target_device_idx = sd.default.device[0]
            print(f"\n[WARN] 未找到指定设备({', '.join(target_names)})，使用默认输入设备: {devices[target_device_idx]['name']} (Index: {target_device_idx})")
        else:
            print("\n[ERROR] 未找到任何音频输入设备！")
            sys.exit(1)

    # 音频参数
    target_sample_rate = 16000 # 模型需要的采样率
    chunk_duration = 0.1 # 100ms
    
    # 获取设备支持的默认采样率
    device_info = sd.query_devices(target_device_idx, 'input')
    device_default_rate = int(device_info['default_samplerate'])
    
    # 决定使用的采样率: 如果设备支持 16k，就用 16k；否则用设备默认的，然后重采样
    # 注意: PortAudio 的 sample rate check 有时不可靠，这里我们优先尝试 16000
    # 但根据报错 PaErrorCode -9997，说明硬件不支持 16000
    
    use_resample = False
    stream_sample_rate = target_sample_rate
    
    if device_default_rate != target_sample_rate:
        print(f"\n[INFO] 设备默认采样率 ({device_default_rate}Hz) 与模型需求 ({target_sample_rate}Hz) 不一致。")
        print("尝试使用设备默认采样率进行录制并重采样...")
        stream_sample_rate = device_default_rate
        use_resample = True
    
    samples_per_read = int(chunk_duration * stream_sample_rate)

    print(f"\n开始监听... 请说出唤醒词: '{wake_word}'")
    print(f"Stream Rate: {stream_sample_rate}Hz, Model Rate: {target_sample_rate}Hz")
    print("-" * 50)
    
    # 初始化重采样器 (如果需要)
    resampler = None
    if use_resample:
        try:
            import soxr
            print("[INFO] 使用 soxr 进行高质量重采样")
            resampler = soxr.ResampleStream(stream_sample_rate, target_sample_rate, 1, dtype="float32")
        except ImportError:
            print("[WARN] 未找到 soxr 库，将使用 scipy.signal.resample (性能可能较低)")
            from scipy import signal

    try:
        # 打开音频流
        with sd.InputStream(device=target_device_idx, 
                            channels=1, 
                            dtype="float32", 
                            samplerate=stream_sample_rate) as stream:
            
            # 用于缓冲重采样后的数据
            buffer = np.array([], dtype=np.float32)
            
            while True:
                # 读取音频块
                samples, _ = stream.read(samples_per_read)
                audio_chunk = samples[:, 0]
                
                # 重采样处理
                if use_resample:
                    if resampler:
                        # 使用 soxr (API 修正)
                        # soxr.ResampleStream.resample_chunk 是正确的方法名 (或者直接 call 对象，取决于版本，但 resample_chunk 更通用)
                        # 实际上 soxr 文档指出可以直接用 resampler.resample_chunk(samples)
                        processed_chunk = resampler.resample_chunk(audio_chunk)
                    else:
                        # 使用 scipy (简单的块重采样可能会有伪影，但在流式中暂且只能这样或使用更复杂的 buffer)
                        # 为了简单演示，这里直接按比例重采样当前块 (注意：这在流式处理中不是完美的，最好用 soxr)
                        num_output = int(len(audio_chunk) * target_sample_rate / stream_sample_rate)
                        processed_chunk = signal.resample(audio_chunk, num_output)
                    
                    audio_chunk = processed_chunk

                # 确保数据长度符合模型 16k 下的 chunk 需求 (处理重采样可能带来的长度波动)
                # 这里简单地将数据喂给 VAD，VAD 内部会处理 buffer
                
                # VAD 处理
                for speech_dict, speech_samples in vad_iterator(audio_chunk):
                    if "start" in speech_dict:
                        model.reset()
                        # print("\n[检测到语音输入...]", end="", flush=True)
                    
                    is_last = "end" in speech_dict
                    
                    # 模型推理
                    # 模型需要 int16 范围的浮点数，但这里直接用 float * 32768
                    # StreamingSenseVoice.streaming_inference 接受的输入是 waveform
                    for res in model.streaming_inference(speech_samples * 32768, is_last):
                        text = res.get("text", "")
                        if text:
                            # 实时打印识别结果
                            print(f"\r当前识别: {text}", end="", flush=True)
                            
                            # 唤醒词检测逻辑 (支持文本和拼音)
                            if check_wake_word(text, wake_word, wake_word_pinyin):
                                print(f"\n\n>>> 唤醒成功! 检测到: {wake_word} <<<\n")
                                # 这里可以加入唤醒后的回调逻辑，例如播放提示音或发送指令
                                # model.reset() # 可选：唤醒后重置上下文
                    
                    if is_last:
                        # 语音段结束，换行准备下一次输出
                        print("") 

    except KeyboardInterrupt:
        print("\n\n停止监听 (KeyboardInterrupt)")
    except Exception as e:
        print(f"\n\n发生错误: {e}")

if __name__ == "__main__":
    main()