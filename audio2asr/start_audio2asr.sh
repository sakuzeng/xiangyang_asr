#!/bin/bash

# 1. 获取脚本所在目录的绝对路径并进入 (关键：防止路径错误)
cd "$(dirname "$0")" || exit

# === 配置 ===
# ⚠️ 请确保这里的文件名和你保存的 Python 代码文件名一致
APP_NAME="server_audio2asr.py"
LOG_DIR="./logs"
PID_FILE="audio2asr_service.pid"

# ✅ 日志文件名包含时-分-秒，确保唯一
DATE=$(date -u -d "+8 hours" "+%Y-%m-%d_%H-%M-%S")
LOG_FILE="$LOG_DIR/audio2asr_service_$DATE.log"

# 2. 检查并创建日志目录 (先创建目录，再清理，防止 find 报错)
if [ ! -d "$LOG_DIR" ]; then
    mkdir -p "$LOG_DIR"
    echo "📂 创建日志目录: $LOG_DIR"
fi

# 3. 清理 logs 目录下超过 7 天的 .log 文件
find "$LOG_DIR" -name "*.log" -type f -mtime +7 -exec rm -f {} \; 2>/dev/null

echo "----------------------------------------------------"
echo "🚀 准备启动 ASR 服务: $APP_NAME"

# 4. 检查服务是否已在运行
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "⚠️  ASR 服务已在运行中 (PID: $OLD_PID)"
        echo "   如需重启，请先执行 ./stop_audio2asr.sh"
        exit 1
    else
        echo "🧹 发现过期的 PID 文件，正在清理..."
        rm -f "$PID_FILE"
    fi
fi

# 5. 启动服务
echo "📝 日志文件: $(pwd)/$LOG_FILE"
echo "⏳ 正在执行启动命令..."

# 使用 python (建议确认环境是否需要 python3)
nohup python -u "$APP_NAME" > "$LOG_FILE" 2>&1 &
NEW_PID=$!

# === 6. 状态检查 (新增核心逻辑) ===
# 暂停 1 秒让程序初始化，捕捉立即崩溃的错误
sleep 1

if kill -0 "$NEW_PID" 2>/dev/null; then
    # --- 启动成功 ---
    echo "$NEW_PID" > "$PID_FILE"
    echo "✅ ASR 服务已成功启动! PID: $NEW_PID"
    echo "👉 查看实时日志: tail -f $(pwd)/$LOG_FILE"
else
    # --- 启动失败 ---
    echo "❌ ASR 服务启动失败！进程在 1 秒内退出。"
    echo "👇 错误日志摘要："
    echo "----------------------------------------------------"
    tail -n 10 "$LOG_FILE"
    echo "----------------------------------------------------"
    exit 1
fi
echo "----------------------------------------------------"