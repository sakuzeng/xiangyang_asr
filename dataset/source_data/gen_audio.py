import asyncio
import edge_tts
import os
import random
import json
from pydub import AudioSegment

# ================= 配置区域 =================

INPUT_FILE = "station_queries.txt"      # 你的文本文件
OUTPUT_DIR = "./data/audio_files"       # 音频保存目录
JSONL_FILE = "./data/train.jsonl"       # 训练用的索引文件

# 微软 Edge-TTS 中文音色列表
# 混合使用男女声，增加模型鲁棒性
VOICES = [
    "zh-CN-XiaoxiaoNeural", # 女声，温暖
    "zh-CN-YunxiNeural",    # 男声，沉稳
    "zh-CN-YunjianNeural",  # 男声，体育/即兴
    "zh-CN-XiaoyiNeural",   # 女声，自然
    "zh-CN-YunyangNeural",  # 男声，新闻
    "zh-CN-LiaoningNeural"  # 东北话口音 (可选，增加方言适应性)
]

# ================= 核心逻辑 =================

async def generate_tts():
    # 1. 创建输出目录
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    # 确保父目录存在用于存放 jsonl
    os.makedirs(os.path.dirname(JSONL_FILE), exist_ok=True)

    # 2. 读取文本
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    print(f"🎤 开始处理 {len(lines)} 条数据...")
    print(f"📂 音频将保存到: {OUTPUT_DIR}")
    print(f"📝 索引将保存到: {JSONL_FILE}")

    # 用于存储 jsonl 数据
    jsonl_data = []
    
    # 限制并发数，防止被微软 API 封禁
    semaphore = asyncio.Semaphore(5)

    async def process_line(index, text):
        async with semaphore:
            # B. 文件名定义 (提前定义以便检查)
            # audio_0001.mp3 (临时) -> audio_0001.wav (最终)
            file_id = f"audio_{index:05d}"
            temp_mp3 = os.path.join(OUTPUT_DIR, f"{file_id}.mp3")
            final_wav = os.path.join(OUTPUT_DIR, f"{file_id}.wav")
            abs_wav_path = os.path.abspath(final_wav)

            # 检查文件是否已存在且有效 (大于 1KB)
            if os.path.exists(final_wav) and os.path.getsize(final_wav) > 1024:
                print(f"⏩ [{index}/{len(lines)}] 跳过已存在: {file_id}")
                return {
                    "key": file_id,
                    "wav": abs_wav_path,
                    "txt": text
                }

            # 重试机制
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # A. 随机参数选择
                    voice = random.choice(VOICES)
                    # 随机语速 (-10% 到 +10%)
                    rate_adjust = random.randint(-10, 10)
                    rate_str = f"{'+' if rate_adjust >= 0 else ''}{rate_adjust}%"
                    
                    # C. 调用 Edge-TTS 生成
                    communicate = edge_tts.Communicate(text, voice, rate=rate_str)
                    await communicate.save(temp_mp3)
                    
                    # D. 转换为 16000Hz 单声道 WAV (ASR 标准格式)
                    # 使用 pydub 进行转换
                    sound = AudioSegment.from_mp3(temp_mp3)
                    sound = sound.set_frame_rate(16000).set_channels(1)
                    sound.export(final_wav, format="wav")
                    
                    # E. 删除临时 mp3
                    if os.path.exists(temp_mp3):
                        os.remove(temp_mp3)

                    # F. 记录到 JSONL 列表 (使用绝对路径)
                    # 格式: {"key": "id", "wav": "/abs/path/to/wav", "txt": "文本"}
                    entry = {
                        "key": file_id,
                        "wav": abs_wav_path,
                        "txt": text
                    }
                    
                    print(f"✅ [{index}/{len(lines)}] {file_id} | {voice} | {rate_str}")
                    return entry

                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"⚠️ [{index}] 生成失败 (第 {attempt + 1} 次重试): {text} | 原因: {e}")
                        await asyncio.sleep(2) # 等待 2 秒后重试
                    else:
                        print(f"❌ [{index}] 最终失败: {text} | 原因: {e}")
                        # 清理可能残留的临时文件
                        if os.path.exists(temp_mp3):
                            os.remove(temp_mp3)
                        return None

    # 3. 创建任务列表
    tasks = []
    for i, line in enumerate(lines):
        task = process_line(i, line)
        tasks.append(task)
    
    # 4. 执行并等待结果
    results = await asyncio.gather(*tasks)
    
    # 5. 写入 JSONL 文件
    valid_count = 0
    with open(JSONL_FILE, "w", encoding="utf-8") as f:
        for res in results:
            if res:
                # json.dumps 会自动处理引号转义，确保格式标准
                f.write(json.dumps(res, ensure_ascii=False) + "\n")
                valid_count += 1

    print("\n" + "="*30)
    print(f"🎉 全部完成！")
    print(f"📊 成功生成: {valid_count} 条")
    print(f"🚀 下一步: 请运行加噪脚本，或直接使用 {JSONL_FILE} 开始微调")

if __name__ == "__main__":
    asyncio.run(generate_tts())