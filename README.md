# hpc-gpu-monitor

> View your HPC's `nvitop` in any browser — pixel-perfect colors, live updates every second.

---

## 中文文档 / Chinese ↓ [jump](#hpc-gpu-监控系统)

---

## Architecture

```
 ┌─────────────────────────────────────────────────────────────┐
 │  HPC  (behind campus firewall, no public IP)                │
 │                                                             │
 │   nvitop -1  ──►  nvitop_ansi_client.py                    │
 │   (ANSI color output, pty-captured)   │                     │
 └───────────────────────────────────────┼─────────────────────┘
                                         │  POST /update_ansi
                                         │  (raw ANSI text, 1 s)
                                         ▼
 ┌─────────────────────────────────────────────────────────────┐
 │  Cloud Server  (public IP, port 8765, proxied via nginx)    │
 │                                                             │
 │   server/app_nvitop_final.py   (FastAPI + uvicorn)          │
 │   ┌─────────────────────────────────────────────┐           │
 │   │  ANSI → HTML converter  (256-color, SGR)    │           │
 │   │  stores latest HTML snapshot in memory      │           │
 │   └─────────────────────────────────────────────┘           │
 │          │  GET /data_html  (JSON, 1 s poll)                │
 └──────────┼──────────────────────────────────────────────────┘
            │
            ▼
 ┌──────────────────────────────┐
 │  Browser  (anywhere)         │
 │                              │
 │  black bg · monospace font   │
 │  colored <span> tags         │
 │  live status dot (●)         │
 └──────────────────────────────┘
```

### Data flow in one sentence

The HPC client runs `nvitop -1` inside a pty every second, captures the raw ANSI-colored output, and POSTs it to the cloud server. The server converts ANSI escape codes to HTML `<span>` tags server-side and stores the result. The browser polls `/data_html` every second and swaps the `<pre>` content — no page reload, no WebSocket needed.

---

## File Structure

```
hpc-gpu-monitor/
├── server/
│   ├── app_nvitop_final.py   ← main server (use this one)
│   └── requirements.txt
├── client/
│   ├── nvitop_ansi_client.py ← main client (use this one)
│   └── requirements.txt
├── nvitop/                   ← nvitop source (reference only)
├── deploy.sh
└── README.md
```

---

## Quick Start

### Prerequisites

| Where | Requirement |
|-------|-------------|
| Cloud server | Python 3.8+, port 8765 open in firewall/security group, nginx + HTTPS |
| HPC | `nvitop` installed (`pip install --user nvitop`), Python 3.8+ |
| SSH | `~/.ssh/config` with aliases for both hosts (see below) |

Recommended `~/.ssh/config` entries:

```
Host myserver
    HostName <cloud-server-public-ip>
    User root

Host jump-H20-8Card
    HostName <hpc-internal-ip>
    User <your-username>
    ProxyJump <jump-server-host>
```

---

### Step 1 — Deploy the server

```bash
# Copy server files
scp server/app_nvitop_final.py server/requirements.txt myserver:~/hpc-gpu-monitor/server/

# SSH in, install deps, start with pm2 (or nohup)
ssh myserver
pip install -r ~/hpc-gpu-monitor/server/requirements.txt
pm2 start ~/hpc-gpu-monitor/server/app_nvitop_final.py \
    --name gpu-monitor-server --interpreter python3
```

Verify:

```bash
curl https://nvitop.jaison.ink/
# should return HTML with lang="en"
```

---

### Step 2 — Deploy the client on HPC

```bash
# Copy client file
scp client/nvitop_ansi_client.py client/requirements.txt \
    jump-H20-8Card:~/hpc-gpu-monitor/client/

# SSH in, install deps
ssh jump-H20-8Card
pip install --user -r ~/hpc-gpu-monitor/client/requirements.txt
```

Edit `SERVER_URL` at the top of `nvitop_ansi_client.py` if needed (default: `https://nvitop.jaison.ink`):

```python
SERVER_URL = "https://nvitop.jaison.ink"
```

Start the client:

```bash
cd ~/hpc-gpu-monitor/client
nohup python3 nvitop_ansi_client.py > ansi_client.log 2>&1 &
```

---

### Step 3 — Open the browser

Navigate to `https://nvitop.jaison.ink`

You should see the nvitop UI appear within 2 seconds. The green dot (●) in the top-left indicates a live connection.

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Main terminal UI page |
| `POST` | `/update_ansi` | Client pushes raw ANSI text |
| `GET` | `/data_html` | Browser polls converted HTML |
| `POST` | `/update_raw` | Legacy plain-text push (no colors) |

---

## Troubleshooting

**Page loads but shows spinner / no data**
- Check client is running: `ssh jump-H20-8Card 'ps aux | grep nvitop_ansi'`
- Check client log: `ssh jump-H20-8Card 'tail -20 ~/hpc-gpu-monitor/client/ansi_client.log'`
- Verify HPC can reach server: `curl https://nvitop.jaison.ink/`

**Colors missing / plain text only**
- Confirm the client log shows `colors=yes`; if not, nvitop may not be in PATH
- Check `nvitop` is findable: `which nvitop` or `~/.local/bin/nvitop --version`

**Server not starting**
- Check port 8765 is free: `ss -tlnp | grep 8765`
- Check server log: `pm2 logs gpu-monitor-server`

**Stop everything**

```bash
# Server
ssh myserver 'pm2 stop gpu-monitor-server'

# HPC client
ssh jump-H20-8Card 'pkill -f nvitop_ansi_client.py'
```

---

---

# hpc-gpu-监控系统

> 在任意浏览器中实时查看 HPC 的 `nvitop` 输出 —— 完整颜色、每秒刷新。

---

## 系统架构

```
 ┌─────────────────────────────────────────────────────────────┐
 │  HPC（校园网内网，无公网 IP）                                 │
 │                                                             │
 │   nvitop -1  ──►  nvitop_ansi_client.py                    │
 │   （通过 pty 捕获 ANSI 彩色输出）      │                     │
 └────────────────────────────────────────┼────────────────────┘
                                          │  POST /update_ansi
                                          │  （原始 ANSI 文本，每秒 1 次）
                                          ▼
 ┌─────────────────────────────────────────────────────────────┐
 │  云服务器（公网 IP，端口 8765，nginx + HTTPS 代理）           │
 │                                                             │
 │   server/app_nvitop_final.py   （FastAPI + uvicorn）        │
 │   ┌─────────────────────────────────────────────┐           │
 │   │  ANSI → HTML 转换器（支持 256 色、SGR 属性） │           │
 │   │  将最新 HTML 快照存入内存                    │           │
 │   └─────────────────────────────────────────────┘           │
 │          │  GET /data_html  （JSON 轮询，每秒 1 次）         │
 └──────────┼──────────────────────────────────────────────────┘
            │
            ▼
 ┌──────────────────────────────┐
 │  浏览器（任意网络）           │
 │                              │
 │  黑色背景 · 等宽字体          │
 │  彩色 <span> 标签             │
 │  实时状态指示灯（●）          │
 └──────────────────────────────┘
```

### 一句话说清楚数据流

HPC 客户端每秒在 pty 内执行一次 `nvitop -1`，捕获带 ANSI 转义码的彩色输出，POST 到云服务器。服务器在服务端将 ANSI 转为 HTML `<span>` 标签并存入内存。浏览器每秒轮询 `/data_html`，直接替换 `<pre>` 内容 —— 无需刷新页面，无需 WebSocket。

---

## 文件结构

```
hpc-gpu-monitor/
├── server/
│   ├── app_nvitop_final.py   ← 主服务端（使用此文件）
│   └── requirements.txt
├── client/
│   ├── nvitop_ansi_client.py ← 主客户端（使用此文件）
│   └── requirements.txt
├── nvitop/                   ← nvitop 源码（仅供参考）
├── deploy.sh
└── README.md
```

---

## 快速部署

### 前置条件

| 位置 | 要求 |
|------|------|
| 云服务器 | Python 3.8+，安全组放行 8765 端口，nginx + HTTPS |
| HPC | 已安装 `nvitop`（`pip install --user nvitop`），Python 3.8+ |
| SSH | `~/.ssh/config` 中配置好两台主机的别名（见下方） |

`~/.ssh/config` 参考配置：

```
Host myserver
    HostName <云服务器公网IP>
    User root

Host jump-H20-8Card
    HostName <HPC内网IP>
    User <你的用户名>
    ProxyJump <跳板机主机名>
```

---

### 第一步 — 部署云端服务器

```bash
# 上传服务端文件
scp server/app_nvitop_final.py server/requirements.txt myserver:~/hpc-gpu-monitor/server/

# SSH 登录，安装依赖，用 pm2 启动（或直接 nohup）
ssh myserver
pip install -r ~/hpc-gpu-monitor/server/requirements.txt
pm2 start ~/hpc-gpu-monitor/server/app_nvitop_final.py \
    --name gpu-monitor-server --interpreter python3
```

验证：

```bash
curl https://nvitop.jaison.ink/
# 返回 HTML 且包含 lang="en" 即为成功
```

---

### 第二步 — 在 HPC 上部署客户端

```bash
# 上传客户端文件
scp client/nvitop_ansi_client.py client/requirements.txt \
    jump-H20-8Card:~/hpc-gpu-monitor/client/

# SSH 登录，安装依赖
ssh jump-H20-8Card
pip install --user -r ~/hpc-gpu-monitor/client/requirements.txt
```

如有需要，修改 `nvitop_ansi_client.py` 顶部的 `SERVER_URL`（默认 `https://nvitop.jaison.ink`）：

```python
SERVER_URL = "https://nvitop.jaison.ink"
```

启动客户端：

```bash
cd ~/hpc-gpu-monitor/client
nohup python3 nvitop_ansi_client.py > ansi_client.log 2>&1 &
```

---

### 第三步 — 打开浏览器

访问 `https://nvitop.jaison.ink`

约 2 秒后出现 nvitop 界面，左上角绿色指示灯（●）表示数据实时传输中。

---

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 终端 UI 主页面 |
| `POST` | `/update_ansi` | 客户端推送原始 ANSI 文本 |
| `GET` | `/data_html` | 浏览器轮询转换后的 HTML |
| `POST` | `/update_raw` | 兼容旧版纯文本推送（无颜色） |

---

## 故障排查

**页面转圈、无数据**
- 检查客户端是否在运行：`ssh jump-H20-8Card 'ps aux | grep nvitop_ansi'`
- 查看客户端日志：`ssh jump-H20-8Card 'tail -20 ~/hpc-gpu-monitor/client/ansi_client.log'`
- 在 HPC 上测试能否访问服务器：`curl https://nvitop.jaison.ink/`

**显示纯文本、无颜色**
- 确认客户端日志显示 `colors=yes`，否则 nvitop 可能不在 PATH 中
- 检查 nvitop 路径：`which nvitop` 或 `~/.local/bin/nvitop --version`

**服务端无法启动**
- 检查 8765 端口是否被占用：`ss -tlnp | grep 8765`
- 查看 pm2 日志：`pm2 logs gpu-monitor-server`

**停止服务**

```bash
# 停止云端服务
ssh myserver 'pm2 stop gpu-monitor-server'

# 停止 HPC 客户端
ssh jump-H20-8Card 'pkill -f nvitop_ansi_client.py'
```
