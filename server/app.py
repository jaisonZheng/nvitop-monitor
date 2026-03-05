from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uvicorn
from datetime import datetime
import json
import html

app = FastAPI()

# 存储GPU数据
gpu_data = {
    "timestamp": "",
    "nvitop_version": "1.6.2",
    "driver_version": "550.163.01",
    "cuda_version": "12.4",
    "hostname": "",
    "username": "",
    "uptime": "",
    "cpu_percent": 0,
    "memory_percent": 0,
    "swap_percent": 0,
    "load_avg": [0, 0, 0],
    "gpus": [],
    "user_processes": [],
    "raw_output": "",
    "mode": "parsed",  # parsed or raw or html
    "html_output": "","replace_all":false}
}

class GPUData(BaseModel):
    timestamp: str
    nvitop_version: str = "1.6.2"
    driver_version: str = "550.163.01"
    cuda_version: str = "12.4"
    hostname: str
    username: str
    uptime: str
    cpu_percent: float
    memory_percent: float
    swap_percent: float
    load_avg: list
    gpus: list
    user_processes: list

class RawOutputData(BaseModel):
    timestamp: str
    raw_output: str
    hostname: str
    username: str

class RawHTMLOutputData(BaseModel):
    timestamp: str
    raw_output: str
    html_output: str
    hostname: str
    username: str

@app.post("/update")
async def update_data(data: GPUData):
    """接收来自HPC客户端的GPU数据"""
    global gpu_data
    gpu_data = data.dict()
    gpu_data["mode"] = "parsed"
    return {"status": "success"}

@app.post("/update_raw")
async def update_raw_data(data: RawOutputData):
    """接收来自HPC客户端的原始nvitop输出"""
    global gpu_data
    gpu_data = {
        "timestamp": data.timestamp,
        "raw_output": data.raw_output,
        "hostname": data.hostname,
        "username": data.username,
        "mode": "raw",
        "html_output": ""
    }
    return {"status": "success"}

@app.post("/update_raw_html")
async def update_raw_html_data(data: RawHTMLOutputData):
    """接收来自HPC客户端的HTML格式nvitop输出"""
    global gpu_data
    gpu_data = {
        "timestamp": data.timestamp,
        "raw_output": data.raw_output,
        "html_output": data.html_output,
        "hostname": data.hostname,
        "username": data.username,
        "mode": "html"
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
        }

        .nvitop-title {
            font-size: 16px;
            font-weight: bold;
            margin-bottom: 5px;
        }

        .system-info {
            text-align: center;
            margin-bottom: 10px;
            font-size: 12px;
        }

        .gpu-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 10px;
        }

        .gpu-table td, .gpu-table th {
            padding: 2px 4px;
            vertical-align: top;
        }

        .border-corner {
            font-weight: bold;
        }

        .gpu-name {
            font-weight: bold;
        }

        .progress-bar {
            display: inline-block;
            width: 200px;
            height: 10px;
            background-color: #333;
            position: relative;
            margin: 0 5px;
        }

        .progress-fill {
            height: 100%;
            background-color: #00ff00;
            position: absolute;
            left: 0;
            top: 0;
        }

        .status-bar {
            margin-top: 10px;
            display: flex;
            justify-content: space-between;
            font-size: 12px;
        }

        .process-table {
            width: 100%;
            margin-top: 10px;
            font-size: 12px;
        }

        .process-header {
            font-weight: bold;
            border-bottom: 1px solid #00ff00;
            margin-bottom: 5px;
            padding-bottom: 2px;
        }

        .process-row {
            display: flex;
            justify-content: space-between;
            padding: 1px 0;
        }

        .loading {
            animation: blink 1s infinite;
        }

        @keyframes blink {
            0%, 50% { opacity: 1; }
            51%, 100% { opacity: 0; }
        }

        .error {
            color: #ff0000;
        }

        .warning {
            color: #ffff00;
        }
    </style>
</head>
<body>
    <div class="container">
        <div id="content">
            <div class="loading">正在连接服务器...</div>
        </div>
    </div>

    <script>
        function formatBytes(bytes) {
            const gb = bytes / (1024 * 1024 * 1024);
            return gb.toFixed(2) + 'GiB';
        }

        function formatPercent(percent) {
            return percent.toFixed(1) + '%';
        }

        function createProgressBar(percent, width = 200) {
            const filled = Math.round((percent / 100) * (width / 3));
            const empty = Math.round((width / 3)) - filled;
            return '█'.repeat(filled) + '▌'.repeat(empty);
        }

        function createASCIIBar(percent, width = 30) {
            const filled = Math.round((percent / 100) * width);
            return '█'.repeat(filled) + '░'.repeat(width - filled);
        }

        function renderGPUData(data) {
            // 如果是原始输出模式，直接显示
            if (data.mode === 'raw' && data.raw_output) {
                // 转义HTML特殊字符但保留空格和换行
                let output = data.raw_output;
                output = output.replace(/&/g, '&amp;');
                output = output.replace(/</g, '&lt;');
                output = output.replace(/>/g, '&gt;');

                // 使用<pre>标签保持格式
                return '<pre style="margin: 0; font-family: inherit; font-size: inherit; line-height: inherit;">' + output + '</pre>';
            }

            // 如果是解析模式，使用之前的渲染逻辑
            if (!data.gpus || data.gpus.length === 0) {
                return '<div class="error">未检测到GPU数据</div>';
            }

            let html = '';

            // Header with system info
            html += `
                <div class="header">
                    <div class="nvitop-title">NVITOP ${data.nvitop_version || '1.6.2'}      Driver Version: ${data.driver_version || 'N/A'}      CUDA Driver Version: ${data.cuda_version || 'N/A'}</div>
                    <div class="system-info">${data.timestamp || ''}  ${data.hostname || ''}  ${data.username || ''}</div>
                </div>
            `;

            // GPU table
            html += '<table class="gpu-table">';

            // Header row
            html += `
                <tr>
                    <td>╒════════════════════════════════════════════════════════════════════════════════════</td>
                    <td>══════════════════════════════════════</td>
                    <td>══════════════════════════════════════╕</td>
                </tr>
                <tr>
                    <td>│ GPU  Name        Persistence-M│ Bus-Id        Disp.A │ MIG M.   Uncorr. ECC │</td>
                    <td>│  Fan  Temp  Perf  Pwr:Usage/Cap│         Memory-Usage │ GPU-Util  Compute M. │</td>
                    <td>│ MEM: ${createProgressBar(data.gpus[0]?.memory_percent || 0)} ${formatPercent(data.gpus[0]?.memory_percent || 0)} │ MBW: ${createProgressBar(data.gpus[0]?.mbw_percent || 0)} ${formatPercent(data.gpus[0]?.mbw_percent || 0)} │</td>
                </tr>
                <tr>
                    <td>╞═══════════════════════════════════╪══════════════════════╪══════════════════════╡</td>
                    <td>══════════════════════════════════════╪══════════════════════════════════════════════════════════════════╪═══════════════════════════════════════════════════════</td>
                    <td>═════════════╡</td>
                </tr>
            `;

            // GPU rows
            data.gpus.forEach((gpu, index) => {
                const isLast = index === data.gpus.length - 1;
                const borderStyle = isLast ? '╘' : '├';

                html += `
                    <tr>
                        <td>│ <span class="gpu-name">${gpu.id.toString().padStart(2)}  ${gpu.name.padEnd(16)}</span>│ ${gpu.persistence || 'Off'} │ ${gpu.bus_id?.padEnd(12) || 'N/A'} ${gpu.display || 'Off'} │ ${gpu.mig_mode || 'Disabled'} ${gpu.ecc || '0'} │</td>
                        <td>│  N/A   ${gpu.temperature.toString().padStart(2)}C   ${gpu.performance || 'P0'}    ${gpu.power}W / ${gpu.power_cap || '500W'} │  ${formatBytes(gpu.memory_used * 1024 * 1024).padStart(8)} / ${formatBytes(gpu.memory_total * 1024 * 1024).padStart(8)} │     ${gpu.gpu_percent.toString().padStart(3)}%      ${gpu.compute_mode || 'Default'} │</td>
                        <td>│ MEM: ${createProgressBar(gpu.memory_percent)} ${formatPercent(gpu.memory_percent).padStart(5)} │ MBW: ${createProgressBar(gpu.mbw_percent || 0)} ${formatPercent(gpu.mbw_percent || 0).padStart(5)} │</td>
                    </tr>
                    <tr>
                        <td>${borderStyle}═══════════════════════════════════╧══════════════════════╧══════════════════════╡</td>
                        <td>══════════════════════════════════════════════════════════════════╧═══════════════════════════════════════════════════════</td>
                        <td>═════════════╡</td>
                    </tr>
                `;
            });

            html += '</table>';

            // System status bar
            html += `
                <div class="status-bar">
                    <div>[ CPU: ${createASCIIBar(data.cpu_percent)} ${formatPercent(data.cpu_percent).padStart(5)} ]  ( Load Average: ${data.load_avg?.join(' ') || '0.00 0.00 0.00'} )</div>
                    <div>[ MEM: ${createASCIIBar(data.memory_percent)} ${formatPercent(data.memory_percent).padStart(5)} ]  [ SWP: ${createASCIIBar(data.swap_percent)} ${formatPercent(data.swap_percent).padStart(5)} ]</div>
                </div>
            `;

            // Processes section
            if (data.user_processes && data.user_processes.length > 0) {
                html += `
                    <div class="process-table">
                        <div class="process-header">Processes: ${' '.repeat(120)} ${data.username || 'N/A'}@${data.hostname || 'N/A'}</div>
                        <div>GPU     PID      USER  GPU-MEM %SM %GMBW  %CPU  %MEM     TIME  COMMAND</div>
                        <div>╞══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════</div>
                `;

                data.user_processes.forEach(proc => {
                    html += `
                        <div class="process-row">
                            <span>${proc.gpu_id.toString().padStart(3)} ${proc.pid.toString().padEnd(8)} ${proc.username?.padEnd(8) || 'N/A'} ${formatBytes(proc.gpu_memory * 1024 * 1024).padEnd(8)} ${proc.gpu_memory_percent?.toString().padStart(3) || '0'}% ${proc.gmbw_percent?.toString().padStart(4) || '0'}% ${proc.cpu_percent?.toString().padStart(5) || 'N/A'} ${proc.memory_percent?.toString().padStart(5) || 'N/A'} ${proc.time?.padStart(8) || 'N/A'}  ${proc.command?.substring(0, 80) || 'N/A'}</span>
                        </div>
                    `;
                });

                html += '</div>';
            }

            return html;
        }

        async function fetchData() {
            try {
                const response = await fetch('/data');
                const data = await response.json();

                if (data.mode === 'raw' && data.raw_output) {
                    // 原始输出模式
                    document.getElementById('content').innerHTML = renderGPUData(data);
                } else if (data.gpus && data.gpus.length > 0) {
                    // 解析模式且有GPU数据
                    document.getElementById('content').innerHTML = renderGPUData(data);
                } else {
                    // 等待数据
                    document.getElementById('content').innerHTML = '<div class="warning">等待GPU数据...</div>';
                }
            } catch (error) {
                console.error('Error fetching data:', error);
                document.getElementById('content').innerHTML = '<div class="error">连接失败: ' + error.message + '</div>';
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