from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, Tuple
import uvicorn
from datetime import datetime
import json
import math
import re

app = FastAPI()

# NVITOP颜色映射 - 完全复刻
NVITOP_COLORS = {
    'black': '#000000',
    'red': '#cd0000',
    'green': '#00cd00',
    'yellow': '#cdcd00',
    'blue': '#0000ee',
    'magenta': '#cd00cd',
    'cyan': '#00cdcd',
    'white': '#e5e5e5',
    'bright_black': '#7f7f7f',
    'bright_red': '#ff0000',
    'bright_green': '#55ff55',
    'bright_yellow': '#ffff55',
    'bright_blue': '#5555ff',
    'bright_magenta': '#ff55ff',
    'bright_cyan': '#55ffff',
    'bright_white': '#ffffff'
}

# 阈值定义 - 完全复刻nvitop
MEMORY_UTILIZATION_THRESHOLDS = (10, 80)
GPU_UTILIZATION_THRESHOLDS = (10, 75)

class LoadingIntensity:
    LIGHT = 0
    MODERATE = 1
    HEAVY = 2

    @staticmethod
    def color(intensity: int) -> str:
        if intensity == LoadingIntensity.LIGHT:
            return 'green'
        if intensity == LoadingIntensity.MODERATE:
            return 'yellow'
        return 'red'

# 存储GPU数据
gpu_data = {
    "timestamp": "",
    "raw_output": "",
    "hostname": "",
    "username": "",
    "parsed_data": {}
}

class RawOutputData(BaseModel):
    timestamp: str
    raw_output: str
    hostname: str
    username: str

def loading_intensity_of(utilization: float | str, type: str = 'memory') -> int:
    """计算负载强度 - 复刻nvitop逻辑"""
    thresholds = {
        'memory': MEMORY_UTILIZATION_THRESHOLDS,
        'gpu': GPU_UTILIZATION_THRESHOLDS,
    }[type]

    if isinstance(utilization, str):
        utilization = utilization.replace('%', '')
    utilization = float(utilization)

    if utilization >= thresholds[-1]:
        return LoadingIntensity.HEAVY
    if utilization >= thresholds[0]:
        return LoadingIntensity.MODERATE
    return LoadingIntensity.LIGHT

def color_of(utilization: float | str, type: str = 'memory') -> str:
    """根据使用率返回颜色 - 复刻nvitop逻辑"""
    return LoadingIntensity.color(loading_intensity_of(utilization, type))

def make_bar_chart(prefix: str, percent: float | str, width: int, extra_text: str = '', swap_text: bool = False) -> str:
    """创建进度条 - 完全复刻nvitop实现"""
    bar_chart = f'{prefix}: '

    if isinstance(percent, str) and percent.endswith('%'):
        percent = percent.replace('%', '')
        percent = float(percent) if '.' in percent else int(percent)

    percentage = max(0.0, min(float(percent) / 100.0, 1.0))
    quotient, remainder = divmod(
        max(1, round(8 * (width - len(bar_chart) - 4) * percentage)),
        8,
    )
    bar_chart += '█' * quotient
    if remainder > 0:
        bar_chart += ' ▏▎▍▌▋▊▉'[remainder]

    if isinstance(percent, float) and len(f'{bar_chart} {percent:.1f}%') <= width:
        text = f'{percent:.1f}%'
    else:
        text = f'{min(round(percent), 100):d}%'.replace('100%', 'MAX')

    bar_chart += '░' * (width - len(bar_chart) - len(text) - 1)
    return f'{bar_chart} {text}'.ljust(width)

def parse_nvitop_output(output: str) -> dict:
    """解析nvitop输出并提取结构化数据"""
    lines = output.split('\n')
    data = {
        'timestamp': '',
        'devices': [],
        'processes': [],
        'system_info': {}
    }

    # 提取时间戳
    if lines:
        data['timestamp'] = lines[0].strip()

    # 解析设备和进程信息
    device_section = False
    process_section = False

    for line in lines:
        # 设备信息行
        if line.startswith('│') and 'H20' in line and not process_section:
            parts = line.split('│')
            if len(parts) >= 3:
                # GPU基本信息
                gpu_info = parts[1].strip()
                util_info = parts[2].strip()

                # 解析GPU编号和名称
                gpu_match = re.search(r'(\d+)\s+(\w+)', gpu_info)
                if gpu_match:
                    gpu_id = int(gpu_match.group(1))
                    gpu_name = gpu_match.group(2)

                    # 解析利用率信息
                    temp_match = re.search(r'(\d+)C', util_info)
                    power_match = re.search(r'(\d+)W\s*/\s*(\d+)W', util_info)
                    mem_match = re.search(r'(\d+\.?\d*)GiB\s*/\s*(\d+\.?\d*)GiB', util_info)
                    gpu_util_match = re.search(r'(\d+)%', util_info)

                    device = {
                        'id': gpu_id,
                        'name': gpu_name,
                        'temperature': int(temp_match.group(1)) if temp_match else 0,
                        'power_draw': int(power_match.group(1)) if power_match else 0,
                        'power_limit': int(power_match.group(2)) if power_match else 500,
                        'memory_used': float(mem_match.group(1)) if mem_match else 0,
                        'memory_total': float(mem_match.group(2)) if mem_match else 95.58,
                        'gpu_utilization': int(gpu_util_match.group(1)) if gpu_util_match else 0,
                        'memory_percent': 0,
                        'power_percent': 0
                    }

                    # 计算百分比
                    if device['memory_total'] > 0:
                        device['memory_percent'] = (device['memory_used'] / device['memory_total']) * 100
                    if device['power_limit'] > 0:
                        device['power_percent'] = (device['power_draw'] / device['power_limit']) * 100

                    data['devices'].append(device)
                    device_section = True

        # 进程信息行
        elif line.startswith('│') and device_section and re.search(r'\d+\s+\d+\s+\w+', line):
            parts = line.split('│')
            if len(parts) >= 2:
                proc_info = parts[1].strip()
                proc_match = re.search(
                    r'(\d+)\s+(\d+)\s+(\w+)\s+([\d.]+GiB)\s+(\d+)%',
                    proc_info
                )
                if proc_match:
                    data['processes'].append({
                        'gpu_id': int(proc_match.group(1)),
                        'pid': int(proc_match.group(2)),
                        'username': proc_match.group(3),
                        'gpu_memory': proc_match.group(4),
                        'gpu_memory_percent': int(proc_match.group(5))
                    })

        # 系统信息
        elif '[ CPU:' in line:
            cpu_match = re.search(r'CPU:\s+([^\]]+)', line)
            if cpu_match:
                data['system_info']['cpu'] = cpu_match.group(1)

            load_match = re.search(r'Load Average:\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)', line)
            if load_match:
                data['system_info']['load_avg'] = [
                    float(load_match.group(1)),
                    float(load_match.group(2)),
                    float(load_match.group(3))
                ]

        elif '[ MEM:' in line:
            mem_match = re.search(r'MEM:\s+([^\]]+)', line)
            if mem_match:
                data['system_info']['memory'] = mem_match.group(1)

    return data

def render_nvitop_colored(data: dict) -> str:
    """渲染带颜色的nvitop输出"""
    html_parts = []

    # 标题和时间
    if data['timestamp']:
        html_parts.append(f"<div style='color: {NVITOP_COLORS['white']}; margin-bottom: 10px;'>{data['timestamp']}</div>")

    # ASCII边框
    border_color = NVITOP_COLORS['white']
    html_parts.append(f"<div style='color: {border_color}; font-family: monospace;'>")
    html_parts.append("╒═════════════════════════════════════════════════════════════════════════════╕")
    html_parts.append("│ NVITOP 1.6.2      Driver Version: 550.163.01      CUDA Driver Version: 12.4 │")
    html_parts.append("├───────────────────────────────┬──────────────────────┬──────────────────────┤")
    html_parts.append("│ GPU  Name        Persistence-M│ Bus-Id        Disp.A │ MIG M.   Uncorr. ECC │")
    html_parts.append("│ Fan  Temp  Perf  Pwr:Usage/Cap│         Memory-Usage │ GPU-Util  Compute M. │")
    html_parts.append("╞═══════════════════════════════╪══════════════════════╪══════════════════════╡")

    # 设备信息
    for device in data['devices']:
        # 确定颜色
        mem_color = NVITOP_COLORS[color_of(device['memory_percent'], 'memory')]
        gpu_color = NVITOP_COLORS[color_of(device['gpu_utilization'], 'gpu')]
        temp_color = NVITOP_COLORS['white']

        # 高温警告
        if device['temperature'] >= 70:
            temp_color = NVITOP_COLORS['red']
        elif device['temperature'] >= 60:
            temp_color = NVITOP_COLORS['yellow']

        # 创建进度条
        mem_bar = make_bar_chart('MEM', device['memory_percent'], 25)
        gpu_bar = make_bar_chart('UTL', device['gpu_utilization'], 25)

        # GPU行
        html_parts.append(f"<div>│ <span style='color: {NVITOP_COLORS['cyan']}'>{device['id']:2d}</span>  <span style='color: {NVITOP_COLORS['green']}'>{device['name']}</span>                  <span style='color: {border_color}'>Off</span> │ <span style='color: {border_color}'>00000000:{device['id']*2:02d}:00.0</span> <span style='color: {border_color}'>Off</span> │ <span style='color: {border_color}'>Disabled</span>           <span style='color: {border_color}'>0</span> │</div>")
        html_parts.append(f"<div>│ <span style='color: {border_color}'>N/A</span>   <span style='color: {temp_color}'>{device['temperature']:2d}C</span>   <span style='color: {border_color}'>P0</span>    <span style='color: {NVITOP_COLORS['magenta']}'>{device['power_draw']:3d}W</span> / <span style='color: {NVITOP_COLORS['magenta']}'>{device['power_limit']:3d}W</span> │  <span style='color: {NVITOP_COLORS['blue']}'>{device['memory_used']:6.2f}GiB</span> / <span style='color: {NVITOP_COLORS['blue']}'>{device['memory_total']:6.2f}GiB</span> │     <span style='color: {gpu_color}'>{device['gpu_utilization']:3d}%</span>      <span style='color: {border_color}'>Default</span> │</div>")
        html_parts.append(f"<div>│ <span style='color: {mem_color}'>{mem_bar}</span> │ <span style='color: {gpu_color}'>{gpu_bar}</span> │</div>")

        if device != data['devices'][-1]:
            html_parts.append("├───────────────────────────────┼──────────────────────┼──────────────────────┤")

    # 底部边框
    html_parts.append("╘═══════════════════════════════╧══════════════════════╧══════════════════════╛")

    # 系统信息
    if data['system_info']:
        if 'cpu' in data['system_info']:
            html_parts.append(f"<div style='color: {NVITOP_COLORS["yellow"]};'>[ CPU: {data['system_info']['cpu']} ]</div>")
        if 'load_avg' in data['system_info']:
            load1, load5, load15 = data['system_info']['load_avg']
            load_color = NVITOP_COLORS['green']
            if load1 >= 32:
                load_color = NVITOP_COLORS['red']
            elif load1 >= 16:
                load_color = NVITOP_COLORS['yellow']
            html_parts.append(f"<div style='color: {load_color};'>( Load Average: {load1:5.2f} {load5:5.2f} {load15:5.2f} )</div>")
        if 'memory' in data['system_info']:
            html_parts.append(f"<div style='color: {NVITOP_COLORS["yellow"]};'>[ MEM: {data['system_info']['memory']} ]</div>")

    # 进程信息
    if data['processes']:
        html_parts.append("")
        html_parts.append(f"<div style='color: {NVITOP_COLORS["white"]};'>╒═════════════════════════════════════════════════════════════════════════════╕</div>")
        html_parts.append(f"<div style='color: {NVITOP_COLORS["white"]};'>│ Processes:                                           {data['username']}@{data['hostname']} │</div>")
        html_parts.append(f"<div style='color: {NVITOP_COLORS["white"]};'>│ GPU     PID      USER  GPU-MEM %SM %GMBW  %CPU  %MEM      TIME  COMMAND     │</div>")
        html_parts.append(f"<div style='color: {NVITOP_COLORS["white"]};'>╞═════════════════════════════════════════════════════════════════════════════╡</div>")

        for proc in data['processes']:
            # 根据GPU内存使用率确定颜色
            proc_color = NVITOP_COLORS[color_of(proc['gpu_memory_percent'], 'memory')]
            html_parts.append(f"<div>│ <span style='color: {NVITOP_COLORS["cyan"]}'>{proc['gpu_id']:3d}</span> <span style='color: {NVITOP_COLORS["yellow"]}'>{proc['pid']}</span> <span style='color: {NVITOP_COLORS["green"]}'>{proc['username'][:8]:8}</span> <span style='color: {proc_color}'>{proc['gpu_memory']:8}</span> <span style='color: {proc_color}'>{proc['gpu_memory_percent']:3d}%</span>   <span style='color: {NVITOP_COLORS["gray"]}'>N/A</span>   <span style='color: {NVITOP_COLORS["gray"]}'>N/A</span>       <span style='color: {NVITOP_COLORS["gray"]}'>N/A</span>  <span style='color: {NVITOP_COLORS["gray"]}'>{proc['command'][:20]}..</span> │</div>")

        html_parts.append(f"<div style='color: {NVITOP_COLORS["white"]};'>╘═════════════════════════════════════════════════════════════════════════════╛</div>")

    html_parts.append("</div>")

    return '\n'.join(html_parts)

@app.post("/update_raw")
async def update_raw_data(data: RawOutputData):
    """接收来自HPC客户端的原始nvitop输出"""
    global gpu_data

    # 解析输出
    parsed_data = parse_nvitop_output(data.raw_output)

    gpu_data = {
        "timestamp": data.timestamp,
        "raw_output": data.raw_output,
        "hostname": data.hostname,
        "username": data.username,
        "parsed_data": parsed_data
    }
    return {"status": "success"}

@app.get("/data")
async def get_data():
    """获取最新的GPU数据"""
    return gpu_data

@app.get("/", response_class=HTMLResponse)
async def index():
    """返回完全复刻nvitop的监控页面"""
    html_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NVITOP GPU Monitor - Clone</title>
    <style>
        /* 完全复刻nvitop终端样式 */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'JetBrains Mono', 'Consolas', 'Monaco', 'Courier New', monospace;
            background: #000;
            color: #e0e0e0;
            overflow: hidden;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }

        /* 终端窗口 */
        .terminal-window {
            flex: 1;
            background: #000;
            border: 2px solid #333;
            border-radius: 8px;
            margin: 10px;
            padding: 15px;
            box-shadow:
                inset 0 0 20px rgba(0, 255, 0, 0.1),
                0 0 20px rgba(0, 0, 0, 0.8);
            overflow: auto;
            position: relative;
        }

        /* 终端内容 */
        .terminal-content {
            font-size: 13px;
            line-height: 1.3;
            white-space: pre;
            font-family: inherit;
        }

        /* 响应式字体大小 */
        @media (max-width: 1400px) {
            .terminal-content { font-size: 12px; }
        }

        @media (max-width: 1200px) {
            .terminal-content { font-size: 11px; }
        }

        @media (max-width: 1000px) {
            .terminal-content { font-size: 10px; }
        }

        /* 状态栏 */
        .status-bar {
            background: linear-gradient(90deg, #1a1a2e 0%, #16213e 50%, #1a1a2e 100%);
            padding: 8px 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
        }

        .status-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 1.5s infinite;
        }

        .status-online { background-color: #00ff00; }
        .status-offline { background-color: #ff0000; }
        .status-waiting { background-color: #ffaa00; }

        @keyframes pulse {
            0% { opacity: 0.4; transform: scale(0.98); }
            50% { opacity: 1; transform: scale(1); }
            100% { opacity: 0.4; transform: scale(0.98); }
        }

        /* 加载动画 */
        .loading-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.9);
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

        /* 滚动条样式 */
        .terminal-window::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }

        .terminal-window::-webkit-scrollbar-track {
            background: #111;
        }

        .terminal-window::-webkit-scrollbar-thumb {
            background: #444;
            border-radius: 4px;
        }

        .terminal-window::-webkit-scrollbar-thumb:hover {
            background: #666;
        }
    </style>
</head>
<body>
    <div class="status-bar">
        <span>
            <span id="status-indicator" class="status-indicator status-waiting"></span>
            <span id="status-text">连接中...</span>
        </span>
        <span id="timestamp">--</span>
    </div>

    <div class="terminal-window">
        <div id="loading" class="loading-overlay">
            <div class="loading-text">正在连接服务器...</div>
        </div>
        <pre id="content" class="terminal-content">等待GPU数据...</pre>
    </div>

    <script>
        // 完全复刻nvitop的颜色处理
        const NVITOP_COLORS = {
            'black': '#000000',
            'red': '#cd0000',
            'green': '#00cd00',
            'yellow': '#cdcd00',
            'blue': '#0000ee',
            'magenta': '#cd00cd',
            'cyan': '#00cdcd',
            'white': '#e5e5e5',
            'bright_black': '#7f7f7f',
            'bright_red': '#ff0000',
            'bright_green': '#55ff55',
            'bright_yellow': '#ffff55',
            'bright_blue': '#5555ff',
            'bright_magenta': '#ff55ff',
            'bright_cyan': '#55ffff',
            'bright_white': '#ffffff'
        };

        // 阈值定义
        const MEMORY_UTILIZATION_THRESHOLDS = [10, 80];
        const GPU_UTILIZATION_THRESHOLDS = [10, 75];

        function loadingIntensityOf(utilization, type = 'memory') {
            const thresholds = type === 'memory' ? MEMORY_UTILIZATION_THRESHOLDS : GPU_UTILIZATION_THRESHOLDS;

            if (typeof utilization === 'string') {
                utilization = utilization.replace('%', '');
            }
            utilization = parseFloat(utilization);

            if (utilization >= thresholds[1]) return 2; // HEAVY
            if (utilization >= thresholds[0]) return 1; // MODERATE
            return 0; // LIGHT
        }

        function colorOf(utilization, type = 'memory') {
            const intensity = loadingIntensityOf(utilization, type);
            if (intensity === 0) return 'green';
            if (intensity === 1) return 'yellow';
            return 'red';
        }

        function applyNvitopColors(text) {
            // 应用nvitop的颜色规则

            // 边框线
            text = text.replace(/([╒╕╞╡╘╛┌┐└┘│─═├┤┬┴┼])/g, <span style="color: ${NVITOP_COLORS['white']}">$1</span>);

            // GPU编号和名称
            text = text.replace(/(\d+)\s+(H20\s+)/g, <span style="color: ${NVITOP_COLORS['cyan']}">$1</span> <span style="color: ${NVITOP_COLORS['green']}">$2</span>);

            // 百分比（根据使用率着色）
            text = text.replace(/(\d+)%/g, (match, p1) => {
                const color = NVITOP_COLORS[colorOf(p1)];
                return `<span style="color: ${color}">${p1}%</span>`;
            });

            // 温度
            text = text.replace(/(\d+)C/g, (match, p1) => {
                const temp = parseInt(p1);
                let color = NVITOP_COLORS['white'];
                if (temp >= 70) color = NVITOP_COLORS['red'];
                else if (temp >= 60) color = NVITOP_COLORS['yellow'];
                return `<span style="color: ${color}">${p1}C</span>`;
            });

            // 功率
            text = text.replace(/(\d+)W/g, <span style="color: ${NVITOP_COLORS['magenta']}">$1W</span>);

            // 内存大小
            text = text.replace(/(\d+\.?\d*GiB)/g, <span style="color: ${NVITOP_COLORS['blue']}">$1</span>);

            // 状态指示
            text = text.replace(/(MAX|Default|Off)/g, <span style="color: ${NVITOP_COLORS['white']}">$1</span>);

            // 进程状态
            text = text.replace(/(No Such Process)/g, <span style="color: ${NVITOP_COLORS['bright_black']}">$1</span>);

            // 时间
            text = text.replace(/(\d+:\d+:\d+)/g, <span style="color: ${NVITOP_COLORS['cyan']}">$1</span>);

            // CPU和内存使用率
            text = text.replace(/(\d+\.?\d*%)\s*(?=CPU|MEM)/g, <span style="color: ${NVITOP_COLORS['yellow']}">$1</span>);

            // 负载平均值
            text = text.replace(/(\d+\.\d+)/g, (match, p1) => {
                const load = parseFloat(p1);
                let color = NVITOP_COLORS['green'];
                if (load >= 32) color = NVITOP_COLORS['red'];
                else if (load >= 16) color = NVITOP_COLORS['yellow'];
                return `<span style="color: ${color}">${p1}</span>`;
            });

            return text;
        }

        async function fetchData() {
            try {
                const response = await fetch('/data');
                const data = await response.json();

                // 更新状态
                document.getElementById('timestamp').textContent = data.timestamp || '--';

                if (data.raw_output && data.raw_output.trim()) {
                    // 应用nvitop颜色
                    const coloredOutput = applyNvitopColors(data.raw_output);
                    document.getElementById('content').innerHTML = coloredOutput;

                    // 更新状态指示器
                    document.getElementById('status-indicator').className = 'status-indicator status-online';
                    document.getElementById('status-text').textContent = '已连接';

                    // 隐藏加载界面
                    document.getElementById('loading').style.display = 'none';
                } else {
                    document.getElementById('status-indicator').className = 'status-indicator status-waiting';
                    document.getElementById('status-text').textContent = '等待数据';
                }

            } catch (error) {
                console.error('Error:', error);
                document.getElementById('content').innerHTML = `<div style="color: ${NVITOP_COLORS['red']};">连接失败: ${error.message}</div>`;
                document.getElementById('status-indicator').className = 'status-indicator status-offline';
                document.getElementById('status-text').textContent = '连接失败';
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