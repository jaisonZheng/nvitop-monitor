from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uvicorn
from datetime import datetime
import json

app = FastAPI()

# 存储GPU数据
gpu_data = {
    "timestamp": "",
    "gpus": [],
    "user_processes": []
}

class GPUData(BaseModel):
    timestamp: str
    gpus: list
    user_processes: list

@app.post("/update")
async def update_data(data: GPUData):
    """接收来自HPC客户端的GPU数据"""
    global gpu_data
    gpu_data = {
        "timestamp": data.timestamp,
        "gpus": data.gpus,
        "user_processes": data.user_processes
    }
    return {"status": "success"}

@app.get("/data")
async def get_data():
    """获取最新的GPU数据"""
    return gpu_data

@app.get("/", response_class=HTMLResponse)
async def index():
    """返回监控页面"""
    html_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GPU监控 - nvitop</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
        body {
            font-family: 'JetBrains Mono', monospace;
            background-color: #0c0c0c;
            color: #00ff00;
        }
        .terminal {
            background-color: #000;
            border: 2px solid #00ff00;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 0 20px rgba(0, 255, 0, 0.3);
        }
        .gpu-card {
            border: 1px solid #00ff00;
            background-color: #111;
            margin-bottom: 10px;
            padding: 10px;
            border-radius: 4px;
        }
        .process-item {
            background-color: #1a1a1a;
            padding: 5px 10px;
            margin: 2px 0;
            border-left: 3px solid #00ff00;
        }
        .loading {
            animation: pulse 1s infinite;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        .status-bar {
            background-color: #00ff00;
            color: #000;
            padding: 5px 10px;
            font-weight: bold;
            margin-bottom: 20px;
            border-radius: 4px;
        }
    </style>
</head>
<body class="min-h-screen p-8">
    <div class="max-w-6xl mx-auto">
        <div class="terminal">
            <div class="status-bar">
                <span id="status">● CONNECTING...</span>
                <span class="float-right" id="timestamp"></span>
            </div>

            <h1 class="text-2xl font-bold mb-6 text-green-400">GPU Monitor - nvitop</h1>

            <div id="gpu-container">
                <div class="text-center loading">
                    <p>等待数据...</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        async function fetchData() {
            try {
                const response = await fetch('/data');
                const data = await response.json();

                if (data.timestamp) {
                    document.getElementById('status').innerHTML = '● CONNECTED';
                    document.getElementById('status').style.color = '#00ff00';
                    document.getElementById('timestamp').textContent = data.timestamp;

                    renderGPUData(data);
                } else {
                    document.getElementById('status').innerHTML = '● NO DATA';
                    document.getElementById('status').style.color = '#ffaa00';
                }
            } catch (error) {
                console.error('Error fetching data:', error);
                document.getElementById('status').innerHTML = '● ERROR';
                document.getElementById('status').style.color = '#ff0000';
            }
        }

        function renderGPUData(data) {
            const container = document.getElementById('gpu-container');
            container.innerHTML = '';

            if (data.gpus && data.gpus.length > 0) {
                data.gpus.forEach((gpu, index) => {
                    const gpuCard = document.createElement('div');
                    gpuCard.className = 'gpu-card';

                    // GPU基本信息
                    gpuCard.innerHTML = `
                        <div class="flex justify-between items-center mb-2">
                            <div class="font-bold text-green-400">
                                GPU ${gpu.id}: ${gpu.name}
                            </div>
                            <div class="text-sm">
                                温度: ${gpu.temperature}°C | 功耗: ${gpu.power}W
                            </div>
                        </div>
                        <div class="mb-2">
                            <div class="flex justify-between text-sm mb-1">
                                <span>显存使用: ${gpu.memory_used}MB / ${gpu.memory_total}MB</span>
                                <span>${gpu.memory_percent}%</span>
                            </div>
                            <div class="w-full bg-gray-800 rounded-full h-2">
                                <div class="bg-green-500 h-2 rounded-full" style="width: ${gpu.memory_percent}%"></div>
                            </div>
                        </div>
                        <div class="mb-2">
                            <div class="flex justify-between text-sm mb-1">
                                <span>GPU利用率</span>
                                <span>${gpu.gpu_percent}%</span>
                            </div>
                            <div class="w-full bg-gray-800 rounded-full h-2">
                                <div class="bg-blue-500 h-2 rounded-full" style="width: ${gpu.gpu_percent}%"></div>
                            </div>
                        </div>
                    `;

                    // 用户进程
                    const userProcesses = data.user_processes.filter(p => p.gpu_id === gpu.id);
                    if (userProcesses.length > 0) {
                        const processesDiv = document.createElement('div');
                        processesDiv.innerHTML = '<div class="text-sm font-bold mb-2 text-yellow-400">用户进程:</div>';

                        userProcesses.forEach(process => {
                            const processItem = document.createElement('div');
                            processItem.className = 'process-item';
                            processItem.innerHTML = `
                                <div class="flex justify-between text-xs">
                                    <span>PID: ${process.pid}</span>
                                    <span>显存: ${process.gpu_memory}MB</span>
                                </div>
                                <div class="text-xs mt-1">${process.command}</div>
                            `;
                            processesDiv.appendChild(processItem);
                        });

                        gpuCard.appendChild(processesDiv);
                    }

                    container.appendChild(gpuCard);
                });
            } else {
                container.innerHTML = '<div class="text-center">未检测到GPU数据</div>';
            }
        }

        // 每秒更新一次
        setInterval(fetchData, 1000);
        // 初始加载
        fetchData();
    </script>
</body>
</html>
    """
    return html_content

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)