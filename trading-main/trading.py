#!/usr/bin/env python38
# -*- coding: utf-8 -*-
"""
实盘交易系统 - Trading System
支持服务模式和交互模式运行
"""

import os
import sys
import time
import signal
import logging
import argparse
import threading
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# 导入项目模块
try:
    from config import *
    from core.strategy import SharpeOptimizedStrategy
    from core.data_loader import DataLoader

    from utils.telegram_notifier import notify_signal, notify_trade, notify_status, notify_error
    from utils.fix_config import (
    apply_user_config, save_trade_history, load_trade_history
)
    from core.exchange_api import RealExchangeAPI
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保在项目根目录运行此脚本")
    sys.exit(1)

class TradingSystem:
    """实盘交易系统核心类"""

    
    def __init__(self, mode='service'):
        """初始化交易系统"""
        self.mode = mode
        self.running = False  # 初始化为False，等待start()方法启动
        self.start_time = datetime.now()
        
        # 加载用户配置
        try:
            success, message = apply_user_config()
            if success:
                print(f"{message}")
            else:
                print(f"{message}")
        except Exception as e:
            print(f"加载用户配置失败: {e}")
        
        # 初始化日志
        self.setup_logging()
        
        # 初始化真实交易API
        self.setup_real_trading()
        
        # 初始化组件
        self.setup_components()
        
        # 初始化资金管理
        self.setup_capital_management()
        
        # 设置信号处理器
        self.setup_signal_handlers()
        
        # 初始化交易状态
        self.setup_trading_state()
        
        # 策略现在是持仓状态的权威数据源
        self.logger.info(f"🔄 策略持仓状态: {self.strategy.get_position()}")
        
        self.logger.info(f"🚀 交易系统初始化完成 - 模式: {mode}")
    
    @property
    def current_position(self):
        """从策略获取当前持仓状态"""
        if hasattr(self, 'strategy') and hasattr(self.strategy, 'get_position'):
            return self.strategy.get_position()
        return 0
    
    @property
    def position_entry_price(self):
        """从策略获取开仓价格"""
        if hasattr(self, 'strategy') and hasattr(self.strategy, 'get_entry_price'):
            return self.strategy.get_entry_price()
        return 0.0
    
    @property
    def position_quantity(self):
        """从策略获取持仓数量"""
        if hasattr(self, 'strategy') and hasattr(self.strategy, 'get_position_quantity'):
            return self.strategy.get_position_quantity()
        return 0.0
    
    def _calculate_ratio(self, current_price, leverage=1.0):
        """
        统一计算盈亏比例 - 考虑杠杆倍数
        
        Args:
            current_price: 当前价格
            leverage: 杠杆倍数，默认为1.0（无杠杆）
            
        Returns:
            float: 盈亏比例
                多头时：价格上涨为正数，下跌时为负数
                空头时：价格上涨为负数，下跌时为正数
        """
        if self.current_position == 0 or self.position_entry_price == 0:
            return 0.0
        
        # 计算价格变动百分比
        price_change_pct = (current_price - self.position_entry_price) / self.position_entry_price
        
        # 根据持仓方向计算盈亏比例
        if self.current_position == 1:  # 多头
            # 多头：价格上涨时为正数，价格下跌时为负数
            ratio = price_change_pct * leverage
        elif self.current_position == -1:  # 空头
            # 空头：价格上涨时为负数，价格下跌时为正数
            ratio = -price_change_pct * leverage
        else:
            return 0.0
        
        return ratio
    
    def get_leverage(self):
        """获取当前杠杆倍数"""
        # 从策略获取当前杠杆倍数（确保同步）
        if hasattr(self, 'strategy') and hasattr(self.strategy, 'leverage'):
            return self.strategy.leverage
        return 1.0  # 默认杠杆倍数

    def set_position(self, position, entry_price=None, current_price=None):
        """设置策略的持仓状态"""
        if hasattr(self, 'strategy'):
            if hasattr(self.strategy, 'update_position_info'):
                margin_used = self.get_margin_used()
                self.strategy.update_position_info(position, entry_price or 0, current_price or 0, datetime.now(), 0.0, margin_value=margin_used)
            else:
                self.strategy.position = position
                if entry_price is not None:
                    self.strategy.entry_price = entry_price
    
    def setup_logging(self):
        """设置日志系统"""
        log_dir = Path(LOGGING_CONFIG.get('LOG_DIR', 'logs'))
        log_dir.mkdir(exist_ok=True)
        
        # 在Web模式下使用固定日志文件，避免重复创建
        if self.mode == 'web':
            log_file = log_dir / "trading_web.log"
            # 检查是否已经有日志处理器配置
            if hasattr(self, 'logger') and self.logger and self.logger.handlers:
                self.logger.info(f"📝 使用现有日志配置: {log_file}")
                return
        else:
            # 其他模式使用时间戳日志文件
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = log_dir / f"trading_other.log"
        
        # 配置日志格式
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # 配置日志处理器
        handlers = [logging.FileHandler(log_file, encoding='utf-8')]
        if LOGGING_CONFIG.get('CONSOLE_OUTPUT', True):
            handlers.append(logging.StreamHandler())
            
        logging.basicConfig(
            level=getattr(logging, LOGGING_CONFIG.get('LEVEL', 'INFO')),
            format=log_format,
            handlers=handlers
        )
        
        # 配置日志过滤
        from utils import configure_logging
        configure_logging()
        
        self.logger = logging.getLogger('TradingSystem')
        self.logger.info(f"📝 日志系统初始化完成: {log_file}")
    
    def setup_real_trading(self):
        """初始化真实交易API"""
        try:
            # 首先尝试从保存的配置中加载交易模式
            from utils.fix_config import load_user_config
            success, message, saved_config = load_user_config()
            if success and saved_config and 'TRADING_CONFIG' in saved_config:
                saved_real_trading = saved_config['TRADING_CONFIG'].get('REAL_TRADING', False)
                print(f"从保存的配置中加载交易模式: {'真实交易' if saved_real_trading else '模拟交易'}")
                self.real_trading = saved_real_trading
            
            # 加载.env文件
            load_dotenv()
            
            # 从环境变量获取API密钥
            api_key = os.getenv('BINANCE_API_KEY', '')
            secret_key = os.getenv('BINANCE_SECRET_KEY', '')
            
            # 如果环境变量没有，API密钥未配置
            if not api_key or not secret_key:
                print("未配置API密钥")
                print("💡 请在项目根目录创建 .env 文件并添加以下内容：")
                print("   BINANCE_API_KEY=你的API密钥")
                print("   BINANCE_SECRET_KEY=你的Secret密钥")
            
            if not api_key or not secret_key:
                print("未配置API密钥，将使用模拟交易模式")
                self.real_trading = False
                self.exchange_api = None
                return
            
            # 初始化真实交易API
            self.exchange_api = RealExchangeAPI(
                api_key=api_key,
                secret_key=secret_key
            )
            self.exchange_api.set_logger(self.logger)
            
            # 测试API连接
            success, message = self.exchange_api.test_connection()
            if success:
                print(" 真实交易API连接成功")
                
                # 初始化保证金类型和杠杆设置
                if self.real_trading:
                    print(" 启用真实交易模式")
                    self._initialize_margin_and_leverage()
                else:
                    print(" 保持模拟交易模式")
            else:
                print(f"真实交易API连接失败: {message}")
                print(" 强制切换到模拟交易模式")
                self.real_trading = False
                
        except Exception as e:
            print(f"初始化真实交易API失败: {e}")
            self.real_trading = False
            self.exchange_api = None
    
    def _initialize_margin_and_leverage(self):
        """初始化保证金类型和杠杆设置"""
        try:
            symbol = TRADING_CONFIG.get('SYMBOL', 'ETHUSDT')
            
            # 检查当前持仓状态
            current_position = self.exchange_api.get_position(symbol)
            current_size = current_position.get('size', 0)
            
            if current_size == 0:
                # 只有在没有开仓时才设置保证金类型和杠杆
                print(f" 初始化保证金类型和杠杆设置...")
                
                # 设置保证金类型
                margin_result = self.exchange_api.set_margin_type(symbol, 'ISOLATED')
                if margin_result['success']:
                    print(f"  ✅ 保证金类型已设置为: ISOLATED")
                else:
                    print(f"  ⚠️  设置保证金类型失败: {margin_result['error']}")
                
                # 设置杠杆
                current_leverage = self.get_leverage()
                leverage_result = self.exchange_api.set_leverage(symbol, current_leverage)
                if leverage_result['success']:
                    print(f"  ✅ 杠杆倍数已设置: {current_leverage}x")
                else:
                    error_msg = leverage_result['error']
                    if 'API权限不足' in error_msg or 'Invalid API-key' in error_msg:
                        print(f"  ⚠️  API权限不足，使用本地配置杠杆: {current_leverage}x")
                    else:
                        print(f"  ⚠️  杠杆设置警告: {error_msg}")
            else:
                print(f"  💡 当前有开仓 ({current_size})，跳过保证金类型和杠杆初始化")
                print(f"  💡 使用当前设置 - 杠杆: {current_position.get('leverage', current_leverage)}x")
                
        except Exception as e:
            print(f"  ❌ 初始化保证金类型和杠杆设置失败: {e}")
    
    def setup_components(self):
        """初始化系统组件"""
        try:
            # 数据加载器
            self.data_loader = DataLoader()
            self.logger.info("数据加载器初始化完成")
            
            # 交易策略 - 将系统模式映射为策略模式
            strategy_mode = 'realtime' if self.mode == 'web' else 'backtest'
            self.strategy = SharpeOptimizedStrategy(
                config=OPTIMIZED_STRATEGY_CONFIG,
                data_loader=self.data_loader,
                mode=strategy_mode  # 传递策略运行模式
            )
            
            # 同步杠杆倍数到策略
            self.strategy.update_leverage_from_trading_system(self)
            
            # 验证风险管理配置
            validation_result = self.strategy.validate_risk_management_config()
            if not validation_result['valid']:
                self.logger.warning("⚠️ 风险管理配置存在问题:")
                for issue in validation_result['issues']:
                    self.logger.warning(f"  - {issue}")
            if validation_result['warnings']:
                self.logger.info("📋 风险管理配置警告:")
                for warning in validation_result['warnings']:
                    self.logger.info(f"  - {warning}")
            
            self.logger.info("📈 交易策略初始化完成")
            
        except Exception as e:
            self.logger.error(f"组件初始化失败: {e}")
            raise
    
    def setup_signal_handlers(self):
        """设置信号处理器"""
        # 在web模式下跳过信号处理，避免线程问题
        if self.mode == 'web':
            self.logger.info("📡 Web模式：跳过信号处理器设置")
            return
            
        try:
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
        except Exception as e:
            self.logger.warning(f"📡 信号处理器设置失败: {e}")
    
    def setup_capital_management(self):
        """设置资金管理"""
        # 重新导入config模块以确保获取最新的配置
        import config
        
        # 获取资金配置
        capital_config = config.TRADING_CONFIG.get('CAPITAL_CONFIG', {})
        
        # 资金状态
        self.initial_capital = capital_config.get('INITIAL_CAPITAL', 10000) #初始资金
        self.current_capital = self.initial_capital #当前资金
        self.available_capital = self.initial_capital #可用资金
        
        # 仓位管理
        self.position_size_percent = capital_config.get('POSITION_SIZE_PERCENT', 0.1)
        self.max_position_size = capital_config.get('MAX_POSITION_SIZE', 0.5)
        self.min_position_size = capital_config.get('MIN_POSITION_SIZE', 0.05)
        
        # 交易配置
        self.signal_check_interval = config.TRADING_CONFIG.get('SIGNAL_CHECK_INTERVAL', 60)

        # 交易记录
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        
        # 重置每日计数
        self.reset_daily_counters()
        
        self.logger.info(f"💰 资金管理初始化完成 - 初始资金: {self.initial_capital} USDT")
        self.logger.info(f"仓位配置 - 单次: {self.position_size_percent*100}%, 最大: {self.max_position_size*100}%")
    
    def get_leverage(self):
        """统一获取杠杆倍数 - 优先从策略获取，回退到配置默认值"""
        if hasattr(self, 'strategy') and hasattr(self.strategy, 'leverage'):
            return self.strategy.leverage
        else:
            # 回退到配置默认值
            import config
            capital_config = config.TRADING_CONFIG.get('CAPITAL_CONFIG', {})
            return capital_config.get('LEVERAGE', 8)
    
    def setup_trading_state(self):
        """初始化交易状态"""
        # 交易状态 - 持仓状态完全由策略管理
        self.last_signal = 0
        self.last_trade_time = None
        self.trade_count = 0
        
        # 加载交易历史
        self.load_trade_history()
        
        # 系统监控
        self.heartbeat_interval = 30  # 心跳间隔(秒)
        self.position_monitor_interval = 60  # 持仓监控间隔(秒)
        self.last_position_update = datetime.now()
        self.logger.info("交易状态初始化完成")
    
    def reset_daily_counters(self):
        """重置每日计数器"""
        current_date = datetime.now().date()
        if not hasattr(self, 'last_reset_date') or self.last_reset_date != current_date:
            self.daily_trades = 0
            self.daily_pnl = 0.0
            self.last_reset_date = current_date
            self.logger.info("🔄 每日计数器已重置")
    
    def signal_handler(self, signum, frame):
        """信号处理器"""
        import traceback
        self.logger.info(f"📡 收到信号 {signum}，系统继续运行...")
        
        # 防止重复处理信号
        if not self.running:
            self.logger.info("📡 系统未运行，忽略信号")
            return
    
    def get_market_data(self):
        """获取市场数据 - 带缓存优化"""
        try:
            # 添加调用频率限制
            current_time = time.time()
            if hasattr(self, '_last_market_data_call'):
                time_since_last_call = current_time - self._last_market_data_call
                if time_since_last_call < 10:  # 10秒内不重复调用
                    if hasattr(self, '_cached_market_data') and self._cached_market_data is not None:
                        self.logger.debug(f"⏰ 调用频率限制：距离上次调用仅 {time_since_last_call:.1f} 秒，使用缓存数据")
                        return self._cached_market_data
            
            # 记录调用时间
            self._last_market_data_call = current_time
            
            # 计算时间范围：获取最近1000条数据
            end_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            start_date = (datetime.now() - timedelta(days=100)).strftime('%Y-%m-%d %H:%M:%S')
            
            # 获取最新K线数据（带缓存）
            klines = self.data_loader.get_klines(
                start_date=start_date,
                end_date=end_date
            )
            
            if klines is None or klines.empty:
                self.logger.warning("无法获取市场数据")
                return None
            
            # 缓存数据
            self._cached_market_data = klines
            
            # 记录数据获取信息
            if not klines.empty:
                self.logger.debug(f"📊 获取市场数据: {len(klines)} 条记录, 时间范围: {klines.index.min()} 至 {klines.index.max()}")
            
            return klines
            
        except Exception as e:
            self.logger.error(f"获取市场数据失败: {e}")
            return None
    
    def execute_trade(self, signal_info, market_data=None):
        """执行交易"""
        try:
            if signal_info is None:
                return
            
            signal_value = signal_info.get('signal', 0)
            signal_score = signal_info.get('signal_score', 0)
            
            # 记录信号
            self.logger.info(f"信号: {signal_value}, 综合评分: {signal_score:.4f}, 基础评分: {signal_info.get('base_score', 0):.4f}, 趋势评分: {signal_info.get('trend_score', 0):.4f}, 信号原因: {signal_info.get('reason', '')}, 投资建议: {signal_info.get('investment_advice', '')}")
            
            # 只处理开仓信号（平仓逻辑已在trading_loop中处理）
            if signal_value == 0 or self.current_position != 0:
                return
            
            # 获取仓位大小
            position_size = signal_info.get('position_size', {})
            if isinstance(position_size, dict):
                position_size_value = position_size.get('size', 0.0)
                position_reason = position_size.get('reason', '策略仓位管理')
            else:
                position_size_value = position_size
                position_reason = '策略仓位管理'
            
            # 确定交易方向
            trade_direction = 'long' if signal_value == 1 else 'short'
            trade_type = 'LONG' if signal_value == 1 else 'SHORT'
            order_side = 'buy' if signal_value == 1 else 'sell'
            
            # 执行交易
            success = self._execute_position_open(
                trade_direction, trade_type, order_side, 
                position_size_value, position_reason, signal_score, market_data
            )
            
            # 更新信号记录
            if success and signal_value != 0:
                self.last_signal = signal_value
                self.logger.debug(f"更新最新信号: {signal_value}")
            
        except Exception as e:
            self.logger.error(f"执行交易失败: {e}")
    
    def _execute_position_open(self, trade_direction, trade_type, order_side, 
                              position_size_value, position_reason, signal_score, market_data):
        """执行开仓操作"""
        try:
            # 计算交易金额
            usdt_amount = self.available_capital * position_size_value
            
            # 验证最小仓位要求
            if not self._validate_position_size(usdt_amount):
                return False
            
            # 获取当前价格和计算ETH数量
            current_price, eth_amount = self._calculate_trade_quantities(usdt_amount, market_data)
            if current_price is None or eth_amount is None:
                return False
            
            # 执行交易
            if self.real_trading and self.exchange_api:
                return self._execute_real_trade(trade_direction, trade_type, order_side, 
                                              usdt_amount, eth_amount, current_price, signal_score, market_data)
            else:
                return self._execute_simulated_trade(trade_direction, trade_type, 
                                                   usdt_amount, eth_amount, current_price, signal_score, market_data, position_reason)
                
        except Exception as e:
            self.logger.error(f"执行开仓操作失败: {e}")
            return False
    
    def _validate_position_size(self, usdt_amount):
        """验证仓位大小"""
        min_usdt_amount = 10.0  # 最小10 USDT
        if usdt_amount < min_usdt_amount:
            self.logger.warning(f"计算仓位过小: {usdt_amount:.2f} USDT < {min_usdt_amount} USDT，使用最小仓位")
            return False
        return True
    
    def _calculate_trade_quantities(self, usdt_amount, market_data):
        """计算交易数量和价格"""
        try:
            current_price = market_data['close'].iloc[-1] if not market_data.empty else 0
            if current_price <= 0:
                current_price = 3000  # 默认价格
                self.logger.warning("无法获取当前价格，使用默认价格3000 USDT")
            
            # 🔧 修复杠杆计算逻辑
            # usdt_amount 是策略计算的仓位大小（如10%的可用资金）
            # 在杠杆交易中，这应该作为保证金，实际持仓价值 = 保证金 × 杠杆倍数
            current_leverage = self.get_leverage()
            actual_position_value = usdt_amount * current_leverage
            
            # 计算ETH数量 - 实际持仓价值除以价格
            eth_amount = actual_position_value / current_price
            eth_amount = round(eth_amount, 3)  # 控制精度
            
            self.logger.info(f"🔧 杠杆计算 - 策略仓位: {usdt_amount:.2f} USDT, 杠杆: {current_leverage}x, 实际持仓价值: {actual_position_value:.2f} USDT, ETH数量: {eth_amount:.4f}")
            
            # 检查最小交易量
            min_eth_amount = 0.001
            if eth_amount < min_eth_amount:
                required_usdt = min_eth_amount * current_price / current_leverage  # 考虑杠杆
                if required_usdt <= self.available_capital:
                    usdt_amount = required_usdt
                    eth_amount = min_eth_amount
                    self.logger.info(f"调整交易量: 保证金={usdt_amount:.2f} USDT, ETH={eth_amount:.6f}")
                else:
                    self.logger.error(f"可用资金不足: 需要保证金{required_usdt:.2f} USDT，可用{self.available_capital:.2f} USDT")
                    return None, None
            
            return current_price, eth_amount
            
        except Exception as e:
            self.logger.error(f"计算交易数量失败: {e}")
            return None, None
    
    def _execute_real_trade(self, trade_direction, trade_type, order_side, 
                           usdt_amount, eth_amount, current_price, signal_score, market_data):
        """执行真实交易"""
        try:
            symbol = TRADING_CONFIG.get('SYMBOL', 'ETHUSDT')
            
            # 检查当前是否有开仓，如果有开仓则跳过保证金类型设置
            current_position = self.exchange_api.get_position(symbol)
            current_size = current_position.get('size', 0)
            
            if current_size == 0:
                # 只有在没有开仓时才设置保证金类型
                margin_result = self.exchange_api.set_margin_type(symbol, 'ISOLATED')
                if not margin_result['success']:
                    self.logger.warning(f"⚠️  设置保证金类型失败: {margin_result['error']}")
                else:
                    self.logger.info(f"✅ 保证金类型已设置为: ISOLATED")
            else:
                self.logger.info(f"💡 当前有开仓 ({current_size})，跳过保证金类型设置")
            
                            # 设置杠杆（只有在没有开仓时才设置）
                if current_size == 0:
                    current_leverage = self.get_leverage()
                    leverage_result = self.exchange_api.set_leverage(symbol, current_leverage)
                    if not leverage_result['success']:
                        error_msg = leverage_result['error']
                        if 'ip_info' in leverage_result:
                            error_msg += f"({leverage_result['ip_info']})"
                        
                        # 检查是否是API权限不足的错误
                        if 'Invalid API-key' in error_msg or 'permissions' in error_msg or '401' in error_msg:
                            self.logger.warning(f"⚠️  API权限不足，跳过Binance杠杆倍数修改: {error_msg}")
                            self.logger.info(f"💡 系统将使用本地配置的杠杆倍数: {current_leverage}x")
                        else:
                            self.logger.warning(f"杠杆设置警告: {error_msg}")
                    else:
                        self.logger.info(f"✅ 杠杆倍数已设置: {current_leverage}x")
                else:
                    current_leverage = self.get_leverage()
                    self.logger.info(f"💡 当前有开仓，跳过杠杆设置，使用当前杠杆: {current_position.get('leverage', current_leverage)}x")
            
            # 执行订单
            result = self.exchange_api.place_order(symbol, order_side, eth_amount)
            
            if result['success']:
                # 设置持仓状态
                position_value = 1 if trade_direction == 'long' else -1
                entry_price = current_price
                self.set_position(position_value, entry_price, current_price)
                
                # 设置策略的持仓数量和杠杆
                if hasattr(self, 'strategy'):
                    if hasattr(self.strategy, 'set_position_quantity'):
                        self.strategy.set_position_quantity(eth_amount)
                    if hasattr(self.strategy, 'set_leverage'):
                        current_leverage = self.get_leverage()
                        self.strategy.set_leverage(current_leverage)
                
                # 更新资金和记录交易 - 期货交易只扣除保证金
                margin_used = usdt_amount  # 保证金就是策略计算的仓位大小
                self.available_capital -= margin_used
                self.save_trading_status()
                
                # 记录交易 - 记录实际持仓价值（包含杠杆效果）
                quantity_sign = 1 if trade_direction == 'long' else -1
                # 从策略获取当前杠杆倍数（确保同步）
                current_leverage = self.get_leverage()
                actual_position_value = usdt_amount * current_leverage  # 实际持仓价值
                self.record_trade(trade_type, actual_position_value, signal_score, 
                                f"{trade_direction}信号触发 (评分:{signal_score:.3f})", 
                                current_price, eth_amount * quantity_sign, 0, margin_used, current_leverage)
                
                # 发送通知
                self._send_trade_notification('open', trade_direction, current_price, eth_amount, signal_score)
                
                self.logger.info(f"🟢 开{trade_direction}仓成功 - 订单ID: {result['order_id']}, ETH数量: {eth_amount:.4f}, 保证金: {margin_used:.2f} USDT (杠杆: {current_leverage}x)")
                return True
            else:
                self.logger.error(f"开{trade_direction}仓失败: {result['error']}")
                self._send_error_notification(f"开{trade_direction}仓失败: {result['error']}", "交易执行")
                return False
                
        except Exception as e:
            self.logger.error(f"执行真实交易失败: {e}")
            return False
    
    def _execute_simulated_trade(self, trade_direction, trade_type, 
                                usdt_amount, eth_amount, current_price, signal_score, market_data, position_reason):
        """执行模拟交易"""
        try:
            # 设置持仓状态
            position_value = 1 if trade_direction == 'long' else -1
            self.set_position(position_value, current_price, current_price)
            
            # 设置策略的持仓数量
            if hasattr(self, 'strategy') and hasattr(self.strategy, 'set_position_quantity'):
                self.strategy.set_position_quantity(eth_amount)
            
            # 更新资金和记录交易 - 期货交易只扣除保证金
            margin_used = usdt_amount  # 保证金就是策略计算的仓位大小
            self.available_capital -= margin_used
            
            # 记录交易 - 记录实际持仓价值（包含杠杆效果）
            quantity_sign = 1 if trade_direction == 'long' else -1
            # 从策略获取当前杠杆倍数（确保同步）
            current_leverage = self.get_leverage()
            actual_position_value = usdt_amount * current_leverage  # 实际持仓价值
            self.record_trade(trade_type, actual_position_value, signal_score, 
                            f"模拟{trade_direction}信号 (评分:{signal_score:.3f})", 
                            current_price, eth_amount * quantity_sign, 0, margin_used, current_leverage)
            
            # 发送通知
            self._send_trade_notification('open', trade_direction, current_price, eth_amount, signal_score, is_simulated=True)
            
            self.logger.info(f"🟢 模拟开{trade_direction}仓 - 保证金: {margin_used:,.2f} USDT, 仓位: {margin_used/self.initial_capital:.1%} (杠杆: {current_leverage}x, {position_reason})")
            return True
            
        except Exception as e:
            self.logger.error(f"执行模拟交易失败: {e}")
            return False
    
    def _send_trade_notification(self, action, direction, price, quantity, signal_score, is_simulated=False):
        """发送交易通知"""
        try:
            prefix = "模拟" if is_simulated else ""
            reason = f"{prefix}{direction}信号 (评分:{signal_score:.3f})"
            notify_trade(action, direction, price, quantity, None, reason)
        except Exception as e:
            self.logger.warning(f"Telegram通知发送失败: {e}")
    
    def _send_error_notification(self, error_msg, context):
        """发送错误通知"""
        try:
            notify_error(error_msg, context)
        except Exception as e:
            self.logger.warning(f"Telegram错误通知发送失败: {e}")
    
    def save_trading_status(self):
        """保存交易系统状态到JSON文件"""
        try:
            from pathlib import Path
            from datetime import datetime
            
            # 确保json目录存在
            json_dir = Path('json')
            json_dir.mkdir(exist_ok=True)
            
            # 准备状态数据
            status_data = {
                'timestamp': datetime.now().isoformat(),
                'current_position': self.current_position,
                'position_entry_price': self.position_entry_price,
                'current_capital': getattr(self, 'current_capital', 0),
                'available_capital': getattr(self, 'available_capital', 0),
                'total_pnl': getattr(self, 'total_pnl', 0),
                'daily_pnl': getattr(self, 'daily_pnl', 0),
                'trade_count': getattr(self, 'trade_count', 0),
                'daily_trades': getattr(self, 'daily_trades', 0),
                'last_trade_time': getattr(self, 'last_trade_time', None),
                'leverage': self.get_leverage(),
                'real_trading': getattr(self, 'real_trading', False)
            }
            
            # 转换datetime对象为字符串
            if status_data['last_trade_time'] and hasattr(status_data['last_trade_time'], 'isoformat'):
                status_data['last_trade_time'] = status_data['last_trade_time'].isoformat()
            
            # 保存到文件
            trading_file = json_dir / 'trading_status.json'
            with open(trading_file, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, indent=2, ensure_ascii=False)
            
            if self.logger:
                self.logger.debug(f"交易状态已保存: {trading_file}")
            
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"保存交易状态失败: {e}")
            return False
    
    def record_trade(self, trade_type, amount, signal_score, reason="", price=0, quantity=0, pnl=None, margin=None, leverage=None):
        """记录交易"""
        try:
            self.trade_count += 1
            self.daily_trades += 1
            self.last_trade_time = datetime.now()
            
            # 如果没有传入保证金和杠杆，使用系统默认值
            current_leverage = self.get_leverage()
            if margin is None:
                margin = amount / current_leverage if current_leverage > 0 else amount
            if leverage is None:
                leverage = current_leverage
            
            trade_record = {
            'timestamp': self.last_trade_time,
            'type': trade_type,
            'amount': amount,
            'reason': reason,
            'price': price,
            'quantity': quantity,
            'signal_score': signal_score,
            'pnl': pnl,
            'position': self.current_position,
            'capital': self.current_capital,
            'available_capital': self.available_capital,
            'margin': margin,
            'leverage': leverage
            }

            self.trade_history.append(trade_record)
            self.save_trade_history()
            self.logger.info(f"📝 交易记录: {trade_type} - 金额: {amount:,.0f} USDT, 保证金: {margin:,.2f} USDT, 杠杆: {leverage}x, 评分: {signal_score:.4f}, 理由: {reason}")

        except Exception as e:
            self.logger.error(f"❌ 记录交易失败: {e}")

    def load_trade_history(self):   
        """从文件加载交易历史"""
        try:
            success, message, history_data = load_trade_history()   # 从文件加载交易历史    
            
            if success:
                self.trade_history = history_data
                self.logger.info(f"✅ {message}")
            else:
                self.logger.error(f"❌ {message}")
                self.trade_history = []
                
        except Exception as e:
            self.logger.error(f"❌ 加载交易历史失败: {e}")
            self.trade_history = []

    def save_trade_history(self):
        """保存交易历史到文件"""
        try:
            success, message = save_trade_history(self.trade_history)
            if success:
                self.logger.info(f"✅ {message}")
            else:
                self.logger.error(f"❌ {message}")
        except Exception as e:
            self.logger.error(f"❌ 保存交易历史失败: {e}")

    #平仓函数
    def _close_position_common(self, close_type, reason, market_data, signal_score=0):
        """通用平仓逻辑"""
        try:
            position_desc = "多头" if self.current_position == 1 else "空头"
            current_price = market_data['close'].iloc[-1] if not market_data.empty else 0
            
            # 获取当前持仓信息用于通知
            current_position_side = 'long' if self.current_position == 1 else 'short'
            # 从策略获取持仓数量
            current_position_quantity = 0.0
            if hasattr(self, 'strategy') and hasattr(self.strategy, 'position_quantity'):
                current_position_quantity = getattr(self.strategy, 'position_quantity', 0.0)
            
            # 添加调试日志
            self.logger.info(f"🔍 平仓数据 - 系统记录: 数量={current_position_quantity:.4f} ETH, 开仓价={self.position_entry_price:.2f}, 当前价={current_price:.2f}")
            
            # 计算已实现盈亏
            realized_pnl = 0
            if self.current_position != 0:  # 只要有持仓就计算盈亏
                # 使用策略的盈亏计算方法，传入杠杆参数
                if hasattr(self, 'strategy') and hasattr(self.strategy, 'calculate_unrealized_pnl'):
                    # 从策略获取当前杠杆倍数（确保同步）
                    current_leverage = self.get_leverage()
                    pnl_result = self.strategy.calculate_unrealized_pnl(current_price, current_leverage)
                    realized_pnl = pnl_result['pnl']
                else:
                    # 回退到简单计算
                    if self.current_position == 1:  # 多头
                        realized_pnl = (current_price - self.position_entry_price) * 0.1
                    elif self.current_position == -1:  # 空头
                        realized_pnl = (self.position_entry_price - current_price) * 0.1
                
                # 构建持仓信息用于日志记录
                position_info = {
                    'position_desc': position_desc,
                    'position_type': current_position_side,
                    'entry_price': self.position_entry_price,
                    'close_price': current_price,
                    'quantity': current_position_quantity
                }
                
               
            # 设置策略持仓状态为无持仓
            self.set_position(0, 0, current_price)
            
            # 清零策略的持仓数量
            if hasattr(self, 'strategy') and hasattr(self.strategy, 'set_position_quantity'):
                self.strategy.set_position_quantity(0.0)
        
            self.available_capital = self.current_capital
            
            # 计算交易金额（持仓价值）
            trade_amount = abs(current_position_quantity * current_price) if current_position_quantity != 0 else 0
            
            # 获取当前信号评分（从策略获取）
            current_signal_score = 0.0
            if hasattr(self, 'strategy') and hasattr(self.strategy, 'last_signal'):
                current_signal_score = self.strategy.last_signal.get('signal_score', 0.0)
            
            # 记录交易 - 传递正确的交易金额和信号评分
            # 计算保证金（从持仓价值反推）
            # 从策略获取当前杠杆倍数（确保同步）
            current_leverage = self.get_leverage()
            margin_used = trade_amount / current_leverage if current_leverage > 0 else trade_amount
            self.record_trade(close_type, trade_amount, current_signal_score, reason, current_price, current_position_quantity, realized_pnl, margin_used, current_leverage)
            
            if self.real_trading and self.exchange_api:
                # 真实平仓
                symbol = TRADING_CONFIG.get('SYMBOL', 'ETHUSDT')
                result = self.exchange_api.close_position(symbol)
                
                if result['success']:
                    self.logger.info(f"⚪ 真实{close_type}成功 ({position_desc}) - {reason}")
                    
                    # 发送Telegram通知
                    try:
                        close_reason = f"真实{close_type} ({reason}) - {position_desc}"
                        # 使用系统内部记录的持仓数量，而不是交易所返回的数量
                        notify_trade('close', current_position_side, 
                                   current_price, abs(current_position_quantity), realized_pnl, close_reason)
                    except Exception as e:
                        self.logger.warning(f"Telegram通知发送失败: {e}")
                else:
                    self.logger.error(f"真实{close_type}失败: {result['error']}")
                    # 发送错误通知
                    try:
                        notify_error(f"{close_type}失败: {result['error']}", "真实交易执行")
                    except Exception as e:
                        self.logger.warning(f"Telegram错误通知发送失败: {e}")
            else:
                # 模拟平仓
                self.logger.info(f"⚪ 模拟{close_type} ({position_desc}) - {reason}")
                
                # 发送Telegram通知
                try:
                    close_reason = f"模拟{close_type} ({reason}) - {position_desc}"
                    notify_trade('close', current_position_side, 
                               current_price, abs(current_position_quantity), realized_pnl, close_reason)
                except Exception as e:
                    self.logger.warning(f"Telegram通知发送失败: {e}")
            
        except Exception as e:
            self.logger.error(f"执行{close_type}失败: {e}")
    
    def execute_risk_management_close(self, risk_action, risk_reason, market_data):
        """执行风险管理平仓（止损/止盈）"""
        position_desc = "多头" if self.current_position == 1 else "空头"
        reason = f"{risk_action} ({risk_reason}) - {position_desc}"
        
        # 获取当前信号评分
        current_signal_score = 0.0
        if hasattr(self, 'strategy') and hasattr(self.strategy, 'last_signal'):
            current_signal_score = self.strategy.last_signal.get('signal_score', 0.0)
        
        self._close_position_common('RISK_CLOSE', reason, market_data, current_signal_score)
    
    def trading_loop(self):
        """主交易循环 - 完全按照回测逻辑修改"""
        self.logger.info("🔄 开始交易循环")
        
        while self.running:
            try:
                # 获取市场数据
                market_data = self.get_market_data()
                if market_data is None:
                    # 使用更短的睡眠间隔，定期检查停止标志
                    for _ in range(30):  # 30秒，每秒检查一次
                        if not self.running:
                            break
                        time.sleep(2)
                    continue
                
                # 获取当前价格和时间
                current_price = market_data['close'].iloc[-1] if not market_data.empty else 0
                current_time = datetime.now()
                
                # 创建增强的行数据
                current_row = market_data.iloc[-1]
                enhanced_row = {'row_data': current_row.to_dict(), 'multi_timeframe_data': None}
                
                # 标记是否在当前时间点执行了平仓
                position_closed_this_time = False
                
                # ===== 策略持仓状态管理（策略现在是权威数据源） =====
                # 更新策略的持仓信息（每次循环都执行）
                if hasattr(self.strategy, 'update_position_info'):
                    margin_used = self.get_margin_used()
                    self.strategy.update_position_info(self.current_position, self.position_entry_price, current_price, current_time, 0.0, margin_value=margin_used)
                
                # ===== 持仓状态下的风险管理检查（优先级最高） =====
                if self.current_position != 0 and hasattr(self.strategy, 'check_risk_management'):
                    try:
                        # 执行策略的风险管理检查
                        risk_action, risk_reason = self.strategy.check_risk_management(
                            current_price, enhanced_row, current_time
                        )
                        
                        self.logger.info(f"🔍 风险管理结果 - 动作: {risk_action}, 原因: {risk_reason}")
                        
                        if risk_action == 'stop_loss':
                            self.logger.info(f"🚨 策略触发止损 - 原因: {risk_reason}")
                            self.execute_risk_management_close(risk_action, risk_reason, market_data)
                            position_closed_this_time = True

                        elif risk_action == 'take_profit':
                            self.logger.info(f"🟢 策略触发止盈 - 原因: {risk_reason}")
                            self.execute_risk_management_close(risk_action, risk_reason, market_data)
                            position_closed_this_time = True
                            
                        elif risk_action == 'hold':
                            # 继续持仓，但继续执行信号检测
                            self.logger.debug(f"📊 持仓状态 - 继续执行信号检测")
                    except Exception as e:
                        self.logger.error(f"策略风险管理检查异常: {e}")
                        # 策略风险管理检查失败时，记录错误但不进行兜底处理
                        # 兜底止损逻辑已移至策略内部统一管理
                elif self.current_position == 0:
                    # 无持仓状态，记录调试信息
                    self.logger.debug(f"📊 无持仓状态 - 跳过风险管理检查，直接执行信号检测")
                
                # ===== 检查冷却处理（记录但不跳过信号检测） =====
                cooldown_active = False
                if hasattr(self.strategy, 'cooldown_manager') and hasattr(self.strategy.cooldown_manager, 'should_skip_trade'):
                    cooldown_active = self.strategy.cooldown_manager.should_skip_trade(self.strategy.enable_cooldown_treatment)
                    if cooldown_active:
                        self.logger.info(f"⏸️ 冷却处理中 - 继续检测信号但不执行交易")
                        # 记录冷却处理状态信息
                        if hasattr(self.strategy.cooldown_manager, 'get_status'):
                            status = self.strategy.cooldown_manager.get_status()
                            self.logger.info(f"冷却处理状态 - 级别: {status.get('cooldown_treatment_level', 0)}, "
                                          f"已跳过: {status.get('skipped_trades_count', 0)}/{status.get('max_skip_trades', 0)}")
                
                # ===== 获取交易信号 =====
                try:
                    signal_info = self.strategy.generate_signals(market_data, verbose=False)
                    signal = signal_info.get('signal', 0)  # 从字典中提取信号值
                    
                    # 发送信号通知（每次生成信号都发送）
                    try:
                        signal_score = signal_info.get('signal_score', 0.0)
                        signal_reason = signal_info.get('reason', '')
                        investment_advice = signal_info.get('investment_advice', '')
                        
                        # 获取信号来源
                        signal_from = signal_info.get('signal_from', 'unknown')
                        
                        # 发送Telegram信号通知
                        notify_signal(signal, current_price, signal_score, signal_reason, investment_advice, signal_from)
                    except Exception as e:
                        self.logger.warning(f"Telegram信号通知发送失败: {e}")
                    
                    # 处理交易信号 - 持仓状态下继续检测信号但不开仓
                    if signal != 0:
                        # 添加调试信息
                        self.logger.debug(f"[{current_time}] 检测到信号 - signal: {signal}, position: {self.current_position}, position_closed_this_time: {position_closed_this_time}")
                        
                        # 记录交易信号到日志
                        signal_type = "多头" if signal == 1 else "空头"
                        position_status = "持仓中" if self.current_position != 0 else "无持仓"
                        self.logger.info(f"信号: {signal_type} | 价格: {current_price:.2f} | 状态: {position_status}")
                        
                        # 检查是否在冷却期间
                        if cooldown_active:
                            # 冷却期间记录信号但不执行交易
                            signal_score = signal_info.get('signal_score', 0.0)
                            self.logger.info(f"⏸️ 冷却期间检测到{signal_type}信号 (评分: {signal_score:.3f}) - 跳过交易执行")
                        # 只在无持仓状态下执行开仓
                        elif self.current_position == 0 and not position_closed_this_time:
                            # 使用策略的开仓检查方法
                            if hasattr(self.strategy, 'should_open_position'):
                                should_open = self.strategy.should_open_position(signal, enhanced_row, current_time)
                                if should_open is False:
                                    self.logger.info(f"📊 策略拒绝开仓 - 信号: {signal_type}, 评分: {signal_score:.3f}")
                                    # 不执行continue，继续执行后续逻辑
                                else:
                                    # 执行开仓
                                    self.execute_trade(signal_info, market_data)
                                    
                                    # 更新策略的持仓信息
                                    if hasattr(self.strategy, 'update_position_info'):
                                        # 获取信号评分
                                        signal_score = signal_info.get('signal_score', 0.0)
                                        margin_used = self.get_margin_used()
                                        self.strategy.update_position_info(self.current_position, self.position_entry_price, current_price, current_time, signal_score, margin_value=margin_used)
                        else:
                            # 持仓状态下记录信号但不执行交易
                            signal_score = signal_info.get('signal_score', 0.0)
                            self.logger.info(f"📊 持仓状态下检测到{signal_type}信号 (评分: {signal_score:.3f}) - 继续监控")
                    
                except Exception as e:
                    self.logger.error(f"获取信号异常: {e}")
                
                # 等待下次循环 - 使用更短的睡眠间隔，定期检查停止标志
                signal_check_interval = TRADING_CONFIG.get('SIGNAL_CHECK_INTERVAL', 300)
                for _ in range(signal_check_interval):  # 每秒检查一次停止标志
                    if not self.running:
                        self.logger.info("🛑 检测到停止信号，退出交易循环")
                        break
                    time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"交易循环异常: {e}")
                # 异常情况下也使用更短的睡眠间隔
                for _ in range(30):
                    if not self.running:
                        break
                    time.sleep(1)
    
    def get_position_info(self):
        """获取持仓信息 - 为Web界面提供数据"""
        try:
            # 获取策略中的持仓数量
            position_quantity = 0.0
            if hasattr(self, 'strategy') and hasattr(self.strategy, 'position_quantity'):
                position_quantity = getattr(self.strategy, 'position_quantity', 0.0)
            
            # 如果持仓数量为0，则视为无仓位
            if position_quantity == 0.0:
                return {
                    'position_desc': '无仓位',
                    'position_direction': 0,
                    'position_type': 'none',
                    'entry_price': 0.0,
                    'quantity': 0.0,
                    'value': 0.0,
                    'unrealized_pnl': 0.0,
                    'unrealized_pnl_percent': 0.0,
                    'is_profitable': False,
                    'position_status': '无持仓'
                }
            
            # 有持仓时，获取持仓信息
            position_desc = {1: '多头', -1: '空头', 0: '无仓位'}.get(self.current_position, '未知')
            
            # 获取当前价格
            current_price = None
            if hasattr(self, '_cached_market_data') and self._cached_market_data is not None:
                current_price = self._cached_market_data['close'].iloc[-1]
            else:
                market_data = self.get_market_data()
                if market_data is not None and not market_data.empty:
                    current_price = market_data['close'].iloc[-1]
            
            # 计算未实现盈亏
            unrealized_pnl = 0.0
            unrealized_pnl_percent = 0.0
            if hasattr(self, 'strategy') and hasattr(self.strategy, 'calculate_unrealized_pnl'):
                try:
                    pnl_result = self.strategy.calculate_unrealized_pnl(current_price)
                    unrealized_pnl = pnl_result.get('pnl', 0.0)
                    unrealized_pnl_percent = pnl_result.get('percentage', 0.0)
                except Exception as e:
                    self.logger.warning(f"计算未实现盈亏失败: {e}")
            
            # 计算持仓价值
            position_value = position_quantity * current_price if current_price is not None else 0.0
            
            return {
                'position_desc': position_desc,
                'position_direction': self.current_position,
                'position_type': 'long' if self.current_position == 1 else 'short',
                'entry_price': self.position_entry_price,
                'quantity': position_quantity,
                'value': position_value,
                'unrealized_pnl': unrealized_pnl,
                'unrealized_pnl_percent': unrealized_pnl_percent,
                'is_profitable': unrealized_pnl > 0,
                'position_status': '盈利' if unrealized_pnl > 0 else '亏损' if unrealized_pnl < 0 else '持平',
                'current_price': current_price
            }
            
        except Exception as e:
            self.logger.error(f"获取持仓信息失败: {e}")
            return {
                'position_desc': '未知',
                'position_direction': 0,
                'position_type': 'none',
                'entry_price': 0.0,
                'quantity': 0.0,
                'value': 0.0,
                'unrealized_pnl': 0.0,
                'unrealized_pnl_percent': 0.0,
                'is_profitable': False,
                'position_status': '异常',
                'current_price': 0.0
            }
    
    def get_current_pnl_info(self):
        """获取当前盈亏信息 - 为Web界面提供数据"""
        try:
            # 获取当前价格
            current_price = None
            if hasattr(self, '_cached_market_data') and self._cached_market_data is not None:
                current_price = self._cached_market_data['close'].iloc[-1]
            else:
                market_data = self.get_market_data()
                if market_data is not None and not market_data.empty:
                    current_price = market_data['close'].iloc[-1]
            
            # 检查是否有实际持仓
            position_quantity = 0.0
            if hasattr(self, 'strategy') and hasattr(self.strategy, 'position_quantity'):
                position_quantity = getattr(self.strategy, 'position_quantity', 0.0)
            
            # 计算未实现盈亏
            unrealized_pnl = 0.0
            if position_quantity > 0.0 and hasattr(self, 'strategy') and hasattr(self.strategy, 'calculate_unrealized_pnl'):
                try:
                    # 传入杠杆参数，确保盈亏计算考虑杠杆倍数
                    # 从策略获取当前杠杆倍数（确保同步）
                    current_leverage = self.get_leverage()
                    pnl_result = self.strategy.calculate_unrealized_pnl(current_price, current_leverage)
                    unrealized_pnl = pnl_result.get('pnl', 0.0)
                    
                    # 记录杠杆效果（用于调试）
                    leverage_effect = pnl_result.get('leverage_effect', '')
                    if leverage_effect:
                        self.logger.debug(f"杠杆盈亏计算: {leverage_effect}")
                        
                except Exception as e:
                    self.logger.warning(f"计算未实现盈亏失败: {e}")
            
            # 总盈亏 = 已实现盈亏 + 未实现盈亏
            total_current_pnl = self.total_pnl + unrealized_pnl
            
            return {
                'realized_pnl': self.total_pnl,
                'unrealized_pnl': unrealized_pnl,
                'total_pnl': total_current_pnl,
                'daily_pnl': self.daily_pnl,
                'current_capital': self.current_capital,
                'available_capital': self.available_capital,
                'position_direction': self.current_position,
                'position_desc': {1: '多头', -1: '空头', 0: '无仓位'}.get(self.current_position, '未知')
            }
            
        except Exception as e:
            self.logger.error(f"获取盈亏信息失败: {e}")
            return {
                'realized_pnl': self.total_pnl,
                'unrealized_pnl': 0.0,
                'total_pnl': self.total_pnl,
                'daily_pnl': self.daily_pnl,
                'current_capital': self.current_capital,
                'available_capital': self.available_capital,
                'position_direction': 0,
                'position_desc': '未知'
            }
    
    def start(self):
        """启动交易系统"""
        if self.running:
            self.logger.warning("系统已在运行中")
            return False, "系统已在运行中"
        
        try:
            self.running = True
            self.logger.info("🚀 启动交易系统")
            
            # 发送系统启动通知
            try:
                notify_status('start', '交易系统启动', 
                             f'ETHUSDT交易系统已成功启动\n'
                             f'运行模式: {self.mode}\n'
                             f'初始资金: {self.initial_capital:,.0f} USDT\n'
                             f'正在监控市场信号...')
            except Exception as e:
                self.logger.warning(f"Telegram启动通知发送失败: {e}")
            
            # 启动交易线程
            self.trading_thread = threading.Thread(target=self.trading_loop, daemon=True)
            self.trading_thread.start()
            
            if self.mode == 'web':
                # Web模式下只启动线程，不进入服务循环
                self.logger.info("🌐 Web模式启动 - 线程已启动，等待Web界面控制")
                return True, "交易系统启动成功"
            else:
                self.service_mode()
                
            return True, "交易系统启动成功"
            
        except Exception as e:
            self.running = False
            self.logger.error(f"启动失败: {e}")
            return False, f"启动失败: {str(e)}"


    def stop(self, force_close_position=False):
        """停止交易系统"""
        if not self.running:
            return True, "系统未在运行"
        
        self.logger.info("🛑 正在停止交易系统...")
        
        # 设置停止标志
        self.running = False
        
        # 保存系统状态
        try:
            self.logger.info("💾 正在保存持仓数据...")
            if hasattr(self, 'strategy') and hasattr(self.strategy, 'save_strategy_status'):
                self.strategy.save_strategy_status()
            else:
                self.logger.warning("策略对象不存在或没有save_strategy_status方法")
        except Exception as e:
            self.logger.error(f"保存持仓数据失败: {e}")
        
        try:
            self.logger.info("💾 正在保存交易历史...")
            self.save_trade_history()
        except Exception as e:
            self.logger.error(f"保存交易历史失败: {e}")
        
        # 等待交易线程结束
        try:
            if hasattr(self, 'trading_thread') and self.trading_thread and self.trading_thread.is_alive():
                self.logger.info("⏳ 等待交易线程结束...")
                self.trading_thread.join(timeout=15)  # 增加超时时间到15秒
                if self.trading_thread.is_alive():
                    self.logger.warning("⚠️ 交易线程未在超时时间内结束，但系统将继续停止")
                else:
                    self.logger.info("✅ 交易线程已结束")
        except Exception as e:
            self.logger.error(f"❌ 等待交易线程时出错: {e}")
        
        # 检查并等待其他可能存在的线程
        thread_attributes = ['heartbeat_thread', 'interactive_thread', 'monitor_thread']
        for thread_name in thread_attributes:
            try:
                if hasattr(self, thread_name) and getattr(self, thread_name) and getattr(self, thread_name).is_alive():
                    self.logger.info(f"⏳ 等待{thread_name}结束...")
                    getattr(self, thread_name).join(timeout=5)
                    if getattr(self, thread_name).is_alive():
                        self.logger.warning(f"⚠️ {thread_name}未在超时时间内结束")
                    else:
                        self.logger.info(f"✅ {thread_name}已结束")
            except Exception as e:
                self.logger.error(f"❌ 等待{thread_name}时出错: {e}")
        
        # 清理资源
        try:
            # 关闭数据库连接（如果有的话）
            if hasattr(self, 'db_connection') and self.db_connection:
                self.db_connection.close()
                self.logger.info("✅ 数据库连接已关闭")
        except Exception as e:
            self.logger.warning(f"关闭数据库连接时出错: {e}")
        
        # 发送系统停止通知
        try:
            uptime = datetime.now() - self.start_time
            notify_status('stop', '交易系统停止', 
                         f'交易系统已停止\n'
                         f'运行时间: {str(uptime).split(".")[0]}\n'
                         f'总交易次数: {self.trade_count}\n'
                         f'当前资金: {self.current_capital:,.0f} USDT\n'
                         f'总盈亏: {self.total_pnl:,.2f} USDT')
        except Exception as e:
            self.logger.warning(f"Telegram停止通知发送失败: {e}")
        
        self.logger.info("✅ 交易系统已停止")
        return True, "交易系统已成功停止"
    
    def service_mode(self):
        """服务模式运行 - 持续监控信号并记录日志"""
        self.logger.info("🔧 服务模式运行中 - 开始持续信号监控...")
        
        # 显示当前持仓状态
        if self.current_position != 0:
            position_desc = {1: '多头', -1: '空头'}.get(self.current_position, '未知')
            # 从策略获取持仓数量
            if hasattr(self, 'strategy') and hasattr(self.strategy, 'position_quantity'):
                position_quantity = self.strategy.position_quantity
            else:
                position_quantity = 0.1  # 默认持仓数量
            position_value = position_quantity * self.position_entry_price if self.position_entry_price > 0 else 0
            print(f"\n当前持仓状态:")
            print(f"  当前仓位: {position_desc}")
            print(f"  持仓数量: {position_quantity:.4f}")
            print(f"  持仓价值: {position_value:,.0f} USDT")
            print(f"  入场价格: {self.position_entry_price:.2f}")
            
            # 计算未实现盈亏
            try:
                if hasattr(self, 'strategy') and hasattr(self.strategy, 'calculate_unrealized_pnl'):
                    pnl_result = self.strategy.calculate_unrealized_pnl()
                    unrealized_pnl = pnl_result['pnl']
                    print(f"  未实现盈亏: {unrealized_pnl:,.2f} USDT")
                else:
                    print(f"  未实现盈亏: 计算中...")
            except:
                print(f"  未实现盈亏: 计算中...")
        else:
            print(f"\n当前无持仓")
        
        print(f"📈 交易统计:")
        print(f"  总交易次数: {self.trade_count}")
        print(f"  当前资金: {self.current_capital:,.0f} USDT")
        print(f"  总盈亏: {self.total_pnl:,.2f} USDT")
        print(f"  今日盈亏: {self.daily_pnl:,.2f} USDT")
        print()
        
        # 导入持续监控模块
        try:
            from tools.continuous_monitor import SignalMonitor
            monitor = SignalMonitor()
            self.logger.info(" 信号监控模块初始化完成")
        except Exception as e:
            self.logger.error(f"信号监控模块初始化失败: {e}")
            # 系统继续运行
            return
        
        # 设置监控间隔（秒）
        monitor_interval = 3600  # 每1小时检查一次，与DeepSeek缓存时间协调
        iteration = 0
        
        try:
            while self.running:
                iteration += 1
                current_time = datetime.now()
                
                # 记录监控开始
                self.logger.info(f"📡 第{iteration}次信号检查 - {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # 获取当前信号
                try:
                    signal_info, current_data = monitor.get_current_signal()
                    
                    # 修复pandas Series布尔判断问题
                    if signal_info is not None and current_data is not None:
                        # 简化信号信息记录（原 log_signal_info 和 check_and_execute_trade 逻辑已整合到 trading_loop）
                        signal = signal_info.get('signal', 0)
                        signal_score = signal_info.get('signal_score', 0)
                        signal_desc = {1: '做多', -1: '做空', 0: '观望'}.get(signal, '未知')
                        self.logger.info(f"第{iteration}次信号 - {signal_desc} (评分: {signal_score:.3f})")
                        self.last_signal = signal
                    else:
                        self.logger.warning(f"第{iteration}次检查 - 无法获取信号数据")
                except Exception as e:
                    self.logger.error(f"第{iteration}次信号检查失败: {e}")
                    import traceback
                    self.logger.error(f"异常堆栈: {traceback.format_exc()}")
                
                # 每10次检查记录一次系统状态
                if iteration % 10 == 0:
                    pass  # 系统状态记录已移除
                
                # 等待下次检查，分段等待以便及时响应停止信号
                for _ in range(monitor_interval):
                    if not self.running:
                        break
                    time.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("📡 收到中断信号，系统继续运行...")
        except Exception as e:
            import traceback
            self.logger.error(f"服务模式异常: {e}")
            self.logger.error(f"异常堆栈: {traceback.format_exc()}")
            # 异常情况下系统继续运行
    
    def generate_signals(self, market_data=None):
        """
        生成交易信号 - 供Web界面调用
        
        Args:
            market_data: 市场数据，如果为None则自动获取
            
        Returns:
            dict: 信号信息字典
        """
        try:
            if market_data is None:
                # 优先使用缓存的市场数据
                if hasattr(self, '_cached_market_data') and self._cached_market_data is not None:
                    market_data = self._cached_market_data
                else:
                    # 缓存中没有数据时才调用get_market_data
                    market_data = self.get_market_data()
            
            if market_data is None or market_data.empty:
                return {'signal': 0, 'reason': '无法获取市场数据'}
            
            # 使用策略生成信号
            signal_info = self.strategy.generate_signals(market_data, verbose=False)
            
            # 添加持仓状态信息
            signal_info['current_position'] = self.current_position
            signal_info['position_status'] = '持仓中' if self.current_position != 0 else '无持仓'
            
            return signal_info
            
        except Exception as e:
            self.logger.error(f"生成信号异常: {e}")
            return {'signal': 0, 'reason': f'信号生成异常: {e}'}

    def get_margin_used(self):
        """获取当前使用的保证金值"""
        try:
            # 如果有策略，优先从策略获取保证金
            if hasattr(self, 'strategy') and hasattr(self.strategy, 'get_margin_value'):
                return self.strategy.get_margin_value()
            
            # 如果没有策略或策略没有保证金信息，计算保证金
            if self.current_position != 0 and self.position_entry_price > 0:
                # 从可用资金变化计算保证金
                # 这里假设保证金等于初始资金减去当前可用资金
                margin_used = self.initial_capital - self.available_capital
                return max(0, margin_used)  # 确保不为负数
            
            return 0.0
        except Exception as e:
            self.logger.warning(f"获取保证金失败: {e}")
            return 0.0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='实盘交易系统')
    parser.add_argument('--mode', choices=['service', 'web'], 
                       default='service', help='运行模式')

    parser.add_argument('--config', type=str, help='配置文件路径')
    parser.add_argument('--web-port', type=int, default=8082, help='Web界面端口')
    parser.add_argument('--web-host', default='0.0.0.0', help='Web界面监听地址')
    
    args = parser.parse_args()
    
    # Web模式特殊处理
    if args.mode == 'web':
        try:
            from web.app import main as web_main
            import sys
            sys.argv = [sys.argv[0], '--host', args.web_host, '--port', str(args.web_port)]
            web_main()
            return
        except ImportError as e:
            print(f"Web界面模块导入失败: {e}")
            print("请确保已安装Flask依赖: pip install Flask Flask-SocketIO")
            return
    
    # 使用默认模式或指定模式
    mode = args.mode
    
    # 使用默认配置
    print("🚀 实盘交易系统启动中...")
    
    # 创建并启动交易系统
    trading_system = None
    try:
        trading_system = TradingSystem(mode=mode)
        trading_system.start()
    except KeyboardInterrupt:
        print("\n📡 收到中断信号，系统继续运行...")
    except Exception as e:
        print(f"系统启动失败: {e}")
        import traceback
        print(f"异常堆栈: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == '__main__':
    main() 