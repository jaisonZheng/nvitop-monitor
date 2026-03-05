# HPC GPU监控系统

在任何终端上实时监控学校HPC的nvitop结果，通过网页展示实时跳动的GPU状态。

## 系统架构

- **云端服务器** (腾讯云): 运行FastAPI服务，接收GPU数据并提供Web界面
- **HPC客户端**: 在HPC服务器上运行，采集GPU数据并发送到云端
- **Web界面**: 终端风格的实时GPU监控页面

## 功能特性

- ✅ 实时显示GPU利用率、显存使用、温度、功耗
- ✅ 显示当前用户的GPU进程
- ✅ 终端风格的Web界面，与nvitop显示一致
- ✅ 自动重连，网络波动不中断
- ✅ 1秒刷新间隔，实时跳动效果

## 文件结构

```
hpc-gpu-monitor/
├── server/
│   ├── app.py              # FastAPI服务端
│   └── requirements.txt    # 服务端依赖
├── client/
│   ├── monitor.py          # HPC监控客户端
│   └── requirements.txt    # 客户端依赖
├── deploy.sh               # 一键部署脚本
└── README.md
```

## 快速部署

### 1. 修改配置

编辑 `client/monitor.py`，将 `SERVER_URL` 改为你的云服务器IP：
```python
SERVER_URL = "http://YOUR_SERVER_IP:8000"
```

### 2. 运行部署脚本

```bash
./deploy.sh <服务器IP> <HPC主机名>

# 示例
./deploy.sh 123.123.123.123 jump-H20-8Card
```

### 3. 启动HPC客户端

部署完成后，在HPC服务器上手动启动客户端：
```bash
ssh jump-H20-8Card
cd ~/hpc-gpu-monitor/client
python monitor.py
```

### 4. 访问监控页面

打开浏览器访问: `http://<服务器IP>:8000`

## 手动部署

### 云端服务器部署

```bash
# 上传server目录到云服务器
ssh myserver
cd ~/hpc-gpu-monitor/server
pip install -r requirements.txt
python app.py  # 或使用nohup后台运行
```

### HPC客户端部署

```bash
# 上传client目录到HPC
ssh jump-H20-8Card
cd ~/hpc-gpu-monitor/client
pip install --user -r requirements.txt
python monitor.py
```

## 注意事项

1. 确保云服务器安全组已开放8000端口
2. HPC服务器需要安装nvidia驱动和nvitop
3. 客户端会自动重试，即使网络暂时中断也不会退出
4. 只有当前用户的GPU进程会被显示

## 故障排查

### 无法访问Web页面
- 检查云服务器安全组设置
- 确认服务已启动: `ssh myserver 'ps aux | grep app.py'`
- 查看日志: `ssh myserver 'cat ~/hpc-gpu-monitor/server/server.log'`

### 没有数据显示
- 确认HPC客户端已运行: `ssh jump-H20-8Card 'ps aux | grep monitor.py'`
- 检查网络连接: 在HPC上执行 `curl http://<服务器IP>:8000/data`
- 确认GPU可用: 在HPC上执行 `python -c "import nvitop; print(nvitop.Device.count())"`

## 停止服务

```bash
# 停止云服务
ssh myserver 'pkill -f "python.*app.py"'

# 停止HPC客户端
ssh jump-H20-8Card 'pkill -f "python.*monitor.py"'
```