import re
from asr.common import setup_logger

logger = setup_logger("text_processing")

def process_agent_response(text):
    """
    处理 Agent 返回的文本，使其更适合 TTS 播报。
    包括：主变编号修正、日期时间格式化、列表符号处理等。
    """
    if not text:
        return text

    # 1. 修正主变编号 (#2主变 -> 2号主变)
    text = re.sub(r'#(\d+)主变', r'\1号主变', text)

    # 2. 处理日期时间 (2026-01-01 00:06:18 -> 2026年1月1日0点6分18秒)
    def replace_datetime(match):
        year, month, day, hour, minute, second = match.groups()
        return f"{year}年{int(month)}月{int(day)}日{int(hour)}点{int(minute)}分{int(second)}秒"
    
    # 增强正则：支持多种分隔符(空格或T)和全角半角冒号，防止漏网
    text = re.sub(r'(\d{4})-(\d{1,2})-(\d{1,2})[\sT]+(\d{1,2})[:：](\d{1,2})[:：](\d{1,2})', replace_datetime, text)

    def replace_date(match):
        year, month, day = match.groups()
        return f"{year}年{int(month)}月{int(day)}日"
    
    # 注意：这里要避免误伤 WXH-813A 这种格式，所以限定年份为4位数字
    text = re.sub(r'(\d{4})-(\d{1,2})-(\d{1,2})', replace_date, text)

    # 3. 单独处理时间 (00:06:18 -> 0点6分18秒)
    def replace_time(match):
        hour, minute, second = match.groups()
        return f"{int(hour)}点{int(minute)}分{int(second)}秒"
    
    text = re.sub(r'(?<!\d)(\d{1,2})[:：](\d{1,2})[:：](\d{1,2})(?!\d)', replace_time, text)

    # 4. 处理列表符号 
    # 4.1 处理 "- 设备名称" -> "设备名称"
    text = re.sub(r'(^|\n)\s*-\s+', r'\1', text)
    # 4.2 处理 "1. 变电站" -> "变电站" (数字序号)
    text = re.sub(r'(^|\n)\s*\d+\.\s*', r'\1', text)

    return text

if __name__ == "__main__":
    # 测试用例
    test_cases = [
        "查询2026-01-01 00:06:18的数据",
        "设备名称：#2主变",
        "- 设备A",
        "1. 变电站名称：孙岗变，最大负载率为83.7252%，发生在2026年1月6日10:54:47。",
        "2. 变电站名称：鹤岗变，最大负载率为83.1157%，发生在2026年1月6日11:24:47。",
        "普通文本，没有特殊格式"
    ]

    logger.info("=== 测试开始 ===")
    for original in test_cases:
        processed = process_agent_response(original)
        logger.info(f"原文本: {original}")
        logger.info(f"处理后: {processed}")
        logger.info("-" * 20)
    logger.info("=== 测试结束 ===")