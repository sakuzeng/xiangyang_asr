import csv
import random
import os

# ================= 配置区域 =================

# 输入文件路径
INPUT_CSV = "station_name.csv"
# 输出文件路径
OUTPUT_TXT = "station_queries.txt"

# 1. 核心指标 (你的定义)
TARGET_LOAD = ["最大负荷", "负荷峰值", "当前负荷", "今日负荷"]
TARGET_RATE = ["最大负载率", "负载率", "重过载情况", "重过载", "最大重过载"]

# 合并为一个大的目标列表，方便遍历
ALL_TARGETS = TARGET_LOAD + TARGET_RATE

# 2. 辅助词槽
TIMES = ["", "今天", "当前", "这个月", "昨天的"]
ASK_WORDS = ["是多少", "查一下", "汇报一下", "怎么样", "有无异常", "的数据", ""]

# ================= 核心逻辑 =================

def load_stations(csv_path):
    """读取 CSV 文件中的变电站名称"""
    stations = []
    if not os.path.exists(csv_path):
        print(f"❌ 错误：找不到文件 {csv_path}")
        return []
    
    try:
        # encoding='utf-8-sig' 可以自动处理 Excel 导出的 UTF-8 BOM
        # 如果报错，尝试改为 'gbk'
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'station_name' in row and row['station_name'].strip():
                    stations.append(row['station_name'].strip())
    except Exception as e:
        print(f"❌ 读取 CSV 失败: {e}")
        return []
    
    print(f"✅ 成功读取 {len(stations)} 个变电站名称")
    return stations

def expand_station_name(name):
    """
    数据增强：增加变电站名称的多样性
    例如：'油坊变' -> 可能是 '油坊变电站', '油坊站', '油坊变'
    """
    base_name = name.replace("变电站", "").replace("变", "")
    
    # 随机返回一种称呼，或者你也可以在这里做全排列
    # 这里为了训练稳定，暂时只返回原始名称，或者按一定概率扩展
    # 如果你想让模型听懂“油坊站”，可以按概率替换
    prob = random.random()
    if prob < 0.3:
        return base_name + "变电站"
    elif prob < 0.6:
        return base_name + "站"
    else:
        return name # 保持原样 (如 "油坊变")

def generate_balanced_corpus(stations):
    """
    【推荐】均衡生成模式
    策略：遍历每一个站，遍历每一个核心指标。
    但“时间”和“疑问词”随机搭配，避免数据爆炸。
    """
    results = []
    
    for station in stations:
        # 遍历所有核心指标（必须覆盖，不能随机漏掉）
        for target in ALL_TARGETS:
            
            # 针对每一对 (站名+指标)，生成 2-3 种不同的问法
            # 这样既保证了覆盖率，又增加了句式丰富度
            for _ in range(2): 
                time_word = random.choice(TIMES)
                ask_word = random.choice(ASK_WORDS)
                
                # 站名增强 (可选)
                final_station_name = expand_station_name(station)
                
                # 句式模版构建
                # 模版1: [时间][站名]的[指标][疑问] (最常见)
                # 模版2: [站名][指标] (最简)
                
                if random.random() > 0.5:
                    text = f"{time_word}{final_station_name}的{target}{ask_word}"
                else:
                    # 去掉“的”，稍微口语化一点
                    text = f"{time_word}{final_station_name}{target}{ask_word}"
                
                # 清洗文本 (移除多余空格、None等)
                text = text.replace(" ", "")
                results.append(text)
                
    return results

def generate_full_enumeration(stations):
    """
    【慎用】全量枚举模式 (笛卡尔积)
    生成数量 = 站名数 * 9个指标 * 5个时间 * 7个疑问词
    如果站名有 100 个，结果就是 31,500 条。
    """
    results = []
    for station in stations:
        for target in ALL_TARGETS:
            for time_word in TIMES:
                for ask_word in ASK_WORDS:
                    text = f"{time_word}{station}的{target}{ask_word}"
                    results.append(text)
    return results

# ================= 运行入口 =================

if __name__ == "__main__":
    # 1. 读取站名
    station_list = load_stations(INPUT_CSV)
    
    if station_list:
        # 2. 生成文本
        # 切换模式：这里使用均衡模式，如果你非要全量枚举，改调 generate_full_enumeration
        corpus = generate_balanced_corpus(station_list)
        
        # 去重（防止随机随重了）
        corpus = list(set(corpus))
        
        # 3. 保存结果
        with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
            for line in corpus:
                f.write(line + "\n")
                
        print(f"🎉 生成完毕！")
        print(f"📊 变电站数量: {len(station_list)}")
        print(f"📝 生成文本行数: {len(corpus)}")
        print(f"📂 结果已保存至: {OUTPUT_TXT}")
        
        print("\n👀 预览前 10 条数据:")
        for line in corpus[:10]:
            print(f" - {line}")