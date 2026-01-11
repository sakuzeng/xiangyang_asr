# 数据集准备

## 整体流程

```mermaid
flowchart LR
    A[Excel设备数据] --> B[生成文本语料<br/>gen_grid_device_query.py]
    B --> C[JSONL文本文件]
    C --> D[生成语音数据<br/>gen_grid_device_audio_data.py]
    D --> E[WAV音频+JSONL]
    D --> F[failed_items.json]
    F --> G[重试失败项<br/>gen_grid_device_audio_data_retry_failed_audio.py]
    G --> E
    G -.->|如有失败| F
    
    style B fill:#e1f5ff
    style D fill:#fff4e1
    style G fill:#f0ffe1
```

---

## 1. 生成文本语料

**脚本**: `gen_grid_device_query.py`

### 功能
基于Excel设备数据生成电力设备查询语料，基本格式为：  
**查询 + 时间 + 变电站 + 电压等级 + 线路名称 + 有功值是多少**

### 生成策略

**三阶段生成**:
1. **覆盖阶段** (80%): 确保所有变电站+线路组合都有语料
   - 遍历每个设备的一端和二端变电站
   - 每个变电站生成N条（默认3条），时间随机不同
   - 50%概率转换: `一回→幺回`, `二回→两回`

2. **特殊读法** (10%): 设备编号场景
   - 数字转电力特殊读法: `1234 → 幺两三肆`
   - 模板: "请切换到{num}号刀闸"

3. **日期时间** (10%): 标准中文读法
   - 避免混淆: `2023 → 二零二三年` (非"两洞两三")
   - 模板: "记录时间为{year}年{month}月{day}日"

### 语料示例

| 类型 | 示例 |
|---|---|
| 普通查询 | `查询今日十六点十五分牛首变二百二十千伏牛乔幺回线有功值是多少` |
| 特殊读法 | `请切换到幺两三肆号刀闸` |
| 日期时间 | `记录时间为二零二三年五月十八日` |

---

## 2. 生成语音数据

### 2.1 主生成脚本

**脚本**: `gen_grid_device_audio_data.py`

**功能**: 
- 读取文本JSONL，调用Edge-TTS生成语音
- 随机音色(8种中文)、随机语速(±10%)
- 转换为16kHz单声道WAV格式
- 失败项记录到 `failed_items.json`

**核心流程**:
1. 检查音频文件是否已存在且有效（>1KB，可读取帧数）
2. 如存在有效文件 → 跳过
3. 如不存在 → 随机选择音色和语速 → 调用Edge-TTS
4. 生成MP3 → 转换为WAV → 验证文件
5. 成功 → 写入JSONL，失败 → 记录到 `failed_items.json`

**重试机制**: 每个失败项自动重试3次，延迟递增（5秒→10秒→15秒）

### 2.2 重试失败项脚本

**脚本**: `gen_grid_device_audio_data_retry_failed_audio.py`

**功能**: 专门处理生成失败的语料

**检查逻辑**:
```
1. 检查 failed_items.json 是否存在 → 无则退出
2. 读取失败列表 → 空则退出
3. 对每个失败项:
   - 检查音频文件是否已存在且有效
   - 已存在 → 标记成功，跳过生成
   - 不存在 → 重新生成(最多3次)
4. 更新结果:
   - 成功的追加到 JSONL
   - 仍失败的更新到 failed_items.json
   - 全部成功则删除 failed_items.json
```

**配置参数**:
- 并发数: 3
- 单项重试: 3次
- 延迟递增: 5秒 → 10秒 → 15秒

**可重复运行**: 直到 `failed_items.json` 被删除或为空

### 2.3 使用流程

```bash
# 步骤1: 生成所有音频
python gen_grid_device_audio_data.py
# 输出: grid_device_audio_data.jsonl (成功的)
#       failed_items.json (失败的)

# 步骤2: 重试失败项 (可多次运行)
python gen_grid_device_audio_data_retry_failed_audio.py
# 如果仍有失败，继续运行直到全部成功

# 步骤3: 检查是否完成
# failed_items.json 被删除 → 全部成功
```

### 2.4 输出格式

**JSONL格式** (`grid_device_audio_data.jsonl`):
```json
{"key": "audio_00001", "source": "/path/to/audio_00001.wav", "source_len": 245, "target": "查询今日牛首变二百二十千伏牛乔幺回线有功值是多少", "target_len": 28, "text_language": "<|zh|>", "emo_target": "<|NEUTRAL|>", "event_target": "<|Speech|>", "with_or_wo_itn": "<|withitn|>"}
```

**失败记录** (`failed_items.json`):
```json
[
  {"idx": 5, "text": "查询某某变电站..."},
  {"idx": 12, "text": "帮我查一下某某线路..."}
]
```



