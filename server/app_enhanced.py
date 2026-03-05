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
    "html_output": "",
    "mode": "parsed"  # parsed or raw or html
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
    """返回增强版监控页面"""
    html_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NVITOP GPU Monitor - Enhanced</title>
    <style>
        /* 基础样式 */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'JetBrains Mono', 'Consolas', 'Monaco', 'Courier New', monospace;
            background: #0a0a0a;
            color: #e0e0e0;
            line-height: 1.4;
            overflow-x: hidden;
        }

        /* 容器样式 */
        .main-container {
            width: 100vw;
            height: 100vh;
            display: flex;
            flex-direction: column;
            padding: 10px;
            background: radial-gradient(circle at center, #1a1a1a 0%, #0a0a0a 100%);
        }

        .header-bar {
            background: linear-gradient(90deg, #1a1a2e 0%, #16213e 50%, #1a1a2e 100%);
            padding: 8px 16px;
            border-radius: 4px;
            margin-bottom: 10px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
        }

        .status-line {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
        }

        .status-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 5px;
            animation: pulse 1.5s infinite;
        }

        .status-online { background-color: #00ff00; }
        .status-offline { background-color: #ff0000; }

        /* 终端样式 */
        .terminal-container {
            flex: 1;
            background: #000;
            border: 2px solid #333;
            border-radius: 8px;
            padding: 10px;
            overflow: auto;
            box-shadow:
                inset 0 0 20px rgba(0, 255, 0, 0.1),
                0 0 20px rgba(0, 0, 0, 0.8);
        }

        .terminal-content {
            font-size: 13px;
            white-space: pre;
            font-family: inherit;
        }

        /* 彩虹渐变样式 */
        .rainbow-bar {
            background: linear-gradient(90deg,
                #ff0000 0%,
                #ff8000 14.28%,
                #ffff00 28.56%,
                #80ff00 42.84%,
                #00ff00 57.12%,
                #00ff80 71.40%,
                #00ffff 85.68%,
                #0080ff 100%
            );
            height: 8px;
            border-radius: 4px;
            display: inline-block;
            vertical-align: middle;
            box-shadow: 0 0 4px rgba(255, 255, 255, 0.3);
        }

        .progress-container {
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }

        .progress-text {
            font-weight: bold;
            min-width: 40px;
        }

        /* 颜色主题 */
        .nvitop-red { color: #ff5555; font-weight: bold; }
        .nvitop-green { color: #55ff55; font-weight: bold; }
        .nvitop-yellow { color: #ffff55; font-weight: bold; }
        .nvitop-blue { color: #5555ff; font-weight: bold; }
        .nvitop-magenta { color: #ff55ff; font-weight: bold; }
        .nvitop-cyan { color: #55ffff; font-weight: bold; }
        .nvitop-white { color: #ffffff; font-weight: bold; }
        .nvitop-gray { color: #888888; }
        .nvitop-bold { font-weight: bold; }
        .nvitop-blink {
            animation: blink 1s infinite;
            color: #ffff00;
        }

        /* ASCII艺术边框 */
        .ascii-border {
            color: #00ff00;
            text-shadow: 0 0 2px #00ff00;
        }

        /* GPU状态颜色 */
        .gpu-temp-high { color: #ff4444; }
        .gpu-temp-medium { color: #ffaa44; }
        .gpu-temp-low { color: #44ff44; }

        .gpu-util-high { color: #ff44ff; }
        .gpu-util-medium { color: #ffaa44; }
        .gpu-util-low { color: #44ff44; }

        /* 响应式设计 */
        @media (max-width: 1400px) {
            .terminal-content {
                font-size: 12px;
            }
        }

        @media (max-width: 1200px) {
            .terminal-content {
                font-size: 11px;
            }
        }

        @media (max-width: 1000px) {
            .terminal-content {
                font-size: 10px;
            }
        }

        /* 加载动画 */
        .loading-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.8);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }

        .loading-text {
            color: #00ff00;
            font-size: 16px;
            animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
            0% { opacity: 0.4; transform: scale(0.98); }
            50% { opacity: 1; transform: scale(1); }
            100% { opacity: 0.4; transform: scale(0.98); }
        }

        /* 滚动条样式 */
        .terminal-container::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }

        .terminal-container::-webkit-scrollbar-track {
            background: #111;
        }

        .terminal-container::-webkit-scrollbar-thumb {
            background: #444;
            border-radius: 4px;
        }

        .terminal-container::-webkit-scrollbar-thumb:hover {
            background: #666;
        }

        /* 隐藏滚动条 */
        .hide-scrollbar::-webkit-scrollbar {
            display: none;
        }
    </style>
</head>
<body>
    <div class="main-container">
        <div class="header-bar">
            <div class="status-line">
                <span>
                    <span id="status-indicator" class="status-indicator status-online"></span>
                    <span id="status-text">连接中...</span>
                </span>
                <span id="timestamp">--</span>
            </div>
        </div>

        <div class="terminal-container">
            <div id="content" class="terminal-content">
                <div class="loading-overlay">
                    <div class="loading-text">正在连接服务器...</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // 彩虹渐变生成器
        function generateRainbowGradient(percent) {
            const hue = (percent / 100) * 240; // 0-240度，红到蓝渐变
            const saturation = 100;
            const lightness = 50;
            return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
        }

        // 创建彩虹进度条
        function createRainbowBar(percent, width = 100) {
            const filled = Math.round((percent / 100) * width);
            const empty = width - filled;

            // 使用不同的Unicode方块字符创建渐变效果
            const blocks = ['█', '▉', '▊', '▋', '▌', '▍', '▎', '▏'];
            let bar = '';

            for (let i = 0; i < filled; i++) {
                const intensity = i / filled;
                const blockIndex = Math.floor(intensity * blocks.length);
                const color = generateRainbowGradient((i / filled) * 100);
                bar += `<span style="color: ${color}; text-shadow: 0 0 2px ${color};">${blocks[Math.min(blockIndex, blocks.length - 1)]}</span>`;
            }

            // 空白部分
            bar += '<span style="color: #333;">' + '░'.repeat(empty) + '</span>';
            return bar;
        }

        // 创建ASCII艺术边框
        function createAsciiBorder(text, width = null) {
            if (width === null) {
                width = Math.max(80, text.length + 4);
            }

            const horizontal = '═'.repeat(width - 2);
            const paddedText = ' ' + text + ' '.repeat(width - text.length - 3) + '│';

            return `<span class="ascii-border">
╒${horizontal}╕
│${paddedText}
╘${horizontal}╛
</span>`;
        }

        // 高亮nvitop文本
        function highlightNvitopText(text) {
            // 边框线
            text = text.replace(/([╒╕╞╡╘╛┌┐└┘│─═├┤┬┴┼])/g, '<span class="ascii-border">$1</span>');

            // GPU编号和名称
            text = text.replace(/(\d+)\s+(H20\s+)/g, '<span class="nvitop-cyan">$1</span> <span class="nvitop-green nvitop-bold">$2</span>');

            // 百分比（高利用率用红色，中用黄色，低用绿色）
            text = text.replace(/(\d+)%/g, (match, p1) => {
                const percent = parseInt(p1);
                if (percent >= 80) return `<span class="gpu-util-high">${p1}%</span>`;
                if (percent >= 50) return `<span class="gpu-util-medium">${p1}%</span>`;
                return `<span class="gpu-util-low">${p1}%</span>`;
            });

            // 温度
            text = text.replace(/(\d+)C/g, (match, p1) => {
                const temp = parseInt(p1);
                if (temp >= 70) return `<span class="gpu-temp-high">${p1}C</span>`;
                if (temp >= 60) return `<span class="gpu-temp-medium">${p1}C</span>`;
                return `<span class="gpu-temp-low">${p1}C</span>`;
            });

            // 功率
            text = text.replace(/(\d+)W/g, '<span class="nvitop-magenta">$1W</span>');

            // 内存大小
            text = text.replace(/(\d+\.?\d*GiB)/g, '<span class="nvitop-blue">$1</span>');

            // 状态指示
            text = text.replace(/(MAX|Default|Off)/g, '<span class="nvitop-white">$1</span>');

            // 进程状态
            text = text.replace(/(No Such Process)/g, '<span class="nvitop-gray">$1</span>');

            // 时间
            text = text.replace(/(\d+:\d+:\d+)/g, '<span class="nvitop-cyan">$1</span>';

            // CPU和内存使用率
            text = text.replace(/(\d+\.?\d*%)\s*(?=CPU|MEM)/g, '<span class="nvitop-yellow nvitop-bold">$1</span>');

            // 负载平均值
            text = text.replace(/(\d+\.\d+)/g, (match, p1) => {
                const load = parseFloat(p1);
                if (load >= 32) return `<span class="nvitop-red nvitop-bold">${p1}</span>`;
                if (load >= 16) return `<span class="nvitop-yellow nvitop-bold">${p1}</span>`;
                return `<span class="nvitop-green">${p1}</span>`;
            });

            return text;
        }

        // 渲染GPU数据
        function renderGPUData(data) {
            // 如果是HTML输出模式，直接显示彩色HTML
            if (data.mode === 'html' && data.html_output) {
                return `
                    <div style="font-family: 'JetBrains Mono', monospace; font-size: 13px; line-height: 1.3;">
                        ${data.html_output}
                    </div>
                `;
            }

            // 如果是原始输出模式，显示带样式的文本
            if (data.mode === 'raw' && data.raw_output) {
                let output = data.raw_output;

                // 转义HTML特殊字符
                output = output.replace(/&/g, '&amp;');
                output = output.replace(/</g, '&lt;');
                output = output.replace(/>/g, '&gt;');

                // 添加语法高亮和彩虹效果
                output = highlightNvitopText(output);

                // 替换进度条为彩虹效果
                output = output.replace(/(MEM:|UTL:|MBW:)\s+([█▌]+)\s+(\d+(?:\.\d+)?%)/g,
                    (match, prefix, bars, percent) => {
                        const percentNum = parseFloat(percent);
                        const rainbowBar = createRainbowBar(percentNum, 50);
                        return `${prefix} ${rainbowBar} <span class="nvitop-yellow">${percent}</span>`;
                    }
                );

                return `
                    <div class="terminal-content" style="font-size: 13px;">
                        ${output}
                    </div>
                `;
            }

            // 如果是解析模式，使用解析渲染逻辑（保持原有逻辑）
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

            // 使用彩虹进度条显示GPU状态
            data.gpus.forEach((gpu, index) => {
                const memBar = createRainbowBar(gpu.memory_percent, 60);
                const utilBar = createRainbowBar(gpu.gpu_percent, 60);

                html += `
                    <div style="margin: 5px 0; padding: 5px; border-left: 2px solid ${generateRainbowGradient((index / data.gpus.length) * 100)};">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span class="nvitop-cyan">GPU ${gpu.id}</span>: <span class="nvitop-green nvitop-bold">${gpu.name}</span>
                            <span class="nvitop-white">${gpu.temperature}°C</span>
                        </div>
                        <div class="progress-container">
                            <span class="progress-text nvitop-blue">MEM:</span>
                            <div class="progress-bar-container">
                                <div class="progress-bar-fill" style="width: ${gpu.memory_percent}%; background: ${generateRainbowGradient(gpu.memory_percent)};"></div>
                            </div>
                            <span class="nvitop-yellow">${gpu.memory_percent.toFixed(1)}%</span>
                        </div>
                        <div class="progress-container">
                            <span class="progress-text nvitop-magenta">GPU:</span>
                            <div class="progress-bar-container">
                                <div class="progress-bar-fill" style="width: ${gpu.gpu_percent}%; background: ${generateRainbowGradient(gpu.gpu_percent)};"></div>
                            </div>
                            <span class="nvitop-yellow">${gpu.gpu_percent.toFixed(1)}%</span>
                        </div>
                    </div>
                `;
            });

            return html;
        }

        // 获取数据
        async function fetchData() {
            try {
                const response = await fetch('/data');
                const data = await response.json();

                // 更新状态
                document.getElementById('timestamp').textContent = data.timestamp || '--';

                if (data.mode && (data.raw_output || data.html_output || data.gpus?.length > 0)) {
                    document.getElementById('status-indicator').className = 'status-indicator status-online';
                    document.getElementById('status-text').textContent = '已连接';

                    // 隐藏加载界面
                    const loadingOverlay = document.querySelector('.loading-overlay');
                    if (loadingOverlay) {
                        loadingOverlay.style.display = 'none';
                    }

                    // 渲染内容
                    document.getElementById('content').innerHTML = renderGPUData(data);
                } else {
                    document.getElementById('status-indicator').className = 'status-indicator status-offline';
                    document.getElementById('status-text').textContent = '等待数据...';
                }
            } catch (error) {
                console.error('Error fetching data:', error);
                document.getElementById('status-indicator').className = 'status-indicator status-offline';
                document.getElementById('status-text').textContent = '连接失败';
            }
        }

        // 每秒更新一次
        setInterval(fetchData, 1000);
        // 初始加载
        fetchData();

        // 响应式字体大小调整
        function adjustFontSize() {
            const width = window.innerWidth;
            const terminal = document.querySelector('.terminal-content');
            if (terminal) {
                if (width >= 1400) {
                    terminal.style.fontSize = '13px';
                } else if (width >= 1200) {
                    terminal.style.fontSize = '12px';
                } else if (width >= 1000) {
                    terminal.style.fontSize = '11px';
                } else {
                    terminal.style.fontSize = '10px';
                }
            }
        }

        window.addEventListener('resize', adjustFontSize);
        adjustFontSize();
    </script>
</body>
</html>
    """
    return html_content

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)