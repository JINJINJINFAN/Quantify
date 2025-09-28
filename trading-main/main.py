# -*- coding: utf-8 -*-
# main.py
import os
import json
import logging
from dotenv import load_dotenv
from core.data_loader import DataLoader
from core.feature_engineer import FeatureEngineer
from core.strategy import (
    SharpeOptimizedStrategy
)
from core.backtester import Backtester
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np

from datetime import datetime, timedelta
import warnings
import psutil
import gc
warnings.filterwarnings('ignore')

def check_dependencies():
    """检查必要的依赖包"""
    required_packages = {
        'pandas': 'pandas',
        'numpy': 'numpy', 
        'matplotlib': 'matplotlib',
        'requests': 'requests',
        'psutil': 'psutil'
    }
    
    missing_packages = []
    for package, import_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"缺少必要的依赖包: {', '.join(missing_packages)}")
        print("请运行: pip install " + " ".join(missing_packages))
        return False
    
    print(" 所有依赖包检查通过")
    return True

def get_memory_usage():
    """获取当前内存使用情况"""
    try:
        process = psutil.Process()
        memory_info = process.memory_info()
        return {
            'rss': memory_info.rss / 1024 / 1024,  # MB
            'vms': memory_info.vms / 1024 / 1024,  # MB
            'percent': process.memory_percent()
        }
    except:
        return None

def log_memory_usage(stage=""):
    """记录内存使用情况"""
    memory_info = get_memory_usage()
    if memory_info:
        logger.info(f"内存使用 {stage}: RSS={memory_info['rss']:.1f}MB, VMS={memory_info['vms']:.1f}MB, 占比={memory_info['percent']:.1f}%")
        print(f"💾 内存使用 {stage}: {memory_info['rss']:.1f}MB (占比: {memory_info['percent']:.1f}%)")

# 导入配置
from config import *

# 加载环境变量（仅用于敏感参数如API密钥）
load_dotenv()

# 设置日志记录
def setup_logging():
    """设置日志记录"""
    try:
        # 创建logs目录
        if not os.path.exists('logs'):
            os.makedirs('logs')
            print("📁 创建日志目录: logs/")
        
        # 生成时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 配置日志格式
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # 创建文件处理器
        log_filename = f'logs/trading_signals_'+timestamp+'.log'
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setLevel(logging.INFO)  # 文件记录INFO级别及以上
        file_handler.setFormatter(logging.Formatter(log_format))
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)  # 控制台只显示WARNING级别及以上
        console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        
        # 配置根日志记录器
        logging.basicConfig(
            level=logging.INFO,  # 根日志级别
            handlers=[file_handler, console_handler],
            format=log_format,
            force=True  # 强制重新配置
        )
        
        # 配置日志过滤
        from utils import configure_logging
        configure_logging()
        
        print(f"📝 日志文件: {log_filename}")
        return log_filename
        
    except Exception as e:
        print(f"日志设置失败: {e}")
        # 使用基本日志配置
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return None

# 初始化日志（将在主函数中调用）
logger = None

# 设置中文字体支持 - 修复matplotlib字体识别问题
try:
    from utils.fix_matplotlib_fonts import force_add_fonts, configure_fonts
    force_add_fonts()
    configure_fonts()
except ImportError:
    # 备用方案
    plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'WenQuanYi Zen Hei', 'SimHei', 'Microsoft YaHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False

def run_comprehensive_backtest():
    """运行完整的策略回测系统，仅使用真实历史数据"""
    print("开始量化交易策略全面回测系统...")
    print("仅使用Binance合约真实历史数据，包含真实相邻时间级别数据")
    print("=" * 80)
    
    # 记录系统启动信息到日志
    logger.info("量化交易策略全面回测系统启动")
    logger.info("仅使用Binance合约真实历史数据，包含真实相邻时间级别数据")
    
    # 1. 数据加载和特征工程
    features, kline_data = load_and_process_data()
    if features is None:
        return
    
    # 2. 定义所有策略
    strategies = define_strategies()
    
    # 3. 运行多时间级别回测
    all_results = run_multi_timeframe_backtest(kline_data, strategies)
    
    # 4. 运行风险控制测试
    risk_test_results = run_risk_control_tests(features, strategies)
    
    # 5. 生成详细报告
    generate_comprehensive_report(all_results, risk_test_results)
    
    # 6. 绘制分析图表
    create_analysis_charts(all_results, risk_test_results, kline_data)
    
    print(f"\n量化交易策略全面回测完成!")
    
    # 记录系统完成信息到日志
    logger.info("量化交易策略全面回测完成")

def load_and_process_data():
    """加载和处理数据 - 支持多时间级别数据"""
    print(" 正在加载和处理历史数据...")
    
    # 从配置读取时间级别
    timeframe = TRADING_CONFIG['TIMEFRAME']
    print(f"使用主时间级别: {timeframe}")
    
    # 记录数据加载开始信息到日志
    logger.info(f"开始加载和处理历史数据 - 时间级别: {timeframe}")
    
    try:
        # 数据加载器配置
        data_loader = DataLoader(timeframe=timeframe)
        
        # 修复时间范围计算 - 从配置读取回测天数和结束时间
        
        # target_time = TRADING_CONFIG.get('TESTTIME')
        target_time = None
        if target_time is None:
            end_date = datetime.now()
        else:
            if isinstance(target_time, str):
                end_date = datetime.strptime(target_time, "%Y-%m-%d %H:%M:%S")
            else:
                end_date = target_time
        
        backtest_days = BACKTEST_CONFIG['BACKTEST_DAYS']  # 从配置读取回测天数
        start_date = end_date - timedelta(days=backtest_days)
        
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        print(f"📅 回测时间范围: {start_date_str} 至 {end_date_str} (最近{backtest_days}天)")
        logger.info(f"回测时间范围: {start_date_str} 至 {end_date_str} (最近{backtest_days}天)")
        
        # 获取主时间级别的合约历史数据
        historical_data = data_loader.get_klines(start_date_str, end_date_str)
        
        if historical_data is None or len(historical_data) == 0:
            error_msg = f"主时间级别合约数据加载失败"
            print(f"{error_msg}")
            logger.error(error_msg)
            return None
        
        # 数据验证和统计
        print(f"成功加载 {len(historical_data)} 条合约历史数据")
        print(f"数据时间范围: {historical_data.index[0]} 至 {historical_data.index[-1]}")
        print(f"💰 价格范围: {historical_data['close'].min():.2f} - {historical_data['close'].max():.2f}")
        
        # 记录数据加载成功信息到日志
        logger.info(f"成功加载 {len(historical_data)} 条合约历史数据")
        logger.info(f"数据时间范围: {historical_data.index[0]} 至 {historical_data.index[-1]}")
        logger.info(f"价格范围: {historical_data['close'].min():.2f} - {historical_data['close'].max():.2f}")
        
        # 验证数据完整性
        if len(historical_data) < 100:
            warning_msg = f"数据量过少 ({len(historical_data)} 条)，可能影响回测准确性"
            print(f"{warning_msg}")
            logger.warning(warning_msg)
        
        # 检查数据异常值
        price_changes = historical_data['close'].pct_change().dropna()
        max_price_change = price_changes.abs().max()
        if max_price_change > 0.5:  # 单日价格变化超过50%
            warning_msg = f"检测到异常价格变化 ({max_price_change*100:.2f}%)，可能存在数据问题"
            print(f"{warning_msg}")
            logger.warning(warning_msg)
        
        # 检查数据连续性
        time_gaps = historical_data.index.to_series().diff().dropna()
        max_gap = time_gaps.max()
        if max_gap > pd.Timedelta(hours=2):  # 超过2小时的数据间隔
            warning_msg = f"检测到数据间隔过大: {max_gap}"
            print(f"{warning_msg}")
            logger.warning(warning_msg)
        
        # 数据获取阶段完成
        print(" 数据获取阶段完成，仅使用当前时间级别数据")
        print("📡 相邻时间级别数据将在回测过程中实时获取")
        logger.info("数据获取阶段完成，仅使用当前时间级别数据")
        
    except ImportError as e:
        error_msg = f"导入模块失败: {e}"
        print(f"{error_msg}")
        logger.error(error_msg)
        return None
    except Exception as e:
        error_msg = f"合约历史数据加载失败: {e}"
        print(f"{error_msg}")
        logger.error(error_msg)
        import traceback
        logger.error(f"详细错误信息: {traceback.format_exc()}")
        return None
    
    # 特征工程 - 仅使用当前时间级别数据
    print("正在进行特征工程...")
    logger.info("开始特征工程处理")
    
    try:
        feature_engineer = FeatureEngineer()
        features = feature_engineer.generate_features(historical_data)
        
        if features is None or len(features) == 0:
            error_msg = "特征工程失败 - 返回空数据"
            print(f"{error_msg}")
            logger.error(error_msg)
            return None
        
        # 验证特征数据质量
        if len(features) < len(historical_data) * 0.8:  # 特征数据少于原始数据的80%
            warning_msg = f"特征数据量减少较多: {len(historical_data)} -> {len(features)}"
            print(f"{warning_msg}")
            logger.warning(warning_msg)
        
        # 检查关键指标是否存在
        required_columns = ['rsi', 'macd', 'macd_signal', 'adx', 'di_plus', 'di_minus']
        missing_columns = [col for col in required_columns if col not in features.columns]
        if missing_columns:
            warning_msg = f"缺少关键技术指标: {missing_columns}"
            print(f"{warning_msg}")
            logger.warning(warning_msg)
        
        print(f"特征工程完成，共 {len(features)} 条特征数据")
        print(f"包含技术指标: RSI, MACD, 布林带, KDJ, ATR等")
        print(f"📈 包含风险指标: 夏普比率, 索提诺比率, 最大回撤等")
        
        # 记录特征工程完成信息到日志
        logger.info(f"特征工程完成，共 {len(features)} 条特征数据")
        logger.info(f"包含技术指标: RSI, MACD, 布林带, KDJ, ATR等")
        logger.info(f"包含风险指标: 夏普比率, 索提诺比率, 最大回撤等")
        
        return features, historical_data
        
    except ImportError as e:
        error_msg = f"特征工程模块导入失败: {e}"
        print(f"{error_msg}")
        logger.error(error_msg)
        return None
    except Exception as e:
        error_msg = f"特征工程异常: {e}"
        print(f"{error_msg}")
        logger.error(error_msg)
        import traceback
        logger.error(f"特征工程详细错误信息: {traceback.format_exc()}")
        return None

# 已删除冗余的相邻时间级别加载函数 - 不再需要

def define_strategies():
    """定义所有要测试的策略"""
    strategies = {
        "夏普优化策略": {
            "class": SharpeOptimizedStrategy,
            "params": {
                # 夏普优化策略参数 - 使用新的配置格式
                'sharpe_params': {
                    'sharpe_lookback': 30,  # 夏普率计算周期
                    'target_sharpe': 1.0,   # 目标夏普率
                    'max_risk_multiplier': 2.0,  # 最大风险乘数
                    'initial_risk_multiplier': 1.0,  # 初始风险乘数
                }
            },
            "description": "基于夏普比率动态调整风险敞口的优化策略，根据市场表现自动调整仓位大小"
        }
    }
    
    # 获取当前时间级别
    current_timeframe = TRADING_CONFIG['TIMEFRAME']
    
    print(f"已定义 {len(strategies)} 个策略:")
    for name, info in strategies.items():
        params = info.get('params', {})
        if params:
            short_periods = params.get('short_window', WINDOW_CONFIG['SHORT_WINDOW'])
            long_periods = params.get('long_window', WINDOW_CONFIG['LONG_WINDOW'])
            
            # 计算实际时间显示
            time_unit_map = {'1m': '分钟', '5m': '分钟', '15m': '分钟', '30m': '分钟', 
                           '1h': '小时', '4h': '小时', '1d': '天', '1w': '周'}
            unit_multiplier = {'1m': 1, '5m': 5, '15m': 15, '30m': 30, 
                             '1h': 1, '4h': 4, '1d': 1, '1w': 1}
            
            unit_name = time_unit_map.get(current_timeframe, '周期')
            multiplier = unit_multiplier.get(current_timeframe, 1)
            
            if current_timeframe.endswith('m'):  # 分钟级别
                short_time = short_periods * multiplier
                long_time = long_periods * multiplier
                param_str = f"(短期:{short_time}分钟, 长期:{long_time}分钟)"
            elif current_timeframe.endswith('h'):  # 小时级别
                short_time = short_periods * multiplier
                long_time = long_periods * multiplier
                param_str = f"(短期:{short_time}小时, 长期:{long_time}小时)"
            else:  # 天/周级别
                short_time = short_periods * multiplier
                long_time = long_periods * multiplier
                param_str = f"(短期:{short_time}{unit_name}, 长期:{long_time}{unit_name})"
        else:
            param_str = ""
        print(f"  {name}{param_str}: {info['description']}")
    
    return strategies

def run_multi_timeframe_backtest(historical_data, strategies):
    """运行时间级别回测"""
    # 从配置读取时间级别
    timeframe = TRADING_CONFIG['TIMEFRAME']
    print(f"\n🔄 开始{timeframe}时间级别回测...")
    
    all_results = {}
    
    print(f"\n 测试 {timeframe} 时间级别...")
    
    # 测试所有策略
    tf_results = []
    timeframe_display = f"{timeframe}时间级别"
    
    for strategy_name, strategy_info in strategies.items():
        # 为每个策略生成相应的特征
        strategy_params = strategy_info.get("params", {}).copy()  # 复制参数字典
        short_window = strategy_params.get("short_window", WINDOW_CONFIG['SHORT_WINDOW'])
        long_window = strategy_params.get("long_window", WINDOW_CONFIG['LONG_WINDOW'])
        
        # 注意：SharpeOptimizedStrategy 不接受 timeframe 参数
        # 时间级别信息将通过其他方式传递
        
        # 计算实际时间显示
        current_timeframe = TRADING_CONFIG['TIMEFRAME']
        if current_timeframe.endswith('m'):
            unit = '分钟'
            multiplier = int(current_timeframe[:-1]) if current_timeframe != '1m' else 1
        elif current_timeframe.endswith('h'):
            unit = '小时'
            multiplier = int(current_timeframe[:-1]) if current_timeframe != '1h' else 1
        else:
            unit = '天'
            multiplier = 1
            
        short_time = short_window * multiplier
        long_time = long_window * multiplier
        print(f"  为策略 {strategy_name} 生成特征 (短期:{short_time}{unit}, 长期:{long_time}{unit})")
        
        # 使用环境变量中的统一窗口期参数
        feature_engineer = FeatureEngineer()
        features = feature_engineer.generate_features(historical_data)  # 使用默认环境变量设置
        
        # 验证数据长度一致性
        if len(features) != len(historical_data):
            print(f"特征工程后数据长度变化: {len(historical_data)} -> {len(features)}")
            print(f"  原因: 窗口期参数 short_window={short_window}, long_window={long_window}")
            print(f"  建议: 使用较小的窗口期参数以减少数据丢失")
        
        if features is None or len(features) == 0:
            print(f"策略 {strategy_name} 特征生成失败")
            continue
            
        print(f"{current_timeframe}时间级别数据准备完成，共 {len(features)} 条数据")
        
        result = run_single_strategy_backtest(
            strategy_info["class"], 
            strategy_params,
            strategy_name, 
            features, 
            timeframe_display
        )
        if result:
            tf_results.append(result)
    
    all_results[timeframe_display] = tf_results
    
    return all_results

def run_single_strategy_backtest(strategy_class, strategy_params, strategy_name, features, timeframe):
    """运行单个策略的回测"""
    try:
        print(f"  测试策略: {strategy_name}")
        
        # 创建策略实例 - 使用完整的OPTIMIZED_STRATEGY_CONFIG
        from config import OPTIMIZED_STRATEGY_CONFIG
        
        # 创建数据加载器实例
        data_loader = DataLoader()
        
        # 创建策略实例，传入data_loader和回测模式
        strategy_instance = strategy_class(config=OPTIMIZED_STRATEGY_CONFIG, data_loader=data_loader, mode='backtest')
        
        # 设置策略的时间级别（用于冷却处理时间计算）
        if hasattr(strategy_instance, 'set_timeframe'):
            strategy_instance.set_timeframe(timeframe)
        
        # 创建回测器
        backtester = Backtester()
        backtester.set_strategy(strategy_instance)
        
        # 执行回测
        result = backtester.run_backtest(features, timeframe)
        
        # 记录过滤器统计信息
        if result and 'trade_log' in result and len(result['trade_log']) > 0:
            trade_log = result['trade_log']
            filtered_signals = 0
            passed_signals = 0
            
            # 统计过滤器的使用情况
            for _, trade in trade_log.iterrows():
                if 'filters' in trade and isinstance(trade['filters'], dict):
                    signal_score_filter = trade['filters'].get('signal_score_filter', {})
                    if signal_score_filter.get('passed', True):
                        passed_signals += 1
                    else:
                        filtered_signals += 1
            
            total_signals = filtered_signals + passed_signals
            if total_signals > 0:
                filter_rate = (filtered_signals / total_signals) * 100
                logger.info(f"策略 {strategy_name} 过滤器统计:")
                logger.info(f" 总信号数: {total_signals}")
                logger.info(f" 通过过滤: {passed_signals} ({100-filter_rate:.1f}%)")
                logger.info(f" 被过滤: {filtered_signals} ({filter_rate:.1f}%)")
                
                # 记录详细的过滤原因统计
                filter_reasons = {}
                for _, trade in trade_log.iterrows():
                    if 'filters' in trade and isinstance(trade['filters'], dict):
                        signal_score_filter = trade['filters'].get('signal_score_filter', {})
                        reason = signal_score_filter.get('reason', '未知原因')
                        if reason not in filter_reasons:
                            filter_reasons[reason] = 0
                        filter_reasons[reason] += 1
                
                if filter_reasons:
                    logger.info(f" 过滤原因统计:")
                    for reason, count in filter_reasons.items():
                        percentage = (count / total_signals) * 100
                        logger.info(f"   {reason}: {count}次 ({percentage:.1f}%)")
        
        if result:
            # 计算额外指标
            trade_df = result['trade_log']
            if len(trade_df) > 0 and 'pnl' in trade_df.columns:
                # 只统计有盈亏的交易（平仓）
                close_trades = trade_df[trade_df['trade_type'].isin(['close'])] if 'trade_type' in trade_df.columns else trade_df
                
                profitable_trades = close_trades[close_trades['pnl'] > 0]
                loss_trades = close_trades[close_trades['pnl'] < 0]
                
                total_close_trades = len(close_trades)
                win_rate = len(profitable_trades) / total_close_trades * 100 if total_close_trades > 0 else 0
                avg_profit = profitable_trades['pnl'].mean() if len(profitable_trades) > 0 else 0
                avg_loss = loss_trades['pnl'].mean() if len(loss_trades) > 0 else 0
                profit_loss_ratio = abs(avg_profit / avg_loss) if avg_loss != 0 else 0
                
                # 计算最大回撤
                total_assets = result['total_assets']
                if len(total_assets) > 0:
                    max_drawdown = calculate_max_drawdown(total_assets)
                else:
                    max_drawdown = 0
                
                # 计算夏普比率
                if len(total_assets) > 1:
                    returns = np.diff(total_assets) / total_assets[:-1]
                    sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
                else:
                    sharpe_ratio = 0
                
                enhanced_result = {
                    'strategy_name': strategy_name,
                    'timeframe': timeframe,
                    'strategy_params': strategy_params,  # 保存策略参数
                    'final_cash': result['final_cash'],
                    'return_ratio': result['return_ratio'],
                    'total_trades': result['total_trades'],
                    'win_rate': win_rate,
                    'avg_profit': avg_profit,
                    'avg_loss': avg_loss,
                    'profit_loss_ratio': profit_loss_ratio,
                    'max_drawdown': max_drawdown,
                    'sharpe_ratio': sharpe_ratio,
                    'total_assets': total_assets,
                    'asset_timestamps': result.get('asset_timestamps', []),  # 🔧 添加时间戳
                    'trade_log': trade_df,  # 添加交易记录
                    'ohlc_data': features
                }
                
                print(f"  完成 - 收益率: {result['return_ratio']:.2f}%, 胜率: {win_rate:.1f}%, 交易次数: {result['total_trades']}")
                return enhanced_result
            else:
                print(f"    失败 - 无交易记录")
                return None
        else:
            print(f"    失败 - 回测异常")
            return None
            
    except Exception as e:
        print(f"    异常: {e}")
        return None

def run_risk_control_tests(features, strategies):
    """运行风险控制测试"""
    print("\n 开始风险控制测试...")
    
    risk_results = {}
    
    for strategy_name, strategy_info in strategies.items():
        print(f"\n 测试 {strategy_name} 风险控制...")
        
        try:
            # 创建策略实例来测试风险状态
            strategy_class = strategy_info["class"]
            from config import OPTIMIZED_STRATEGY_CONFIG
            strategy_instance = strategy_class(config=OPTIMIZED_STRATEGY_CONFIG)
            
            # 获取风险状态
            if hasattr(strategy_instance, 'get_risk_status'):
                risk_status = strategy_instance.get_risk_status(features)
                risk_results[strategy_name] = risk_status
                print(f" 风险等级: {risk_status.get('risk_level', 'unknown')}")
                print(f" 状态: {risk_status.get('status', 'unknown')}")
                print(f" 消息: {risk_status.get('message', 'N/A')}")
            else:
                print(f" 策略无风险控制功能")
                
        except Exception as e:
            print(f"  风险控制测试失败: {e}")
    
    return risk_results

def calculate_max_drawdown(total_assets):
    """计算最大回撤"""
    if len(total_assets) < 2:
        return 0
    
    peak = total_assets[0]
    max_dd = 0
    
    for value in total_assets:
        if value > peak:
            peak = value
        dd = (peak - value) / peak
        if dd > max_dd:
            max_dd = dd
    
    return max_dd

def generate_comprehensive_report(all_results, risk_test_results):
    """生成综合报告"""
    print("\n" + "="*80)
    print(" 量化交易策略综合回测报告")
    print("="*80)
    
    # 1. 策略性能排名
    print("\n 策略性能排名:")
    print("-" * 60)
    
    all_strategy_results = []
    for timeframe, results in all_results.items():
        for result in results:
            all_strategy_results.append(result)
    
    # 按收益率排序
    sorted_results = sorted(all_strategy_results, key=lambda x: x['return_ratio'], reverse=True)
    
    for i, result in enumerate(sorted_results[:10], 1):  # 显示前10名
        print(f"{i:2d}. {result['strategy_name']} ({result['timeframe']})")
        print(f"   收益率: {result['return_ratio']:6.2f}% | 胜率: {result['win_rate']:5.1f}% | "
              f"交易次数: {result['total_trades']:3d} | 最大回撤: {result['max_drawdown']:5.1%} | "
              f"夏普比率: {result['sharpe_ratio']:5.2f}")
    
    # 2. 最优策略分析
    if sorted_results:
        best_strategy = sorted_results[0]
        print(f"\n 全局最优策略: {best_strategy['strategy_name']}")
        print(f"  时间级别: {best_strategy['timeframe']}")
        print(f"  收益率: {best_strategy['return_ratio']:.2f}%")
        print(f"  胜率: {best_strategy['win_rate']:.1f}%")
        print(f"  交易次数: {best_strategy['total_trades']}")
        print(f"  盈亏比: {best_strategy['profit_loss_ratio']:.2f}")
        print(f"  最大回撤: {best_strategy['max_drawdown']:.1%}")
        print(f"  夏普比率: {best_strategy['sharpe_ratio']:.2f}")
    
    # 3. 风险控制分析
    print(f"\n 风险控制分析:")
    print("-" * 40)
    for strategy_name, risk_status in risk_test_results.items():
        print(f"{strategy_name}: {risk_status.get('risk_level', 'unknown')} - {risk_status.get('message', 'N/A')}")
    
    # 4. 时间级别分析
    print(f"\n 时间级别分析:")
    print("-" * 40)
    for timeframe, results in all_results.items():
        if results:
            avg_return = np.mean([r['return_ratio'] for r in results])
            avg_trades = np.mean([r['total_trades'] for r in results])
            print(f"{timeframe}: 平均收益率 {avg_return:.2f}%, 平均交易次数 {avg_trades:.0f}")

def create_analysis_charts(all_results, risk_test_results, kline_data=None, symbol=None):
    """
    创建分析图表
    
    Args:
        all_results: 所有回测结果
        risk_test_results: 风险测试结果
        kline_data: K线数据
        symbol: 交易对符号，如果为None则使用配置文件中的默认值
    """
    # 从配置文件获取默认交易对
    if symbol is None:
        from config import TRADING_CONFIG
        symbol = TRADING_CONFIG["SYMBOL"]
    
    print("\n 正在生成分析图表...")
    
    # 1. 策略性能对比图
    create_performance_comparison_chart(all_results, symbol)
    
    # 2. 资金曲线图（带K线数据）
    create_equity_curves_with_kline(all_results, kline_data, symbol)
    

    


def create_performance_comparison_chart(all_results, symbol=None):
    """
    创建性能对比图表
    
    Args:
        all_results: 所有回测结果
        symbol: 交易对符号，如果为None则使用配置文件中的默认值
    """
    # 从配置文件获取默认交易对
    if symbol is None:
        from config import TRADING_CONFIG
        symbol = TRADING_CONFIG["SYMBOL"]
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(f'{symbol} 量化交易策略性能对比分析', fontsize=16, fontweight='bold')
    
    # 提取数据
    strategies = []
    returns = []
    win_rates = []
    trade_counts = []
    sharpe_ratios = []
    
    for timeframe, results in all_results.items():
        for result in results:
            strategies.append(f"{result['strategy_name']}\n({result['timeframe']})")
            returns.append(result['return_ratio'])
            win_rates.append(result['win_rate'])
            trade_counts.append(result['total_trades'])
            sharpe_ratios.append(result['sharpe_ratio'])
    
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']
    
    # 收益率对比
    ax1 = axes[0, 0]
    bars1 = ax1.bar(strategies, returns, color=colors[:len(strategies)])
    ax1.set_title('策略收益率对比', fontweight='bold')
    ax1.set_ylabel('收益率 (%)')
    ax1.tick_params(axis='x', rotation=45)
    
    # 添加数值标签
    for bar, val in zip(bars1, returns):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + max(0.5, abs(height) * 0.02),
                f'{val:.1f}%', ha='center', va='bottom', fontweight='bold')
    
    # 胜率对比
    ax2 = axes[0, 1]
    bars2 = ax2.bar(strategies, win_rates, color=colors[:len(strategies)])
    ax2.set_title('策略胜率对比', fontweight='bold')
    ax2.set_ylabel('胜率 (%)')
    ax2.tick_params(axis='x', rotation=45)
    
    for bar, val in zip(bars2, win_rates):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height + max(0.2, height * 0.02),
                f'{val:.1f}%', ha='center', va='bottom', fontweight='bold')
    
    # 交易次数对比
    ax3 = axes[1, 0]
    bars3 = ax3.bar(strategies, trade_counts, color=colors[:len(strategies)])
    ax3.set_title('策略交易次数对比', fontweight='bold')
    ax3.set_ylabel('交易次数')
    ax3.tick_params(axis='x', rotation=45)
    
    for bar, val in zip(bars3, trade_counts):
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height + max(1, height * 0.02),
                f'{val}', ha='center', va='bottom', fontweight='bold')
    
    # 夏普比率对比
    ax4 = axes[1, 1]
    bars4 = ax4.bar(strategies, sharpe_ratios, color=colors[:len(strategies)])
    ax4.set_title('策略夏普比率对比', fontweight='bold')
    ax4.set_ylabel('夏普比率')
    ax4.tick_params(axis='x', rotation=45)
    
    for bar, val in zip(bars4, sharpe_ratios):
        height = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2., height + max(0.01, abs(height) * 0.02),
                f'{val:.2f}', ha='center', va='bottom', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('strategy_performance_comparison.png', dpi=300, bbox_inches='tight')
    print(" 策略性能对比图已保存为: strategy_performance_comparison.png")
    plt.show()

def create_equity_curves_chart(all_results):
    """创建资金曲线图"""
    fig, ax = plt.subplots(figsize=(15, 8))
    
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD']
    color_idx = 0
    
    for timeframe, results in all_results.items():
        for result in results:
            if len(result['total_assets']) > 0:
                # 生成时间轴
                # 从配置文件获取回测天数和结束时间
                from config import BACKTEST_CONFIG, TRADING_CONFIG
                backtest_days = BACKTEST_CONFIG.get('BACKTEST_DAYS', 60)
                
                # 使用配置中的TESTTIME作为结束时间
                 # target_time = TRADING_CONFIG.get('TESTTIME')
                target_time = None
                if target_time is None:
                    end_time = datetime.now()
                else:
                    if isinstance(target_time, str):
                        end_time = datetime.strptime(target_time, "%Y-%m-%d %H:%M:%S")
                    else:
                        end_time = target_time
                
                time_points = pd.date_range(
                    start=end_time - timedelta(days=backtest_days),
                    periods=len(result['total_assets']),
                    freq='H'
                )
                
                # 绘制资金曲线（仅显示资金变化，不标注交易点）
                ax.plot(time_points, result['total_assets'], 
                       label=f"{result['strategy_name']} ({result['timeframe']})",
                       color=colors[color_idx % len(colors)], linewidth=2, alpha=0.8)
                color_idx += 1
    
    ax.set_title('策略资金曲线对比', fontsize=16, fontweight='bold')
    ax.set_xlabel('时间')
    ax.set_ylabel('资金 (USDT)')
    ax.grid(True, alpha=0.3)
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    # 添加初始资金线
    ax.axhline(y=1000, color='black', linestyle='--', alpha=0.5, label='初始资金')
    
    plt.tight_layout()
    plt.savefig('equity_curves_comparison.png', dpi=300, bbox_inches='tight')
    print(" 资金曲线图已保存为: equity_curves_comparison.png")
    plt.show()

def create_equity_curves_with_kline(all_results, kline_data=None, symbol=None):
    """
    创建权益曲线与K线图对比
    
    Args:
        all_results: 所有回测结果
        kline_data: K线数据
        symbol: 交易对符号，如果为None则使用配置文件中的默认值
    """
    # 从配置文件获取默认交易对
    if symbol is None:
        from config import TRADING_CONFIG
        symbol = TRADING_CONFIG["SYMBOL"]
    
    if kline_data is None:
        print("⚠ 未提供K线数据，使用标准资金曲线图")
        create_equity_curves_chart(all_results)
        return
    
    # 创建子图：上方显示K线和指标，下方显示资金曲线
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12), height_ratios=[2, 1])
    
    # 上方子图：绘制K线图
    ax1.set_title(f'{symbol} 价格走势与交易位置 (含综合分、方向分、强度分)', fontsize=14, fontweight='bold')
    
    # 检查kline_data是否包含技术指标
    has_technical_indicators = ('lineWMA' in kline_data.columns or 
                               'openEMA' in kline_data.columns or 
                               'closeEMA' in kline_data.columns)
    
    # 获取资金曲线的实际长度，用于确定K线数据的显示范围
    equity_length = 0
    for timeframe, results in all_results.items():
        for result in results:
            if len(result['total_assets']) > 0:
                equity_length = len(result['total_assets'])
                break
        if equity_length > 0:
            break
    
    print(f"数据长度分析:")
    print(f"  K线数据总长度: {len(kline_data)}")
    print(f"  资金曲线长度: {equity_length}")
    
    # 确保K线数据长度与资金曲线长度匹配
    if equity_length > 0:
        if len(kline_data) > equity_length:
            # 截取K线数据以匹配资金曲线长度
            kline_data = kline_data.iloc[:equity_length]
            print(f" 截取K线数据以匹配资金曲线长度: {len(kline_data)}")
        elif len(kline_data) < equity_length:
            # K线数据不足，需要补充
            missing_length = equity_length - len(kline_data)
            print(f"  K线数据不足，需要补充 {missing_length} 条数据")
            
            # 从原始数据的末尾复制数据来补充
            if len(kline_data) > 0:
                # 复制最后几行数据来补充
                last_rows = kline_data.iloc[-min(missing_length, len(kline_data)):]
                kline_data = pd.concat([kline_data, last_rows], ignore_index=True)
                print(f" 补充K线数据至 {len(kline_data)} 条")
            else:
                print(f"   无法补充K线数据，使用空数据")
    
    # 🔧 修复：确保K线数据索引与资金曲线时间戳匹配
    if equity_length > 0 and len(kline_data) == equity_length:
        # 从回测结果中获取资金曲线的时间戳
        for timeframe, results in all_results.items():
            for result in results:
                if 'asset_timestamps' in result and len(result['asset_timestamps']) > 0:
                    # 使用资金曲线的时间戳重新索引K线数据
                    equity_timestamps = result['asset_timestamps']
                    if len(equity_timestamps) == len(kline_data):
                        # 重新索引K线数据以匹配资金曲线时间戳
                        kline_data.index = equity_timestamps
                        print(f" 重新索引K线数据以匹配资金曲线时间戳")
                        print(f"  时间范围: {kline_data.index[0]} 至 {kline_data.index[-1]}")
                        break
    
    # 如果K线数据不包含技术指标，尝试从回测结果中获取
    if not has_technical_indicators:
        print("⚠ 原始K线数据不包含技术指标，尝试从回测结果中获取...")
        # 优先从回测结果中获取完整的K线数据
        for timeframe, results in all_results.items():
            if results and len(results) > 0:
                result = results[0]  # 获取第一个策略结果
                if 'ohlc_data' in result and len(result['ohlc_data']) > 0:
                    # 使用回测结果中的完整K线数据
                    kline_data = result['ohlc_data']
                    print(f"使用回测结果中的完整K线数据: {len(kline_data)} 条")
                    has_technical_indicators = ('lineWMA' in kline_data.columns or 
                                               'openEMA' in kline_data.columns or 
                                               'closeEMA' in kline_data.columns)
                    if has_technical_indicators:
                        print(f"回测结果包含技术指标")
                        break
                
                # 如果回测结果中没有完整数据，尝试重新计算
                try:
                    from feature_engineer import FeatureEngineer
                    feature_engineer = FeatureEngineer()
                    kline_data_with_features = feature_engineer.generate_features(kline_data)  # 使用环境变量默认设置
                    if kline_data_with_features is not None:
                        kline_data = kline_data_with_features
                        print(f"已重新计算技术指标 (使用环境变量默认窗口期)")
                        print(f"  重新计算后K线数据长度: {len(kline_data)}")
                        
                        # 🔧 修复：确保重新计算后的K线数据长度与资金曲线匹配
                        if len(kline_data) < equity_length:
                            print(f"重新计算后K线数据不足，需要补充数据")
                            missing_length = equity_length - len(kline_data)
                            
                            # 保存原始数据用于补充
                            original_kline_data = kline_data.copy()
                            
                            # 从原始数据的末尾复制数据来补充
                            if len(original_kline_data) > 0:
                                # 复制最后几行数据来补充
                                last_rows = original_kline_data.iloc[-min(missing_length, len(original_kline_data)):]
                                kline_data = pd.concat([kline_data, last_rows], ignore_index=True)
                                print(f" 补充K线数据至 {len(kline_data)} 条")
                            else:
                                print(f"  无法补充数据，使用现有数据")
                        break
                except Exception as e:
                    print(f"⚠ 重新计算技术指标失败: {e}")
                    break
    
    # 如果K线数据太多，进行采样以提高显示效果
    if len(kline_data) > 1000:
        # 每10个数据点取1个，减少显示密度
        sample_interval = len(kline_data) // 1000
        kline_sample = kline_data.iloc[::sample_interval]
        print(f"K线数据采样: 从 {len(kline_data)} 条数据采样到 {len(kline_sample)} 条")
    else:
        kline_sample = kline_data
    
    # 绘制市场状态背景
    if 'market_regime' in kline_sample.columns:
        print(f"添加市场状态背景区分...")
        
        # 获取价格范围用于背景高度
        price_min = kline_sample[['low']].min().min()
        price_max = kline_sample[['high']].max().max()
        price_range = price_max - price_min
        background_height = price_range * 0.1  # 背景高度为价格范围的10%
        background_bottom = price_min - background_height
        
        # 绘制市场状态背景
        for i in range(len(kline_sample)):
            current_time = kline_sample.index[i]
            # 确保current_time是pandas Timestamp类型
            if not isinstance(current_time, pd.Timestamp):
                current_time = pd.to_datetime(current_time)
            
            market_regime = kline_sample.iloc[i].get('market_regime', 0)
            
            # 根据市场状态设置背景颜色
            if market_regime == 2:  # 强震荡市场
                background_color = '#FFE5B4'  # 橙色
                alpha = 0.6
            elif market_regime == 1:  # 强趋势市场
                background_color = '#B3D9FF'  # 蓝色
                alpha = 0.6
            else:  # 混合状态
                background_color = '#E0E0E0'  # 灰色
                alpha = 0.4
            
            # 绘制背景矩形
            try:
                ax1.axvspan(current_time, current_time + pd.Timedelta(hours=1), 
                           color=background_color, alpha=alpha, zorder=0)
            except (TypeError, ValueError) as e:
                # 如果时间类型有问题，跳过这个背景绘制
                continue
        
        # 添加图例说明
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#FFE5B4', alpha=0.6, label='强震荡市场'),
            Patch(facecolor='#B3D9FF', alpha=0.6, label='强趋势市场'),
            Patch(facecolor='#E0E0E0', alpha=0.4, label='混合市场')
        ]
        ax1.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(0, 1.02))
    
    # 绘制K线图
    for i in range(len(kline_sample)):
        # 获取当前K线数据
        open_price = kline_sample.iloc[i]['open']
        high_price = kline_sample.iloc[i]['high']
        low_price = kline_sample.iloc[i]['low']
        close_price = kline_sample.iloc[i]['close']
        current_time = kline_sample.index[i]
        
        # 确保current_time是pandas Timestamp类型
        if not isinstance(current_time, pd.Timestamp):
            current_time = pd.to_datetime(current_time)
        
        # 确定K线颜色（红涨绿跌）
        if close_price >= open_price:
            color = '#FF4444'  # 红色，上涨
            body_color = '#FF6666'
        else:
            color = '#44FF44'  # 绿色，下跌
            body_color = '#66FF66'
        
        # 绘制影线（最高价到最低价）
        try:
            ax1.plot([current_time, current_time], [low_price, high_price], 
                    color=color, linewidth=1)
        except (TypeError, ValueError) as e:
            continue
        
        # 绘制实体（开盘价到收盘价）
        body_height = abs(close_price - open_price)
        if body_height > 0:
            try:
                ax1.bar(current_time, body_height, bottom=min(open_price, close_price),
                       color=body_color, width=pd.Timedelta(hours=0.8), alpha=0.8)
            except (TypeError, ValueError) as e:
                continue
    
    # 绘制牛熊线和中轨线
    if 'lineWMA' in kline_sample.columns:
        # 绘制牛熊线（WMA线）- 橙色
        ax1.plot(kline_sample.index, kline_sample['lineWMA'], 
                color='#FF8C00', linewidth=1, alpha=0.8, label='牛熊线(WMA)')
    
    if 'openEMA' in kline_sample.columns and 'closeEMA' in kline_sample.columns:
        # 绘制openEMA和closeEMA线（实线，不同颜色）
        ax1.plot(kline_sample.index, kline_sample['openEMA'], 
                color='#32CD32', linewidth=0.5, alpha=0.8, label='开盘EMA')
        
        ax1.plot(kline_sample.index, kline_sample['closeEMA'], 
                color='#FF6347', linewidth=0.5, alpha=0.8, label='收盘EMA')
    

    

    
    # 绘制交易位置标记
    strategy_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD']
    buy_colors = ['#FF4444', '#44FF44', '#4444FF', '#FFFF44', '#FF44FF', '#44FFFF']  # 买入颜色
    sell_colors = ['#CC0000', '#00CC00', '#0000CC', '#CCCC00', '#CC00CC', '#00CCCC']  # 卖出颜色
    
    color_idx = 0
    legend_added = set()  # 用于跟踪已添加的图例项
    
    # 计算多头base_score平均评分
    long_base_scores = []
    short_base_scores = []
    
    for timeframe, results in all_results.items():
        for result in results:
            if 'trade_log' in result and len(result['trade_log']) > 0:
                trade_log = result['trade_log']
                strategy_color = strategy_colors[color_idx % len(strategy_colors)]
                buy_color = buy_colors[color_idx % len(buy_colors)]
                sell_color = sell_colors[color_idx % len(sell_colors)]
                
                # 收集多头和空头的base_score数据
                open_trades = trade_log[trade_log['action'].str.contains('开多|开空', na=False)]
                for _, trade in open_trades.iterrows():
                    base_score = trade.get('base_score', 0)
                    if pd.notna(base_score) and abs(base_score) > 0.01:
                        if '开多' in trade['action']:
                            long_base_scores.append(base_score)
                        elif '开空' in trade['action']:
                            short_base_scores.append(base_score)
                
                # 绘制开仓点（向上三角形）
                open_trades = trade_log[trade_log['action'].str.contains('开多|开空', na=False)]
                if len(open_trades) > 0:
                    for _, trade in open_trades.iterrows():
                        if 'date' in trade and 'price' in trade and pd.notna(trade['date']):
                            # 确保日期是pandas Timestamp类型
                            trade_date = trade['date']
                            if not isinstance(trade_date, pd.Timestamp):
                                try:
                                    trade_date = pd.to_datetime(trade_date)
                                except:
                                    continue
                            
                            # 判断多单还是空单
                            is_long = '开多' in trade['action']
                            
                            try:
                                if is_long:
                                    # 多单：红色实心三角形无边框
                                    legend_key = f"{result['strategy_name']}_long_open"
                                    if legend_key not in legend_added:
                                        ax1.scatter(trade_date, trade['price'], 
                                                  marker='^', s=60, color='#CC0000', 
                                                  edgecolors='none', linewidth=0, 
                                                  alpha=0.9, zorder=5,
                                                  label=f"{result['strategy_name']} 开多")
                                        legend_added.add(legend_key)
                                    else:
                                        ax1.scatter(trade_date, trade['price'], 
                                                  marker='^', s=60, color='#CC0000', 
                                                  edgecolors='none', linewidth=0, 
                                                  alpha=0.9, zorder=5)
                                else:
                                    # 空单：绿色实心三角形（无边框）
                                    legend_key = f"{result['strategy_name']}_short_open"
                                    if legend_key not in legend_added:
                                        ax1.scatter(trade_date, trade['price'], 
                                                  marker='^', s=60, color='#00CC00', 
                                                  edgecolors='none', linewidth=0, 
                                                  alpha=0.9, zorder=5,
                                                  label=f"{result['strategy_name']} 开空")
                                        legend_added.add(legend_key)
                                    else:
                                        ax1.scatter(trade_date, trade['price'], 
                                                  marker='^', s=60, color='#00CC00', 
                                                  edgecolors='none', linewidth=0, 
                                                  alpha=0.9, zorder=5)
                                
                                # 添加信号评分标签 - 只在有实际评分时显示
                                signal_score = trade.get('signal_score', 0)
                                base_score = trade.get('base_score', 0)
                                trend_score = trade.get('trend_score', 0)
                                
                                # 只有当评分不为0时才显示标签
                                if abs(signal_score) > 0.01 or abs(base_score) > 0.01 or abs(trend_score) > 0.01:
                                    # 创建更详细的标签文本
                                    label_text = f"综合:{signal_score:.3f}\n基础:{base_score:.3f}\n趋势:{trend_score:.3f}"
                                    
                                    # 根据信号强度调整标签位置和大小
                                    if abs(signal_score) > 0.3:
                                        fontsize = 6
                                        y_offset = 20
                                    elif abs(signal_score) > 0.1:
                                        fontsize = 5
                                        y_offset = 15
                                    else:
                                        fontsize = 4
                                        y_offset = 12
                                    
                                    # 添加标签
                                    ax1.annotate(label_text, 
                                                xy=(trade_date, trade['price'] + y_offset),
                                                xytext=(0, 0),
                                                textcoords='offset points',
                                                ha='center', va='bottom',
                                                fontsize=fontsize, color='#CC0000' if is_long else '#00CC00', 
                                                weight='bold',
                                                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8, 
                                                         edgecolor='#CC0000' if is_long else '#00CC00', linewidth=0.5),
                                                alpha=0.5,
                                                arrowprops=dict(arrowstyle='->', 
                                                               color='#CC0000' if is_long else '#00CC00', 
                                                               alpha=0.7))
                            except (TypeError, ValueError) as e:
                                continue
                
                # 绘制平仓点（向下三角形）
                close_trades = trade_log[trade_log['action'].str.contains('平多|平空', na=False)]
                if len(close_trades) > 0:
                    for _, trade in close_trades.iterrows():
                        if 'date' in trade and 'price' in trade and pd.notna(trade['date']):
                            # 确保日期是pandas Timestamp类型
                            trade_date = trade['date']
                            if not isinstance(trade_date, pd.Timestamp):
                                try:
                                    trade_date = pd.to_datetime(trade_date)
                                except:
                                    continue
                            
                            # 判断多单还是空头
                            is_long = '平多' in trade['action']
                            
                            # 确定盈亏状态和颜色
                            pnl = trade.get('pnl', 0)
                            is_profitable = pnl > 0
                            
                            # 根据交易方向确定三角形颜色
                            if is_long:
                                triangle_color = '#CC0000'  # 多单：红色
                            else:
                                triangle_color = '#00CC00'  # 空头：绿色
                            
                            # 根据盈亏确定符号
                            symbol_color = '#FFFFFF'        # 白色符号
                            if is_profitable:
                                symbol_text = '+'           # 盈利："+"号
                            else:
                                symbol_text = '-'           # 亏损："-"号
                            
                            try:
                                if is_long:
                                    # 多单：实心三角形无边框
                                    legend_key = f"{result['strategy_name']}_long_close"
                                    if legend_key not in legend_added:
                                        ax1.scatter(trade_date, trade['price'], 
                                                  marker='v', s=60, color=triangle_color, 
                                                  edgecolors='none', linewidth=0, 
                                                  alpha=0.9, zorder=5,
                                                  label=f"{result['strategy_name']} 平多")
                                        legend_added.add(legend_key)
                                    else:
                                        ax1.scatter(trade_date, trade['price'], 
                                                  marker='v', s=60, color=triangle_color, 
                                                  edgecolors='none', linewidth=0, 
                                                  alpha=0.9, zorder=5)
                                else:
                                    # 空单：实心三角形（无边框）
                                    legend_key = f"{result['strategy_name']}_short_close"
                                    if legend_key not in legend_added:
                                        ax1.scatter(trade_date, trade['price'], 
                                                  marker='v', s=60, color=triangle_color, 
                                                  edgecolors='none', linewidth=0, 
                                                  alpha=0.9, zorder=5,
                                                  label=f"{result['strategy_name']} 平空")
                                        legend_added.add(legend_key)
                                    else:
                                        ax1.scatter(trade_date, trade['price'], 
                                                  marker='v', s=60, color=triangle_color, 
                                                  edgecolors='none', linewidth=0, 
                                                  alpha=0.9, zorder=5)
                                
                                # 在三角形中间添加盈亏符号
                                ax1.text(trade_date, trade['price'], symbol_text, 
                                       fontsize=8, fontweight='bold', color=symbol_color,
                                       ha='center', va='center', zorder=6)
                            except (TypeError, ValueError) as e:
                                continue
                
                color_idx += 1
    
    ax1.set_ylabel('价格 (USDT)')
    ax1.grid(True, alpha=0.3)
    
    # 添加图例（去除重复项）
    handles, labels = ax1.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax1.legend(by_label.values(), by_label.keys(), loc='upper left', fontsize=9)
    
    # 添加评分标签说明
    ax1.text(0.02, 0.98, '评分标签说明:\n综合: 综合评分(基础+趋势+风险+回撤)\n基础: 基础技术指标评分\n趋势: 趋势强度评分', 
             transform=ax1.transAxes, fontsize=9, verticalalignment='top',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8, edgecolor='gray'))
    
    # 下方子图：绘制资金曲线
    ax2.set_title(f'{symbol} 策略资金曲线对比', fontsize=14, fontweight='bold')
    
    # 在资金曲线下方添加市场状态背景
    if 'market_regime' in kline_sample.columns:
        print(f"在资金曲线图添加市场状态背景...")
        
        # 获取资金曲线的时间范围
        equity_times = []
        for timeframe, results in all_results.items():
            for result in results:
                if len(result['total_assets']) > 0:
                    if 'asset_timestamps' in result and len(result['asset_timestamps']) > 0:
                        equity_times = pd.to_datetime(result['asset_timestamps'])
                        break
            if len(equity_times) > 0:
                break
        
        if len(equity_times) > 0:
            # 获取资金范围用于背景高度
            equity_min = min([min(result['total_assets']) for timeframe, results in all_results.items() 
                            for result in results if len(result['total_assets']) > 0])
            equity_max = max([max(result['total_assets']) for timeframe, results in all_results.items() 
                            for result in results if len(result['total_assets']) > 0])
            equity_range = equity_max - equity_min
            background_height = equity_range * 0.1  # 背景高度为资金范围的10%
            background_bottom = equity_min - background_height
            

        
    
    color_idx = 0
    for timeframe, results in all_results.items():
        for result in results:
            if len(result['total_assets']) > 0:
                # 🔧 修复：使用回测记录的准确时间轴
                equity_data = result['total_assets']
                equity_length = len(equity_data)
                
                print(f"策略: {result['strategy_name']}")
                print(f"  资金曲线长度: {equity_length}")
                print(f"  K线数据长度: {len(kline_data)}")
                
                # 优先使用回测记录的时间戳，确保时间对齐准确性
                if 'asset_timestamps' in result and len(result['asset_timestamps']) == equity_length:
                    # 使用回测记录的准确时间戳
                    time_points = pd.to_datetime(result['asset_timestamps'])
                    print(f" 使用回测记录的准确时间轴: {len(time_points)} 个时间点")
                    print(f"  时间范围: {time_points[0]} 至 {time_points[-1]}")
                elif kline_data is not None:
                    # 使用K线数据时间轴，确保长度匹配
                    if equity_length <= len(kline_data):
                        time_points = kline_data.index[:equity_length]
                        print(f" 使用K线数据时间轴: {len(time_points)} 个时间点")
                        print(f"  时间范围: {time_points[0]} 至 {time_points[-1]}")
                    else:
                        # 资金曲线比K线数据长，截断资金曲线
                        time_points = kline_data.index
                        equity_data = equity_data[:len(time_points)]
                        print(f"  截断资金曲线以匹配K线数据")
                else:
                    # 没有任何时间参考，创建默认时间轴
                    # 从配置文件获取回测天数和结束时间
                    from config import BACKTEST_CONFIG, TRADING_CONFIG
                    backtest_days = BACKTEST_CONFIG.get('BACKTEST_DAYS', 60)
                    
                    # 使用配置中的TESTTIME作为结束时间
                    # target_time = TRADING_CONFIG.get('TESTTIME')
                    target_time = None
                    if target_time is None:
                        end_time = datetime.now()
                    else:
                        if isinstance(target_time, str):
                            end_time = datetime.strptime(target_time, "%Y-%m-%d %H:%M:%S")
                        else:
                            end_time = target_time
                    
                    time_points = pd.date_range(
                        start=end_time - timedelta(days=backtest_days),
                        periods=equity_length,
                        freq='H'
                    )
                
                print(f"  最终时间轴长度: {len(time_points)}")
                print(f"  资金曲线长度: {len(equity_data)}")
                
                # 确保时间轴和资金曲线长度完全匹配
                if len(time_points) != len(equity_data):
                    print(f"  最终长度验证失败，进行调整")
                    print(f"  原因: 时间轴长度({len(time_points)}) != 资金曲线长度({len(equity_data)})")
                    min_length = min(len(time_points), len(equity_data))
                    time_points = time_points[:min_length]
                    equity_data = equity_data[:min_length]
                    print(f" 调整后长度: 时间轴={len(time_points)}, 资金曲线={len(equity_data)}")
                else:
                    print(f" 长度验证通过: 时间轴={len(time_points)}, 资金曲线={len(equity_data)}")
                
                # 使用与交易点相同的颜色方案
                strategy_color = strategy_colors[color_idx % len(strategy_colors)]
                
                # 绘制资金曲线
                try:
                    # 确保时间轴是pandas DatetimeIndex类型
                    if not isinstance(time_points, pd.DatetimeIndex):
                        time_points = pd.to_datetime(time_points)
                    
                    ax2.plot(time_points, equity_data, 
                           label=f"{result['strategy_name']} ({result['timeframe']})",
                           color=strategy_color, linewidth=2, alpha=0.8)
                except (TypeError, ValueError) as e:
                    print(f"绘制资金曲线时出错: {e}")
                    continue
                
                # 在资金曲线上标识买入卖出点
                if 'trade_log' in result and len(result['trade_log']) > 0:
                    trade_log = result['trade_log']
                    
                    for _, trade in trade_log.iterrows():
                        if 'date' in trade and pd.notna(trade['date']):
                            # 🔧 修复：精确匹配交易时间点
                            try:
                                trade_time = pd.to_datetime(trade['date'])
                                
                                # 确保time_points是pandas DatetimeIndex类型
                                if not isinstance(time_points, pd.DatetimeIndex):
                                    time_points = pd.to_datetime(time_points)
                                
                                # 尝试精确匹配时间
                                if trade_time in time_points:
                                    # 精确匹配
                                    closest_idx = time_points.get_loc(trade_time)
                                    if isinstance(closest_idx, slice):
                                        closest_idx = closest_idx.start
                                else:
                                    # 找到最接近的时间点（容差在一个时间间隔内）
                                    time_diff = abs(time_points - trade_time)
                                    closest_idx = time_diff.argmin()
                                    
                                    # 验证时间差不超过合理范围（例如一个时间间隔）
                                    min_diff = time_diff.iloc[closest_idx] if hasattr(time_diff, 'iloc') else time_diff[closest_idx]
                                    if min_diff > pd.Timedelta(hours=4):  # 超过4小时认为时间不匹配
                                        print(f"交易时间 {trade_time} 与资金曲线时间轴差异过大: {min_diff}")
                                        continue
                                
                                if closest_idx < len(equity_data):
                                    equity_value = equity_data[closest_idx]
                                    
                                    # 判断交易类型 - 使用与K线图完全相同的颜色和样式
                                    if '开多' in trade['action']:
                                        # 开多：红色实心向上三角形（与K线图一致）
                                        ax2.scatter(time_points[closest_idx], equity_value, 
                                                   marker='^', s=80, color='#CC0000', 
                                                   edgecolors='none', linewidth=0, 
                                                   alpha=0.9, zorder=5)
                                    elif '开空' in trade['action']:
                                        # 开空：绿色实心向上三角形（与K线图一致）
                                        ax2.scatter(time_points[closest_idx], equity_value, 
                                                   marker='^', s=80, color='#00CC00', 
                                                   edgecolors='none', linewidth=0, 
                                                   alpha=0.9, zorder=5)
                                    elif '平多' in trade['action']:
                                        # 平多：红色实心向下三角形（与K线图一致）
                                        pnl = trade.get('pnl', 0)
                                        triangle_color = '#CC0000'  # 多单：红色
                                        symbol_color = '#FFFFFF'    # 白色符号
                                        
                                        # 实心红色三角形（与K线图一致）
                                        ax2.scatter(time_points[closest_idx], equity_value, 
                                                   marker='v', s=80, color=triangle_color, 
                                                   edgecolors='none', linewidth=0, 
                                                   alpha=0.9, zorder=5)
                                        
                                        # 添加盈亏符号（与K线图一致）
                                        if pnl > 0:
                                            symbol_text = '+'  # 盈利："+"号
                                        else:
                                            symbol_text = '-'  # 亏损："-"号
                                        
                                        ax2.text(time_points[closest_idx], equity_value, symbol_text, 
                                               fontsize=6, fontweight='bold', color=symbol_color,
                                               ha='center', va='center', zorder=6)
                                        
                                    elif '平空' in trade['action']:
                                        # 平空：绿色实心向下三角形（与K线图一致）
                                        pnl = trade.get('pnl', 0)
                                        triangle_color = '#00CC00'  # 空单：绿色
                                        symbol_color = '#FFFFFF'    # 白色符号
                                        
                                        # 实心绿色三角形（与K线图一致）
                                        ax2.scatter(time_points[closest_idx], equity_value, 
                                                   marker='v', s=80, color=triangle_color, 
                                                   edgecolors='none', linewidth=0, 
                                                   alpha=0.9, zorder=5)
                                        
                                        # 添加盈亏符号（与K线图一致）
                                        if pnl > 0:
                                            symbol_text = '+'  # 盈利："+"号
                                        else:
                                            symbol_text = '-'  # 亏损："-"号
                                        
                                        ax2.text(time_points[closest_idx], equity_value, symbol_text, 
                                               fontsize=6, fontweight='bold', color=symbol_color,
                                               ha='center', va='center', zorder=6)
                            except Exception as e:
                                # 如果时间匹配失败，跳过这个交易点
                                continue
                
                color_idx += 1
    
    ax2.set_xlabel('时间')
    ax2.set_ylabel('资金 (USDT)')
    ax2.set_title('资金曲线与交易标记', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    
    # 添加资金曲线图例
    ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    # 添加交易标记说明（与K线图标识完全一致）
    legend_elements = [
        plt.Line2D([0], [0], marker='^', color='w', markerfacecolor='#CC0000', 
                   markersize=8, label='开多', markeredgecolor='none', markeredgewidth=0),
        plt.Line2D([0], [0], marker='^', color='w', markerfacecolor='#00CC00', 
                   markersize=8, label='开空', markeredgecolor='none', markeredgewidth=0),
        plt.Line2D([0], [0], marker='v', color='w', markerfacecolor='#CC0000', 
                   markersize=8, label='平多(+盈利/-亏损)', markeredgecolor='none', markeredgewidth=0),
        plt.Line2D([0], [0], marker='v', color='w', markerfacecolor='#00CC00', 
                   markersize=8, label='平空(+盈利/-亏损)', markeredgecolor='none', markeredgewidth=0)
    ]
    
    # 在资金曲线下方添加交易标记图例
    ax2.legend(handles=legend_elements, bbox_to_anchor=(1.05, 0), loc='lower left', 
               title='交易标记说明', title_fontsize=10, fontsize=9)
    
    # 添加初始资金线
    ax2.axhline(y=1000, color='black', linestyle='--', alpha=0.5, label='初始资金')
    

    
    # 设置x轴范围 - 使用资金曲线的实际时间范围
    if kline_data is not None:
        # 获取资金曲线的实际时间范围
        equity_times = []
        for timeframe, results in all_results.items():
            for result in results:
                if len(result['total_assets']) > 0:
                    equity_length = len(result['total_assets'])
                    if equity_length <= len(kline_data):
                        strategy_times = kline_data.index[:equity_length]
                        equity_times.extend(strategy_times)
        
        if equity_times:
            equity_times = pd.to_datetime(equity_times)
            x_min = equity_times.min()
            x_max = equity_times.max()
            print(f"设置图表时间轴范围: {x_min} 至 {x_max}")
            ax1.set_xlim(x_min, x_max)
            ax2.set_xlim(x_min, x_max)
            
            # 🔧 优化：根据时间跨度动态设置日期间隔
            time_span = (x_max - x_min).days
            from config import BACKTEST_CONFIG
            backtest_days = BACKTEST_CONFIG.get('BACKTEST_DAYS', 60)
            
            if time_span <= 7:
                interval = 1  # 7天内每天显示
            elif time_span <= 30:
                interval = 3  # 30天内每3天显示
            elif time_span <= backtest_days:
                interval = 7  # 配置天数内每周显示
            else:
                interval = 14  # 超过配置天数每两周显示
            
            print(f"📅 时间跨度: {time_span}天, 设置日期间隔: {interval}天")
            
            for ax in [ax1, ax2]:
                ax.xaxis.set_major_locator(mdates.DayLocator(interval=interval))
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
                ax.tick_params(axis='x', rotation=45)
                # 设置次要刻度，显示更多时间点但不显示标签
                ax.xaxis.set_minor_locator(mdates.DayLocator(interval=1))
        else:
            # 使用K线数据的时间范围
            ax1.set_xlim(kline_data.index[0], kline_data.index[-1])
            ax2.set_xlim(kline_data.index[0], kline_data.index[-1])
            
            # 🔧 优化：根据时间跨度动态设置日期间隔
            time_span = (kline_data.index[-1] - kline_data.index[0]).days
            from config import BACKTEST_CONFIG
            backtest_days = BACKTEST_CONFIG.get('BACKTEST_DAYS', 60)
            
            if time_span <= 7:
                interval = 1  # 7天内每天显示
            elif time_span <= 30:
                interval = 3  # 30天内每3天显示
            elif time_span <= backtest_days:
                interval = 7  # 配置天数内每周显示
            else:
                interval = 14  # 超过配置天数每两周显示
            
            print(f"📅 时间跨度: {time_span}天, 设置日期间隔: {interval}天")
            
            for ax in [ax1, ax2]:
                ax.xaxis.set_major_locator(mdates.DayLocator(interval=interval))
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
                ax.tick_params(axis='x', rotation=45)
                # 设置次要刻度，显示更多时间点但不显示标签
                ax.xaxis.set_minor_locator(mdates.DayLocator(interval=1))
    
    # 添加多头base_score平均评分统计
    if long_base_scores or short_base_scores:
        # 计算统计信息
        long_avg = np.mean(long_base_scores) if long_base_scores else 0
        short_avg = np.mean(short_base_scores) if short_base_scores else 0
        long_count = len(long_base_scores)
        short_count = len(short_base_scores)
        
        # 在图表上添加统计信息
        stats_text = f"多头base_score统计:\n平均: {long_avg:.3f} (共{long_count}次)\n空头base_score统计:\n平均: {short_avg:.3f} (共{short_count}次)"
        
        # 在图表右上角添加统计信息
        ax1.text(0.98, 0.98, stats_text,
                transform=ax1.transAxes, fontsize=10, verticalalignment='top', horizontalalignment='right',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.9, edgecolor='gray'),
                color='black')
        
        print(f"多头base_score平均评分: {long_avg:.3f} (共{long_count}次)")
        print(f"空头base_score平均评分: {short_avg:.3f} (共{short_count}次)")
    
    plt.tight_layout()
    plt.savefig('equity_curves_with_kline.png', dpi=300, bbox_inches='tight')
    print(" 带K线数据、交易位置和WMA线的资金曲线图已保存为: equity_curves_with_kline.png")
    plt.show()

def cleanup_strategies_data(strategies):
    """清理所有策略的持仓维护数据"""
    try:
        print("🧹 正在清理策略持仓维护数据...")
        
        for strategy_name, strategy in strategies.items():
            if hasattr(strategy, 'reset_position'):
                strategy.reset_position()
                print(f"  ✅ {strategy_name} 持仓状态已重置")
            
            # 确保风险管理器状态重置
            if hasattr(strategy, 'risk_manager') and hasattr(strategy.risk_manager, 'reset_state'):
                strategy.risk_manager.reset_state()
                print(f"  ✅ {strategy_name} 风险管理器状态已重置")
            
            # 确保冷却管理器状态重置
            if hasattr(strategy, 'cooldown_manager') and hasattr(strategy.cooldown_manager, 'reset_state'):
                strategy.cooldown_manager.reset_state()
                print(f"  ✅ {strategy_name} 冷却管理器状态已重置")
        
        print("✅ 所有策略持仓维护数据清理完成")
        logger.info("策略持仓维护数据清理完成")
        
    except Exception as e:
        error_msg = f"清理策略数据时出错: {e}"
        print(f"❌ {error_msg}")
        logger.error(error_msg)

# CSV文件生成功能已删除


def main():
    """主函数 - 回测所有策略，使用配置的时间级别，仅使用真实历史数据"""
    try:
        # 初始化日志
        global logger
        log_file = setup_logging()
        logger = logging.getLogger(__name__)
        
        # 检查依赖包
        print("🔍 检查系统依赖...")
        try:
            if not check_dependencies():
                print("依赖检查失败，但继续执行...")
        except:
            print("依赖检查异常，但继续执行...")
        
        timeframe = TRADING_CONFIG['TIMEFRAME']
        print("=" * 100)
        print("🚀 量化交易策略回测系统启动")
        print(f"时间级别: {timeframe}")
        print("=" * 100)
        print(f"开始量化交易策略回测 - {timeframe}时间级别")
        print("数据获取阶段：仅获取当前时间级别的真实历史数据")
        print("📡 回测过程中：根据当前时间点实时获取相邻时间级别数据")
        print("🕐 确保多时间级别分析的准确性")
        print("=" * 80)
        
        # 记录主程序启动信息到日志
        logger.info("=" * 80)
        logger.info(f"🚀 量化交易策略回测主程序启动 - 时间级别: {timeframe}")
        logger.info("数据获取阶段：仅获取当前时间级别的真实历史数据")
        logger.info("📡 回测过程中：根据当前时间点实时获取相邻时间级别数据")
        logger.info("🕐 确保多时间级别分析的准确性")
        logger.info("=" * 80)
        
        # 加载和处理数据
        print("\n📥 开始数据加载和处理...")
        log_memory_usage("数据加载前")
        features, kline_data = load_and_process_data()
        if features is None:
            error_msg = "数据加载失败，程序退出"
            print(f"{error_msg}")
            logger.error(error_msg)
            return
        log_memory_usage("数据加载后")
        
        # 获取交易对信息
        try:
            data_loader = DataLoader(timeframe=timeframe)
            symbol = data_loader.symbol
            print(f"📈 交易对: {symbol}")
            logger.info(f"交易对: {symbol}")
        except Exception as e:
            error_msg = f"获取交易对信息失败: {e}"
            print(f"{error_msg}")
            logger.warning(error_msg)
            symbol = TRADING_CONFIG.get('SYMBOL', 'UNKNOWN')
        
        # 定义策略
        print("\n定义交易策略...")
        strategies = define_strategies()
        if not strategies:
            error_msg = "策略定义失败"
            print(f"{error_msg}")
            logger.error(error_msg)
            return
        
        print(f"\n🔄 开始{timeframe}时间级别回测...")
        logger.info(f"开始{timeframe}时间级别回测")
        
        # 运行时间级别回测 (传递原始历史数据)
        log_memory_usage("回测前")
        all_results = run_multi_timeframe_backtest(kline_data, strategies)
        if not all_results:
            warning_msg = "回测未产生结果"
            print(f"{warning_msg}")
            logger.warning(warning_msg)
        log_memory_usage("回测后")
        
        # 清理内存
        gc.collect()
        log_memory_usage("内存清理后")
        
        # 运行风险控制测试
        print("\n🛡️ 运行风险控制测试...")
        risk_test_results = run_risk_control_tests(features, strategies)
        
        # 生成综合报告
        print("\n📋 生成综合报告...")
        generate_comprehensive_report(all_results, risk_test_results)
        
        # 创建分析图表
        print("\n创建分析图表...")
        create_analysis_charts(all_results, risk_test_results, kline_data, symbol)
        
        # 清理所有策略的持仓维护数据
        print("\n🧹 清理持仓维护数据...")
        cleanup_strategies_data(strategies)
        
        # CSV文件生成功能已删除
        
        print(f"\n {timeframe}时间级别回测完成!")
        logger.info(f"{timeframe}时间级别回测完成")
        logger.info("=" * 80)
        
    except KeyboardInterrupt:
        print("\n用户中断程序执行")
        logger.warning("用户中断程序执行")
    except Exception as e:
        error_msg = f"主程序执行异常: {e}"
        print(f"{error_msg}")
        logger.error(error_msg)
        import traceback
        logger.error(f"详细错误信息: {traceback.format_exc()}")
        print("程序异常退出，请检查日志文件获取详细信息")



if __name__ == "__main__":
    main()