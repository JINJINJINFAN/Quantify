# -*- coding: utf-8 -*-
"""
快速信号查看工具
"""

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime, timedelta
import warnings
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_loader import DataLoader
from core.feature_engineer import FeatureEngineer
from core.strategy import SharpeOptimizedStrategy
from config import *

warnings.filterwarnings('ignore')

def quick_signal_check():
    """快速检查当前信号"""
    try:
        print("🔍 正在获取当前信号...")
        
        # 初始化组件
        data_loader = DataLoader()
        feature_engineer = FeatureEngineer()
        from config import OPTIMIZED_STRATEGY_CONFIG
        strategy = SharpeOptimizedStrategy(config=OPTIMIZED_STRATEGY_CONFIG, data_loader=data_loader, mode='realtime')
        
        # 获取最近数据
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)
        
        start_date_str = start_time.strftime("%Y-%m-%d")
        end_date_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 获取K线数据
        data = data_loader.get_klines(start_date_str, end_date_str)
        
        if data is None or data.empty:
            print(" 无法获取市场数据")
            return
        
        # 特征工程
        features = feature_engineer.generate_features(data)
        
        if features is None or features.empty:
            print(" 特征工程失败")
            return
        
        # 计算信号
        signal_info = strategy._calculate_signal(features, verbose=False)
        current_data = features.iloc[-1]
        
        # 显示结果
        current_time = datetime.now()
        current_price = current_data.get('close', 0)
        signal = signal_info.get('signal', 0)
        
        print(f"\n{'='*50}")
        print(f"实时信号 - {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*50}")
        
        # 信号类型
        if signal == 1:
            print(f"🟢 多头信号")
        elif signal == -1:
            print(f"🔴 空头信号")
        else:
            print(f"⚪ 观望信号")
        
        print(f"💰 当前价格: {current_price:.2f} USDT")
        print(f"综合评分: {signal_info.get('signal_score', 0):.3f}")
        print(f"基础评分: {signal_info.get('base_score', 0):.3f}")
        print(f"趋势评分: {signal_info.get('trend_score', 0):.3f}")
        
        # 显示投资建议
        investment_advice = signal_info.get('investment_advice', '')
        if investment_advice:
            print(f"\n📋 投资建议:")
            print(investment_advice)
        
        # 过滤器状态
        filters = signal_info.get('filters', {})
        if filters:
            signal_score_filter = filters.get('signal_score_filter', {})
            if signal_score_filter.get('passed', True) is False:
                print(f"🔍 被过滤: {signal_score_filter.get('reason', 'N/A')}")
        
        # 技术指标
        debug_info = signal_info.get('debug_info', {})
        if debug_info:
            print(f"\n📈 技术指标:")
            print(f" RSI: {debug_info.get('rsi', 0):.1f}")
            print(f" MACD: {debug_info.get('macd', 0):.4f}")
            print(f" ADX: {debug_info.get('adx', 0):.1f}")
            print(f" LineWMA: {debug_info.get('lineWMA', 0):.2f}")
        
        print(f"{'='*50}")
        
    except Exception as e:
        print(f"检查失败: {e}")

if __name__ == "__main__":
    quick_signal_check() 