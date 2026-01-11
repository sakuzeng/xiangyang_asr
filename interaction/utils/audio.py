import sounddevice as sd
import sys
import logging
import time
from asr.common import setup_logger

# 配置日志
logger = setup_logger(__name__)

def get_audio_device(required_device_name="Wireless microphone"):
    """
    查找指定的音频设备
    :param required_device_name: 设备名称片段
    :return: 设备索引 (int)
    :raises RuntimeError: 如果未找到设备
    """
    print("\n正在查找音频设备...")
    devices = sd.query_devices()
    target_device_idx = None
    
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            if required_device_name in device['name']:
                target_device_idx = i
                print(f"\n✅ 找到指定设备: {device['name']} (Index: {i})")
                break
    
    # 🆕 未找到则启动失败
    if target_device_idx is None:
        print(f"\n❌ 错误: 未找到音频设备 '{required_device_name}'")
        print("\n可用设备列表:")
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                print(f"  [{i}] {device['name']} (输入通道: {device['max_input_channels']})")
        print(f"\n请确保 '{required_device_name}' 已连接并被系统识别")
        raise RuntimeError(f"音频设备 '{required_device_name}' 不可用，服务启动失败")
        
    return target_device_idx

def get_audio_config(device_idx, target_sample_rate=16000, chunk_duration=0.1):
    """获取音频配置和重采样器"""
    device_info = sd.query_devices(device_idx, 'input')
    device_default_rate = int(device_info['default_samplerate'])
    
    use_resample = False
    stream_sample_rate = target_sample_rate
    
    if device_default_rate != target_sample_rate:
        print(f"\n[INFO] 设备默认采样率 ({device_default_rate}Hz) 与模型需求 ({target_sample_rate}Hz) 不一致。")
        print("尝试使用设备默认采样率进行录制并重采样...")
        stream_sample_rate = device_default_rate
        use_resample = True
    
    samples_per_read = int(chunk_duration * stream_sample_rate)
    
    resampler = None
    if use_resample:
        try:
            import soxr
            print("[INFO] 使用 soxr 进行高质量重采样")
            resampler = soxr.ResampleStream(stream_sample_rate, target_sample_rate, 1, dtype="float32")
        except ImportError:
            print("[WARN] 未找到 soxr 库，将使用 scipy.signal.resample (性能可能较低)")
            pass

    return stream_sample_rate, samples_per_read, use_resample, resampler

def create_input_stream(device_idx, sample_rate):
    """创建输入流"""
    return sd.InputStream(
        device=device_idx,
        channels=1,
        dtype="float32",
        samplerate=sample_rate
    )