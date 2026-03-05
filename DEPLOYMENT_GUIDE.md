# HPC GPU监控系统部署指南

## 系统概述

本系统实现了在任何终端上实时监控学校HPC的nvitop结果，通过网页展示与终端完全一致的实时跳动的GPU状态。系统采用客户端-服务器架构：

- **云端服务器**（腾讯云）：运行FastAPI服务，接收GPU数据并提供Web界面
- **HPC客户端**：在HPC服务器上运行，采集GPU数据并发送到云端
- **Web界面**：增强版终端界面，支持彩虹渐变、响应式布局和语法高亮

## 🎯 新特性

✅ **彩虹渐变进度条**：根据使用率显示彩虹色彩渐变
✅ **响应式布局**：根据浏览器宽度自动调整字体大小
✅ **语法高亮**：智能识别和高亮GPU状态信息
✅ **彩色主题**：复刻nvitop终端配色方案
✅ **实时动画**：状态指示器和加载动画
✅ **增强UI**：现代化终端界面设计

## 快速部署

### 1. 克隆项目
```bash
git clone <项目地址>
cd hpc-gpu-monitor
```

### 2. 部署云服务器端

登录腾讯云服务器（myserver）：
```bash
ssh myserver
```

安装依赖并启动服务：
```bash
cd ~/hpc-gpu-monitor/server
pip install fastapi uvicorn
pm2 start ecosystem.config.js
pm2 save
pm2 startup
```

### 3. 部署HPC客户端

登录HPC服务器：
```bash
ssh jump-H20-8Card
```

安装依赖：
```bash
cd ~/hpc-gpu-monitor/client
pip install --user requests psutil
```

启动监控：
```bash
# 基础版本（黑白）
python3 simple_nvitop.py

# 增强版本（彩色）
python3 nvitop_colorful.py
```

### 4. 访问监控界面

打开浏览器访问：http://43.136.42.69:8000/

## 详细配置

### 服务器端配置

编辑 `server/app.py`：
```python
# 修改服务器地址
SERVER_URL = "http://YOUR_SERVER_IP:8000"
```

### 客户端配置

编辑 `client/nvitop_colorful.py`：
```python
# 修改服务器地址
SERVER_URL = "http://YOUR_SERVER_IP:8000"
```

## 系统管理

### 查看服务状态
```bash
# 云服务器状态
ssh myserver 'pm2 status'

# HPC客户端状态
ssh jump-H20-8Card 'ps aux | grep nvitop_colorful'
```

### 重启服务
```bash
# 重启云服务
ssh myserver 'pm2 restart gpu-monitor-server'

# 重启HPC客户端
ssh jump-H20-8Card 'cd ~/hpc-gpu-monitor/client && python3 nvitop_colorful.py'
```

### 查看日志
```bash
# 云服务日志
ssh myserver 'pm2 logs gpu-monitor-server'

# HPC客户端日志
ssh jump-H20-8Card 'cd ~/hpc-gpu-monitor/client && tail -f colorful.log'
```

## 故障排查

### 无法访问Web界面
1. 检查云服务器安全组是否开放8000端口
2. 确认服务状态：`ssh myserver 'pm2 status'`
3. 查看服务日志：`ssh myserver 'pm2 logs gpu-monitor-server'`

### 没有数据显示
1. 检查HPC客户端是否运行：`ssh jump-H20-8Card 'ps aux | grep nvitop'`
2. 检查客户端日志：`ssh jump-H20-8Card 'cd ~/hpc-gpu-monitor/client && tail -20 colorful.log'`
3. 手动测试nvitop：`ssh jump-H20-8Card '/home/zhengzsh5/.local/bin/nvitop -1'`

### 网络连接问题
1. 在HPC上测试连接：`curl -s http://YOUR_SERVER_IP:8000/data`
2. 检查防火墙设置
3. 确认服务器IP地址正确

## 高级功能

### 自定义颜色主题
编辑 `server/app.py` 中的CSS部分，修改颜色变量：
```css
.nvitop-red { color: #ff5555; }
.nvitop-green { color: #55ff55; }
.nvitop-yellow { color: #ffff55; }
```

### 调整更新频率
编辑客户端文件，修改UPDATE_INTERVAL：
```python
UPDATE_INTERVAL = 1  # 秒
```

### 启用/禁用彩虹渐变
在 `renderGPUData` 函数中切换使用：
```javascript
// 使用彩虹渐变
const rainbowBar = createRainbowBar(percent, 50);
// 使用普通进度条
const normalBar = '█'.repeat(filled) + '░'.repeat(empty);
```

## 技术架构

### 数据流
1. HPC客户端运行nvitop捕获输出
2. 客户端将输出发送到云服务器
3. 云服务器存储并转发给Web前端
4. 前端实时渲染并显示

### 颜色处理
- 使用HSL色彩空间生成彩虹渐变
- 根据GPU状态智能分配颜色
- 支持响应式颜色强度调整

### 响应式设计
- 根据屏幕宽度自动调整字体大小
- 最小宽度支持到800px
- 保持终端比例不变形

## 性能优化

### 前端优化
- 使用虚拟DOM减少重绘
- 智能更新机制，只更新变化部分
- CSS动画使用GPU加速

### 后端优化
- 使用pm2管理进程，支持自动重启
- 数据缓存减少重复计算
- 异步处理提高并发能力

## 安全建议

1. **使用HTTPS**：在生产环境中启用HTTPS
2. **访问控制**：添加基本的身份验证
3. **IP白名单**：限制访问IP范围
4. **定期更新**：保持系统和依赖更新

## 更新日志

### v2.0 (当前版本)
- ✨ 新增彩虹渐变进度条
- ✨ 添加语法高亮功能
- ✨ 实现响应式布局
- ✨ 优化UI界面设计
- ✨ 增加状态指示器

### v1.0
- ✨ 基础监控功能
- ✨ 实时数据更新
- ✨ 原始nvitop输出显示

## 支持与反馈

如有问题或建议，请通过以下方式联系：
- 提交GitHub Issue
- 发送邮件至维护者

---

**注意**：本系统专为HPC环境设计，确保您有权限访问相关服务器和资源。