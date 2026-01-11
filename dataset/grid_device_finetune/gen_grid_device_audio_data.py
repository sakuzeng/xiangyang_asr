import asyncio
import edge_tts
import json
import os
from pathlib import Path
import wave
import contextlib
import random
import time
from pydub import AudioSegment
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# 配置路径
TEXT_FILE = "grid_device_query_2.jsonl"  # 输入的JSONL文件
AUDIO_DIR = "audio_data_2/grid_device_audio_data"  # 音频保存目录
JSONL_FILE = "audio_data_2/grid_device_audio_data.jsonl"  # JSONL 输出文件

# 创建音频保存目录
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs("audio_data", exist_ok=True)

# Edge-TTS 中文语音列表（随机选择）
CHINESE_VOICES = [
    "zh-CN-XiaoxiaoNeural",  # 女声 - 温暖
    "zh-CN-XiaoyiNeural",    # 女声 - 自然
    "zh-CN-YunjianNeural",   # 男声 - 体育/即兴
    "zh-CN-YunxiNeural",     # 男声 - 沉稳
    "zh-CN-YunyangNeural",   # 男声 - 新闻
    "zh-CN-XiaochenNeural",  # 女声 - 儿童
    "zh-CN-XiaohanNeural",   # 女声 - 温和
    "zh-CN-XiaomoNeural",    # 女声 - 亲切
]

# 速率限制配置
MAX_CONCURRENT = 5  # 最大并发数（避免被封禁）
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 2  # 重试延迟（秒）
MIN_FILE_SIZE = 1024  # 最小文件大小（字节），用于验证文件有效性


def get_audio_duration_frames(wav_file, frame_size_ms=10):
    """
    获取音频时长对应的帧数（10ms为一帧）
    """
    with contextlib.closing(wave.open(wav_file, 'r')) as f:
        frames = f.getnframes()
        rate = f.getframerate()
        duration_seconds = frames / float(rate)
        # 转换为10ms帧数
        duration_frames = int(duration_seconds * 1000 / frame_size_ms)
    return duration_frames


async def generate_audio_with_retry(text, output_path, voice, rate_adjust, index, total, max_retries=MAX_RETRIES):
    """
    使用 edge-tts 生成音频（带重试机制和格式转换）
    
    Args:
        text: 要合成的文本
        output_path: 输出WAV文件路径
        voice: 使用的语音
        rate_adjust: 语速调整百分比
        index: 当前索引
        total: 总数
        max_retries: 最大重试次数
    """
    temp_mp3 = output_path.replace('.wav', '.mp3')
    rate_str = f"{'+' if rate_adjust >= 0 else ''}{rate_adjust}%"
    
    for attempt in range(max_retries):
        try:
            # 生成MP3（Edge-TTS原生格式）
            communicate = edge_tts.Communicate(text, voice, rate=rate_str)
            await communicate.save(temp_mp3)
            
            # 转换为16kHz单声道WAV（ASR标准格式）
            sound = AudioSegment.from_mp3(temp_mp3)
            sound = sound.set_frame_rate(16000).set_channels(1)
            sound.export(output_path, format="wav")
            
            # 删除临时MP3
            if os.path.exists(temp_mp3):
                os.remove(temp_mp3)
            
            return True
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"    ⚠️ [{index}/{total}] 生成失败 (第 {attempt + 1} 次重试): {e}")
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
            else:
                print(f"    ❌ [{index}/{total}] 最终失败: {e}")
                # 清理可能残留的临时文件
                if os.path.exists(temp_mp3):
                    os.remove(temp_mp3)
                if os.path.exists(output_path):
                    os.remove(output_path)
                return False
    
    return False


async def process_single_text(index, text, total, semaphore):
    """
    处理单条文本（带并发控制）
    
    Args:
        index: 索引
        text: 文本内容
        total: 总数
        semaphore: 信号量（控制并发）
    """
    async with semaphore:
        # 生成文件路径
        file_id = f"audio_{index:05d}"
        audio_filename = f"{file_id}.wav"
        audio_path = os.path.join(AUDIO_DIR, audio_filename)
        audio_abs_path = os.path.abspath(audio_path)
        
        # 检查文件是否已存在且有效（大于1KB）
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > MIN_FILE_SIZE:
            try:
                source_len = get_audio_duration_frames(audio_path)
                print(f"⏩ [{index+1}/{total}] 跳过已存在: {file_id}")
                
                return {
                    "key": file_id,
                    "source": audio_abs_path,
                    "source_len": source_len,
                    "target": text,
                    "target_len": len(text),
                    "text_language": "<|zh|>",
                    "emo_target": "<|NEUTRAL|>",
                    "event_target": "<|Speech|>",
                    "with_or_wo_itn": "<|withitn|>"
                }
            except Exception as e:
                print(f"⚠️ [{index+1}/{total}] 现有文件损坏，将重新生成: {e}")
        
        # 随机选择参数
        voice = random.choice(CHINESE_VOICES)
        rate_adjust = random.randint(-10, 10)  # 语速 -10% 到 +10%
        rate_str = f"{'+' if rate_adjust >= 0 else ''}{rate_adjust}%"
        
        print(f"🎤 [{index+1}/{total}] 处理: {text[:30]}{'...' if len(text) > 30 else ''}")
        print(f"    语音: {voice} | 语速: {rate_str}")
        
        # 生成音频
        success = await generate_audio_with_retry(
            text, audio_path, voice, rate_adjust, index+1, total
        )
        
        if not success:
            print(f"    ❌ [{index+1}/{total}] 生成失败，跳过该条")
            return None
        
        # 获取音频时长（10ms帧数）
        try:
            source_len = get_audio_duration_frames(audio_path)
            
            # 创建JSONL条目
            entry = {
                "key": file_id,
                "source": audio_abs_path,
                "source_len": source_len,
                "target": text,
                "target_len": len(text),
                "text_language": "<|zh|>",
                "emo_target": "<|NEUTRAL|>",
                "event_target": "<|Speech|>",
                "with_or_wo_itn": "<|withitn|>"
            }
            
            print(f"    ✅ [{index+1}/{total}] 成功: {audio_filename}, 帧数: {source_len}, 文本长度: {len(text)}\n")
            
            return entry
            
        except Exception as e:
            print(f"    ❌ [{index+1}/{total}] 处理音频失败: {e}\n")
            return None


async def process_jsonl_file():
    """
    处理JSONL文件，生成音频和JSONL（并发处理）
    """
    # 读取JSONL文本数据
    texts = []
    with open(TEXT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                texts.append(data.get('text', '').strip())
    
    # 过滤空文本
    texts = [t for t in texts if t]
    
    total_texts = len(texts)
    
    print(f"共需处理 {total_texts} 条文本")
    print(f"最大并发数: {MAX_CONCURRENT}")
    print(f"最大重试次数: {MAX_RETRIES}\n")
    
    # 创建信号量控制并发
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    
    # 创建任务列表
    tasks = []
    for i, text in enumerate(texts):
        task = process_single_text(i, text, total_texts, semaphore)
        tasks.append(task)
    
    # 并发执行所有任务
    print("="*60)
    print("开始并发生成音频...")
    print("="*60)
    print()
    
    results = await asyncio.gather(*tasks)
    
    # 过滤有效结果
    jsonl_data = [r for r in results if r is not None]
    failed_count = total_texts - len(jsonl_data)
    
    # 保存JSONL文件
    with open(JSONL_FILE, 'w', encoding='utf-8') as f:
        for entry in jsonl_data:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    print(f"\n{'='*60}")
    print(f"处理完成！")
    print(f"  ✅ 成功生成: {len(jsonl_data)} 条")
    print(f"  ❌ 失败: {failed_count} 条")
    print(f"  📂 音频文件保存在: {AUDIO_DIR}")
    print(f"  📝 JSONL文件保存在: {JSONL_FILE}")
    print(f"{'='*60}")
    
    # 显示使用的语音统计
    print(f"\n可用中文语音:")
    for voice in CHINESE_VOICES:
        print(f"  - {voice}")
    
    # 保存失败记录
    if failed_count > 0:
        failed_items = []
        for i, (text, result) in enumerate(zip(texts, results)):
            if result is None:
                failed_items.append({
                    'idx': i,
                    'text': text
                })
        
        failed_file = "audio_data_2/failed_items.json"
        with open(failed_file, 'w', encoding='utf-8') as f:
            json.dump(failed_items, f, ensure_ascii=False, indent=2)
        print(f"\n⚠️ 失败记录已保存到: {failed_file}")


async def main():
    """
    主函数
    """
    # 检查文本文件是否存在
    if not os.path.exists(TEXT_FILE):
        print(f"❌ 错误: 找不到文本文件 {TEXT_FILE}")
        return
    
    print("="*60)
    print("🎤 电力设备语音数据生成工具")
    print("="*60)
    print(f"📄 输入文件: {TEXT_FILE}")
    print(f"📂 输出目录: {AUDIO_DIR}")
    print(f"📝 输出JSONL: {JSONL_FILE}")
    print(f"🎵 可用中文语音数: {len(CHINESE_VOICES)}")
    print(f"\n⚙️ 配置:")
    print(f"  - 最大并发: {MAX_CONCURRENT}")
    print(f"  - 最大重试: {MAX_RETRIES}次")
    print(f"  - 音频格式: 16kHz 单声道 WAV")
    print(f"  - 语速范围: -10% ~ +10%")
    print("="*60)
    print()
    
    start_time = time.time()
    await process_jsonl_file()
    end_time = time.time()
    
    elapsed_time = end_time - start_time
    print(f"\n⏱️ 总耗时: {elapsed_time:.2f}秒 ({elapsed_time/60:.2f}分钟)")
    print(f"\n🚀 下一步: 请运行加噪脚本，或直接使用 {JSONL_FILE} 开始微调")


if __name__ == "__main__":
    asyncio.run(main())