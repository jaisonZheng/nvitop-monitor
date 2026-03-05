#!/usr/bin/env python3
"""
捕获nvitop的彩色输出并发送到服务器的监控客户端
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

def capture_nvitop_with_colors():
    """运行nvitop并捕获带颜色的输出"""
    try:
        # 设置环境变量强制启用颜色输出
        env = os.environ.copy()
        env['FORCE_COLOR'] = '1'
        env['TERM'] = 'xterm-256color'

        # 使用stdbuf禁用输出缓冲
        cmd = ['stdbuf', '-oL', '/home/zhengzsh5/.local/bin/nvitop', '-1']

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            env=env
        )

        # 检查是否有ANSI颜色代码
        if '\033[' in result.stdout:
            print("检测到ANSI颜色代码")

        return result.stdout

    except subprocess.TimeoutExpired:
        return ""
    except Exception as e:
        print(f"运行nvitop失败: {e}")
        return ""

def parse_ansi_colors(text):
    """解析ANSI颜色代码并转换为HTML"""
    # ANSI颜色代码到CSS颜色的映射
    ansi_to_css = {
        '30': 'color: #000000',  # black
        '31': 'color: #cd0000',  # red
        '32': 'color: #00cd00',  # green
        '33': 'color: #cdcd00',  # yellow
        '34': 'color: #0000ee',  # blue
        '35': 'color: #cd00cd',  # magenta
        '36': 'color: #00cdcd',  # cyan
        '37': 'color: #e5e5e5',  # white
        '90': 'color: #7f7f7f',  # bright black (gray)
        '91': 'color: #ff0000',  # bright red
        '92': 'color: #00ff00',  # bright green
        '93': 'color: #ffff00',  # bright yellow
        '94': 'color: #5c5cff',  # bright blue
        '95': 'color: #ff00ff',  # bright magenta
        '96': 'color: #00ffff',  # bright cyan
        '97': 'color: #ffffff',  # bright white
        '0': '',  # reset
    }

    # 背景色映射
    bg_ansi_to_css = {
        '40': 'background-color: #000000',
        '41': 'background-color: #cd0000',
        '42': 'background-color: #00cd00',
        '43': 'background-color: #cdcd00',
        '44': 'background-color: #0000ee',
        '45': 'background-color: #cd00cd',
        '46': 'background-color: #00cdcd',
        '47': 'background-color: #e5e5e5',
        '100': 'background-color: #7f7f7f',
        '101': 'background-color: #ff0000',
        '102': 'background-color: #00ff00',
        '103': 'background-color: #ffff00',
        '104': 'background-color: #5c5cff',
        '105': 'background-color: #ff00ff',
        '106': 'background-color: #00ffff',
        '107': 'background-color: #ffffff',
    }

    # 属性映射
    attr_to_css = {
        '1': 'font-weight: bold',
        '2': 'opacity: 0.5',
        '4': 'text-decoration: underline',
        '5': 'animation: blink 1s infinite',
        '7': 'filter: invert(1)',
    }

    html_lines = []
    current_styles = []

    for line in text.split('\n'):
        # 解析ANSI转义序列
        import re

        # 查找ANSI转义序列
        ansi_pattern = r'\033\[([0-9;]+)m'
        parts = re.split(ansi_pattern, line)

        html_parts = []
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
                    elif code in attr_to_css:
                        current_styles.append(attr_to_css[code])
                    elif code in ansi_to_css:
                        current_styles.append(ansi_to_css[code])
                    elif code in bg_ansi_to_css:
                        current_styles.append(bg_ansi_to_css[code])

        html_line = ''.join(html_parts)
        html_lines.append(html_line)

    return '<br>'.join(html_lines)

def send_data(output, html_output):
    """发送数据到服务器"""
    data = {
        "timestamp": datetime.now().strftime("%a %b %d %H:%M:%S %Y"),
        "raw_output": output,
        "html_output": html_output,
        "hostname": socket.gethostname(),
        "username": getpass.getuser()
    }

    try:
        response = requests.post(
            f"{SERVER_URL}/update_raw_html",
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        print(f"发送失败: {e}")
        return False

def main():
    print("=== NVITOP 彩色监控 ===")
    print(f"服务器地址: {SERVER_URL}")
    print("开始捕获彩色输出...")

    while True:
        try:
            # 捕获nvitop输出
            output = capture_nvitop_with_colors()

            if output.strip():
                # 转换为HTML
                html_output = parse_ansi_colors(output)

                print(f"[{datetime.now().strftime('%H:%M:%S')}] 捕获输出")

                # 发送到服务器
                if send_data(output, html_output):
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
    import os
    main()