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
    <title>NVITOP GPU Monitor - Simple</title>
</head>
<body style="margin: 0; padding: 20px; background: #000; color: #00ff00; font-family: monospace;">
    <h1 style="text-align: center;">NVITOP GPU Monitor</h1>
    <div id="status">连接中...</div>
    <pre id="content" style="background: #111; border: 1px solid #333; padding: 15px; white-space: pre-wrap; font-size: 13px; line-height: 1.3; min-height: 400px;">等待GPU数据...</pre>

    <script>
        console.log('Script starting...');

        async function fetchData() {
            console.log('Fetching data...');
            try {
                const response = await fetch('/data');
                console.log('Response received:', response.status);

                if (!response.ok) {
                    throw new Error('HTTP error! status: ' + response.status);
                }

                const data = await response.json();
                console.log('Data parsed:', data);

                if (data.raw_output && data.raw_output.trim()) {
                    document.getElementById('content').textContent = data.raw_output;
                    document.getElementById('status').textContent = '已连接 - ' + data.timestamp;
                    console.log('Content updated');
                } else {
                    document.getElementById('status').textContent = '等待数据';
                    console.log('Waiting for data');
                }

            } catch (error) {
                console.error('Error:', error);
                document.getElementById('status').textContent = '错误: ' + error.message;
            }
        }

        // 立即执行一次
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