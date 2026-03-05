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
    """返回最终版监控页面"""
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
            padding: 0;
            background: #000;
            color: #00ff00;
            font-family: 'Courier New', monospace;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }

        .header {
            background: #111;
            padding: 10px 20px;
            border-bottom: 1px solid #333;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .terminal {
            flex: 1;
            padding: 20px;
            overflow: auto;
            background: #000;
        }

        .terminal-content {
            font-size: 13px;
            line-height: 1.2;
            white-space: pre;
        }

        .status {
            font-size: 12px;
        }

        @media (max-width: 1200px) {
            .terminal-content { font-size: 12px; }
        }

        @media (max-width: 800px) {
            .terminal-content { font-size: 11px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1 style="margin: 0; font-size: 18px;">NVITOP GPU Monitor</h1>
        <div class="status">
            <span id="status-text">连接中...</span>
            <span id="timestamp">--</span>
        </div>
    </div>

    <div class="terminal">
        <pre id="content" class="terminal-content">等待GPU数据...</pre>
    </div>

    <script>
        let updateCount = 0;

        async function fetchData() {
            updateCount++;
            console.log(`[${updateCount}] Fetching data...`);

            try {
                const response = await fetch('/data');
                console.log(`[${updateCount}] Response status:`, response.status);

                if (!response.ok) {
                    throw new Error('HTTP error! status: ' + response.status);
                }

                const data = await response.json();
                console.log(`[${updateCount}] Data received:`, {
                    hasRawOutput: !!data.raw_output,
                    timestamp: data.timestamp,
                    hostname: data.hostname
                });

                if (data.raw_output && data.raw_output.trim()) {
                    document.getElementById('content').textContent = data.raw_output;
                    document.getElementById('status-text').textContent = '已连接';
                    document.getElementById('timestamp').textContent = data.timestamp || '--';
                    console.log(`[${updateCount}] Content updated, length:`, data.raw_output.length);
                } else {
                    document.getElementById('status-text').textContent = '等待数据';
                    document.getElementById('timestamp').textContent = '--';
                    console.log(`[${updateCount}] No data available`);
                }

            } catch (error) {
                console.error(`[${updateCount}] Error:`, error);
                document.getElementById('status-text').textContent = '连接失败';
                document.getElementById('timestamp').textContent = '--';
            }
        }

        // 立即执行
        fetchData();

        // 每秒更新
        setInterval(fetchData, 1000);
    </script>
</body>
</html>
    """
    return html_content

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)