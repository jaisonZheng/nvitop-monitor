#!/usr/bin/env python3
"""
简单的nvitop输出捕获脚本
直接运行nvitop命令并捕获输出
"""

import subprocess
import time
import requests
import getpass
import socket
from datetime import datetime

SERVER_URL = "http://43.136.42.69:8000"

def capture_nvitop():
    """运行nvitop并捕获输出"""
    try:
        # 使用timeout运行nvitop，捕获一帧输出
        result = subprocess.run(
            ['/home/zhengzsh5/.local/bin/nvitop', '-1'],  # -1 表示只显示一帧
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        return ""
    except Exception as e:
        print(f"运行nvitop失败: {e}")
        return ""

def send_data(output):
    """发送数据到服务器"""
    data = {
        "timestamp": datetime.now().strftime("%a %b %d %H:%M:%S %Y"),
        "raw_output": output,
        "hostname": socket.gethostname(),
        "username": getpass.getuser()
    }

    try:
        response = requests.post(
            f"{SERVER_URL}/update_raw",
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        print(f"发送失败: {e}")
        return False

def main():
    print("=== NVITOP 简单监控 ===")
    print(f"服务器地址: {SERVER_URL}")
    print("开始监控...")

    while True:
        try:
            # 捕获nvitop输出
            output = capture_nvitop()

            if output.strip():
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 捕获输出")

                # 发送到服务器
                if send_data(output):
                    print("  ✓ 数据发送成功")
                else:
                    print("  ✗ 数据发送失败")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 未捕获到输出")

            # 等待1秒
            time.sleep(1)

        except KeyboardInterrupt:
            print("\n正在退出...")
            break
        except Exception as e:
            print(f"发生错误: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()