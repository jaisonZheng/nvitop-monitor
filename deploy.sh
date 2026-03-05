#!/bin/bash

# HPC GPU监控系统部署脚本

set -e

echo "=== HPC GPU监控系统部署脚本 ==="
echo

# 检查参数
if [ $# -ne 2 ]; then
    echo "用法: $0 <服务器IP> <HPC主机名>"
    echo "示例: $0 123.123.123.123 jump-H20-8Card"
    exit 1
fi

SERVER_IP=$1
HPC_HOST=$2
SERVER_URL="http://${SERVER_IP}:8000"

echo "服务器IP: $SERVER_IP"
echo "HPC主机: $HPC_HOST"
echo "服务器URL: $SERVER_URL"
echo

# 更新客户端配置
echo "1. 更新客户端配置..."
sed -i "s|SERVER_URL = \"http://YOUR_SERVER_IP:8000\"|SERVER_URL = \"$SERVER_URL\"|g" client/monitor.py
echo "   ✓ 已更新服务器地址"

# 打包项目
echo
echo "2. 打包项目..."
cd "$(dirname "$0")"
tar -czf /tmp/hpc-gpu-monitor.tar.gz --exclude='.git' --exclude='__pycache__' --exclude='.venv' .
echo "   ✓ 项目已打包到 /tmp/hpc-gpu-monitor.tar.gz"

# 部署到云服务器
echo
echo "3. 部署到云服务器..."
ssh myserver "
    # 创建目录
    mkdir -p ~/hpc-gpu-monitor

    # 停止已有的服务
    pkill -f 'python.*server/app.py' || true
    pkill -f 'uvicorn' || true

    # 清理旧文件
    rm -rf ~/hpc-gpu-monitor/*
"

# 上传文件
echo "   上传文件到云服务器..."
scp /tmp/hpc-gpu-monitor.tar.gz myserver:~/
ssh myserver "
    cd ~
    tar -xzf hpc-gpu-monitor.tar.gz
    rm hpc-gpu-monitor.tar.gz

    # 安装依赖
    cd hpc-gpu-monitor/server
    pip install -r requirements.txt

    # 启动服务
    nohup python app.py > server.log 2>&1 &

    # 等待服务启动
    sleep 3

    # 检查服务状态
    if curl -s http://localhost:8000 > /dev/null; then
        echo '   ✓ 云服务启动成功'
    else
        echo '   ✗ 云服务启动失败，请检查日志'
        cat server.log
        exit 1
    fi
"

# 部署到HPC服务器
echo
echo "4. 部署到HPC服务器..."
ssh "$HPC_HOST" "
    # 创建目录
    mkdir -p ~/hpc-gpu-monitor

    # 停止旧的监控进程
    pkill -f 'python.*monitor.py' || true

    # 清理旧文件
    rm -rf ~/hpc-gpu-monitor/*
"

# 上传文件到HPC
echo "   上传文件到HPC服务器..."
scp /tmp/hpc-gpu-monitor.tar.gz "$HPC_HOST":~/
ssh "$HPC_HOST" "
    cd ~
    tar -xzf hpc-gpu-monitor.tar.gz
    rm hpc-gpu-monitor.tar.gz

    # 安装依赖
    cd hpc-gpu-monitor/client
    pip install --user -r requirements.txt

    echo '   ✓ HPC客户端部署完成'
    echo '   请手动运行: cd ~/hpc-gpu-monitor/client && python monitor.py'
"

# 清理本地临时文件
rm -f /tmp/hpc-gpu-monitor.tar.gz

echo
echo "=== 部署完成 ==="
echo
echo "访问地址: http://$SERVER_IP:8000"
echo
echo "下一步操作:"
echo "1. 在HPC服务器上运行: ssh $HPC_HOST 'cd ~/hpc-gpu-monitor/client && python monitor.py'"
echo "2. 打开浏览器访问: http://$SERVER_IP:8000"
echo
echo "要停止服务:"
echo "- 云服务器: ssh myserver 'pkill -f python'"
echo "- HPC客户端: ssh $HPC_HOST 'pkill -f monitor.py'"
echo