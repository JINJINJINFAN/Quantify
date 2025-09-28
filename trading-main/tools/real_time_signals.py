# -*- coding: utf-8 -*-
"""
实时信号监控工具
"""

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime, timedelta
import time
import warnings
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_loader import DataLoader
from core.feature_engineer import FeatureEngineer
from core.strategy import SharpeOptimizedStrategy
from config import *

warnings.filterwarnings('ignore')

def get_current_signal():
    """获取当前市场信号"""
    try:
        # 初始化组件
        data_loader = DataLoader()
        feature_engineer = FeatureEngineer()
        from config import OPTIMIZED_STRATEGY_CONFIG
        strategy = SharpeOptimizedStrategy(config=OPTIMIZED_STRATEGY_CONFIG, data_loader=data_loader)
        
        # 获取最近数据
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)
        
        start_date_str = start_time.strftime("%Y-%m-%d")
        end_date_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"📡 获取市场数据: {start_date_str} 至 {end_date_str}")
        
        # 获取K线数据
        data = data_loader.get_klines(start_date_str, end_date_str)
        
        if data is None or data.empty:
            print(" 无法获取市场数据")
            return None
        
        print(f"成功获取 {len(data)} 条市场数据")
        
        # 特征工程
        features = feature_engineer.generate_features(data)
        
        if features is None or features.empty:
            print(" 特征工程失败")
            return None
        
        # 计算信号
        signal_info = strategy._calculate_signal(features, verbose=True)
        
        return signal_info, features.iloc[-1]
        
    except Exception as e:
        print(f"获取信号失败: {e}")
        return None, None

def display_signal(signal_info, current_data):
    """显示信号信息"""
    if signal_info is None:
        return
    
    print("\n" + "="*80)
    print(f"实时信号分析 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # 当前价格
    current_price = current_data.get('close', 0)
    print(f"\n💰 当前价格: {current_price:.2f} USDT")
    
    # 核心信号
    signal = signal_info.get('signal', 0)
    signal_type = "🟢 多头" if signal == 1 else "🔴 空头" if signal == -1 else "⚪ 观望"
    print(f"交易信号: {signal_type}")
    print(f"📝 信号原因: {signal_info.get('reason', 'N/A')}")
    
    # 评分系统
    print(f"\n🧮 评分系统:")
    print(f" 基础评分: {signal_info.get('base_score', 0):.3f}")
    print(f" 趋势评分: {signal_info.get('trend_score', 0):.3f}")
    print(f" 风险评分: {signal_info.get('risk_score', 0):.3f}")
    print(f" 回撤评分: {signal_info.get('drawdown_score', 0):.3f}")
    print(f" 综合评分: {signal_info.get('signal_score', 0):.3f}")
    
    # 投资建议
    investment_advice = signal_info.get('investment_advice', '')
    if investment_advice:
        print(f"\n📋 投资建议:")
        print(investment_advice)
    
    # 仓位管理
    position_size = signal_info.get('position_size', {})
    if isinstance(position_size, dict):
        print(f" 仓位大小: {position_size.get('size', 0):.1%}")
        print(f" 仓位方向: {position_size.get('direction', 'N/A')}")
        print(f" 仓位原因: {position_size.get('reason', 'N/A')}")
    else:
        print(f" 仓位大小: {position_size:.1%}")
    
    # 技术指标
    debug_info = signal_info.get('debug_info', {})
    if debug_info:
        print(f"\n技术指标:")
        print(f" RSI: {debug_info.get('rsi', 0):.1f}")
        print(f" MACD: {debug_info.get('macd', 0):.4f}")
        print(f" ADX: {debug_info.get('adx', 0):.1f}")
        print(f" LineWMA: {debug_info.get('lineWMA', 0):.2f}")
        print(f" OpenEMA: {debug_info.get('openEMA', 0):.2f}")
        print(f" CloseEMA: {debug_info.get('closeEMA', 0):.2f}")
        print(f" ATR: {debug_info.get('atr', 0):.2f}")
        print(f" 成交量: {debug_info.get('volume', 0):.0f}")
        print(f" 贪婪指数: {debug_info.get('greed_score', 0):.1f}")
        print(f" 情绪评分: {debug_info.get('sentiment_score', 0):.3f}")
    
    # 过滤器状态
    filters = signal_info.get('filters', {})
    if filters:
        print(f"\n🔍 信号过滤器:")
        signal_score_filter = filters.get('signal_score_filter', {})
        filter_status = " 通过" if signal_score_filter.get('passed', True) else " 被过滤"
        print(f" 过滤状态: {filter_status}")
        print(f" 过滤原因: {signal_score_filter.get('reason', 'N/A')}")
    
    # 市场状态
    market_regime = current_data.get('market_regime', 0)
    market_status = {
        0: "混合市场",
        1: "强趋势市场", 
        2: "强震荡市场"
    }.get(market_regime, "未知")
    print(f"\n🌍 市场状态: {market_status}")
    
    print("="*80)

def main():
    """主函数"""
    print("🚀 实时信号监控工具")
    print(f"交易对: {TRADING_CONFIG['SYMBOL']}")
    print(f"🕐 时间级别: {TRADING_CONFIG['TIMEFRAME']}")
    
    # 获取当前信号
    signal_info, current_data = get_current_signal()
    
    if signal_info is not None:
        display_signal(signal_info, current_data)
    else:
        print(" 无法获取信号")

if __name__ == "__main__":
    main() 