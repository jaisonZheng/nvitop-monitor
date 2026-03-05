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
from datetime import datetime
from typing import List, Dict, Any

try:
    import nvitop
except ImportError:
    print("错误: 未安装nvitop包")
    print("请运行: pip install nvitop")
    exit(1)

# 配置
SERVER_URL = "http://YOUR_SERVER_IP:8000"  # 替换为你的服务器地址
UPDATE_INTERVAL = 1  # 更新间隔（秒）
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 5  # 重试延迟（秒）

def get_gpu_info() -> List[Dict[str, Any]]:
    """获取所有GPU的信息"""
    gpus = []

    try:
        device_count = nvitop.Device.count()

        for i in range(device_count):
            device = nvitop.Device(i)

            # 获取GPU信息
            gpu_info = {
                "id": i,
                "name": device.name(),
                "memory_total": device.memory_total() // 1024 // 1024,  # MB
                "memory_used": device.memory_used() // 1024 // 1024,    # MB
                "memory_percent": device.memory_percent(),
                "gpu_percent": device.gpu_utilization(),
                "temperature": device.temperature(),
                "power": device.power_draw()  # W
            }

            gpus.append(gpu_info)

    except Exception as e:
        print(f"获取GPU信息失败: {e}")

    return gpus

def get_user_processes(username: str) -> List[Dict[str, Any]]:
    """获取当前用户的GPU进程"""
    processes = []

    try:
        device_count = nvitop.Device.count()

        for gpu_id in range(device_count):
            device = nvitop.Device(gpu_id)

            # 获取所有进程
            gpu_processes = device.processes()

            for pid, process in gpu_processes.items():
                # 检查是否属于当前用户
                if process.username() == username:
                    try:
                        # 获取进程信息
                        proc_info = {
                            "gpu_id": gpu_id,
                            "pid": pid,
                            "username": username,
                            "gpu_memory": process.gpu_memory() // 1024 // 1024,  # MB
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
            # 获取数据
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            gpus = get_gpu_info()
            user_processes = get_user_processes(username)

            # 准备数据
            data = {
                "timestamp": timestamp,
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