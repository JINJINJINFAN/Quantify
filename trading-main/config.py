# -*- coding: utf-8 -*-
# ============================================================================
# 基础配置参数
# ============================================================================

import os
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

# 交易对与时间级别配置
TRADING_CONFIG = {
    'SYMBOL': 'WLFIUSDT',
    'TIMEFRAME': '1h',
    'TIMEFRAME_DAY': '1D',
    'TESTTIME': '2025-06-02 14:00:00',
    'SIGNAL_CHECK_INTERVAL': 300,  # 信号检查间隔(秒)
    
    # 资金管理配置
    'CAPITAL_CONFIG': {
        'INITIAL_CAPITAL': 100,        # 初始资金 (USDT)
        'POSITION_SIZE_PERCENT': 0.1,    # 每次开仓资金比例 (10%)
        'MAX_POSITION_SIZE': 0.55,        # 最大仓位比例 (50%)
        'MIN_POSITION_SIZE': 0.06,       # 最小仓位比例 (5%)
        'LEVERAGE': 5,                  # 杠杆倍数 (期货交易)
    },
    
    # 风险控制配置
    'RISK_CONFIG': {
        'MAX_DAILY_TRADES': 12,          # 每日最大交易次数
        'MIN_TRADE_INTERVAL': 450,       # 最小交易间隔(秒)
        'MAX_DAILY_LOSS': 0.05,          # 每日最大亏损比例 (5%)
        'MAX_TOTAL_LOSS': 0.22,          # 总资金最大亏损比例 (20%)
        'EMERGENCY_STOP_LOSS': 0.30,     # 紧急止损比例 (30%)
    },
}

# 策略窗口参数配置
WINDOW_CONFIG = {
    'SHORT_WINDOW': 75,  # 从30减少到10 200
    'LONG_WINDOW': 150,   # 从60减少到20 400
}

# 回测配置参数
BACKTEST_CONFIG = {
    'BACKTEST_DAYS': 60,
}

# ============================================================================
# 技术指标参数配置
# ============================================================================

# EMA指标参数配置
EMA_CONFIG = {
    'LINEEMA_PERIOD': 55,
    'OPENEMA_PERIOD': 25,
    'CLOSEEMA_PERIOD': 25,
    'EMA9_PERIOD': 9,
    'EMA20_PERIOD': 20,
    'EMA50_PERIOD': 50,
    'EMA104_PERIOD': 104,
}

# 技术指标参数配置
PERIOD_CONFIG = {
    'RSI_PERIOD': 14,
    'OBV_PERIOD': 20,    # OBV周期
    'ATR_PERIOD': 14,    # ATR周期   
}

# ============================================================================
# 日志和调试配置
# ============================================================================

# 日志配置
LOGGING_CONFIG = {
    'LEVEL': 'INFO',  # 改回INFO级别，减少日志输出
    'CONSOLE_OUTPUT': True,
    'FILE_OUTPUT': True,  # 启用文件输出
    'LOG_DIR': 'logs',  # 使用相对路径，在当前目录下创建logs文件夹
}

# 调试配置
DEBUG_CONFIG = {
    'SHOW_API_URLS': False,  # 关闭API URL显示
    'ENABLE_VERBOSE_OUTPUT': False,
    'ENABLE_SIGNAL_LOGGING': True,
    'ENABLE_PERFORMANCE_STATS': True,
    'LOG_LEVEL': LOGGING_CONFIG['LEVEL'],  # 统一日志级别
}

# ============================================================================
# 交易所API配置
# ============================================================================

# Binance API配置
BINANCE_API_CONFIG = {
    # 主网配置
    'MAINNET': {
        'BASE_URL': 'https://fapi.binance.com',
        'API_VERSION': 'v1',  # 修复：Binance合约API使用v1版本
        'FUTURES_API_VERSION': 'v1',  # 修复：Binance合约API使用v1版本
        'TIMEOUT': 10,
        'RECV_WINDOW': 10000,
    },
    
    # 现货API配置
    'SPOT': {
        'BASE_URL': 'https://api.binance.com',
        'API_VERSION': 'v3',
        'TIMEOUT': 10,
        'RECV_WINDOW': 10000,
    },
    
    # 通用配置
    'COMMON': {
        'DEFAULT_MARGIN_TYPE': 'ISOLATED',
        'MAX_LEVERAGE': 125,
        'MIN_ORDER_SIZE': 0.001,
    }
}

# ============================================================================
# 策略配置
# ============================================================================

# SharpeOptimizedStrategy 配置
OPTIMIZED_STRATEGY_CONFIG = {
    # 基础窗口配置
    'windows': {
        'short': WINDOW_CONFIG['SHORT_WINDOW'],
        'long': WINDOW_CONFIG['LONG_WINDOW']
    },
    
    # 杠杆倍数配置
    'leverage': TRADING_CONFIG['CAPITAL_CONFIG']['LEVERAGE'],  # 杠杆倍数，从TRADING_CONFIG获取
    
    # 手续费配置
    'trading_fee': 0.001,  # 交易手续费率 (0.1%)
    
    # 信号方向配置
    'signal_direction': {
        'long_threshold': 0.01,      # 多头阈值，综合信号需要>0.01
        'short_threshold': -0.01,    # 空头阈值，综合信号需要<-0.01
        'neutral': 0    # 中性信号
    },
    
    # 评分权重配置
    'score_weights': {
        'signal_weight': 0.6,     # 指标评分权重 30%
        'trend_weight': 0.4,      # 趋势强度评分权重 40%
        'risk_weight': 0.00,       # 风险评分权重 20%
        'drawdown_weight': 0.00    # 回撤评分权重 10%
    },
    
   
 
    # 信号过滤器配置
    'signal_score_filters': {
        # 核心过滤器开关 - 保留必要的过滤器
        
        # 过滤参数 - 调整阈值以产生被过滤信号
        'enable_price_deviation_filter': True, # 价格偏离过滤器（关闭）
        'price_deviation_threshold': 3.0,       # 价格偏离阈值3%
        
        # RSI过滤器
        'enable_rsi_filter': True,              # RSI过滤器
        'rsi_overbought_threshold': 85,         # RSI超买阈值（收紧）
        'rsi_oversold_threshold': 25,           # RSI超卖阈值（收紧）
        
        # 波动率过滤器参数
        'enable_volatility_filter': True,      # 波动率过滤器（关闭）
        'min_volatility': 0.003,                # 最小波动率
        'max_volatility': 0.60,                 # 最大波动率
        'volatility_period': 50,                # 波动率计算周期
        
        # 价格均线纠缠过滤参数 - 只使用距离阈值
        'enable_price_ma_entanglement': True,  # 价格均线纠缠过滤器
        'entanglement_distance_threshold': 0.03, # 纠缠距离阈值（放宽）
        
        # 信号过滤器参数
        'enable_signal_score_filter': True,      # 信号评分过滤器
        'filter_long_base_score': 0.35,          # 多头信号评分阈值 过滤微弱信号
        'filter_long_trend_score': 0.3,         # 多头趋势评分阈值 过滤微弱趋势

        'filter_short_base_score': -0.25,        # 空头信号评分阈值 过滤微弱信号
        'filter_short_trend_score': -0.3,       # 空头趋势评分阈值 过滤微弱趋势
    },
    
    # 夏普优化策略参数
    'sharpe_params': {
        'sharpe_lookback': 30,           # 夏普率计算周期
        'target_sharpe': 1.0,            # 目标夏普率
        'max_risk_multiplier': 2.0,      # 最大风险乘数
        'initial_risk_multiplier': 1.0,  # 初始风险乘数
    },
    
    # 仓位管理配置,根据信号评分，管理仓位大小
    'position_config': {
        'full_position_threshold_min': -0.5,  # 全仓位阈值下限(空头信号),综合评分<-0.5时
        'full_position_threshold_max': 0.5,   # 全仓位阈值上限(多头信号),综合评分>0.5时
        'full_position_size': 0.9,          # 全仓位大小(10%)
        'avg_adjusted_position': 0.5,       # 一般仓位大小(6%)
        'max_adjusted_position': 0.8,       # 最大仓位大小(15%)
    },
    
    # 风险管理配置
    'risk_management': {
        'stop_loss': {
            'enable': False,
            'enable_fixed_stop_loss': True,        # 固定止损开关
             'fixed_stop_loss': -0.10,              # 固定止损 -5% (基于价格变动，考虑8倍杠杆后实际止损40%)
            'enable_signal_score_stop_loss': True, # 信号评分止损开关
            'signal_score_threshold': 0.3,         # 正负信号评分止损触发阈值
        },
        'take_profit': {
            'enable': True,

            'linewma_take_profit_enabled': False,   # linewma止盈 - 启用

            'time_based_take_profit': False,        # 时间止盈 - 启用
            'time_based_periods': 96,               # 时间止盈周期数 (96小时) - 延长给LineWMA反转止盈更多机会

            'enable_callback': True,                # 回调止盈
            'callback_periods': 20,                 # 回调周期数
            'callback_ratio': 0.05,                 # 回调阈值 (降低到1.5%，更敏感)
        }
    },
    
    # 冷却处理配置
    'cooldown_treatment': {
        'enable_cooldown_treatment': True,  # 启用冷却处理
        'consecutive_loss_threshold': 2,  # 连续亏损阈值（改回2次）
        'mode': 'backtest',              # backtest 或 realtime - 回测时使用backtest模式
        # 回测模式配置 - 只使用仓位减少
        'backtest_mode': {
            'position_reduction_levels': {
                'level_1': 0.8,  # 轻度冷却：仓位减少到90%（更宽松）
                'level_2': 0.6,  # 中度冷却：仓位减少到70%（更宽松）
                'level_3': 0.4,  # 重度冷却：仓位减少到50%（更宽松）
            },
            'recovery_conditions': {
                'consecutive_wins': 1,  # 连续盈利1次即可恢复
                'max_cooldown_periods': 24,  # 最大冷却时间24小时
            }
        },
        
        # 实盘模式配置
        'realtime_mode': {
            'max_cooldown_treatment_duration': 72,  # 最大冷却时间(小时)
            'cooldown_treatment_levels': {
                'level_1': {'consecutive_losses': 2, 'duration': 3},  # 轻度冷却：连续亏损2次，持续3小时
                'level_2': {'consecutive_losses': 4, 'duration': 5},  # 中度冷却：连续亏损4次，持续5小时
                'level_3': {'consecutive_losses': 6, 'duration': 7},  # 重度冷却：连续亏损6次，持续7小时
            },
            'position_reduction_levels': {
                'level_1': 0.8,  # 轻度冷却：仓位减少到80%
                'level_2': 0.6,  # 中度冷却：仓位减少到60%
                'level_3': 0.4,  # 重度冷却：仓位减少到40%
            }
        }
    },
    
    # DeepSeek AI信号整合配置
    'enable_deepseek_integration': True,  # 是否启用DeepSeek AI信号整合
    'deepseek_mode': 'realtime_only',      # 模式: 'realtime_only'(仅实盘), 'backtest_only'(仅回测), 'both'(都启用)
    'deepseek_weight': 0.6,                # DeepSeek信号权重 (0-1)
    'cache_timeout': 60 * 10,         # 缓存超时时间(秒) - 10分钟
    
}

# ============================================================================
# Telegram通知配置
# ============================================================================
TELEGRAM_CONFIG = {
    'BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN', ''),  # Telegram Bot Token (从环境变量读取)
    'CHAT_ID': os.getenv('TELEGRAM_CHAT_ID', ''),      # Telegram Chat ID (从环境变量读取)
    'ENABLED': True,                       # 是否启用Telegram通知
    'NOTIFICATION_TYPES': {
        'SIGNALS': True,                   # 交易信号通知
        'TRADES': True,                    # 交易执行通知
        'ERRORS': True,                    # 错误通知
        'STATUS': True,                    # 状态通知
        'NEUTRAL_SIGNALS': True,           # 观望信号通知（已启用）
    },
    'MESSAGE_FORMAT': {
        'PARSE_MODE': 'HTML',              # 消息格式: HTML 或 Markdown
        'DISABLE_WEB_PREVIEW': True,       # 禁用网页预览
    }
}
