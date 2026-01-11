#!/bin/bash

# 获取脚本所在目录的绝对路径并进入，无论在哪个目录下执行
cd "$(dirname "$0")" || exit

# === 配置 ===
APP_NAME="interaction.py"
PID_FILE="interaction.pid"
LOG_DIR="./logs"
DATE=$(date -u -d "+8 hours" "+%Y-%m-%d_%H-%M-%S")
LOG_FILE="$LOG_DIR/interaction_$DATE.log"

# 创建日志目录
if [ ! -d "$LOG_DIR" ]; then
    mkdir -p "$LOG_DIR"
    echo "📂 创建日志目录: $LOG_DIR"
fi

# 清理 logs 目录下超过 7 天的 .log 文件
find "$LOG_DIR" -name "*.log" -type f -mtime +7 -exec rm -f {} \;

echo "----------------------------------------------------"
echo "🚀 正在启动交互系统 (Interaction System)..."

# 检查是否已运行
if [ -f "$PID_FILE" ]; then
    pid=$(cat "$PID_FILE")
    if kill -0 "$pid" 2>/dev/null; then
        echo "⚠️  服务 $APP_NAME 已经在运行中 (PID: $pid)。"
        exit 1
    else
        echo "⚠️  发现过期的 PID 文件，正在清理..."
        rm "$PID_FILE"
    fi
fi

# 启动服务
# 关键点解释：
# 1. python3 -u : 禁用输出缓存，确保 print() 的内容能立即写入日志，而不需要改代码用 logger
# 2. > "$LOG_FILE" 2>&1 : 将标准输出(stdout)和错误输出(stderr)都重定向到同一个日志文件
nohup python3 -u "$APP_NAME" > "$LOG_FILE" 2>&1 &

new_pid=$!
# 等待 1 秒，捕捉立即崩溃的错误（如语法错误、模块缺失）
sleep 1

# 检查进程是否依然存活
if kill -0 "$new_pid" 2>/dev/null; then
    # --- 启动成功 ---
    echo "$new_pid" > "$PID_FILE"
    echo "✅ $APP_NAME 已启动 (PID: $new_pid)"
    echo "📝 日志文件: $(pwd)/$LOG_FILE"
    echo "👉 请使用 tail -f $(pwd)/$LOG_FILE 查看详细运行情况"
else
    # --- 启动失败 ---
    echo "❌ $APP_NAME 启动失败！进程在启动后立即退出。"
    echo "🔍 以下是日志文件 ($LOG_FILE) 的最后 10 行输出："
    echo "----------------------------------------------------"
    tail -n 10 "$LOG_FILE"
    echo "----------------------------------------------------"
    # 返回非 0 状态码，方便外部监控脚本判断
    exit 1
fi
echo "----------------------------------------------------"