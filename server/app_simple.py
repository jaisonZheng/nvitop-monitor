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
    "raw_output": "",
    "hostname": "",
    "username": ""
}

class RawOutputData(BaseModel):
    timestamp: str
    raw_output: str
    hostname: str
    username: str

@app.post("/update_raw")
async def update_raw_data(data: RawOutputData):
    """接收来自HPC客户端的原始nvitop输出"""
    global gpu_data
    gpu_data = {
        "timestamp": data.timestamp,
        "raw_output": data.raw_output,
        "hostname": data.hostname,
        "username": data.username
    }
    return {"status": "success"}

@app.get("/data")
async def get_data():
    """获取最新的GPU数据"""
    return gpu_data

@app.get("/", response_class=HTMLResponse)
async def index():
    """返回简化版监控页面"""
    html_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NVITOP GPU Monitor</title>
    <style>
        body {
            margin: 0;
            padding: 20px;
            background-color: #000;
            color: #00ff00;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.2;
        }

        .container {
            max-width: 100%;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            margin-bottom: 10px;
            padding: 10px;
            border-bottom: 1px solid #00ff00;
        }

        .status {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            font-size: 12px;
        }

        .terminal {
            background: #111;
            border: 1px solid #333;
            border-radius: 4px;
            padding: 15px;
            white-space: pre-wrap;
            font-size: 13px;
            line-height: 1.3;
            overflow-x: auto;
            min-height: 400px;
        }

        .loading {
            text-align: center;
            animation: blink 1s infinite;
        }

        @keyframes blink {
            0%, 50% { opacity: 1; }
            51%, 100% { opacity: 0.5; }
        }

        .error {
            color: #ff0000;
        }

        /* 响应式设计 */
        @media (max-width: 1200px) {
            .terminal { font-size: 12px; }
        }

        @media (max-width: 800px) {
            .terminal { font-size: 11px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>NVITOP GPU Monitor</h1>
        </div>

        <div class="status">
            <span id="status-left">状态: <span id="connection-status">连接中...</span></span>
            <span id="status-right">更新时间: <span id="timestamp">--</span></span>
        </div>

        <div class="terminal" id="content">
            <div class="loading">正在连接服务器...</div>
        </div>
    </div>

    <script>
        let lastData = null;

        async function fetchData() {
            try {
                const response = await fetch('/data');
                const data = await response.json();

                // 更新状态
                document.getElementById('timestamp').textContent = data.timestamp || '--';

                if (data.raw_output && data.raw_output !== lastData) {
                    // 显示原始输出
                    document.getElementById('content').innerHTML = data.raw_output;
                    document.getElementById('connection-status').textContent = '已连接';
                    lastData = data.raw_output;
                } else if (!data.raw_output && !data.hostname) {
                    document.getElementById('content').innerHTML = '<div class="loading">等待GPU数据...</div>';
                    document.getElementById('connection-status').textContent = '等待数据';
                }

            } catch (error) {
                console.error('Error:', error);
                document.getElementById('content').innerHTML = '<div class="error">连接失败: ' + error.message + '</div>';
                document.getElementById('connection-status').textContent = '连接失败';
            }
        }

        // 每秒更新一次
        setInterval(fetchData, 1000);
        fetchData();
    </script>
</body>
</html>
    """
    return html_content

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)