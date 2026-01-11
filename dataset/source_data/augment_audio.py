import os
import json
import soundfile as sf
import numpy as np
from audiomentations import Compose, AddGaussianNoise, AddBackgroundNoise, PolarityInversion

# ================= 配置区域 =================

# 1. 你的输入文件 (包含电力+AIShell的混合数据)
INPUT_JSONL = "./data/train_all.jsonl"

# 2. 输出文件 (生成的加噪数据索引)
OUTPUT_JSONL = "./data/train_noisy.jsonl"

# 3. 加噪后的音频保存目录
OUTPUT_AUDIO_DIR = "./data/audio_noisy"

# 4. 噪音文件所在目录 (请务必放几个真实的 wav 噪音文件进去)
# 如果该目录不存在或为空，脚本会自动跳过背景噪，只加高斯白噪
NOISE_DIR = "./data/noises"

# Docker 路径映射配置
# Windows: ...\workspace\asr\dataset
# Docker:  /home/devuser/workspace/asr/dataset
DOCKER_PREFIX = "/home/devuser/workspace/asr/dataset"
WINDOWS_BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 

# ================= 增强管道定义 =================

# 定义增强流程
# p=0.5 表示每个文件有 50% 的概率应用该效果
transforms = []

# A. 高斯白噪 (模拟电路底噪) - 始终启用
transforms.append(
    AddGaussianNoise(min_amplitude=0.001, max_amplitude=0.015, p=0.5)
)

# B. 背景噪音 (模拟环境音) - 仅在目录存在时启用
if os.path.exists(NOISE_DIR) and len(os.listdir(NOISE_DIR)) > 0:
    print(f"✅ 检测到背景噪音目录: {NOISE_DIR}，启用环境音叠加。")
    transforms.append(
        AddBackgroundNoise(
            sounds_path=NOISE_DIR,
            min_snr_db=3.0,   # 修正参数名: min_snr_in_db -> min_snr_db
            max_snr_db=30.0,  # 修正参数名: max_snr_in_db -> max_snr_db
            p=0.7                # 70% 的概率叠加背景音
        )
    )
else:
    print(f"⚠️ 警告: 未找到背景噪音目录 {NOISE_DIR}，将仅使用高斯白噪。建议添加真实噪音文件以提升效果。")

# C. 极性反转 (增加信号多样性)
transforms.append(PolarityInversion(p=0.5))

# 初始化增强器
augmenter = Compose(transforms)

# ================= 核心逻辑 =================

def process_augmentation():
    # 确保输出目录存在
    if not os.path.exists(OUTPUT_AUDIO_DIR):
        os.makedirs(OUTPUT_AUDIO_DIR)

    # 读取输入列表
    with open(INPUT_JSONL, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    print(f"🔄 开始处理 {len(lines)} 条数据...")
    
    new_entries = []
    
    for i, line in enumerate(lines):
        try:
            item = json.loads(line)
            src_wav_path_raw = item["wav"]
            
            # 处理 Docker 路径映射回 Windows 本地路径
            # 如果路径以 /home/devuser 开头，说明是 Docker 路径，需要转换回本地 Windows 路径读取音频
            if src_wav_path_raw.startswith(DOCKER_PREFIX):
                # 去掉前缀 /home/devuser/workspace/asr/dataset
                rel_path = src_wav_path_raw[len(DOCKER_PREFIX):].lstrip("/")
                # 替换分隔符
                rel_path_win = rel_path.replace("/", os.sep)
                src_wav_path = os.path.join(WINDOWS_BASE_DIR, rel_path_win)
            else:
                # 假设是本地绝对路径或相对路径
                src_wav_path = src_wav_path_raw

            original_key = item["key"]
            text = item["txt"]

            # 1. 读取原始音频
            # soundfile 读取出来是 numpy array (float32)
            if not os.path.exists(src_wav_path):
                print(f"⚠️ 跳过找不到的文件: {src_wav_path}")
                continue
                
            audio, sample_rate = sf.read(src_wav_path)

            # 2. 应用增强
            # audiomentations 期望输入是 float32
            augmented_audio = augmenter(samples=audio, sample_rate=sample_rate)

            # 3. 保存新文件
            # 文件名加后缀 _noisy
            new_filename = f"{original_key}_noisy.wav"
            new_wav_path = os.path.join(OUTPUT_AUDIO_DIR, new_filename)
            
            # 写入 WAV
            sf.write(new_wav_path, augmented_audio, sample_rate)

            # 4. 构建新的 JSON 条目
            # 注意：key 也改名，避免和原数据冲突
            # 计算 Docker 内的绝对路径
            rel_path_noisy = os.path.relpath(new_wav_path, WINDOWS_BASE_DIR).replace(os.sep, "/")
            docker_wav_path = f"{DOCKER_PREFIX}/{rel_path_noisy}"
            
            new_entry = {
                "key": f"{original_key}_noisy",
                "wav": docker_wav_path,
                "txt": text  # 文本保持不变
            }
            new_entries.append(new_entry)

            if i % 100 == 0:
                print(f"   进度: {i}/{len(lines)}...")

        except Exception as e:
            print(f"❌ 处理失败: {line} | 原因: {e}")

    # 5. 写入输出 JSONL
    with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
        for entry in new_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print("="*30)
    print(f"🎉 加噪完成！生成了 {len(new_entries)} 条新数据。")
    print(f"📂 新索引文件: {OUTPUT_JSONL}")
    print(f"📂 新音频目录: {OUTPUT_AUDIO_DIR}")

if __name__ == "__main__":
    process_augmentation()