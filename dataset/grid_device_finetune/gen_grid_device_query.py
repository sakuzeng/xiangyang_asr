import pandas as pd
import random
from datetime import datetime, timedelta
import json
from pathlib import Path

class PowerCorpusGenerator:
    def __init__(self, excel_path='grid_device_name.xlsx'):
        """初始化语料生成器"""
        self.df = pd.read_excel(excel_path)
        
        # 数字到中文映射（电力场景特殊读法）
        self.digit_map = {
            '0': '洞', '1': '幺', '2': '两', '3': '三', '4': '肆',
            '5': '伍', '6': '陆', '7': '柒', '8': '捌', '9': '玖'
        }
        
        # 时间表达模板
        self.time_templates = [
            '今天', '昨天', '前天', '本月{}日', '{}月{}日'
        ]
        
        # 查询模板 - 修改为包含变电站
        self.query_templates = [
            '查询{time}{station}{voltage}{line}有功值是多少',
            '请问{time}{station}{voltage}{line}的有功值',
            '{time}{station}{voltage}{line}有功是多少',
            '帮我查一下{time}{station}{voltage}{line}有功值',
            '{time}{station}{voltage}{line}有功功率是多少',
            '查一下{time}{station}{voltage}{line}的有功',
        ]
        
        # 电力特殊读法语句模板
        self.special_reading_templates = [
            '请切换到{num}号刀闸',
            '检查{num}号开关状态',
            '操作{num}号断路器',
            '{num}号变压器运行正常',
            '监测{num}号线路电流',
            '{station}{num}号主变投入运行',
            '{num}号母线电压为{voltage}',
            '记录{num}号设备巡检时间',
            '{station}{num}号间隔已送电',
            '关闭{num}号隔离开关',
        ]
        
        # 日期时间标准读法模板（用于对比和避免混淆）
        self.datetime_templates = [
            '记录时间为{year}年{month}月{day}日',
            '{year}年{month}月{day}日设备检修',
            '今天是{year}年{month}月{day}日',
            '{station}在{year}年{month}月{day}日投运',
            '{year}年{month}月{day}日{hour}点{minute}分进行巡检',
            '检修计划安排在{year}年{month}月{day}日',
            '{year}年{month}月的巡检报告',
            '上次检修时间是{year}年{month}月{day}日',
            '{station}{year}年{month}月运行数据',
            '{year}年第{quarter}季度运行报告',
        ]
    
    def number_to_chinese(self, num_str):
        """将数字字符串转换为中文（电力场景特殊读法）"""
        return ''.join(self.digit_map.get(d, d) for d in str(num_str))
    
    def number_to_standard_chinese(self, num):
        """将数字转换为标准中文读法"""
        digit_map_standard = {
            '0': '零', '1': '一', '2': '二', '3': '三', '4': '四',
            '5': '五', '6': '六', '7': '七', '8': '八', '9': '九'
        }
        return ''.join(digit_map_standard.get(d, d) for d in str(num))
    
    def year_to_chinese(self, year):
        """将年份转换为标准中文读法（逐位读）"""
        return self.number_to_standard_chinese(year)
    
    def month_to_chinese(self, month):
        """将月份转换为标准中文读法"""
        if month < 10:
            return f'{self.number_to_standard_chinese(month)}'
        elif month == 10:
            return '十'
        elif month == 11:
            return '十一'
        else:  # 12
            return '十二'
    
    def day_to_chinese(self, day):
        """将日期转换为标准中文读法"""
        if day < 10:
            return f'{self.number_to_standard_chinese(day)}'
        elif day == 10:
            return '十'
        elif day < 20:
            return f'十{self.number_to_standard_chinese(day % 10)}'
        elif day == 20:
            return '二十'
        elif day < 30:
            return f'二十{self.number_to_standard_chinese(day % 10)}'
        elif day == 30:
            return '三十'
        else:
            return f'三十{self.number_to_standard_chinese(day % 10)}'
    
    def voltage_to_chinese(self, voltage_id):
        """将电压等级转换为中文"""
        voltage_map = {
            '10': '一十千伏',
            '35': '三十五千伏',
            '110': '一百一十千伏',
            '220': '二百二十千伏',
            '500': '五百千伏',
            '1000': '一千千伏'
        }
        voltage_str = str(voltage_id).replace('kV', '').replace('KV', '').strip()
        return voltage_map.get(voltage_str, f'{voltage_str}千伏')
    
    def time_to_chinese(self, hour, minute):
        """将时间转换为中文口语表达"""
        hour_map = {
            0: '零', 1: '一', 2: '两', 3: '三', 4: '四', 5: '五',
            6: '六', 7: '七', 8: '八', 9: '九', 10: '十',
            11: '十一', 12: '十二', 13: '十三', 14: '十四', 15: '十五',
            16: '十六', 17: '十七', 18: '十八', 19: '十九', 20: '二十',
            21: '二十一', 22: '二十二', 23: '二十三'
        }
        
        minute_map = {
            0: '零零', 15: '十五', 30: '三十', 45: '四十五'
        }
        
        # 对于其他分钟数
        if minute not in minute_map:
            if minute < 10:
                minute_str = f'零{hour_map[minute]}'
            else:
                tens = minute // 10
                ones = minute % 10
                if tens == 1:
                    minute_str = f'十{hour_map[ones] if ones else ""}'
                else:
                    minute_str = f'{hour_map[tens]}十{hour_map[ones] if ones else ""}'
        else:
            minute_str = minute_map[minute]
        
        return f'{hour_map[hour]}点{minute_str}分'
    
    def generate_time_expression(self):
        """生成时间表达"""
        time_type = random.choice(['relative', 'specific_date', 'specific_datetime'])
        
        if time_type == 'relative':
            return random.choice(['今天', '昨天', '前天'])
        
        elif time_type == 'specific_date':
            month = random.randint(1, 12)
            day = random.randint(1, 28)
            return f'{month}月{day}日'
        
        else:  # specific_datetime
            hour = random.choice([0, 8, 9, 10, 12, 14, 16, 18, 20, 22])
            minute = random.choice([0, 15, 30, 45])
            time_str = self.time_to_chinese(hour, minute)
            
            date_prefix = random.choice(['今日', '昨日', '', f'{random.randint(1, 12)}月{random.randint(1, 28)}日'])
            return f'{date_prefix}{time_str}' if date_prefix else time_str
    
    def normalize_line_name(self, line_name, convert_probability=0.5):
        """规范化线路名称，以一定概率转换一回/二回为幺回/两回
        
        Args:
            line_name: 线路名称
            convert_probability: 转换概率 (0-1)，默认0.5表示50%概率转换
        """
        if not line_name:
            return ''
        
        line_name = str(line_name).strip()
        
        # 以一定概率进行转换
        if random.random() < convert_probability:
            # 转换为电力特殊读法
            line_name = line_name.replace('1回', '幺回').replace('2回', '两回')
            line_name = line_name.replace('一回', '幺回').replace('二回', '两回')
        else:
            # 保持原样或统一为汉字
            line_name = line_name.replace('1回', '一回').replace('2回', '二回')
        
        # 如果不以'线'结尾，添加'线'
        if not line_name.endswith('线'):
            line_name += '线'
        
        return line_name
    
    def generate_special_number_corpus(self):
        """生成电力场景特殊数字读法语句"""
        template = random.choice(self.special_reading_templates)
        
        # 生成特殊数字（1-9位数字组合）
        num_length = random.choice([1, 2, 3, 4])  # 数字长度
        num_str = ''.join([str(random.randint(0, 9)) for _ in range(num_length)])
        num_chinese = self.number_to_chinese(num_str)
        
        # 随机获取变电站和电压
        if '{station}' in template or '{voltage}' in template:
            row = self.df.sample(n=1).iloc[0]
            # 修改：使用大写的ID
            station = random.choice([row.get('一端变电站ID', ''), row.get('二端变电站ID', '')])
            voltage_id = row.get('电压类型ID', '220')
            voltage_chinese = self.voltage_to_chinese(voltage_id)
            
            corpus = template.format(
                num=num_chinese,
                station=station,
                voltage=voltage_chinese
            )
        else:
            corpus = template.format(num=num_chinese)
        
        return {
            'text': corpus,
            'metadata': {
                'type': 'special_reading',
                'original_number': num_str,
                'chinese_number': num_chinese
            }
        }
    
    def generate_datetime_corpus(self):
        """生成日期时间标准读法语料（用于对比，避免混淆）"""
        template = random.choice(self.datetime_templates)
        
        # 生成随机日期时间
        year = random.randint(2020, 2025)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        hour = random.choice([8, 9, 10, 14, 16, 18])
        minute = random.choice([0, 15, 30, 45])
        quarter = random.randint(1, 4)
        
        # 转换为标准中文
        year_chinese = self.year_to_chinese(year)
        month_chinese = self.month_to_chinese(month)
        day_chinese = self.day_to_chinese(day)
        hour_chinese = self.time_to_chinese(hour, minute).split('点')[0]
        minute_chinese = self.time_to_chinese(hour, minute).split('点')[1].replace('分', '')
        
        # 随机选择变电站（如果模板需要）
        if '{station}' in template:
            row = self.df.sample(n=1).iloc[0]
            # 修改：使用大写的ID
            station = random.choice([row.get('一端变电站ID', ''), row.get('二端变电站ID', '')])
        else:
            station = ''
        
        # 生成语料
        corpus = template.format(
            year=year_chinese,
            month=month_chinese,
            day=day_chinese,
            hour=hour_chinese,
            minute=minute_chinese,
            quarter=quarter,
            station=station
        )
        
        return {
            'text': corpus,
            'metadata': {
                'type': 'datetime_standard',
                'year': year,
                'month': month,
                'day': day,
                'hour': hour if '{hour}' in template else None,
                'minute': minute if '{minute}' in template else None
            }
        }
    
    def generate_single_corpus_from_row(self, row, convert_probability=0.5):
        """从指定的行生成单条语料
        
        Args:
            row: DataFrame的一行数据
            convert_probability: 线路名称转换为特殊读法的概率
        """
        # 随机选择使用一端还是二端变电站
        station_options = []
        # 修改：使用大写的ID
        if pd.notna(row.get('一端变电站ID', '')):
            station_options.append(str(row.get('一端变电站ID', '')).strip())
        if pd.notna(row.get('二端变电站ID', '')):
            station_options.append(str(row.get('二端变电站ID', '')).strip())
        
        # 如果没有变电站信息，使用空字符串
        station = random.choice(station_options) if station_options else ''
        
        # 获取电压等级
        # 修改：使用大写的ID
        voltage_id = row.get('电压类型ID', '220')
        voltage_chinese = self.voltage_to_chinese(voltage_id)
        
        # 获取线路名称并规范化（带转换概率）
        line_name = self.normalize_line_name(row.get('中文名称', ''), convert_probability)
        
        # 生成时间表达
        time_expr = self.generate_time_expression()
        
        # 选择查询模板
        template = random.choice(self.query_templates)
        
        # 生成完整语料
        corpus = template.format(
            time=time_expr,
            station=station,
            voltage=voltage_chinese,
            line=line_name
        )
        
        return {
            'text': corpus,
            'metadata': {
                'type': 'normal_query',
                'station': station,
                'voltage': voltage_id,
                'line': row.get('中文名称', ''),
                'converted_line': line_name,
                'time': time_expr
            }
        }
    
    def generate_single_corpus(self, convert_probability=0.5):
        """生成单条语料（随机选择设备）
        
        Args:
            convert_probability: 线路名称转换为特殊读法的概率
        """
        # 随机选择一条设备记录
        row = self.df.sample(n=1).iloc[0]
        return self.generate_single_corpus_from_row(row, convert_probability)
    
    def generate_corpus_batch(self, samples_per_station=3,
                         special_ratio=0.1, 
                         datetime_ratio=0.1,
                         line_convert_probability=0.5, 
                         output_file='grid_device_query.jsonl'):
        """批量生成语料,确保所有变电站+线路组合都被覆盖,时间随机变化
        
        Args:
            samples_per_station: 每个变电站+线路组合生成的样本数 (默认3,时间不同)
            special_ratio: 特殊读法语句的比例 (0-1)
            datetime_ratio: 日期时间标准读法语句的比例 (0-1)
            line_convert_probability: 线路名称转换为特殊读法的概率 (0-1)
            output_file: 输出文件名
        """
        corpus_list = []
        
        print(f'开始生成语料：')
        print(f'  - Excel中设备总数: {len(self.df)} 条')
        print(f'  - 每个变电站+线路组合生成: {samples_per_station} 条 (时间随机)')
        print(f'  - 线路名称转换概率: {line_convert_probability * 100}%\n')
        
        # 第一阶段：为所有变电站+线路组合生成多条语料(时间不同)
        print('第一阶段：为所有变电站+线路组合生成语料...')
        device_count = 0
        combination_count = {'一端': 0, '二端': 0}
        
        for idx, row in self.df.iterrows():
            line_name_original = row.get('中文名称', '')
            
            # 为一端变电站生成多条语料(时间不同)
            # 修改：使用大写的ID
            if pd.notna(row.get('一端变电站ID', '')):
                for sample_idx in range(samples_per_station):
                    try:
                        corpus_data = self.generate_corpus_with_station(
                            row, '一端变电站ID', line_convert_probability
                        )
                        corpus_list.append(corpus_data)
                    except Exception as e:
                        print(f'生成设备 {idx} 一端变电站语料时出错: {e}')
                        continue
                combination_count['一端'] += 1
            
            # 为二端变电站生成多条语料(时间不同)
            # 修改：使用大写的ID
            if pd.notna(row.get('二端变电站ID', '')):
                for sample_idx in range(samples_per_station):
                    try:
                        corpus_data = self.generate_corpus_with_station(
                            row, '二端变电站ID', line_convert_probability
                        )
                        corpus_list.append(corpus_data)
                    except Exception as e:
                        print(f'生成设备 {idx} 二端变电站语料时出错: {e}')
                        continue
                combination_count['二端'] += 1
            
            device_count += 1
            if device_count % 50 == 0:
                print(f'已处理 {device_count}/{len(self.df)} 个设备')
        
        normal_count = len(corpus_list)
        print(f'第一阶段完成：生成 {normal_count} 条普通查询语料')
        print(f'  - 一端变电站+线路组合: {combination_count["一端"]} 个 × {samples_per_station}条')
        print(f'  - 二端变电站+线路组合: {combination_count["二端"]} 个 × {samples_per_station}条\n')
        
        # 计算特殊语句和日期时间语句数量(基于普通语料数量的比例)
        num_special = int(normal_count * special_ratio / (1 - special_ratio - datetime_ratio))
        num_datetime = int(normal_count * datetime_ratio / (1 - special_ratio - datetime_ratio))
        
        # 第二阶段：生成特殊读法语句
        print(f'第二阶段：生成特殊读法语句...')
        for i in range(num_special):
            try:
                corpus_data = self.generate_special_number_corpus()
                corpus_list.append(corpus_data)
                
                if (i + 1) % 100 == 0:
                    print(f'已生成特殊语句 {i + 1}/{num_special} 条')
            
            except Exception as e:
                print(f'生成第 {i + 1} 条特殊语句时出错: {e}')
                continue
        
        print(f'第二阶段完成：生成 {num_special} 条特殊读法语句\n')
        
        # 第三阶段：生成日期时间标准读法语句
        print(f'第三阶段：生成日期时间标准读法语句...')
        for i in range(num_datetime):
            try:
                corpus_data = self.generate_datetime_corpus()
                corpus_list.append(corpus_data)
                
                if (i + 1) % 100 == 0:
                    print(f'已生成日期时间语句 {i + 1}/{num_datetime} 条')
            
            except Exception as e:
                print(f'生成第 {i + 1} 条日期时间语句时出错: {e}')
                continue
        
        print(f'第三阶段完成：生成 {num_datetime} 条日期时间标准读法语句\n')
        
        # 随机打乱
        random.shuffle(corpus_list)
        
        # 保存为JSONL格式
        with open(output_file, 'w', encoding='utf-8') as f:
            for item in corpus_list:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
        
        # 统计信息
        final_normal_count = len([item for item in corpus_list if item['metadata']['type'] == 'normal_query'])
        special_count = len([item for item in corpus_list if item['metadata']['type'] == 'special_reading'])
        datetime_count = len([item for item in corpus_list if item['metadata']['type'] == 'datetime_standard'])
        
        print(f'\n========== 语料生成完成 ==========')
        print(f'总计生成: {len(corpus_list)} 条')
        print(f'  - 普通查询语句: {final_normal_count} 条 ({final_normal_count/len(corpus_list)*100:.1f}%)')
        print(f'  - 特殊读法语句: {special_count} 条 ({special_count/len(corpus_list)*100:.1f}%)')
        print(f'  - 日期时间标准读法: {datetime_count} 条 ({datetime_count/len(corpus_list)*100:.1f}%)')
        print(f'已保存到: {output_file}\n')
        
        print(f'数据分布说明:')
        print(f'  - 每个变电站+线路组合: {samples_per_station} 条 (时间随机不同)')
        print(f'  - 线路名称转换概率: {line_convert_probability*100:.0f}% (幺回/两回 vs 一回/二回)')
        print(f'  - 时间表达方式: 相对时间/具体日期/具体时间 随机生成\n')
        
        # 分类打印示例
        normal_samples = [item for item in corpus_list if item['metadata']['type'] == 'normal_query'][:5]
        special_samples = [item for item in corpus_list if item['metadata']['type'] == 'special_reading'][:3]
        datetime_samples = [item for item in corpus_list if item['metadata']['type'] == 'datetime_standard'][:3]
        
        print('普通查询语句示例 (同一设备不同时间):')
        for i, item in enumerate(normal_samples, 1):
            print(f'{i}. {item["text"]}')
            print(f'   变电站: {item["metadata"]["station"]}, 时间: {item["metadata"]["time"]}')
        
        print('\n特殊读法语句示例:')
        for i, item in enumerate(special_samples, 1):
            print(f'{i}. {item["text"]} (原始数字: {item["metadata"]["original_number"]})')
        
        print('\n日期时间标准读法示例:')
        for i, item in enumerate(datetime_samples, 1):
            print(f'{i}. {item["text"]}')
        
        return corpus_list
    
    def generate_corpus_with_station(self, row, station_column, convert_probability=0.5):
        """为指定变电站生成语料
        
        Args:
            row: DataFrame的一行数据
            station_column: '一端变电站ID' 或 '二端变电站ID'
            convert_probability: 线路名称转换为特殊读法的概率
        """
        # 获取指定的变电站
        station = str(row.get(station_column, '')).strip()
        
        # 获取电压等级
        # 修改：使用大写的ID
        voltage_id = row.get('电压类型ID', '220')
        voltage_chinese = self.voltage_to_chinese(voltage_id)
        
        # 获取线路名称并规范化（带转换概率）
        line_name = self.normalize_line_name(row.get('中文名称', ''), convert_probability)
        
        # 生成时间表达
        time_expr = self.generate_time_expression()
        
        # 选择查询模板
        template = random.choice(self.query_templates)
        
        # 生成完整语料
        corpus = template.format(
            time=time_expr,
            station=station,
            voltage=voltage_chinese,
            line=line_name
        )
        
        return {
            'text': corpus,
            'metadata': {
                'type': 'normal_query',
                'station': station,
                'station_type': '一端' if station_column == '一端变电站ID' else '二端',
                'voltage': voltage_id,
                'line': row.get('中文名称', ''),
                'converted_line': line_name,
                'time': time_expr
            }
        }


# 使用示例
if __name__ == '__main__':
    generator = PowerCorpusGenerator('grid_device_name.xlsx')
    
    # 生成语料
    # samples_per_station: 每个变电站+线路组合生成3条,时间随机不同
    # 假设100个设备,每个2端 → 200个组合 × 3条 = 600条普通查询
    # 加上10%特殊 + 10%日期 → 总数约 600/(1-0.1-0.1) = 750条
    corpus = generator.generate_corpus_batch(
        samples_per_station=3,     # 每个组合生成3条,时间不同
        special_ratio=0.1,          # 10%特殊读法
        datetime_ratio=0.1,         # 10%日期时间
        line_convert_probability=0.5,  # 50%概率转换幺回/两回
        output_file='grid_device_query_2.jsonl'
    )