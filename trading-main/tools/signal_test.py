# -*- coding: utf-8 -*-
"""
单一数据点信号详情数据获取工具 - 基于SharpeOptimizedStrategy
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_loader import DataLoader
from core.feature_engineer import FeatureEngineer
from core.strategy import SharpeOptimizedStrategy
import warnings
warnings.filterwarnings('ignore')



def print_signal_details(strategy_result):
    """
    打印信号详情信息 - 直接读取strategy.py中calculate_signal方法的返回数据
    
    Args:
        strategy_result: strategy.py中calculate_signal方法返回的字典
    """
    if not isinstance(strategy_result, dict):
        print(f"数据格式错误: 期望字典类型，实际为 {type(strategy_result)}")
        return
    
    print("\n" + "="*80)
    print("夏普优化策略信号分析报告")
    print("="*80)
    
    # 核心信号结果
    print(f"\n核心信号结果:")
    signal = strategy_result.get('signal', 0)
    signal_type = "多头" if signal == 1 else "空头" if signal == -1 else "观望"
    signal_emoji = "🟢" if signal == 1 else "🔴" if signal == -1 else "⚪"
    
    print(f" 信号类型: {signal_emoji} {signal_type}")
    print(f" 信号原因: {strategy_result.get('reason', 'N/A')}")
    
    # 评分系统
    print(f"\n🧮 评分系统:")
    print(f" 基础评分: {strategy_result.get('base_score', 0):.3f}")
    print(f" 趋势评分: {strategy_result.get('trend_score', 0):.3f}")
    print(f" 风险评分: {strategy_result.get('risk_score', 0):.3f}")
    print(f" 回撤评分: {strategy_result.get('drawdown_score', 0):.3f}")
    print(f" 综合评分: {strategy_result.get('signal_score', 0):.3f}")
    
    # 仓位管理
    position_size = strategy_result.get('position_size', {})
    if isinstance(position_size, dict):
        print(f" 仓位大小: {position_size.get('size', 0):.1%}")
        print(f" 仓位方向: {position_size.get('direction', 'N/A')}")
        print(f" 仓位原因: {position_size.get('reason', 'N/A')}")
    else:
        print(f" 仓位大小: {position_size:.1%}")
    
    # 调试信息
    debug_info = strategy_result.get('debug', {})
    if debug_info:
        print(f"\n🔧 技术指标详情:")
        print(f" ADX: {debug_info.get('adx', 0):.1f}")
        print(f" ADX评分: {debug_info.get('adx_score', 0):.3f}")
        print(f" DI+: {debug_info.get('di_plus', 0):.1f}")
        print(f" DI-: {debug_info.get('di_minus', 0):.1f}")
        print(f" LineWMA评分: {debug_info.get('line_wma_score', 0):.3f}")
        print(f" RSI: {debug_info.get('rsi', 0):.1f}")
        print(f" RSI评分: {debug_info.get('rsi_score', 0):.3f}")
        print(f" MACD: {debug_info.get('macd', 0):.4f}")
        print(f" MACD信号线: {debug_info.get('macd_signal', 0):.4f}")
        print(f" MACD评分: {debug_info.get('macd_score', 0):.3f}")
        print(f" LineWMA: {debug_info.get('line_wma', 0):.4f}")
        print(f" OpenEMA: {debug_info.get('open_ema', 0):.4f}")
        print(f" CloseEMA: {debug_info.get('close_ema', 0):.4f}")
        print(f" OBV: {debug_info.get('obv', 0):.0f}")
        print(f" OBV评分: {debug_info.get('obv_score', 0):.3f}")
        print(f" VIX恐慌指数: {debug_info.get('vix_fear', 0):.1f}")
        print(f" 贪婪指数: {debug_info.get('greed_score', 0):.1f}")
        print(f" 市场情绪评分: {debug_info.get('marker_score', 0):.3f}")
        # print(f" 新闻情感评分: {debug_info.get('news_sentiment_score', 0):.3f} (原始情感)")

        threshold = debug_info.get('threshold', 0)
        print(f" 信号阈值: ±{threshold:.3f} (多头≥{threshold:.3f}, 空头≤-{threshold:.3f})")
    
    # 过滤器信息
    filters = strategy_result.get('filters', {})
    if filters:
        print(f"\n🔍 信号过滤器状态:")
        signal_score_filter = filters.get('signal_score_filter', {})
        print(f" 是否通过过滤: {' 是' if signal_score_filter.get('passed', True) else ' 否'}")
        print(f" 过滤原因: {signal_score_filter.get('reason', 'N/A')}")
        
        # 显示其他过滤器状态
        for filter_name, filter_status in filters.items():
            if filter_name != 'signal_score_filter':
                status_icon = "" if filter_status.get('passed', True) else ""
                print(f" {status_icon} {filter_name}: {filter_status.get('reason', '通过')}")
    
    
    print("="*80)

def main():
    """主函数"""
    print("🚀 单一数据点信号详情数据获取工具 - 夏普优化策略版本")
    print("="*80)
    
    # 直接调用strategy.py中的calculate_signal方法
    try:
        from core.strategy import SharpeOptimizedStrategy
        from core.data_loader import DataLoader
        from config import BACKTEST_CONFIG, TRADING_CONFIG
        
        # 初始化数据加载器
        data_loader = DataLoader()
        
        # 初始化策略
        from config import OPTIMIZED_STRATEGY_CONFIG
        strategy = SharpeOptimizedStrategy(config=OPTIMIZED_STRATEGY_CONFIG, data_loader=data_loader)
        strategy.debug_mode = True  # 启用调试模式
        
        # 获取数据 - 从TRADING_CONFIG中读取TESTTIME
        target_time = TRADING_CONFIG.get('TESTTIME')
        
        # 加载数据
        # 计算时间范围
        if target_time is None:
            end_time = datetime.now()
        else:
            if isinstance(target_time, str):
                end_time = datetime.strptime(target_time, "%Y-%m-%d %H:%M:%S")
            else:
                end_time = target_time
        
        # 获取过去N天的数据（动态读取配置文件）
       
        backtest_days = BACKTEST_CONFIG.get('BACKTEST_DAYS', 90)

        start_time = end_time - timedelta(days=backtest_days)
        
        start_date_str = start_time.strftime("%Y-%m-%d")
        end_date_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"📅 数据获取范围: {start_date_str} 至 {end_date_str}")
        
        # 获取K线数据
        data = data_loader.get_klines(start_date_str, end_date_str)
        
        if data is None or data.empty:
            print(" 无法获取K线数据")
            return None
        
        # 检查数据格式
        # print(f"🔍 数据类型: {type(data)}")
        # print(f"🔍 数据形状: {data.shape}")
        # print(f"🔍 数据列: {list(data.columns)}")
        # print(f"🔍 索引类型: {type(data.index)}")
        # print(f"🔍 索引前5个: {data.index[:5]}")
        
        # 验证时间索引
        if data.index.isna().any():
            print("警告: 时间索引包含NaN值")
            print(f"🔍 NaN索引数量: {data.index.isna().sum()}")
        
        # 确保索引是datetime类型
        if not isinstance(data.index, pd.DatetimeIndex):
            print("警告: 索引不是DatetimeIndex类型，尝试转换")
            try:
                data.index = pd.to_datetime(data.index)
            except Exception as e:
                print(f"索引转换失败: {e}")
                return None
        
        print(f"成功加载 {len(data)} 条K线数据")
        
        # 执行特征工程
        from core.feature_engineer import FeatureEngineer
        feature_engineer = FeatureEngineer()
        data = feature_engineer.generate_features(data)
        
        if data is None or data.empty:
            print(" 特征工程失败")
            return None
        
        print(f"特征工程完成，生成了 {len(data.columns)} 个技术指标")
        
        if data is not None and len(data) > 0:
            # 调用策略的_calculate_signal方法
            strategy_result = strategy._calculate_signal(data, verbose=True)
            
            # 打印详细信息
            print_signal_details(strategy_result)
            
            return strategy_result
        else:
            print(" 无法获取数据")
            return None
            
    except Exception as e:
        print(f"执行失败: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    main() 