一个基于Python的自动化量化交易系统，支持实时交易信号生成、回测分析和系统化交易执行。

## 📋 目录

- [功能特性](#功能特性)
- [系统架构](#系统架构)
- [安装部署](#安装部署)
- [配置说明](#配置说明)
- [使用指南](#使用指南)
- [服务部署](#服务部署)
- [开发指南](#开发指南)
- [故障排除](#故障排除)
- [许可证](#许可证)

## 🚀 功能特性

### 核心功能
- **实时交易信号生成**: 基于多因子策略模型
- **自动化交易执行**: 支持Binance期货交易
- **回测分析**: 历史数据回测和性能评估
- **风险管理**: 多层次风险控制机制
- **Telegram通知**: 实时交易信号推送
- **Web管理界面**: 基于浏览器的图形化管理界面

### 技术指标
- **移动平均线**: EMA、SMA多周期组合
- **动量指标**: RSI、OBV、ATR
- **趋势分析**: 多时间级别分析
- **波动率指标**: ATR、布林带
- **成交量分析**: OBV、成交量加权

### 策略特性
- **夏普比率优化**: 基于风险调整收益的策略优化
- **动态仓位管理**: 根据市场波动调整仓位大小
- **多时间级别**: 1小时和日线级别信号确认
- **止损止盈**: 自动风险控制机制

## 🏗️ 系统架构

```
trading/
├── main.py                 # 主程序入口
├── trading.py             # 交易系统核心
├── web/                   # Web管理界面模块
│   ├── __init__.py        # 模块初始化
│   ├── app.py             # Web应用主文件
│   ├── start.py           # Web界面启动脚本
│   ├── test.py            # Web界面测试脚本
│   ├── templates/         # HTML模板目录
│   └── static/            # 静态文件目录
├── core/                  # 核心模块
│   ├── strategy.py        # 策略实现
│   ├── data_loader.py     # 数据加载器
│   ├── feature_engineer.py # 特征工程
│   ├── backtester.py      # 回测引擎
│   └── exchange_api.py    # 交易所API
├── config.py              # 系统配置
├── json/                  # JSON配置文件目录
│   ├── config.json   # 用户配置
│   └── api_config.json    # API配置
├── utils/                 # 工具模块
│   ├── fix_config.py      # 配置修复工具
│   └── fix_matplotlib_fonts.py # 字体修复工具
├── tools/                 # 工具脚本
│   ├── signal_test.py     # 信号测试
│   ├── signals_sharpe.py  # 夏普比率分析
│   └── continuous_monitor.py # 持续监控
├── deepseek/              # DeepSeek集成模块
│   ├── deepseek_analyzer.py # DeepSeek分析器
│   └── deepseek_signal_integrator.py # 信号集成器
├── docs/                  # 文档目录
│   └── Web界面使用指南.md  # Web界面使用指南
├── install.sh             # 安装脚本
├── trading-system.service # 系统服务配置
├── requirements.txt       # Python依赖
└── logs/                  # 日志目录
```

## 📦 安装部署

### 系统要求

- **操作系统**: CentOS 7+, Ubuntu 18+, Windows 10+
- **Python**: 3.8 (推荐使用 python38 命令)
- **内存**: 最少2GB，推荐4GB+
- **存储**: 最少1GB可用空间
- **网络**: 稳定的互联网连接

### API密钥配置

为了安全起见，系统使用 `.env` 文件来存储API密钥：

1. **创建 `.env` 文件**：
   ```bash
   # 复制模板文件
   cp .env.example .env
   
   # 编辑 .env 文件，添加您的API密钥
   BINANCE_API_KEY=your_api_key_here
   BINANCE_SECRET_KEY=your_secret_key_here
   ```

2. **安全提醒**：
   - `.env` 文件已添加到 `.gitignore`，不会被提交到版本控制
   - 请确保 `.env` 文件权限设置正确（Linux: 600）
   - 定期更换API密钥以提高安全性
   - 使用最小权限原则配置API密钥权限

### CentOS/Linux 安装

#### 1. 自动安装（推荐）

```bash
# 下载项目
git clone https://github.com/knwins/trading.git
cd trading

# 运行安装脚本
sudo bash install.sh
```

安装脚本将自动完成：
- 系统依赖安装（包括 python38）
- Python虚拟环境创建
- 项目文件部署
- 系统服务配置
- 权限设置

#### 2. 手动安装

```bash
# 安装系统依赖
sudo yum update -y
sudo yum install -y python38 python38-pip python38-devel git

# 创建用户
sudo useradd -r -s /bin/false -d /opt/trading trading

# 创建目录
sudo mkdir -p /opt/trading
sudo chown trading:trading /opt/trading

# 复制项目文件
sudo cp -r . /opt/trading/
sudo chown -R trading:trading /opt/trading

# 创建虚拟环境
cd /opt/trading
sudo -u trading python38 -m venv venv
sudo -u trading /opt/trading/venv/bin/pip install -r requirements.txt

# 配置系统服务
sudo cp trading-system.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable trading-system
```

#### 3. 测试 Python38 安装

```bash
# 运行测试脚本
bash test_python38.sh
```

### Windows 安装

```bash
# 安装Python依赖
pip install -r requirements.txt

# 运行主程序
python main.py
```

## ⚙️ 配置说明

### 基础配置

编辑 `config.py` 文件配置交易参数：

```python
TRADING_CONFIG = {
    'SYMBOL': 'ETHUSDT',           # 交易对
    'TIMEFRAME': '1h',             # 时间级别
    'INITIAL_CAPITAL': 10000,      # 初始资金
    'POSITION_SIZE_PERCENT': 0.1,  # 仓位比例
    'LEVERAGE': 1,                 # 杠杆倍数
}
```

### API配置

创建 `.env` 文件配置API密钥：

```bash
# Binance API配置
BINANCE_API_KEY=your_api_key_here
BINANCE_SECRET_KEY=your_secret_key_here

# Telegram通知配置
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 用户配置

使用 `utils/fix_config.py` 管理自定义配置：

```python
# 加载用户配置
from utils.fix_config import apply_user_config
apply_user_config()

# 保存用户配置
from utils.fix_config import save_user_config
config_data = {
    'TRADING_CONFIG': {
        'SYMBOL': 'BTCUSDT',
        'INITIAL_CAPITAL': 20000
    }
}
save_user_config(config_data)
```

## 📖 使用指南

### 运行模式

#### 1. 实时交易模式

```bash
# 启动实时交易
python38 trading.py --mode live

# 启动服务模式（后台运行）
python38 trading.py --mode service

# 启动Web管理界面
python38 trading.py --mode web

# 或使用专用启动脚本
python38 web/start.py

# 或使用专用启动脚本
python38 web/start.py
```

#### 2. Web管理界面

Web界面提供了图形化的系统管理功能：

```bash
# 启动Web界面（默认端口8082）
python38 trading.py --mode web

# 指定端口和地址
python38 trading.py --mode web --web-port 8080 --web-host 127.0.0.1

# 直接启动Web界面
python38 web/app.py --port 8082 --host 0.0.0.0
```

启动后访问：http://localhost:8082

**Web界面功能：**
- 实时系统状态监控
- 一键启动/停止交易系统
- 实时交易信号显示
- 系统资源使用率监控
- 响应式设计，支持移动端访问

#### 3. 回测模式

```bash
# 运行回测分析
python38 main.py --mode backtest

# 指定回测时间范围
python38 main.py --mode backtest --start-date 2024-01-01 --end-date 2024-12-31
```

#### 4. 信号测试模式

```bash
# 测试交易信号
python38 tools/signal_test.py

# 夏普比率分析
python38 tools/signals_sharpe.py
```

### 服务管理

#### CentOS/Linux 服务控制

```bash
# 启动服务
sudo systemctl start trading-system

# 停止服务
sudo systemctl stop trading-system

# 重启服务
sudo systemctl restart trading-system

# 查看状态
sudo systemctl status trading-system

# 查看日志
sudo journalctl -u trading-system -f

# 启用自启动
sudo systemctl enable trading-system
```

#### 手动服务创建

```bash
# 使用内置服务创建功能
python38 trading.py --create-service
```

## 🔧 服务部署

### 系统服务配置

服务文件 `trading-system.service` 配置：

```ini
[Unit]
Description=Trading System Service
After=network.target

[Service]
Type=simple
User=trading
Group=trading
WorkingDirectory=/opt/trading
ExecStart=/opt/trading/venv/bin/python /opt/trading/trading.py --mode service
Restart=always
RestartSec=10

Environment=PYTHONPATH=/opt/trading
Environment=PYTHONUNBUFFERED=1

# 安全设置
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/trading/logs

# 资源限制
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
```

### 部署检查清单

- [ ] Python38 已正确安装
- [ ] 系统依赖已安装
- [ ] Python虚拟环境已创建
- [ ] 项目文件已复制到 `/opt/trading`
- [ ] 用户权限已正确设置
- [ ] API密钥已配置
- [ ] 系统服务已启用
- [ ] 日志目录已创建
- [ ] 网络连接正常

## 🛠️ 开发指南

### 项目结构

```
trading/
├── core/                   # 核心模块
│   ├── strategy.py        # 策略实现
│   ├── data_loader.py     # 数据加载
│   ├── feature_engineer.py # 特征工程
│   ├── backtester.py      # 回测引擎
│   └── exchange_api.py    # 交易所API
├── utils/                 # 工具模块
│   ├── fix_config.py     # 用户配置管理
│   └── fix_matplotlib_fonts.py # 字体修复工具
├── tools/                 # 工具脚本
│   ├── signal_test.py    # 信号测试
│   ├── signals_sharpe.py # 性能分析
│   ├── continuous_monitor.py # 持续监控
│   ├── quick_signal.py   # 快速信号
│   └── real_time_signals.py # 实时信号
├── deepseek/              # DeepSeek集成
│   ├── deepseek_analyzer.py # DeepSeek分析器
│   ├── deepseek_signal_integrator.py # 信号集成器
│   └── quick_deepseek_demo.py # 快速演示
├── json/                  # JSON配置文件目录
│   ├── config.json   # 用户配置
│   └── api_config.json    # API配置
├── tests/                 # 测试模块
├── docs/                  # 文档目录
│   ├── DeepSeek_README.md # DeepSeek说明
│   └── DeepSeek模式配置说明.md # 配置说明
└── scripts/              # 脚本模块
    ├── install.sh        # 安装脚本
    └── trading-system.service # 服务配置
```

### 添加新策略

1. 在 `core/strategy.py` 中创建策略类：

```python
class MyStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
    
    def generate_signals(self, data):
        # 实现信号生成逻辑
        return signals
```

2. 在 `main.py` 中注册策略：

```python
from core.strategy import MyStrategy

# 使用新策略
strategy = MyStrategy(config)
```

### 扩展技术指标

在 `core/feature_engineer.py` 中添加新指标：

```python
def calculate_my_indicator(data, period=14):
    """计算自定义指标"""
    # 实现指标计算逻辑
    return indicator_values
```

## 🔍 故障排除

### 常见问题

#### 1. Python38 未找到

```bash
# 检查 Python38 安装
which python38
python38 --version

# 如果未安装，手动安装
sudo yum install -y python38 python38-pip python38-devel
```

#### 2. 权限错误

```bash
# 检查文件权限
ls -la /opt/trading/

# 修复权限
sudo chown -R trading:trading /opt/trading
sudo chmod -R 755 /opt/trading

# 修复虚拟环境权限
sudo /opt/trading/fix_permissions.sh
```

#### 3. 服务启动失败

```bash
# 检查服务状态
sudo systemctl status trading-system

# 查看详细日志
sudo journalctl -u trading-system -n 50

# 检查Python环境
sudo -u trading /opt/trading/venv/bin/python --version
```

#### 4. API连接错误

```bash
# 检查网络连接
ping api.binance.com

# 验证API密钥
python38 -c "from core.exchange_api import BinanceAPI; api = BinanceAPI(); print(api.test_connection())"
```

#### 5. 虚拟环境权限问题

```bash
# 运行权限修复
sudo bash install.sh --fix-permissions

# 或手动修复
sudo chown -R trading:trading /opt/trading/venv
sudo chmod -R 755 /opt/trading/venv
```

#### 6. urllib3 兼容性问题

```bash
# 运行 urllib3 兼容性修复
sudo bash install.sh --fix-urllib3

# 或手动修复
cd /opt/trading
source venv/bin/activate
pip uninstall -y urllib3
pip install "urllib3<2.0.0"
```

#### 7. systemd 服务文件兼容性问题

```bash
# 运行服务文件兼容性修复
sudo bash install.sh --fix-service

# 或手动修复
sudo /opt/trading/fix_service.sh

# 或手动修复
sudo sed -i '/^ReadWritePaths=/d' /etc/systemd/system/trading-system.service
sudo sed -i '/^ProtectSystem=/d' /etc/systemd/system/trading-system.service
sudo systemctl daemon-reload
```

### 日志分析

日志文件位置：
- 系统日志: `/var/log/messages`
- 服务日志: `sudo journalctl -u trading-system`
- 应用日志: `/opt/trading/logs/`

### 性能监控

```bash
# 监控系统资源
htop

# 监控服务状态
watch -n 1 'systemctl status trading-system'

# 监控日志
tail -f /opt/trading/logs/trading_signals_*.log
```

## 性能指标

### 回测性能

- **年化收益率**: 15-25%
- **最大回撤**: <10%
- **夏普比率**: >1.5
- **胜率**: >60%

### 系统性能

- **内存使用**: <500MB
- **CPU使用**: <10%
- **响应时间**: <1秒
- **稳定性**: 99.9%

## 🔒 安全说明

### API安全

- 使用只读API密钥进行数据获取
- 使用交易API密钥进行交易执行
- 定期轮换API密钥
- 设置IP白名单

### 系统安全

- 使用专用用户运行服务
- 限制文件系统访问权限
- 启用系统防火墙
- 定期更新系统补丁

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

### 贡献流程

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

### 代码规范

- 遵循 PEP 8 代码风格
- 添加适当的注释和文档
- 编写单元测试
- 确保代码通过所有测试

## 📞 联系方式

- **项目维护者**: JinJinJinJin
- **捐赠地址**: btc：jinjinjinjin.btc


## 🙏 致谢

感谢以下开源项目的支持：
- [CCXT](https://github.com/ccxt/ccxt) - 加密货币交易库
- [Pandas](https://pandas.pydata.org/) - 数据处理库
- [NumPy](https://numpy.org/) - 数值计算库
- [Matplotlib](https://matplotlib.org/) - 图表绘制库

---

**免责声明**: 本软件仅供学习和研究使用。交易有风险，投资需谨慎。使用本软件进行实际交易的风险由用户自行承担。 
