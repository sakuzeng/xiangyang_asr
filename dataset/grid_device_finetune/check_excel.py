import pandas as pd

# 读取Excel检查数据结构
df = pd.read_excel('grid_device_name.xlsx')

print("Excel列名:")
print(df.columns.tolist())
print("\n前5行数据:")
print(df.head())
print("\n数据类型:")
print(df.dtypes)
print("\n一端变电站id是否有空值:")
print(df['一端变电站id'].isna().sum())
print("\n二端变电站id是否有空值:")
print(df['二端变电站id'].isna().sum())
print("\n示例数据:")
print(df[['一端变电站id', '二端变电站id', '中文名称']].head(10))