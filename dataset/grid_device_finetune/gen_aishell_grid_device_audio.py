import json
import random
import wave
import contextlib
import os
from pathlib import Path

# 配置路径
AISHELL_FILE = "../source_data/aishell_train.jsonl"  # 输入的JSONL文件
OUTPUT_DIR = "audio_data_2"  # 输出目录
OUTPUT_FILE = "audio_data_2/aishell_grid_device_audio_data.jsonl"  # 输出文件

# 创建输出目录
os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_audio_duration_frames(wav_file, frame_size_ms=10):
    """
    获取音频时长对应的帧数（10ms为一帧）
    """
    try:
        with contextlib.closing(wave.open(wav_file, 'r')) as f:
            frames = f.getnframes()
            rate = f.getframerate()
            duration_seconds = frames / float(rate)
            # 转换为10ms帧数
            duration_frames = int(duration_seconds * 1000 / frame_size_ms)
        return duration_frames
    except Exception as e:
        print(f"⚠️ 无法读取音频文件 {wav_file}: {e}")
        return 0


def load_aishell_data(file_path):
    """
    加载aishell训练数据
    """
    data_list = []
    
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return data_list
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                try:
                    data = json.loads(line)
                    # 检查必需的字段
                    if 'key' in data and 'wav' in data and 'txt' in data:
                        data_list.append(data)
                except json.JSONDecodeError as e:
                    print(f"⚠️ JSON解析错误: {e}")
                    continue
    
    return data_list


def generate_aishell_jsonl(sample_count=3000):
    """
    生成指定数量的aishell jsonl数据
    """
    # 加载原始数据
    print("📖 正在加载aishell数据...")
    aishell_data = load_aishell_data(AISHELL_FILE)
    
    if not aishell_data:
        print("❌ 没有可用的aishell数据")
        return
    
    print(f"✅ 加载了 {len(aishell_data)} 条数据")
    
    # 确定实际采样数量
    actual_count = min(sample_count, len(aishell_data))
    
    if actual_count < sample_count:
        print(f"⚠️ 数据不足，实际只能生成 {actual_count} 条")
    
    # 随机采样
    print(f"🎲 随机采样 {actual_count} 条数据...")
    sampled_data = random.sample(aishell_data, actual_count)
    
    # 生成新的jsonl数据
    output_data = []
    success_count = 0
    fail_count = 0
    
    print(f"🔄 开始转换数据格式...")
    
    for idx, item in enumerate(sampled_data):
        # 检查音频文件是否存在
        wav_path = item['wav']
        
        if not os.path.exists(wav_path):
            print(f"⚠️ [{idx+1}/{actual_count}] 音频文件不存在: {wav_path}")
            fail_count += 1
            continue
        
        # 获取音频时长
        source_len = get_audio_duration_frames(wav_path)
        
        if source_len == 0:
            print(f"⚠️ [{idx+1}/{actual_count}] 无法获取音频时长: {wav_path}")
            fail_count += 1
            continue
        
        # 构建新的数据格式（保留原始key）
        entry = {
            "key": item['key'],  # 保留原始key
            "source": wav_path,
            "source_len": source_len,
            "target": item['txt'],
            "target_len": len(item['txt']),
            "text_language": "<|zh|>",
            "emo_target": "<|NEUTRAL|>",
            "event_target": "<|Speech|>",
            "with_or_wo_itn": "<|withitn|>"
        }
        
        output_data.append(entry)
        success_count += 1
        
        # 每处理100条打印一次进度
        if (idx + 1) % 100 == 0:
            print(f"  处理进度: {idx+1}/{actual_count}")
    
    # 保存为jsonl文件
    print(f"\n💾 正在保存到: {OUTPUT_FILE}")
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for entry in output_data:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    # 打印统计信息
    print(f"\n{'='*60}")
    print(f"生成完成！")
    print(f"  ✅ 成功: {success_count} 条")
    print(f"  ❌ 失败: {fail_count} 条")
    print(f"  📄 输出文件: {OUTPUT_FILE}")
    print(f"  📊 文件大小: {os.path.getsize(OUTPUT_FILE) / 1024:.2f} KB")
    print(f"{'='*60}")
    
    # 显示前3条示例
    if output_data:
        print(f"\n📋 数据示例（前3条）:")
        for i, entry in enumerate(output_data[:3]):
            print(f"\n[{i+1}]")
            print(f"  key: {entry['key']}")  # 显示原始key
            print(f"  source: {entry['source']}")
            print(f"  source_len: {entry['source_len']}")
            print(f"  target: {entry['target']}")
            print(f"  target_len: {entry['target_len']}")


def main():
    """
    主函数
    """
    print("="*60)
    print("🎵 AISHELL数据转换工具")
    print("="*60)
    print(f"📄 输入文件: {AISHELL_FILE}")
    print(f"📁 输出目录: {OUTPUT_DIR}")
    print(f"📝 输出文件: {OUTPUT_FILE}")
    print(f"🎯 目标数量: 3000条")
    print(f"⚙️ 保留原始key")
    print("="*60)
    print()
    
    # 生成数据
    generate_aishell_jsonl(sample_count=3000)


if __name__ == "__main__":
    main()