# -*- coding: utf-8 -*-
"""
夏普优化策略信号生成工具
基于SharpeOptimizedStrategy生成交易信号
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import sys
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_loader import DataLoader
from core.feature_engineer import FeatureEngineer
from core.strategy import SharpeOptimizedStrategy
from config import TRADING_CONFIG, BACKTEST_CONFIG

# 设置中文字体 - 修复matplotlib字体识别问题
try:
    from utils.fix_matplotlib_fonts import force_add_fonts, configure_fonts
    force_add_fonts()
    configure_fonts()
except ImportError:
    # 备用方案
    plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'WenQuanYi Zen Hei', 'SimHei', 'Microsoft YaHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False


def calculate_all_signals_sharpe():
    """
    使用SharpeOptimizedStrategy计算所有数据点的信号
    """
    # 1. 加载数据
    timeframe = TRADING_CONFIG.get('TIMEFRAME', '1h')
    signal_days = BACKTEST_CONFIG.get('BACKTEST_DAYS', 60)
    
    data_loader = DataLoader(timeframe=timeframe)
    
    # 从配置中读取TESTTIME作为end_time
    target_time = TRADING_CONFIG.get('TESTTIME')
    if target_time is None:
        end_time = datetime.now()
    else:
        if isinstance(target_time, str):
            end_time = datetime.strptime(target_time, "%Y-%m-%d %H:%M:%S")
        else:
            end_time = target_time
    
    start_time = end_time - timedelta(days=signal_days)
    
    try:
        kline_data = data_loader.get_klines(
            start_date=start_time.strftime("%Y-%m-%d"),
            end_date=end_time.strftime("%Y-%m-%d")
        )
        
        if kline_data is None or len(kline_data) == 0:
            print(" 无法获取K线数据")
            return None
            
    except Exception as e:
        print(f"数据加载失败: {e}")
        return None
    
    # 2. 特征工程
    feature_engineer = FeatureEngineer()
    features = feature_engineer.generate_features(kline_data)
    
    if features is None or len(features) == 0:
        print(" 特征工程失败")
        return None
    
    # 3. 初始化SharpeOptimizedStrategy
    from config import OPTIMIZED_STRATEGY_CONFIG
    strategy = SharpeOptimizedStrategy(config=OPTIMIZED_STRATEGY_CONFIG, data_loader=data_loader)
    
    # 4. 生成信号
    signals = []
    signal_scores = []
    signal_reasons = []
    base_scores = []
    trend_scores = []
    risk_scores = []
    drawdown_scores = []
    position_sizes = []
    original_signals = []  # 保存原始信号
    filter_reasons = []    # 保存过滤原因
    
    print(f"🔍 开始计算夏普优化策略信号，共 {len(features)} 个数据点...")
    
    for i in range(len(features)):
        # 获取当前数据点及其历史数据
        current_data = features.iloc[:i+1]
        
        if len(current_data) < 3:  # 降低历史数据要求
            signals.append(0)
            base_scores.append(0.0)
            signal_scores.append(0.0)
            signal_reasons.append("数据不足")
            trend_scores.append(0.0)
            risk_scores.append(0.0)
            drawdown_scores.append(0.0)
            position_sizes.append(0.0)
            original_signals.append(0)
            filter_reasons.append("数据不足")
            continue
        
        # 计算信号
        try:
            # 添加调试信息
            if i < 10:  # 只对前10个数据点显示调试信息
                print(f"🔍 计算第 {i+1} 个数据点信号，数据长度: {len(current_data)}")
            
            signal_info = strategy._calculate_signal(current_data, verbose=False)
            
            # 添加更详细的调试信息
            if i < 10:  # 只对前10个数据点显示调试信息
                print(f" 信号: {signal_info.get('signal', 0)}, 评分: {signal_info.get('signal_score', 0.0):.3f}, 原因: {signal_info.get('reason', '未知')}")
            
            signals.append(signal_info.get('signal', 0))
            base_scores.append(signal_info.get('base_score', 0.0))
            signal_scores.append(signal_info.get('signal_score', 0.0))
            signal_reasons.append(signal_info.get('reason', '未知'))
            trend_scores.append(signal_info.get('trend_score', 0.0))
            risk_scores.append(signal_info.get('risk_score', 0.0))
            drawdown_scores.append(signal_info.get('drawdown_score', 0.0))
            
            # 处理position_size，它可能是一个字典
            position_size_info = signal_info.get('position_size', {})
            if isinstance(position_size_info, dict):
                position_sizes.append(position_size_info.get('size', 0.0))
            else:
                position_sizes.append(position_size_info)
            
            # 保存原始信号和过滤信息
            original_signal_info = signal_info.get('original_signal', {})
            original_signal = original_signal_info.get('signal', 0)
            original_signals.append(original_signal)
            
            # 检查是否被过滤
            if signal_info.get('signal', 0) == 0 and original_signal != 0:
                filter_reason = signal_info.get('reason', '未知')
                filter_reasons.append(filter_reason)
                
                # 打印被过滤的信号信息
                current_time = features.index[i] if i < len(features) else "未知时间"
                if hasattr(current_time, 'strftime'):
                    time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    time_str = str(current_time)
                print(f"[{time_str}]信号被过滤: 原始信号 {original_signal} -> 过滤后信号 {signal_info.get('signal', 0)}, 过滤原因: {filter_reason}")
            else:
                filter_reasons.append("")
            
        except Exception as e:
            print(f"第 {i} 个数据点信号计算失败: {e}")
            signals.append(0)
            base_scores.append(0.0)
            signal_scores.append(0.0)
            signal_reasons.append(f"计算失败: {str(e)}")
            trend_scores.append(0.0)
            risk_scores.append(0.0)
            drawdown_scores.append(0.0)
            position_sizes.append(0.0)
            original_signals.append(0)
            filter_reasons.append("计算失败")
    
    # 5. 创建结果DataFrame
    # 确保所有数组长度一致
    min_length = min(len(signals), len(base_scores), len(signal_scores), len(signal_reasons), 
                    len(trend_scores), len(risk_scores), len(drawdown_scores),
                    len(position_sizes), len(original_signals), 
                    len(filter_reasons), len(features))
    
    # 截取到最小长度
    signals = signals[:min_length]
    base_scores = base_scores[:min_length]
    signal_scores = signal_scores[:min_length]
    signal_reasons = signal_reasons[:min_length]
    trend_scores = trend_scores[:min_length]
    risk_scores = risk_scores[:min_length]
    drawdown_scores = drawdown_scores[:min_length]
    position_sizes = position_sizes[:min_length]
    original_signals = original_signals[:min_length]
    filter_reasons = filter_reasons[:min_length]
    
    result_df = features.iloc[:min_length].copy()
    result_df['signal'] = signals
    result_df['base_score'] = base_scores
    result_df['signal_score'] = signal_scores
    result_df['signal_reason'] = signal_reasons
    result_df['trend_score'] = trend_scores
    result_df['risk_score'] = risk_scores
    result_df['drawdown_score'] = drawdown_scores
    result_df['position_size'] = position_sizes
    result_df['original_signal'] = original_signals
    result_df['filter_reason'] = filter_reasons
    
    # 6. 根据sideways_score计算市场状态
    print("🔍 计算市场状态 (基于sideways_score)...")
    
    # 检查是否已有market_regime列（来自特征工程）
    if 'market_regime' in result_df.columns:
        print(f" 使用特征工程计算的market_regime")
        
        # 计算综合sideways_score (如果存在多个sideways_score，取平均值)
        sideways_columns = [col for col in result_df.columns if 'sideways_score' in col]
        if sideways_columns:
            print(f"  发现sideways_score列: {sideways_columns}")
            # 计算综合sideways_score
            result_df['combined_sideways_score'] = result_df[sideways_columns].mean(axis=1)
            
            print(f"  市场状态分布:")
            regime_counts = result_df['market_regime'].value_counts().sort_index()
            regime_names = {0: '混合市场', 1: '强趋势市场', 2: '强震荡市场'}
            for regime, count in regime_counts.items():
                percentage = (count / len(result_df)) * 100
                print(f"    {regime_names[regime]}: {count} 个 ({percentage:.1f}%)")
            
            print(f"  综合sideways_score统计:")
            print(f"    平均: {result_df['combined_sideways_score'].mean():.3f}")
            print(f"    最大: {result_df['combined_sideways_score'].max():.3f}")
            print(f"    最小: {result_df['combined_sideways_score'].min():.3f}")
            print(f"    标准差: {result_df['combined_sideways_score'].std():.3f}")
        else:
            print("   未发现sideways_score列")
    else:
        print("   未发现market_regime列，使用默认市场状态")
        result_df['market_regime'] = 0  # 默认混合市场
        result_df['combined_sideways_score'] = 0.5  # 默认混合市场
    
    return result_df

def plot_kline_with_signals(df):
    """
    绘制K线图并标注信号，包括震荡/趋势行情背景区分
    """
    
    # 创建图形 - 增加一个子图用于显示sideways_score
    fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(15, 16), height_ratios=[3, 1, 1, 1])
    
    # 转换时间索引为datetime
    if isinstance(df.index[0], str):
        df.index = pd.to_datetime(df.index)
    
    # 添加市场状态背景色
    if 'market_regime' in df.columns:
        # 获取价格范围用于背景色
        price_min = df['low'].min()
        price_max = df['high'].max()
        price_range = price_max - price_min
        
        # 为不同市场状态添加背景色
        for i in range(len(df)):
            row = df.iloc[i]
            time = df.index[i]
            market_regime = row.get('market_regime', 0)
            
            # 设置背景色
            if market_regime == 2:  # 强震荡市场
                ax1.axvspan(time - timedelta(hours=0.5), time + timedelta(hours=0.5), 
                           alpha=0.6, color='#FFE5B4', label='强震荡市场' if i == 0 else "")
            elif market_regime == 1:  # 强趋势市场
                ax1.axvspan(time - timedelta(hours=0.5), time + timedelta(hours=0.5), 
                           alpha=0.6, color='#B3D9FF', label='强趋势市场' if i == 0 else "")
            # market_regime == 0 为混合市场，不添加背景色
    
    # 绘制K线图
    for i in range(len(df)):
        row = df.iloc[i]
        time = df.index[i]
        
        # K线颜色和样式
        if row['close'] >= row['open']:
            color = 'red'  # 阳线
            alpha = 0.8
        else:
            color = 'green'  # 阴线
            alpha = 0.8
        
        # 绘制K线实体
        ax1.bar(time, row['close'] - row['open'], 
                bottom=min(row['open'], row['close']),
                width=timedelta(hours=0.8), 
                color=color, alpha=alpha)
        
        # 绘制上下影线
        ax1.plot([time, time], [row['low'], row['high']], 
                color=color, linewidth=1, alpha=alpha)
    
    # 绘制移动平均线
    if 'lineWMA' in df.columns:
        ax1.plot(df.index, df['lineWMA'], label='WMA牛熊线', color='blue', linewidth=2)
    
    if 'openEMA' in df.columns:
        ax1.plot(df.index, df['openEMA'], label='开盘价EMA', color='orange', linewidth=1, alpha=0.7)
    
    if 'closeEMA' in df.columns:
        ax1.plot(df.index, df['closeEMA'], label='收盘价EMA', color='purple', linewidth=1, alpha=0.7)
    
    # 标注信号点
    long_signals = df[df['signal'] == 1]
    short_signals = df[df['signal'] == -1]
    
    # 被过滤的信号（原始信号不为0但最终信号为0）
    filtered_long_signals = df[(df['original_signal'] == 1) & (df['signal'] == 0)]
    filtered_short_signals = df[(df['original_signal'] == -1) & (df['signal'] == 0)]
    
    # 调试信息：打印信号统计
    print(f"🔍 信号统计调试:")
    print(f"  有效做多信号: {len(long_signals)} 个")
    print(f"  有效空头信号: {len(short_signals)} 个")
    print(f"  被过滤做多信号: {len(filtered_long_signals)} 个")
    print(f"  被过滤空头信号: {len(filtered_short_signals)} 个")
    print(f"  原始信号不为0的总数: {len(df[df['original_signal'] != 0])} 个")
    print(f"  最终信号不为0的总数: {len(df[df['signal'] != 0])} 个")
    
    # 检查是否有被过滤的信号
    if len(filtered_long_signals) > 0:
        print(f"  被过滤做多信号示例: {filtered_long_signals[['original_signal', 'signal', 'filter_reason']].head()}")
    if len(filtered_short_signals) > 0:
        print(f"  被过滤空头信号示例: {filtered_short_signals[['original_signal', 'signal', 'filter_reason']].head()}")

    # 做多信号 - 红色小圆点标注，位置在K线下方，去边框
    if len(long_signals) > 0:
        ax1.scatter(long_signals.index, long_signals['low'] - (df['high'].max() - df['low'].min()) * 0.02, 
                   color='red', marker='o', s=10, alpha=1, 
                   label=f'做多信号 ({len(long_signals)}个)', zorder=5, edgecolors='none')
    
    # 空头信号 - 绿色小圆点标注，位置在K线上方，去边框
    if len(short_signals) > 0:
        ax1.scatter(short_signals.index, short_signals['high'] + (df['high'].max() - df['low'].min()) * 0.02, 
                   color='green', marker='o', s=10, alpha=1, 
                   label=f'空头信号 ({len(short_signals)}个)', zorder=5, edgecolors='none')
    
    # 被过滤的做多信号 - 红色X标记标注，透明度30%
    if len(filtered_long_signals) > 0:
        ax1.scatter(filtered_long_signals.index, filtered_long_signals['low'] - (df['high'].max() - df['low'].min()) * 0.02, 
                   color='red', marker='X', s=15, alpha=0.3, 
                   label=f'被过滤做多信号 ({len(filtered_long_signals)}个)', zorder=4, edgecolors='none')
    
    # 被过滤的空头信号 - 绿色X标记标注，透明度30%
    if len(filtered_short_signals) > 0:
        ax1.scatter(filtered_short_signals.index, filtered_short_signals['high'] + (df['high'].max() - df['low'].min()) * 0.02, 
                   color='green', marker='X', s=15, alpha=0.3, 
                   label=f'被过滤空头信号 ({len(filtered_short_signals)}个)', zorder=4, edgecolors='none')
    
    # 设置K线图属性
    ax1.set_title('ETH/USDT K线图与夏普优化策略信号', fontsize=16, fontweight='bold')
    ax1.set_ylabel('价格 (USDT)', fontsize=12)
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # 动态调整日期标签密度
    time_span = (df.index[-1] - df.index[0]).days
    if time_span <= 7:
        interval = 6
    elif time_span <= 30:
        interval = 24
    elif time_span <= 90:
        interval = 72
    else:
        interval = 168
    
    # 格式化x轴时间
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    ax1.xaxis.set_major_locator(mdates.HourLocator(interval=interval))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
    
    # 绘制信号强度图
    signal_scores = df['signal_score'].values
    
    # 添加市场状态背景色到信号强度图
    if 'market_regime' in df.columns:
        for i in range(len(df)):
            row = df.iloc[i]
            time = df.index[i]
            market_regime = row.get('market_regime', 0)
            
            # 设置背景色（与主图保持一致）
            if market_regime == 2:  # 强震荡市场
                ax2.axvspan(time - timedelta(hours=0.5), time + timedelta(hours=0.5), 
                           alpha=0.6, color='#FFE5B4')
            elif market_regime == 1:  # 强趋势市场
                ax2.axvspan(time - timedelta(hours=0.5), time + timedelta(hours=0.5), 
                           alpha=0.6, color='#B3D9FF')
    
    ax2.plot(df.index, signal_scores, color='gray', linewidth=1, alpha=0.7)
    
    # 填充信号区域 - 修复正负值填充逻辑
    positive_scores = np.where(signal_scores > 0, signal_scores, 0)
    negative_scores = np.where(signal_scores < 0, signal_scores, 0)
    
    ax2.fill_between(df.index, positive_scores, 0, 
                      color='red', alpha=0.3, label='做多信号强度')
    ax2.fill_between(df.index, negative_scores, 0, 
                      color='green', alpha=0.3, label='空头信号强度')
    
    # 设置信号图属性
    ax2.set_title('信号强度', fontsize=14, fontweight='bold')
    ax2.set_ylabel('信号强度', fontsize=12)
    ax2.legend(loc='upper left')
    ax2.grid(True, alpha=0.3)
    ax2.axhline(y=0, color='black', linestyle='-', alpha=0.5)
    
    # 绘制仓位大小图
    position_sizes = df['position_size'].values
    
    # 添加市场状态背景色到仓位图
    if 'market_regime' in df.columns:
        for i in range(len(df)):
            row = df.iloc[i]
            time = df.index[i]
            market_regime = row.get('market_regime', 0)
            
            # 设置背景色（与主图保持一致）
            if market_regime == 2:  # 强震荡市场
                ax3.axvspan(time - timedelta(hours=0.5), time + timedelta(hours=0.5), 
                           alpha=0.6, color='#FFE5B4')
            elif market_regime == 1:  # 强趋势市场
                ax3.axvspan(time - timedelta(hours=0.5), time + timedelta(hours=0.5), 
                           alpha=0.6, color='#B3D9FF')
    
    ax3.plot(df.index, position_sizes, color='blue', linewidth=2, alpha=0.8, label='仓位大小')
    
    # 设置仓位图属性
    ax3.set_title('动态仓位管理', fontsize=14, fontweight='bold')
    ax3.set_ylabel('仓位大小', fontsize=12)
    ax3.set_xlabel('时间', fontsize=12)
    ax3.legend(loc='upper left')
    ax3.grid(True, alpha=0.3)
    ax3.axhline(y=0, color='black', linestyle='-', alpha=0.5)
    
    # 格式化x轴时间
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=interval))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
    
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    ax3.xaxis.set_major_locator(mdates.HourLocator(interval=interval))
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45)
    
    # 绘制sideways_score图
    if 'combined_sideways_score' in df.columns:
        # 添加市场状态背景色到sideways_score图
        if 'market_regime' in df.columns:
            for i in range(len(df)):
                row = df.iloc[i]
                time = df.index[i]
                market_regime = row.get('market_regime', 0)
                
                # 设置背景色（与主图保持一致）
                if market_regime == 2:  # 强震荡市场
                    ax4.axvspan(time - timedelta(hours=0.5), time + timedelta(hours=0.5), 
                               alpha=0.6, color='#FFE5B4')
                elif market_regime == 1:  # 强趋势市场
                    ax4.axvspan(time - timedelta(hours=0.5), time + timedelta(hours=0.5), 
                               alpha=0.6, color='#B3D9FF')
        
        # 绘制综合sideways_score
        ax4.plot(df.index, df['combined_sideways_score'], color='purple', linewidth=2, alpha=0.8, label='综合震荡评分')
        
        # 添加阈值线
        ax4.axhline(y=0.7, color='red', linestyle='--', alpha=0.7, label='强震荡阈值 (0.7)')
        ax4.axhline(y=0.3, color='blue', linestyle='--', alpha=0.7, label='强趋势阈值 (0.3)')
        
        # 填充不同市场状态区域
        ax4.fill_between(df.index, df['combined_sideways_score'], 0.7, 
                        where=(df['combined_sideways_score'] >= 0.7), 
                        color='red', alpha=0.2, label='强震荡区域')
        ax4.fill_between(df.index, df['combined_sideways_score'], 0.3, 
                        where=(df['combined_sideways_score'] <= 0.3), 
                        color='blue', alpha=0.2, label='强趋势区域')
        
        # 设置sideways_score图属性
        ax4.set_title('市场状态分析 (基于sideways_score)', fontsize=14, fontweight='bold')
        ax4.set_ylabel('震荡评分', fontsize=12)
        ax4.set_xlabel('时间', fontsize=12)
        ax4.legend(loc='upper left')
        ax4.grid(True, alpha=0.3)
        ax4.set_ylim(0, 1)
        
        # 格式化x轴时间
        ax4.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        ax4.xaxis.set_major_locator(mdates.HourLocator(interval=interval))
        plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45)
        
        # 添加市场状态统计
        if 'market_regime' in df.columns:
            regime_counts = df['market_regime'].value_counts().sort_index()
            regime_names = {0: '混合市场', 1: '强趋势市场', 2: '强震荡市场'}
            stats_text = "市场状态分布:\n"
            for regime, count in regime_counts.items():
                percentage = (count / len(df)) * 100
                stats_text += f"{regime_names[regime]}: {count}个 ({percentage:.1f}%)\n"
            
            ax4.text(0.02, 0.98, stats_text, transform=ax4.transAxes, fontsize=10,
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    else:
        ax4.text(0.5, 0.5, '无sideways_score数据', transform=ax4.transAxes, 
                ha='center', va='center', fontsize=14, color='gray')
        ax4.set_title('市场状态分析', fontsize=14, fontweight='bold')
    
    # 调整布局
    plt.tight_layout()
    
    # 保存图片
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"kline_signals_sharpe_{timestamp}.png"
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    
    return filename

def print_signal_analysis(df):
    """
    打印信号分析报告
    """
    
    print("\n" + "="*60)
    print("夏普优化策略信号分析报告")
    print("="*60)
    
    # 信号统计
    signal_counts = pd.Series(df['signal']).value_counts()
    total_signals = len(df)
    
    # 信号统计
    
    print(f"\n信号统计:")
    print(f"  总数据点: {total_signals}")
    print(f"  做多信号 (1): {signal_counts.get(1, 0)} 个 ({signal_counts.get(1, 0)/total_signals*100:.1f}%)")
    print(f"  空头信号 (-1): {signal_counts.get(-1, 0)} 个 ({signal_counts.get(-1, 0)/total_signals*100:.1f}%)")
    print(f"  观望信号 (0): {signal_counts.get(0, 0)} 个 ({signal_counts.get(0, 0)/total_signals*100:.1f}%)")
    
    print(f"\n信号质量分析:")
    print(f"  有效信号: {len(df[df['signal'] != 0])} 个")
    print(f"  信号有效率: {len(df[df['signal'] != 0]) / len(df) * 100:.1f}%")
    
    # 被过滤信号统计
    filtered_signals = df[(df['original_signal'] != 0) & (df['signal'] == 0)]
    if len(filtered_signals) > 0:
        print(f"  被过滤信号: {len(filtered_signals)} 个")
        print(f"  过滤率: {len(filtered_signals) / len(df[df['original_signal'] != 0]) * 100:.1f}%")
        
        # 被过滤信号的详细统计
        filtered_long = len(filtered_signals[filtered_signals['original_signal'] == 1])
        filtered_short = len(filtered_signals[filtered_signals['original_signal'] == -1])
        print(f"  被过滤做多信号: {filtered_long} 个")
        print(f"  被过滤空头信号: {filtered_short} 个")
    
    # 信号强度分析
    print(f"\n📈 评分系统分析:")
    print(f"  基础评分 (base_score):")
    print(f"    平均: {df['base_score'].mean():.3f}")
    print(f"    最大: {df['base_score'].max():.3f}")
    print(f"    最小: {df['base_score'].min():.3f}")
    print(f"    标准差: {df['base_score'].std():.3f}")
    
    print(f"  趋势评分 (trend_score):")
    print(f"    平均: {df['trend_score'].mean():.3f}")
    print(f"    最大: {df['trend_score'].max():.3f}")
    print(f"    最小: {df['trend_score'].min():.3f}")
    print(f"    标准差: {df['trend_score'].std():.3f}")
    
    print(f"  风险评分 (risk_score):")
    print(f"    平均: {df['risk_score'].mean():.3f}")
    print(f"    最大: {df['risk_score'].max():.3f}")
    print(f"    最小: {df['risk_score'].min():.3f}")
    print(f"    标准差: {df['risk_score'].std():.3f}")
    
    print(f"  回撤评分 (drawdown_score):")
    print(f"    平均: {df['drawdown_score'].mean():.3f}")
    print(f"    最大: {df['drawdown_score'].max():.3f}")
    print(f"    最小: {df['drawdown_score'].min():.3f}")
    print(f"    标准差: {df['drawdown_score'].std():.3f}")
    
    print(f"  综合评分 (signal_score):")
    print(f"    平均: {df['signal_score'].mean():.3f}")
    print(f"    最大: {df['signal_score'].max():.3f}")
    print(f"    最小: {df['signal_score'].min():.3f}")
    
    # 仓位管理分析
    print(f"\n💰 仓位管理分析:")
    print(f"  平均仓位大小: {df['position_size'].mean():.3f}")
    print(f"  最大仓位大小: {df['position_size'].max():.3f}")
    print(f"  最小仓位大小: {df['position_size'].min():.3f}")
    

    
    # 市场状态分析
    if 'market_regime' in df.columns:
        print(f"\n市场状态分析:")
        regime_counts = df['market_regime'].value_counts().sort_index()
        regime_names = {0: '混合市场', 1: '强趋势市场', 2: '强震荡市场'}
        
        for regime, count in regime_counts.items():
            percentage = (count / len(df)) * 100
            print(f"  {regime_names[regime]}: {count} 条 ({percentage:.1f}%)")
        
        # 不同市场状态下的信号分布
        print(f"\n不同市场状态下的信号分布:")
        for regime in [0, 1, 2]:
            regime_data = df[df['market_regime'] == regime]
            if len(regime_data) > 0:
                regime_signals = regime_data['signal'].value_counts()
                print(f"  {regime_names[regime]}:")
                print(f"    做多信号: {regime_signals.get(1, 0)} 个")
                print(f"    空头信号: {regime_signals.get(-1, 0)} 个")
                print(f"    观望信号: {regime_signals.get(0, 0)} 个")
    
    # sideways_score分析
    if 'combined_sideways_score' in df.columns:
        print(f"\n📈 sideways_score分析:")
        print(f"  综合震荡评分统计:")
        print(f"    平均: {df['combined_sideways_score'].mean():.3f}")
        print(f"    最大: {df['combined_sideways_score'].max():.3f}")
        print(f"    最小: {df['combined_sideways_score'].min():.3f}")
        print(f"    标准差: {df['combined_sideways_score'].std():.3f}")
        
        # 震荡评分分布
        high_sideways = len(df[df['combined_sideways_score'] >= 0.7])
        low_sideways = len(df[df['combined_sideways_score'] < 0.3])
        medium_sideways = len(df[(df['combined_sideways_score'] >= 0.3) & (df['combined_sideways_score'] < 0.7)])
        
        print(f"  震荡评分分布:")
        print(f"    强震荡 (≥0.7): {high_sideways} 个 ({high_sideways/len(df)*100:.1f}%)")
        print(f"    混合市场 (0.3-0.7): {medium_sideways} 个 ({medium_sideways/len(df)*100:.1f}%)")
        print(f"    强趋势 (<0.3): {low_sideways} 个 ({low_sideways/len(df)*100:.1f}%)")
        
        # 不同震荡评分下的信号分布
        print(f"\n不同震荡评分下的信号分布:")
        high_sideways_data = df[df['combined_sideways_score'] >= 0.7]
        low_sideways_data = df[df['combined_sideways_score'] < 0.3]
        medium_sideways_data = df[(df['combined_sideways_score'] >= 0.3) & (df['combined_sideways_score'] < 0.7)]
        
        if len(high_sideways_data) > 0:
            high_signals = high_sideways_data['signal'].value_counts()
            print(f"  强震荡市场 (≥0.7):")
            print(f"    做多信号: {high_signals.get(1, 0)} 个")
            print(f"    空头信号: {high_signals.get(-1, 0)} 个")
            print(f"    观望信号: {high_signals.get(0, 0)} 个")
        
        if len(medium_sideways_data) > 0:
            medium_signals = medium_sideways_data['signal'].value_counts()
            print(f"  混合市场 (0.3-0.7):")
            print(f"    做多信号: {medium_signals.get(1, 0)} 个")
            print(f"    空头信号: {medium_signals.get(-1, 0)} 个")
            print(f"    观望信号: {medium_signals.get(0, 0)} 个")
        
        if len(low_sideways_data) > 0:
            low_signals = low_sideways_data['signal'].value_counts()
            print(f"  强趋势市场 (<0.3):")
            print(f"    做多信号: {low_signals.get(1, 0)} 个")
            print(f"    空头信号: {low_signals.get(-1, 0)} 个")
            print(f"    观望信号: {low_signals.get(0, 0)} 个")
    
    # 最近信号
    recent_signals = df[df['signal'] != 0].tail(5)
    if len(recent_signals) > 0:
        print(f"\n🕒 最近5个交易信号:")
        for idx, row in recent_signals.iterrows():
            signal_type = "做多" if row['signal'] == 1 else "做空"
            print(f"  {idx.strftime('%m-%d %H:%M')}: {signal_type}")
            print(f"    基础评分: {row['base_score']:.3f}, 趋势评分: {row['trend_score']:.3f}, 风险评分: {row['risk_score']:.3f}, 回撤评分: {row['drawdown_score']:.3f}")
            print(f"    综合评分: {row['signal_score']:.3f}, 仓位大小: {row['position_size']:.3f}")
            print(f"    信号原因: {row['signal_reason']}")
            print()
    
    print("\n" + "="*60)

def main():
    """
    主函数
    """
    print("🔍 开始计算夏普优化策略信号...")
    
    # 计算所有信号
    df = calculate_all_signals_sharpe()
    
    if df is not None:
        
        # 打印分析报告
        print_signal_analysis(df)
        
        # 绘制K线图
        plot_filename = plot_kline_with_signals(df)
        print(f"📈 图片已保存: {plot_filename}")
        
        # 保存结果到CSV
        df.to_csv('signals_sharpe_results.csv', index=True)
        print("💾 结果已保存到 signals_sharpe_results.csv")
        
        # 保存详细报告
        with open('signals_sharpe_report.txt', 'w', encoding='utf-8') as f:
            f.write("夏普优化策略信号生成报告\n")
            f.write("="*50 + "\n\n")
            
            # 写入信号统计
            signal_counts = pd.Series(df['signal']).value_counts()
            f.write(f"信号统计:\n")
            f.write(f"做多信号 (1): {signal_counts.get(1, 0)} 个\n")
            f.write(f"空头信号 (-1): {signal_counts.get(-1, 0)} 个\n")
            f.write(f"观望信号 (0): {signal_counts.get(0, 0)} 个\n\n")
            
            # 写入最近信号详情
            recent_signals = df[df['signal'] != 0].tail(10)
            if len(recent_signals) > 0:
                f.write("最近10个交易信号详情:\n")
                for idx, row in recent_signals.iterrows():
                    signal_type = "做多" if row['signal'] == 1 else "做空"
                    f.write(f"{idx.strftime('%Y-%m-%d %H:%M')}: {signal_type}\n")
                    f.write(f" 信号强度: {row['signal_score']:.3f}\n")
                    f.write(f" 仓位大小: {row['position_size']:.3f}\n")
                    f.write(f" 信号原因: {row['signal_reason']}\n\n")
        
        print("📄 详细报告已保存到 signals_sharpe_report.txt")
        
    else:
        print(" 无法计算信号")

if __name__ == "__main__":
    main() 