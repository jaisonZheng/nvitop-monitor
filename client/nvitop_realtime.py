#!/usr/bin/env python3
"""
直接捕获nvitop终端输出并实时发送到服务器的监控客户端
使用pty来完全复现终端界面
"""

import os
import pty
import subprocess
import select
import requests
import time
import getpass
import socket
from datetime import datetime

# 配置
SERVER_URL = "http://43.136.42.69:8000"
UPDATE_INTERVAL = 0.5  # 更新间隔（秒）

def capture_nvitop():
    """使用pty捕获nvitop的完整终端输出"""
    # 创建伪终端
    master, slave = pty.openpty()

    # 启动nvitop
    try:
        process = subprocess.Popen(
            ['/home/zhengzsh5/.local/bin/nvitop'],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            preexec_fn=os.setsid  # 创建新的会话
        )
    except FileNotFoundError:
        print("错误: 未找到nvitop命令")
        exit(1)

    # 关闭从设备，我们只需要主设备
    os.close(slave)

    # 设置主设备为非阻塞模式
    import fcntl
    fcntl.fcntl(master, fcntl.F_SETFL, os.O_NONBLOCK)

    buffer = ""
    last_send = time.time()

    try:
        while True:
            # 检查是否有数据可读
            ready, _, _ = select.select([master], [], [], 0.1)

            if ready:
                try:
                    data = os.read(master, 4096).decode('utf-8', errors='ignore')
                    buffer += data

                    # 检查是否收集到完整的nvitop界面
                    if 'NVITOP' in buffer and 'Processes:' in buffer and buffer.count('│') > 20:
                        # 找到最后一个完整的界面
                        lines = buffer.split('\n')

                        # 从后往前找，找到包含完整界面的部分
                        end_idx = -1
                        start_idx = -1

                        for i in range(len(lines) - 1, -1, -1):
                            if 'NVITOP' in lines[i]:
                                start_idx = i
                                break

                        for i in range(len(lines) - 1, -1, -1):
                            if '[ CPU:' in lines[i] and '[ MEM:' in lines[i]:
                                end_idx = i + 1
                                break

                        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                            # 提取完整的nvitop输出
                            full_output = '\n'.join(lines[start_idx:end_idx])

                            # 立即发送
                            yield full_output

                            # 清空缓冲区，保留未处理的部分
                            buffer = '\n'.join(lines[end_idx:])
                            last_send = time.time()

                except OSError:
                    # 没有更多数据
                    pass

            # 定期发送，即使没有完整界面
            if time.time() - last_send > 2 and buffer.strip():
                # 发送当前缓冲区内容
                yield buffer.strip()
                buffer = ""
                last_send = time.time()

    except KeyboardInterrupt:
        pass
    finally:
        # 清理
        try:
            os.kill(process.pid, 9)
            process.wait()
        except:
            pass
        os.close(master)

def send_raw_output(output: str) -> bool:
    """直接发送原始输出到服务器"""
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
    """主函数"""
    print("=== NVITOP 实时监控客户端（完整终端输出）===")
    print(f"服务器地址: {SERVER_URL}")
    print("正在启动nvitop...")

    # 检查nvitop是否存在
    try:
        subprocess.run(['/home/zhengzsh5/.local/bin/nvitop', '--version'], check=True, capture_output=True)
    except:
        print("错误: 未找到nvitop命令")
        exit(1)

    print("开始捕获nvitop输出...")
    print("按 Ctrl+C 退出\n")

    # 运行nvitop并捕获输出
    for output in capture_nvitop():
        if output.strip():
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 发送更新")

            # 发送到服务器
            if send_raw_output(output):
                print("  ✓ 数据发送成功")
            else:
                print("  ✗ 数据发送失败")

if __name__ == "__main__":
    main()