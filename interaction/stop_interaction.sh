#!/bin/bash

# 获取脚本所在目录的绝对路径并进入
cd "$(dirname "$0")" || exit

APP_NAME="interaction.py"
PID_FILE="interaction.pid"

echo "----------------------------------------------------"
echo "🛑 正在停止交互系统 (Interaction System)..."

if [ -f "$PID_FILE" ]; then
    pid=$(cat "$PID_FILE")
    
    # 检查进程是否存在
    if kill -0 "$pid" 2>/dev/null; then
        
        # === 新增安全检查 ===
        # 防止 PID 重用：检查该 PID 对应的进程命令行是否真的包含脚本名称
        # ps -p <pid> -o args= : 获取该 PID 的完整启动命令
        if ps -p "$pid" -o args= | grep -q "$APP_NAME"; then
        
            # --- 确认是目标进程，开始停止 ---
            kill "$pid"
            echo "✅ 已发送停止信号给 $APP_NAME (PID: $pid)"
            
            # 循环等待进程结束
            for i in {1..5}; do
                if ! kill -0 "$pid" 2>/dev/null; then
                    break
                fi
                sleep 1
            done
            
            # 检查是否还在运行
            if kill -0 "$pid" 2>/dev/null; then
                echo "⚠️  进程未响应，正在强制停止 (kill -9)..."
                kill -9 "$pid"
            fi
            
            rm "$PID_FILE"
            echo "✅ 服务已完全停止。"
            
        else
            # --- PID 存在但不是我们的程序 ---
            echo "⚠️  安全警告：PID $pid 正在运行，但进程名不匹配 $APP_NAME。"
            echo "⚠️  这可能是因为服务器重启后 PID 被其他重要进程重用。"
            echo "🛑 为防止误杀，跳过停止操作，并清理过期的 PID 文件。"
            rm "$PID_FILE"
        fi
        
    else
        echo "⚠️  进程 (PID: $pid) 不存在，清理无效的 PID 文件。"
        rm "$PID_FILE"
    fi
else
    echo "⚠️  未找到 PID 文件 ($PID_FILE)，服务可能未运行。"
fi
echo "----------------------------------------------------"