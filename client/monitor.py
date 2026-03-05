#!/usr/bin/env python3
"""
HPC GPU监控客户端
从nvitop获取GPU信息并发送到云端服务器
"""

import time
import requests
import json
import getpass
import socket
import psutil
from datetime import datetime
from typing import List, Dict, Any

try:
    import nvitop
except ImportError:
    print("错误: 未安装nvitop包")
    print("请运行: pip install nvitop")
    exit(1)

# 配置
SERVER_URL = "http://43.136.42.69:8000"  # 云服务器地址
UPDATE_INTERVAL = 1  # 更新间隔（秒）
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 5  # 重试延迟（秒）

def get_system_info() -> Dict[str, Any]:
    """获取系统信息"""
    try:
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=0.1)

        # 内存信息
        memory = psutil.virtual_memory()
        memory_percent = memory.percent

        # 交换分区信息
        swap = psutil.swap_memory()
        swap_percent = swap.percent

        # 负载平均值
        load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]

        # 系统运行时间
        uptime_seconds = time.time() - psutil.boot_time()
        uptime_days = uptime_seconds / (24 * 3600)
        uptime_str = f"{uptime_days:.1f} days"

        # 主机名
        hostname = socket.gethostname()

        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "swap_percent": swap_percent,
            "load_avg": [round(l, 2) for l in load_avg],
            "uptime": uptime_str,
            "hostname": hostname
        }
    except Exception as e:
        print(f"获取系统信息失败: {e}")
        return {
            "cpu_percent": 0,
            "memory_percent": 0,
            "swap_percent": 0,
            "load_avg": [0, 0, 0],
            "uptime": "N/A",
            "hostname": "unknown"
        }

def get_gpu_info() -> List[Dict[str, Any]]:
    """获取所有GPU的信息"""
    gpus = []

    try:
        device_count = nvitop.Device.count()

        for i in range(device_count):
            device = nvitop.Device(i)

            # 获取GPU利用率信息
            gpu_utilization = device.gpu_utilization()
            memory_utilization = device.memory_utilization()

            # 获取PCIe信息（某些系统可能不支持）
            try:
                pci_gen = device.pcie_link_gen()
                pci_width = device.pcie_link_width()
            except:
                pci_gen = 4
                pci_width = 16

            # 获取MBW（Memory Bandwidth Utilization）
            mbw_percent = memory_utilization  # 使用内存利用率作为近似值

            # 获取GPU信息
            gpu_info = {
                "id": i,
                "name": device.name(),
                "persistence": "Off",  # 默认Off
                "bus_id": device.bus_id(),
                "display": "Off",
                "mig_mode": "Disabled",
                "ecc": "0",
                "memory_total": device.memory_total() // 1024 // 1024,  # MB
                "memory_used": device.memory_used() // 1024 // 1024,    # MB
                "memory_percent": device.memory_percent(),
                "memory_free": (device.memory_total() - device.memory_used()) // 1024 // 1024,  # MB
                "gpu_percent": gpu_utilization,
                "temperature": device.temperature(),
                "performance": "P0",  # 默认P0
                "power": device.power_draw(),
                "power_cap": device.power_limit(),
                "power_percent": (device.power_draw() / device.power_limit() * 100) if device.power_limit() > 0 else 0,
                "compute_mode": "Default",
                "mbw_percent": mbw_percent,
                "pcie_gen": pci_gen,
                "pcie_width": pci_width
            }

            gpus.append(gpu_info)

    except Exception as e:
        print(f"获取GPU信息失败: {e}")

    return gpus

def get_all_processes() -> List[Dict[str, Any]]:
    """获取所有GPU进程"""
    processes = []

    try:
        device_count = nvitop.Device.count()

        for gpu_id in range(device_count):
            device = nvitop.Device(gpu_id)

            # 获取所有进程
            gpu_processes = device.processes()

            for pid, process in gpu_processes.items():
                try:
                        # 获取进程CPU和内存使用率
                        try:
                            ps_process = psutil.Process(pid)
                            cpu_percent = round(ps_process.cpu_percent(), 1)
                            memory_percent = round(ps_process.memory_percent(), 1)
                            # 获取进程运行时间
                            create_time = ps_process.create_time()
                            run_time = time.time() - create_time
                            hours = int(run_time // 3600)
                            minutes = int((run_time % 3600) // 60)
                            seconds = int(run_time % 60)
                            time_str = f"{hours}:{minutes:02d}:{seconds:02d}"
                        except:
                            cpu_percent = 0.0
                            memory_percent = 0.0
                            time_str = "0:00:00"

                        # 获取进程信息
                        proc_info = {
                            "gpu_id": gpu_id,
                            "pid": pid,
                            "username": process.username(),
                            "gpu_memory": process.gpu_memory() // 1024 // 1024,  # MB
                            "gpu_memory_percent": round((process.gpu_memory() / device.memory_total() * 100), 1),
                            "gmbw_percent": 0,  # 单进程的MBW利用率需要额外计算
                            "cpu_percent": cpu_percent,
                            "memory_percent": memory_percent,
                            "time": time_str,
                            "command": process.command()[:100]  # 限制长度
                        }
                        processes.append(proc_info)
                    except:
                        # 进程可能在获取信息时已经结束
                        continue

    except Exception as e:
        print(f"获取用户进程失败: {e}")

    return processes

def send_data_to_server(data: Dict[str, Any]) -> bool:
    """发送数据到服务器"""
    for attempt in range(MAX_RETRIES):
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
            print(f"发送数据失败 (尝试 {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

    return False

def main():
    """主函数"""
    print("=== HPC GPU监控客户端 ===")
    print(f"服务器地址: {SERVER_URL}")
    print(f"更新间隔: {UPDATE_INTERVAL}秒")
    print("按 Ctrl+C 退出\n")

    # 获取当前用户名
    username = getpass.getuser()
    print(f"当前用户: {username}")

    # 检查GPU
    try:
        device_count = nvitop.Device.count()
        if device_count == 0:
            print("错误: 未检测到GPU")
            exit(1)
        print(f"检测到 {device_count} 个GPU\n")
    except Exception as e:
        print(f"GPU检测失败: {e}")
        exit(1)

    # 主循环
    while True:
        try:
            # 获取系统信息
            system_info = get_system_info()

            # 获取GPU数据
            timestamp = datetime.now().strftime("%a %b %d %H:%M:%S %Y")
            gpus = get_gpu_info()
            user_processes = get_user_processes(username)

            # 准备数据
            data = {
                "timestamp": timestamp,
                "nvitop_version": "1.6.2",
                "driver_version": "550.163.01",
                "cuda_version": "12.4",
                "hostname": system_info["hostname"],
                "username": username,
                "uptime": system_info["uptime"],
                "cpu_percent": system_info["cpu_percent"],
                "memory_percent": system_info["memory_percent"],
                "swap_percent": system_info["swap_percent"],
                "load_avg": system_info["load_avg"],
                "gpus": gpus,
                "user_processes": user_processes
            }

            # 打印状态
            print(f"[{timestamp}] 获取到 {len(gpus)} 个GPU, {len(user_processes)} 个用户进程")

            # 发送到服务器
            if send_data_to_server(data):
                print(f"  ✓ 数据发送成功")
            else:
                print(f"  ✗ 数据发送失败")

            # 等待下一次更新
            time.sleep(UPDATE_INTERVAL)

        except KeyboardInterrupt:
            print("\n正在退出...")
            break
        except Exception as e:
            print(f"发生错误: {e}")
            time.sleep(UPDATE_INTERVAL)

if __name__ == "__main__":
    main()