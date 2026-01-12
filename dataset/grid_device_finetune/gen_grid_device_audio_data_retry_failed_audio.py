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

# 配置路径
FAILED_FILE = "audio_data_2/failed_items.json"  # 失败记录文件
ORIGINAL_TEXT_FILE = "grid_device_query_2.jsonl"  # 原始文本文件
AUDIO_DIR = "audio_data_2/grid_device_audio_data"  # 音频保存目录
JSONL_FILE = "audio_data_2/grid_device_audio_data.jsonl"  # JSONL 输出文件
RETRY_OUTPUT = "audio_data_2/retry_results.json"  # 重试结果记录

# Edge-TTS 中文语音列表
CHINESE_VOICES = [
    "zh-CN-XiaoxiaoNeural",
    "zh-CN-XiaoyiNeural",
    "zh-CN-YunjianNeural",
    "zh-CN-YunxiNeural",
    "zh-CN-YunyangNeural",
    "zh-CN-XiaochenNeural",
    "zh-CN-XiaohanNeural",
    "zh-CN-XiaomoNeural",
]

# 重试配置（更保守的策略）
MAX_CONCURRENT = 3  # 降低并发数
MAX_RETRIES = 3  # 增加重试次数
RETRY_DELAY = 5  # 增加延迟
MIN_FILE_SIZE = 1024
REQUEST_DELAY = 2  # 每个请求之间的延迟


def get_audio_duration_frames(wav_file, frame_size_ms=10):
    """获取音频时长对应的帧数（10ms为一帧）"""
    with contextlib.closing(wave.open(wav_file, 'r')) as f:
        frames = f.getnframes()
        rate = f.getframerate()
        duration_seconds = frames / float(rate)
        duration_frames = int(duration_seconds * 1000 / frame_size_ms)
    return duration_frames


async def generate_audio_with_retry(text, output_path, voice, rate_adjust, index, total, max_retries=MAX_RETRIES):
    """使用 edge-tts 生成音频（带重试机制）"""
    temp_mp3 = output_path.replace('.wav', '.mp3')
    rate_str = f"{'+' if rate_adjust >= 0 else ''}{rate_adjust}%"
    
    for attempt in range(max_retries):
        try:
            # 生成MP3
            communicate = edge_tts.Communicate(text, voice, rate=rate_str)
            await communicate.save(temp_mp3)
            
            # 检查文件是否生成成功
            if not os.path.exists(temp_mp3) or os.path.getsize(temp_mp3) < 100:
                raise Exception("生成的MP3文件无效或过小")
            
            # 转换为16kHz单声道WAV
            sound = AudioSegment.from_mp3(temp_mp3)
            sound = sound.set_frame_rate(16000).set_channels(1)
            sound.export(output_path, format="wav")
            
            # 删除临时MP3
            if os.path.exists(temp_mp3):
                os.remove(temp_mp3)
            
            # 验证WAV文件
            if not os.path.exists(output_path) or os.path.getsize(output_path) < MIN_FILE_SIZE:
                raise Exception("生成的WAV文件无效或过小")
            
            return True
            
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = RETRY_DELAY * (attempt + 1)
                print(f"    ⚠️ [{index}/{total}] 第 {attempt + 1} 次重试失败: {e}")
                print(f"    等待 {wait_time} 秒后重试...")
                await asyncio.sleep(wait_time)
            else:
                print(f"    ❌ [{index}/{total}] 最终失败: {e}")
                # 清理临时文件
                for f in [temp_mp3, output_path]:
                    if os.path.exists(f):
                        try:
                            os.remove(f)
                        except:
                            pass
                return False
    
    return False


async def process_single_failed_item(idx, text, total, semaphore, texts_data):
    """处理单个失败项"""
    async with semaphore:
        # 生成文件路径
        file_id = f"audio_{idx:05d}"
        audio_filename = f"{file_id}.wav"
        audio_path = os.path.join(AUDIO_DIR, audio_filename)
        audio_abs_path = os.path.abspath(audio_path)
        
        # 检查是否已存在有效文件
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > MIN_FILE_SIZE:
            try:
                source_len = get_audio_duration_frames(audio_path)
                print(f"✅ [{idx+1}/{len(texts_data)}] 已存在有效文件: {file_id}")
                
                return {
                    "success": True,
                    "entry": {
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
                }
            except Exception as e:
                print(f"⚠️ 现有文件损坏: {e}")
        
        # 随机选择语音和语速
        voice = random.choice(CHINESE_VOICES)
        rate_adjust = random.randint(-10, 10)
        rate_str = f"{'+' if rate_adjust >= 0 else ''}{rate_adjust}%"
        
        print(f"\n🔄 [{idx+1}/{len(texts_data)}] 重试: {text[:40]}{'...' if len(text) > 40 else ''}")
        print(f"   语音: {voice} | 语速: {rate_str}")
        
        # 请求前延迟
        await asyncio.sleep(REQUEST_DELAY)
        
        # 生成音频
        success = await generate_audio_with_retry(
            text, audio_path, voice, rate_adjust, idx+1, len(texts_data)
        )
        
        if not success:
            return {"success": False, "idx": idx, "text": text}
        
        # 获取音频信息
        try:
            source_len = get_audio_duration_frames(audio_path)
            
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
            
            print(f"   ✅ 成功生成: {audio_filename}, 帧数: {source_len}")
            
            return {"success": True, "entry": entry}
            
        except Exception as e:
            print(f"   ❌ 处理失败: {e}")
            return {"success": False, "idx": idx, "text": text}


async def retry_failed_items():
    """重试所有失败的项目"""
    # 检查失败记录文件
    if not os.path.exists(FAILED_FILE):
        print(f"❌ 找不到失败记录文件: {FAILED_FILE}")
        return
    
    # 读取失败记录
    with open(FAILED_FILE, 'r', encoding='utf-8') as f:
        failed_items = json.load(f)
    
    if not failed_items:
        print("✅ 没有需要重试的项目")
        return
    
    print("="*60)
    print("🔄 失败项目重试工具")
    print("="*60)
    print(f"📋 需要重试的项目数: {len(failed_items)}")
    print(f"⚙️ 配置:")
    print(f"  - 最大并发: {MAX_CONCURRENT}")
    print(f"  - 最大重试: {MAX_RETRIES}次")
    print(f"  - 请求延迟: {REQUEST_DELAY}秒")
    print("="*60)
    print()
    
    # 创建信号量
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    
    # 读取原始文本数据（用于获取完整的文本列表）
    texts = []
    with open(ORIGINAL_TEXT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                texts.append(data.get('text', '').strip())
    
    # 创建重试任务
    tasks = []
    for item in failed_items:
        idx = item['idx']
        text = item['text']
        task = process_single_failed_item(idx, text, len(failed_items), semaphore, texts)
        tasks.append(task)
    
    # 执行重试
    print("开始重试...\n")
    start_time = time.time()
    results = await asyncio.gather(*tasks)
    end_time = time.time()
    
    # 统计结果
    success_results = [r for r in results if r.get("success")]
    failed_results = [r for r in results if not r.get("success")]
    
    # 更新JSONL文件
    if success_results:
        # 读取现有的JSONL
        existing_entries = []
        if os.path.exists(JSONL_FILE):
            with open(JSONL_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        existing_entries.append(json.loads(line))
        
        # 添加新成功的条目
        for result in success_results:
            existing_entries.append(result["entry"])
        
        # 按key排序
        existing_entries.sort(key=lambda x: x["key"])
        
        # 重新写入JSONL
        with open(JSONL_FILE, 'w', encoding='utf-8') as f:
            for entry in existing_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    # 更新失败记录
    if failed_results:
        new_failed_items = [
            {"idx": r["idx"], "text": r["text"]} 
            for r in failed_results
        ]
        with open(FAILED_FILE, 'w', encoding='utf-8') as f:
            json.dump(new_failed_items, f, ensure_ascii=False, indent=2)
    else:
        # 删除失败记录文件
        if os.path.exists(FAILED_FILE):
            os.remove(FAILED_FILE)
    
    # 保存重试结果
    retry_summary = {
        "total_retry": len(failed_items),
        "success": len(success_results),
        "failed": len(failed_results),
        "time_elapsed": end_time - start_time,
        "failed_items": [{"idx": r["idx"], "text": r["text"]} for r in failed_results] if failed_results else []
    }
    
    with open(RETRY_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(retry_summary, f, ensure_ascii=False, indent=2)
    
    # 打印结果
    print(f"\n{'='*60}")
    print(f"重试完成！")
    print(f"  ✅ 成功: {len(success_results)} 条")
    print(f"  ❌ 仍然失败: {len(failed_results)} 条")
    print(f"  ⏱️ 耗时: {end_time - start_time:.2f}秒")
    print(f"  📝 JSONL已更新: {JSONL_FILE}")
    print(f"  📊 重试结果: {RETRY_OUTPUT}")
    print(f"{'='*60}")
    
    if failed_results:
        print(f"\n⚠️ 仍有 {len(failed_results)} 条失败")
        print(f"   可以再次运行此脚本继续重试")
        print(f"   失败记录已更新: {FAILED_FILE}")
    else:
        print(f"\n🎉 所有项目已成功生成！")


async def main():
    await retry_failed_items()


if __name__ == "__main__":
    asyncio.run(main())