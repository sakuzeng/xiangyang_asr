#!/bin/bash

# 获取脚本所在目录的绝对路径并进入
cd "$(dirname "$0")" || exit

PID_FILE="audio2asr_service.pid"
APP_NAME="server_audio2asr.py"

echo "----------------------------------------------------"
echo "🛑 正在停止 ASR 服务..."

# 1. 检查 PID 文件是否存在
if [ ! -f "$PID_FILE" ]; then
    echo "⚠️  未找到 PID 文件 ($PID_FILE)，尝试通过进程名查找..."
    
    # 兜底方案：如果没有 PID 文件，尝试直接通过进程名匹配杀掉
    # pkill -f 会匹配完整的命令行参数
    if pkill -f "python -u $APP_NAME"; then
        echo "✅ 已通过进程名强制停止残留的 ASR 服务。"
    else
        echo "❌ 未找到运行中的 ASR 服务。"
    fi
    exit 0
fi

# 2. 读取 PID 并检查进程
PID=$(cat "$PID_FILE")

if kill -0 "$PID" 2>/dev/null; then
    
    # === 安全检查：防止 PID 重用误杀 ===
    # 检查该 PID 对应的进程名是否包含我们的脚本名
    if ps -p "$PID" -o args= | grep -q "$APP_NAME"; then
        
        # 发送停止信号
        kill "$PID"
        echo "✅ 已发送停止信号 (PID: $PID)"

        # 循环等待进程结束 (最多 5 秒)
        for i in {1..5}; do
            if ! kill -0 "$PID" 2>/dev/null; then
                break
            fi
            sleep 1
        done

        # 检查是否还在运行
        if kill -0 "$PID" 2>/dev/null; then
            echo "⚠️  进程未响应，正在强制终止 (kill -9)..."
            kill -9 "$PID"
        fi

        # 清理 PID 文件
        rm -f "$PID_FILE"
        echo "✅ ASR 服务已停止。"
        
    else
        echo "⚠️  严重警告：PID $PID 存在，但进程名不匹配 $APP_NAME！"
        echo "⚠️  可能是服务器重启导致 PID 被其他进程重用。"
        echo "🛑 跳过停止操作，并清理过期的 PID 文件。"
        rm -f "$PID_FILE"
    fi

else
    echo "⚠️  进程 $PID 不存在，清理残留 PID 文件。"
    rm -f "$PID_FILE"
fi
echo "----------------------------------------------------"