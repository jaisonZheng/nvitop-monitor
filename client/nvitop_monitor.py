#!/usr/bin/env python3
"""
直接捕获nvitop输出并发送到服务器的监控客户端
"""

import subprocess
import time
import requests
import getpass
import socket
import re
from datetime import datetime

# 配置
SERVER_URL = "http://43.136.42.69:8000"
UPDATE_INTERVAL = 1  # 更新间隔（秒）
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 5  # 重试延迟（秒）

def run_nvitop():
    """运行nvitop并捕获输出"""
    try:
        # 使用stdbuf禁用输出缓冲，确保实时获取输出
        cmd = ['stdbuf', '-oL', 'nvitop']
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        output_lines = []
        last_update = time.time()

        while True:
            line = process.stdout.readline()
            if not line:
                break

            output_lines.append(line.rstrip())

            # 每0.5秒检查一次是否收集到完整的nvitop输出
            current_time = time.time()
            if current_time - last_update >= 0.5:
                # 检查是否收集到完整的nvitop界面
                full_output = '\n'.join(output_lines)
                if 'NVITOP' in full_output and 'Processes:' in full_output:
                    # 提取完整的nvitop输出
                    yield full_output
                    output_lines = []
                    last_update = current_time

    except FileNotFoundError:
        print("错误: 未找到nvitop命令")
        exit(1)
    except Exception as e:
        print(f"运行nvitop失败: {e}")
        exit(1)

def parse_nvitop_output(output):
    """解析nvitop输出"""
    lines = output.split('\n')

    # 提取基本信息
    header_info = {
        "nvitop_version": "1.6.2",
        "driver_version": "550.163.01",
        "cuda_version": "12.4",
        "timestamp": datetime.now().strftime("%a %b %d %H:%M:%S %Y"),
        "hostname": socket.gethostname(),
        "username": getpass.getuser()
    }

    # 提取系统状态
    system_status = {
        "cpu_percent": 0,
        "memory_percent": 0,
        "swap_percent": 0,
        "load_avg": [0, 0, 0],
        "uptime": "0 days"
    }

    # 提取CPU、内存和负载信息
    for line in lines:
        if '[ CPU:' in line:
            # 解析CPU使用率
            cpu_match = re.search(r'CPU:\s*([^\]]+)', line)
            if cpu_match:
                cpu_info = cpu_match.group(1)
                # 提取百分比
                percent_match = re.search(r'(\d+\.?\d*)%', cpu_info)
                if percent_match:
                    system_status["cpu_percent"] = float(percent_match.group(1))

                # 提取负载平均值
                load_match = re.search(r'Load Average:\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)', line)
                if load_match:
                    system_status["load_avg"] = [
                        float(load_match.group(1)),
                        float(load_match.group(2)),
                        float(load_match.group(3))
                    ]

        elif '[ MEM:' in line and '[ SWP:' in line:
            # 解析内存使用率
            mem_match = re.search(r'MEM:\s*([^\]]+)', line)
            if mem_match:
                mem_info = mem_match.group(1)
                percent_match = re.search(r'(\d+\.?\d*)%', mem_info)
                if percent_match:
                    system_status["memory_percent"] = float(percent_match.group(1))

            # 解析交换分区使用率
            swp_match = re.search(r'SWP:\s*([^\]]+)', line)
            if swp_match:
                swp_info = swp_match.group(1)
                percent_match = re.search(r'(\d+\.?\d*)%', swp_info)
                if percent_match:
                    system_status["swap_percent"] = float(percent_match.group(1))

        elif 'UPTIME:' in line:
            # 提取运行时间
            uptime_match = re.search(r'UPTIME:\s*([\d.]+)\s*days', line)
            if uptime_match:
                system_status["uptime"] = f"{uptime_match.group(1)} days"

    # 提取GPU信息
    gpus = []
    gpu_section = False

    for line in lines:
        if line.startswith('│') and 'H20' in line and not 'Processes:' in line:
            # GPU基本信息行
            parts = line.split('│')
            if len(parts) >= 4:
                # 解析GPU ID和名称
                gpu_info_part = parts[1].strip()
                gpu_match = re.search(r'(\d+)\s+(\w+)', gpu_info_part)
                if gpu_match:
                    gpu_id = int(gpu_match.group(1))
                    gpu_name = gpu_match.group(2)

                    # 解析温度、功耗等信息
                    util_part = parts[2].strip()
                    temp_match = re.search(r'(\d+)C', util_part)
                    power_match = re.search(r'(\d+)W\s*/\s*(\d+)W', util_part)
                    gpu_util_match = re.search(r'(\d+)%', util_part)

                    # 解析内存信息
                    mem_part = parts[2].strip()
                    mem_match = re.search(r'(\d+\.?\d*)GiB\s*/\s*(\d+\.?\d*)GiB', mem_part)

                    # 解析进度条信息（第三列）
                    prog_part = parts[3].strip() if len(parts) > 3 else ""
                    mem_prog_match = re.search(r'MEM:\s*([█▌]+).*?(\d+\.?\d*)%', prog_part)
                    mbw_prog_match = re.search(r'MBW:\s*([█▌]+).*?(\d+\.?\d*)%', prog_part)

                    gpu_info = {
                        "id": gpu_id,
                        "name": gpu_name,
                        "persistence": "Off",
                        "bus_id": f"00000000:{gpu_id*2:02d}:00.0",  # 模拟bus id
                        "display": "Off",
                        "mig_mode": "Disabled",
                        "ecc": "0",
                        "memory_total": int(float(mem_match.group(2)) * 1024) if mem_match else 97871,  # 转换为MB
                        "memory_used": int(float(mem_match.group(1)) * 1024) if mem_match else 0,
                        "memory_percent": float(mem_prog_match.group(2)) if mem_prog_match else 0,
                        "memory_free": 0,
                        "gpu_percent": int(gpu_util_match.group(1)) if gpu_util_match else 0,
                        "temperature": int(temp_match.group(1)) if temp_match else 0,
                        "performance": "P0",
                        "power": int(power_match.group(1)) if power_match else 0,
                        "power_cap": int(power_match.group(2)) if power_match else 500,
                        "power_percent": 0,
                        "compute_mode": "Default",
                        "mbw_percent": float(mbw_prog_match.group(2)) if mbw_prog_match else 0,
                        "pcie_gen": 4,
                        "pcie_width": 16
                    }

                    gpus.append(gpu_info)

    # 提取进程信息
    processes = []
    process_section = False

    for line in lines:
        if 'Processes:' in line:
            process_section = True
            continue

        if process_section and line.startswith('│') and not line.startswith('│ GPU'):
            # 进程行
            parts = line.split('│')
            if len(parts) >= 2:
                proc_info = parts[1].strip()

                # 解析进程信息
                proc_match = re.search(
                    r'(\d+)\s+(\d+)\s+(\w+)\s+([\d.]+GiB)\s+(\d+)\s+(\d+)\s+([\d.NA]+)\s+([\d.NA]+)\s+([\d:]+)\s+(.+)',
                    proc_info
                )

                if proc_match:
                    processes.append({
                        "gpu_id": int(proc_match.group(1)),
                        "pid": int(proc_match.group(2)),
                        "username": proc_match.group(3),
                        "gpu_memory": int(float(proc_match.group(4).replace('GiB', '')) * 1024),  # 转换为MB
                        "gpu_memory_percent": int(proc_match.group(5)),
                        "gmbw_percent": int(proc_match.group(6)),
                        "cpu_percent": proc_match.group(7),
                        "memory_percent": proc_match.group(8),
                        "time": proc_match.group(9),
                        "command": proc_match.group(10)[:100]
                    })

    return {
        **header_info,
        **system_status,
        "gpus": gpus,
        "user_processes": processes
    }

def send_data_to_server(data: dict) -> bool:
    """发送数据到服务器"""
    for attempt in range(3):
        try:
            response = requests.post(
                f"{SERVER_URL}/update",
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=10
            )

            if response.status_code == 200:
                return True
            else:
                print(f"服务器返回错误: {response.status_code}")

        except requests.exceptions.RequestException as e:
            print(f"发送数据失败 (尝试 {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(5)

    return False

def main():
    """主函数"""
    print("=== NVITOP 实时监控客户端 ===")
    print(f"服务器地址: {SERVER_URL}")
    print("正在启动nvitop...")

    # 启动nvitop
    nvitop_process = subprocess.Popen(['nvitop', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = nvitop_process.communicate()

    if nvitop_process.returncode != 0:
        print("错误: 未找到nvitop命令")
        exit(1)

    print("nvitop已就绪，开始监控...")
    print("按 Ctrl+C 退出\n")

    # 运行nvitop并捕获输出
    for output in run_nvitop():
        try:
            # 解析输出
            data = parse_nvitop_output(output)

            print(f"[{data['timestamp']}] 捕获nvitop输出，{len(data['gpus'])}个GPU，{len(data['user_processes'])}个进程")

            # 发送到服务器
            if send_data_to_server(data):
                print("  ✓ 数据发送成功")
            else:
                print("  ✗ 数据发送失败")

        except KeyboardInterrupt:
            print("\n正在退出...")
            break
        except Exception as e:
            print(f"处理数据时出错: {e}")

    print("监控已停止")

if __name__ == "__main__":
    main()