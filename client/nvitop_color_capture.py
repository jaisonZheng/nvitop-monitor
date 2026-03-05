#!/usr/bin/env python3
"""
捕获nvitop的彩色输出并发送到服务器的监控客户端
完全复刻nvitop的显示效果
"""

import subprocess
import time
import requests
import getpass
import socket
from datetime import datetime

# 配置
SERVER_URL = "http://43.136.42.69:8000"
UPDATE_INTERVAL = 1  # 更新间隔（秒）

def capture_nvitop_with_ansi():
    """运行nvitop并捕获带ANSI转义序列的输出"""
    try:
        # 设置环境变量强制启用颜色和256色支持
        env = {
            'TERM': 'xterm-256color',
            'FORCE_COLOR': '1',
            'CLICOLOR': '1',
            'CLICOLOR_FORCE': '1',
            'PROMPT_COLOR': '1',
            'PY_COLORS': '1',
            'PYTHON_COLORS': '1',
        }
        # 合并当前环境变量
        env.update({k: v for k, v in os.environ.items() if k not in env})

        # 运行nvitop
        result = subprocess.run(
            ['/home/zhengzsh5/.local/bin/nvitop', '-1'],
            capture_output=True,
            text=True,
            timeout=5,
            env=env
        )

        # 检查输出
        if result.stdout:
            print(f"捕获输出成功，长度: {len(result.stdout)}")
            # 检查是否包含ANSI转义序列
            if '\033[' in result.stdout:
                print("检测到ANSI颜色代码")
            return result.stdout
        else:
            print("nvitop没有输出")
            return ""

    except subprocess.TimeoutExpired:
        print("nvitop超时")
        return ""
    except Exception as e:
        print(f"运行nvitop失败: {e}")
        return ""

def parse_ansi_to_html(text):
    """将ANSI转义序列转换为HTML"""
    if not text:
        return ""

    # ANSI颜色代码到CSS的映射
    ansi_to_css = {
        '0': '',  # reset
        '1': 'font-weight: bold',
        '2': 'opacity: 0.5',
        '4': 'text-decoration: underline',
        '5': 'animation: blink 1s infinite',
        '7': 'filter: invert(1)',

        # 前景色
        '30': 'color: #000000',
        '31': 'color: #cd0000',
        '32': 'color: #00cd00',
        '33': 'color: #cdcd00',
        '34': 'color: #0000ee',
        '35': 'color: #cd00cd',
        '36': 'color: #00cdcd',
        '37': 'color: #e5e5e5',

        # 亮前景色
        '90': 'color: #7f7f7f',
        '91': 'color: #ff0000',
        '92': 'color: #00ff00',
        '93': 'color: #ffff00',
        '94': 'color: #5c5cff',
        '95': 'color: #ff00ff',
        '96': 'color: #00ffff',
        '97': 'color: #ffffff',

        # 背景色
        '40': 'background-color: #000000',
        '41': 'background-color: #cd0000',
        '42': 'background-color: #00cd00',
        '43': 'background-color: #cdcd00',
        '44': 'background-color: #0000ee',
        '45': 'background-color: #cd00cd',
        '46': 'background-color: #00cdcd',
        '47': 'background-color: #e5e5e5',

        # 亮背景色
        '100': 'background-color: #7f7f7f',
        '101': 'background-color: #ff0000',
        '102': 'background-color: #00ff00',
        '103': 'background-color: #ffff00',
        '104': 'background-color: #5c5cff',
        '105': 'background-color: #ff00ff',
        '106': 'background-color: #00ffff',
        '107': 'background-color: #ffffff'
    }

    # 将文本按ANSI代码分割
    import re
    pattern = r'\033\[([0-9;]+)m'
    parts = re.split(pattern, text)

    html_parts = []
    current_styles = []

    for i, part in enumerate(parts):
        if i % 2 == 0:  # 普通文本
            if part:
                if current_styles:
                    style = '; '.join(current_styles)
                    html_parts.append(f'<span style="{style}">{part}</span>')
                else:
                    html_parts.append(part)
        else:  # ANSI代码
            codes = part.split(';')
            for code in codes:
                code = code.strip()
                if code == '0':  # reset
                    current_styles = []
                elif code in ansi_to_css:
                    if ansi_to_css[code]:  # 非空样式
                        current_styles.append(ansi_to_css[code])

    return ''.join(html_parts)

def send_data_to_server(raw_output: str, html_output: str) -> bool:
    """发送数据到服务器"""
    data = {
        "timestamp": datetime.now().strftime("%a %b %d %H:%M:%S %Y"),
        "raw_output": raw_output,
        "html_output": html_output,
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
    print("=== NVITOP 彩色输出捕获客户端 ===")
    print(f"服务器地址: {SERVER_URL}")
    print("开始捕获nvitop彩色输出...")
    print("按 Ctrl+C 退出\n")

    while True:
        try:
            # 捕获nvitop输出
            output = capture_nvitop_with_ansi()

            if output.strip():
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 捕获输出，长度: {len(output)}")

                # 转换为HTML
                html_output = parse_ansi_to_html(output)

                # 发送到服务器
                if send_data_to_server(output, html_output):
                    print("  ✓ 数据发送成功")
                else:
                    print("  ✗ 数据发送失败")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 未捕获到输出")

            # 等待下一次更新
            time.sleep(UPDATE_INTERVAL)

        except KeyboardInterrupt:
            print("\n正在退出...")
            break
        except Exception as e:
            print(f"发生错误: {e}")
            time.sleep(UPDATE_INTERVAL)

if __name__ == "__main__":
    import os
    main()