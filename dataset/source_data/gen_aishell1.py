import os
import json

# ================= 配置区域 =================

# 脚本所在目录 (dataset)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 输入路径
AISHELL_ROOT = os.path.join(BASE_DIR, "speech_asr_aishell1_testsets")
WAV_ROOT = os.path.join(AISHELL_ROOT, "wav")
TRANSCRIPT_FILE = os.path.join(AISHELL_ROOT, "transcript", "data.text")

# 输出文件
OUTPUT_JSONL = os.path.join(BASE_DIR, "data", "aishell_train.jsonl")

# Docker 路径映射配置
# 如果您是在 Docker 中运行训练，需要将 Windows 路径转换为容器内路径
# 根据您之前的 train.jsonl，映射关系如下：
# Windows: ...\workspace\asr\dataset
# Docker:  /home/devuser/workspace/asr/dataset
DOCKER_PREFIX = "/home/devuser/workspace/asr/dataset"

def generate_jsonl():
    print("🚀 开始生成 AISHELL-1 训练索引文件...")
    
    # 1. 读取标注文件
    print(f"📖 读取标注文件: {TRANSCRIPT_FILE}")
    id_to_text = {}
    
    if not os.path.exists(TRANSCRIPT_FILE):
        print(f"❌ 错误: 找不到标注文件 {TRANSCRIPT_FILE}")
        return

    with open(TRANSCRIPT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            # 格式: BAC009S0002W0122 而对楼市成交抑制作用最大的限购
            parts = line.strip().split(maxsplit=1)
            if len(parts) == 2:
                file_id, text = parts
                # 去除空格 (中文 ASR 通常不需要字之间的空格)
                id_to_text[file_id] = text.replace(" ", "")

    print(f"✅ 加载了 {len(id_to_text)} 条标注数据")

    # 2. 遍历音频文件
    print(f"🔍 扫描音频文件目录: {WAV_ROOT}")
    jsonl_data = []
    valid_count = 0
    missing_count = 0
    
    for root, dirs, files in os.walk(WAV_ROOT):
        for file in files:
            if file.lower().endswith(".wav"):
                # 获取文件名作为 ID (例如: BAC009S0724W0121)
                file_id = os.path.splitext(file)[0]
                
                if file_id in id_to_text:
                    # 获取 Windows 绝对路径
                    abs_path = os.path.abspath(os.path.join(root, file))
                    
                    # === 路径转换逻辑 ===
                    # 计算相对于 dataset 目录的相对路径
                    # 例如: speech_asr_aishell1_testsets\wav\dev\S0724\BAC009S0724W0121.wav
                    rel_path = os.path.relpath(abs_path, BASE_DIR)
                    
                    # 转换为 Linux 风格路径 (将 \ 替换为 /)
                    rel_path_linux = rel_path.replace("\\", "/")
                    
                    # 拼接 Docker 前缀
                    final_path = f"{DOCKER_PREFIX}/{rel_path_linux}"
                    
                    entry = {
                        "key": file_id,
                        "wav": final_path,
                        "txt": id_to_text[file_id]
                    }
                    jsonl_data.append(entry)
                    valid_count += 1
                else:
                    # 如果找不到对应的标注，记录一下（可选）
                    # print(f"⚠️ 警告: 找不到 ID {file_id} 的标注")
                    missing_count += 1

    # 3. 写入 JSONL 文件
    os.makedirs(os.path.dirname(OUTPUT_JSONL), exist_ok=True)
    print(f"💾 正在写入数据到: {OUTPUT_JSONL}")
    
    with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
        for entry in jsonl_data:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print("\n" + "="*30)
    print(f"🎉 全部完成！")
    print(f"📊 成功匹配并写入: {valid_count} 条")
    if missing_count > 0:
        print(f"⚠️ 未找到标注的音频: {missing_count} 条")
    print(f"📂 输出文件: {OUTPUT_JSONL}")
    print(f"ℹ️  注意: 生成的路径已转换为 Docker 格式 ({DOCKER_PREFIX}/...)")

if __name__ == "__main__":
    generate_jsonl()