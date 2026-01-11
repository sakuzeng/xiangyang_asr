# 语音交互控制接口

## 接口信息

### 1. 获取近期识别文本 (listen_recent)

| 接口名称 | listen_recent |
| :--- | :--- |
| 接口描述 | 非侵入式获取音频缓冲区中的最近文本。该接口不会触发系统状态切换，不占用互斥锁，不清除缓冲区，适用于旁路监听或调试。 |
| 请求方法 | POST |
| 请求路径 | `http://localhost:8004/listen_recent` |
| Content-Type | application/json |

**请求参数**

| 参数名称 | 类型 | 是否必须 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- | :--- |
| duration | float | 否 | 5.0 | 获取最近多少秒内的音频识别结果 |
| since_time | float | 否 | null | 指定起始时间戳。如果提供，将忽略 duration，返回该时间点之后的内容 |

**响应参数**

| 参数名称 | 类型 | 描述 |
| :--- | :--- | :--- |
| text | string | 识别到的文本内容 |
| success | bool | 是否执行成功 |
| error | string | 错误信息 (如果有) |

**请求示例**
```json
{
    "duration": 3.0
}
```

**返回示例**
```json
{
    "text": "你好小安",
    "success": true,
    "error": null
}
```

### 2. 获取系统状态 (get_status)

| 接口名称 | get_status |
| :--- | :--- |
| 接口描述 | 获取交互系统当前的运行状态，包括缓冲状态、系统状态机状态、唤醒检测锁状态等。 |
| 请求方法 | GET |
| 请求路径 | `http://localhost:8004/status` |

**请求参数**: 无

**响应参数**

| 参数名称 | 类型 | 描述 |
| :--- | :--- | :--- |
| buffer_active | bool | 音频缓冲区是否处于活跃状态 |
| system_state | string | 当前状态机状态 (WAIT_WAKE, LISTENING, THINKING, SPEAKING) |
| wake_paused | bool | 唤醒检测是否被暂停 |
| pause_source | string | 暂停唤醒检测的来源 (如有) |

**返回示例**
```json
{
    "buffer_active": true,
    "system_state": "WAIT_WAKE",
    "wake_paused": false,
    "pause_source": null
}
```

### 3. 暂停唤醒检测 (wake/pause)

| 接口名称 | pause_wake_detection |
| :--- | :--- |
| 接口描述 | 暂停系统的唤醒词检测。通常在 TTS 开始播报时调用，以防止系统听到自己的声音而产生误触发 (回声消除机制的一部分)。 |
| 请求方法 | POST |
| 请求路径 | `http://localhost:8004/wake/pause` |
| Content-Type | application/json |

**请求参数**

| 参数名称 | 类型 | 是否必须 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- | :--- |
| source | string | 否 | "api" | 请求暂停的来源标识 (例如 "tts_player") |

**响应参数**

| 参数名称 | 类型 | 描述 |
| :--- | :--- | :--- |
| success | bool | 操作是否成功。如果已被其他来源暂停且来源不一致，则返回 false |
| message | string | 结果描述信息 |

**请求示例**
```json
{
    "source": "tts_player"
}
```

**返回示例**
```json
{
    "success": true,
    "message": "Wake detection paused"
}
```

### 4. 恢复唤醒检测 (wake/resume)

| 接口名称 | resume_wake_detection |
| :--- | :--- |
| 接口描述 | 恢复系统的唤醒词检测。通常在 TTS 播报结束时调用。 |
| 请求方法 | POST |
| 请求路径 | `http://localhost:8004/wake/resume` |
| Content-Type | application/json |

**请求参数**

| 参数名称 | 类型 | 是否必须 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- | :--- |
| source | string | 否 | "api" | 请求恢复的来源标识。必须与暂停时的 source 一致才能成功解锁。 |

**响应参数**

| 参数名称 | 类型 | 描述 |
| :--- | :--- | :--- |
| success | bool | 操作是否成功 |
| message | string | 结果描述信息 |

**请求示例**
```json
{
    "source": "tts_player"
}
```

**返回示例**
```json
{
    "success": true,
    "message": "Wake detection resumed"
}
```