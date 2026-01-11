import random
import os

# --- 配置区域 ---
INPUT_FILE = 'audio_data/all_data.jsonl'  # 输入文件路径
TRAIN_OUTPUT = 'audio_data/train.jsonl'              # 训练集输出路径
VAL_OUTPUT = 'audio_data/val.jsonl'                  # 验证集输出路径 (建议使用 .jsonl 后缀)
SPLIT_RATIO = 0.95                        # 分割比例
RANDOM_SEED = 42                          # 随机种子，保证每次打乱顺序一致
# ----------------

def main():
    # 1. 检查文件是否存在
    if not os.path.exists(INPUT_FILE):
        print(f"错误: 找不到文件 {INPUT_FILE}")
        return

    print(f"正在读取 {INPUT_FILE} ...")
    
    # 2. 读取所有行
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 过滤掉可能的空行
    lines = [line for line in lines if line.strip()]
    total_lines = len(lines)
    
    print(f"总行数: {total_lines}")

    # 3. 打乱数据
    random.seed(RANDOM_SEED)
    random.shuffle(lines)

    # 4. 计算分割点
    split_index = int(total_lines * SPLIT_RATIO)
    
    train_data = lines[:split_index]
    val_data = lines[split_index:]

    # 5. 写入训练集
    print(f"正在写入 {TRAIN_OUTPUT} ({len(train_data)} 行)...")
    with open(TRAIN_OUTPUT, 'w', encoding='utf-8') as f:
        f.writelines(train_data)

    # 6. 写入验证集
    print(f"正在写入 {VAL_OUTPUT} ({len(val_data)} 行)...")
    with open(VAL_OUTPUT, 'w', encoding='utf-8') as f:
        f.writelines(val_data)

    print("分割完成！")

if __name__ == "__main__":
    main()