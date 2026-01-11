import os
import json
import soundfile as sf
import numpy as np
import random
from audiomentations import Compose, AddGaussianNoise, AddBackgroundNoise, PolarityInversion
from pathlib import Path

# ================= 配置区域 =================

# 1. 输入文件
AISHELL_JSONL = "audio_data_2/aishell_grid_device_audio_data.jsonl"
GRID_DEVICE_JSONL = "audio_data_2/grid_device_audio_data.jsonl"

# 2. 输出文件
AISHELL_OUTPUT = "audio_data_2/aishell_grid_device_audio_data_with_noise.jsonl"
GRID_DEVICE_OUTPUT = "audio_data_2/grid_device_audio_data_with_noise.jsonl"

# 3. 加噪后的音频保存目录
OUTPUT_AUDIO_DIR = "audio_data_2/grid_device2aishell_audio_data_withnoise"

# 4. 噪音文件所在目录
NOISE_DIR = "./noises"

# 5. 噪声数据生成比例
NOISE_RATIO = 0.5  # 生成一半的噪声数据

# ================= 增强管道定义 =================

def create_augmenter():
    """创建音频增强器"""
    transforms = []
    
    # A. 高斯白噪 (模拟电路底噪)
    transforms.append(
        AddGaussianNoise(min_amplitude=0.001, max_amplitude=0.015, p=0.5)
    )
    
    # B. 背景噪音 (模拟环境音) - 仅在目录存在时启用
    if os.path.exists(NOISE_DIR) and os.listdir(NOISE_DIR):
        noise_files = [f for f in os.listdir(NOISE_DIR) if f.endswith(('.wav', '.mp3', '.flac'))]
        if noise_files:
            print(f"✅ 检测到背景噪音目录: {NOISE_DIR}，找到 {len(noise_files)} 个噪音文件，启用环境音叠加。")
            transforms.append(
                AddBackgroundNoise(
                    sounds_path=NOISE_DIR,
                    min_snr_db=3.0,
                    max_snr_db=30.0,
                    p=0.7
                )
            )
        else:
            print(f"⚠️ 警告: {NOISE_DIR} 目录为空，将仅使用高斯白噪。")
    else:
        print(f"⚠️ 警告: 未找到背景噪音目录 {NOISE_DIR}，将仅使用高斯白噪。")
    
    # C. 极性反转
    transforms.append(PolarityInversion(p=0.5))
    
    return Compose(transforms)


def process_jsonl_file(input_jsonl, output_jsonl, augmenter, source_type="grid"):
    """
    处理单个JSONL文件，随机选择一半数据生成噪声
    
    Args:
        input_jsonl: 输入的JSONL文件路径
        output_jsonl: 输出的JSONL文件路径
        augmenter: 音频增强器
        source_type: 数据来源类型 ('grid' 或 'aishell')
    
    Returns:
        success_count: 成功处理的数量
        fail_count: 失败的数量
    """
    print(f"\n{'='*60}")
    print(f"🔄 开始处理: {input_jsonl}")
    print(f"{'='*60}")
    
    # 确保输出目录存在
    os.makedirs(OUTPUT_AUDIO_DIR, exist_ok=True)
    
    # 读取输入文件
    with open(input_jsonl, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    
    total_lines = len(lines)
    print(f"📋 共读取 {total_lines} 条数据")
    
    # 随机选择一半的数据
    sample_size = int(total_lines * NOISE_RATIO)
    selected_indices = set(random.sample(range(total_lines), sample_size))
    
    print(f"🎲 随机选择 {sample_size} 条数据进行加噪 ({NOISE_RATIO*100:.0f}%)")
    
    new_entries = []
    success_count = 0
    fail_count = 0
    skip_count = 0
    
    for i, line in enumerate(lines):
        # 检查是否被选中
        if i not in selected_indices:
            skip_count += 1
            continue
        
        try:
            item = json.loads(line)
            
            # 获取字段
            src_wav_path = item["source"]
            original_key = item["key"]
            text = item["target"]
            
            # 检查文件是否存在
            if not os.path.exists(src_wav_path):
                print(f"⚠️ [{success_count+1}/{sample_size}] 跳过找不到的文件: {src_wav_path}")
                fail_count += 1
                continue
            
            # 1. 读取原始音频
            audio, sample_rate = sf.read(src_wav_path)
            
            # 2. 应用增强
            augmented_audio = augmenter(samples=audio, sample_rate=sample_rate)
            
            # 3. 保存新文件
            new_filename = f"{original_key}_with_noise.wav"
            new_wav_path = os.path.join(OUTPUT_AUDIO_DIR, new_filename)
            
            # 写入WAV
            sf.write(new_wav_path, augmented_audio, sample_rate)
            
            # 4. 计算新的source_len (10ms为一帧)
            duration_seconds = len(augmented_audio) / sample_rate
            source_len = int(duration_seconds * 1000 / 10)
            
            # 5. 构建新的JSON条目（使用绝对路径）
            abs_wav_path = os.path.abspath(new_wav_path)
            
            new_entry = {
                "key": f"{original_key}_with_noise",
                "source": abs_wav_path,
                "source_len": source_len,
                "target": text,
                "target_len": item.get("target_len", len(text)),
                "text_language": item.get("text_language", "<|zh|>"),
                "emo_target": item.get("emo_target", "<|NEUTRAL|>"),
                "event_target": item.get("event_target", "<|Speech|>"),
                "with_or_wo_itn": item.get("with_or_wo_itn", "<|withitn|>")
            }
            
            new_entries.append(new_entry)
            success_count += 1
            
            # 每处理50条打印一次进度
            if success_count % 50 == 0:
                print(f"  进度: {success_count}/{sample_size} (失败: {fail_count})")
        
        except Exception as e:
            print(f"❌ [{success_count+1}/{sample_size}] 处理失败: {e}")
            fail_count += 1
    
    # 6. 写入输出JSONL
    with open(output_jsonl, "w", encoding="utf-8") as f:
        for entry in new_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    print(f"\n{'='*60}")
    print(f"✅ 处理完成！")
    print(f"  📊 成功: {success_count} 条")
    print(f"  ❌ 失败: {fail_count} 条")
    print(f"  ⏭️ 跳过: {skip_count} 条")
    print(f"  📝 输出文件: {output_jsonl}")
    print(f"{'='*60}")
    
    return success_count, fail_count


def main():
    """主函数"""
    print("="*60)
    print("🎵 电力设备+AIShell 音频加噪工具")
    print("="*60)
    print(f"📍 工作目录: {os.getcwd()}")
    print(f"📄 输入文件1: {AISHELL_JSONL}")
    print(f"📄 输入文件2: {GRID_DEVICE_JSONL}")
    print(f"📂 输出音频目录: {OUTPUT_AUDIO_DIR}")
    print(f"📝 输出文件1: {AISHELL_OUTPUT}")
    print(f"📝 输出文件2: {GRID_DEVICE_OUTPUT}")
    print(f"🎯 噪声生成比例: {NOISE_RATIO*100:.0f}%")
    print("="*60)
    
    # 设置随机种子以便复现
    random.seed(42)
    print(f"🌱 随机种子: 42 (可复现)")
    
    # 统计输入数据量
    total_input_count = 0
    aishell_count = 0
    grid_count = 0
    
    if os.path.exists(AISHELL_JSONL):
        with open(AISHELL_JSONL, 'r') as f:
            aishell_count = sum(1 for line in f if line.strip())
        total_input_count += aishell_count
        print(f"📊 AIShell数据: {aishell_count} 条")
    
    if os.path.exists(GRID_DEVICE_JSONL):
        with open(GRID_DEVICE_JSONL, 'r') as f:
            grid_count = sum(1 for line in f if line.strip())
        total_input_count += grid_count
        print(f"📊 Grid Device数据: {grid_count} 条")
    
    expected_noise_count = int(total_input_count * NOISE_RATIO)
    print(f"📊 总输入数据: {total_input_count} 条")
    print(f"🎯 预计生成: {expected_noise_count} 条加噪数据 ({NOISE_RATIO*100:.0f}%)")
    print("="*60)
    
    # 创建增强器
    augmenter = create_augmenter()
    
    total_success = 0
    total_fail = 0
    
    # 处理AIShell数据
    if os.path.exists(AISHELL_JSONL):
        success, fail = process_jsonl_file(
            AISHELL_JSONL,
            AISHELL_OUTPUT,
            augmenter,
            source_type="aishell"
        )
        total_success += success
        total_fail += fail
    else:
        print(f"\n⚠️ 未找到文件: {AISHELL_JSONL}")
    
    # 处理Grid Device数据
    if os.path.exists(GRID_DEVICE_JSONL):
        success, fail = process_jsonl_file(
            GRID_DEVICE_JSONL,
            GRID_DEVICE_OUTPUT,
            augmenter,
            source_type="grid"
        )
        total_success += success
        total_fail += fail
    else:
        print(f"\n⚠️ 未找到文件: {GRID_DEVICE_JSONL}")
    
    # 最终统计
    print(f"\n{'='*60}")
    print(f"🎉 所有文件处理完成！")
    print(f"{'='*60}")
    print(f"📊 总计:")
    print(f"  ✅ 成功生成: {total_success} 条噪声数据")
    print(f"  ❌ 失败: {total_fail} 条")
    print(f"  📂 音频文件保存在: {os.path.abspath(OUTPUT_AUDIO_DIR)}")
    print(f"  📝 新索引文件:")
    print(f"    - {os.path.abspath(AISHELL_OUTPUT)}")
    print(f"    - {os.path.abspath(GRID_DEVICE_OUTPUT)}")
    print(f"{'='*60}")
    
    # 计算文件大小
    if os.path.exists(OUTPUT_AUDIO_DIR):
        total_size = 0
        file_count = 0
        for root, dirs, files in os.walk(OUTPUT_AUDIO_DIR):
            for file in files:
                if file.endswith('.wav'):
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
                    file_count += 1
        
        print(f"\n💾 存储统计:")
        print(f"  音频文件数: {file_count}")
        print(f"  总大小: {total_size / (1024**3):.2f} GB")
        print(f"  平均每个文件: {total_size / file_count / 1024:.2f} KB" if file_count > 0 else "")
    
    # 数据分布统计
    print(f"\n📈 数据分布:")
    print(f"  AIShell原始: {aishell_count} 条")
    print(f"  AIShell加噪: {int(aishell_count * NOISE_RATIO)} 条 (预期)")
    print(f"  Grid原始: {grid_count} 条")
    print(f"  Grid加噪: {int(grid_count * NOISE_RATIO)} 条 (预期)")
    print(f"  总计: {total_input_count + total_success} 条 (原始+加噪)")
    
    # 给出后续建议
    print(f"\n💡 下一步:")
    print(f"  1. 检查生成的音频文件: {OUTPUT_AUDIO_DIR}")
    print(f"  2. 验证JSONL文件格式: head -n 3 {AISHELL_OUTPUT}")
    print(f"  3. 合并原始数据和加噪数据:")
    print(f"     cat {AISHELL_JSONL} {AISHELL_OUTPUT} > audio_data/aishell_combined.jsonl")
    print(f"     cat {GRID_DEVICE_JSONL} {GRID_DEVICE_OUTPUT} > audio_data/grid_combined.jsonl")
    print(f"  4. 或合并所有数据:")
    print(f"     cat {AISHELL_JSONL} {AISHELL_OUTPUT} {GRID_DEVICE_JSONL} {GRID_DEVICE_OUTPUT} > audio_data/all_data.jsonl")


if __name__ == "__main__":
    main()