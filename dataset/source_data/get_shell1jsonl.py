import os

# ================= 配置区域 =================

# 脚本所在目录 (dataset)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 文件路径
TRAIN_JSONL = os.path.join(BASE_DIR, "data", "train.jsonl")            # 参考文件（您的业务数据）
AISHELL_JSONL = os.path.join(BASE_DIR, "data", "aishell_train.jsonl")   # 源文件（公开数据集）
OUTPUT_JSONL = os.path.join(BASE_DIR, "data", "aishell_train_balanced.jsonl") # 输出文件

def count_lines(filepath):
    """统计文件行数"""
    count = 0
    if not os.path.exists(filepath):
        print(f"❌ 错误: 找不到文件 {filepath}")
        return 0
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for _ in f:
            count += 1
    return count

def main():
    print("🚀 开始提取平衡数据集...")

    # 1. 获取目标数量
    print(f"🔍 正在统计业务数据量: {TRAIN_JSONL}")
    target_count = count_lines(TRAIN_JSONL)
    
    if target_count == 0:
        print("⚠️ 业务数据为空或文件不存在，停止操作。")
        return

    print(f"🎯 目标提取数量: {target_count} 条")
    
    # 2. 从 AISHELL 数据中提取
    print(f"📖 正在从 AISHELL 读取数据: {AISHELL_JSONL}")
    extracted_lines = []
    
    if not os.path.exists(AISHELL_JSONL):
        print(f"❌ 错误: 找不到源文件 {AISHELL_JSONL}")
        print("💡 请先运行 gen_aishell_jsonl.py 生成该文件")
        return

    with open(AISHELL_JSONL, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i < target_count:
                extracted_lines.append(line)
            else:
                break
    
    current_count = len(extracted_lines)
    print(f"✅ 已提取 {current_count} 条数据")
    
    if current_count < target_count:
        print(f"⚠️ 警告: AISHELL 数据总量 ({current_count}) 少于业务数据量 ({target_count})，已全部提取。")

    # 3. 保存结果
    print(f"💾 正在保存到: {OUTPUT_JSONL}")
    with open(OUTPUT_JSONL, 'w', encoding='utf-8') as f:
        f.writelines(extracted_lines)
        
    print("\n" + "="*30)
    print(f"🎉 处理完成！")
    print(f"📂 新文件: {OUTPUT_JSONL}")
    print(f"🔢 数据量: {current_count} (与业务数据 1:1 配比)")

if __name__ == "__main__":
    main()