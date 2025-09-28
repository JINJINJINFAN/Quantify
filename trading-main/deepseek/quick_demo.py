#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek ETHUSDT实时技术指标分析 - 快速演示

功能：
1. 获取ETHUSDT实时技术指标
2. 显示MACD、ADX、ATR、布林带、RSI等指标
3. 展示新增的交易量和价格波动指标
4. 显示支撑阻力位
5. 提供期货交易建议
"""


import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from .analyzer import DeepSeekAnalyzer
except ImportError:
    from analyzer import DeepSeekAnalyzer
import json

def main():
    """主函数"""
    print("🚀 DeepSeek ETHUSDT实时技术指标分析演示")
    print("=" * 60)
    
    try:
        # 创建分析器
        analyzer = DeepSeekAnalyzer()
        print("正在获取ETHUSDT实时分析...")
        
        # 获取基础数据和技术指标
        df = analyzer.get_ethusdt_data()
        if df is None:
            print("❌ 无法获取市场数据1")
            return
            
        indicators = analyzer.calculate_technical_indicators(df)
        if not indicators:
            print("❌ 无法计算技术指标")
            return
        
        # 获取实时分析结果
        result = analyzer.get_real_time_analysis(df, force_refresh=False)
        
        if result and 'trend_score' in result:
            # 显示基本信息
            current_price = indicators.get('support_resistance', {}).get('current_price', 0)
            print(f"\n💰 当前价格: ${current_price:,.2f}")
            
            # 显示技术指标
            print("\n📈 技术指标:")
            print("-" * 40)
            
            # MACD
            macd = indicators.get('macd', {})
            print(f"MACD: {macd.get('macd', 0):.2f}")
            print(f"信号线: {macd.get('signal', 0):.2f}")
            print(f"柱状图: {macd.get('histogram', 0):.2f}")
            print(f"趋势: {macd.get('trend', 'N/A')}")
            
            # ADX
            adx = indicators.get('adx', {})
            adx_value = adx.get('adx')
            if adx_value is not None:
                print(f"\nADX: {adx_value:.2f}")
                print(f"趋势强度: {adx.get('trend_strength', 'N/A')}")
                print(f"趋势方向: {adx.get('trend_direction', 'N/A')}")
                print(f"状态: {adx.get('status', 'N/A')}")
            else:
                print(f"\nADX: 数据不足")
                print(f"状态: {adx.get('status', 'N/A')}")
                print(f"需要至少28个数据点来计算ADX")
            
            # RSI
            rsi = indicators.get('rsi', {})
            print(f"\nRSI: {rsi.get('rsi', 0):.2f}")
            print(f"状态: {rsi.get('status', 'N/A')}")
            
            # 布林带
            bb = indicators.get('bollinger_bands', {})
            print(f"\n布林带:")
            print(f" 上轨: ${bb.get('upper', 0):,.2f}")
            print(f" 中轨: ${bb.get('middle', 0):,.2f}")
            print(f" 下轨: ${bb.get('lower', 0):,.2f}")
            print(f" 位置: {bb.get('position', 0):.2f}")
            print(f" 挤压: {bb.get('squeeze', 'N/A')}")
            
            # 新增：交易量指标
            volume = indicators.get('volume', {})
            if volume:
                print(f"\n交易量指标:")
                print(f" 当前成交量: {volume.get('current_volume', 0):,.0f}")
                print(f" 平均成交量: {volume.get('avg_volume', 0):,.0f}")
                print(f" 成交量比率: {volume.get('volume_ratio', 0):.2f}")
                print(f" 成交量趋势: {volume.get('volume_trend', 'N/A')}")
            
            # 新增：价格波动指标
            volatility = indicators.get('price_volatility', {})
            if volatility:
                print(f"\n💹 价格波动指标:")
                print(f" 波动率: {volatility.get('volatility', 0):.2f}%")
                print(f" 波动等级: {volatility.get('volatility_level', 'N/A')}")
                print(f" 价格动量: {volatility.get('price_momentum', 0):.2f}%")
                print(f" 动量方向: {volatility.get('momentum_direction', 'N/A')}")
            
            # 支撑阻力位
            sr = indicators.get('support_resistance', {})
            print(f"\n支撑阻力位:")
            resistance = sr.get('resistance', [])
            support = sr.get('support', [])
            print(f" 阻力位: {[f'${price:,.2f}' for price in resistance]}")
            print(f" 支撑位: {[f'${price:,.2f}' for price in support]}")
            
            # 获取DeepSeek API分析结果
            deepseek_analysis = analyzer.get_deepseek_analysis(indicators)
            if deepseek_analysis:
                # DeepSeek API返回的level数据
                level = deepseek_analysis.get('level', {})
                if level:
                    print(f"\nDeepSeek API价位分析:")
                    print(f" 当前价格: ${level.get('current', 0):,.2f}")
                    print(f" 阻力位: ${level.get('resistance', 0):,.2f}")
                    print(f" 支撑位: ${level.get('support', 0):,.2f}")
                    
                    # 计算距离
                    current_price = level.get('current', 0)
                    resistance_price = level.get('resistance', 0)
                    support_price = level.get('support', 0)
                    
                    if current_price > 0:
                        resistance_distance = ((resistance_price - current_price) / current_price) * 100
                        support_distance = ((current_price - support_price) / current_price) * 100
                        print(f" 距离阻力位: {resistance_distance:.2f}%")
                        print(f" 距离支撑位: {support_distance:.2f}%")
                
                # 显示DeepSeek的其他分析结果
                trend = deepseek_analysis.get('trend', 'N/A')
                risk = deepseek_analysis.get('risk', 'N/A')
                action = deepseek_analysis.get('action', 'N/A')
                advice = deepseek_analysis.get('advice', 'N/A')
                
                print(f"\nDeepSeek API分析结果:")
                print(f" 趋势: {trend}")
                print(f" 风险等级: {risk}")
                print(f" 操作建议: {action}")
                print(f" 投资建议: {advice}")
                
                # 显示DeepSeek的评分
                confidence_score = deepseek_analysis.get('confidence_score', {})
                if confidence_score:
                    print(f"\nDeepSeek API评分:")
                    print(f" 趋势评分: {confidence_score.get('trend_score', 0):.3f}")
                    print(f" 指标评分: {confidence_score.get('indicator_score', 0):.3f}")
                    print(f" 情绪评分: {confidence_score.get('sentiment_score', 0):.3f}")
            
            # 评分系统
            print(f"\n评分系统:")
            print("-" * 40)
            
            trend_score = result.get('trend_score', {})
            print(f"趋势评分: {trend_score.get('trend_score', 0):.3f}")
            print(f"数据来源: {trend_score.get('source', 'N/A')}")
            
            indicator_score = result.get('indicator_score', {})
            print(f"指标评分: {indicator_score.get('indicator_score', 0):.3f}")
            print(f"数据来源: {indicator_score.get('source', 'N/A')}")
            
            sentiment_score = result.get('sentiment_score', {})
            print(f"情绪评分: {sentiment_score.get('sentiment_score', 0):.3f}")
            print(f"数据来源: {sentiment_score.get('source', 'N/A')}")
            
            # 显示DeepSeek信号
            deepseek_signal = result.get('deepseek_signal', 0)
            print(f"DeepSeek信号: {deepseek_signal}")
            
            # 市场分析
            print(f"\n📋 市场分析:")
            print("-" * 40)
            
            trend = result.get('trend', 'unknown')
            action = result.get('action', 'wait')
            advice = result.get('advice', '')
            risk = result.get('risk', 'medium')
            
            print(f"趋势: {trend}")
            print(f"操作建议: {action}")
            print(f"投资建议: {advice}")
            print(f"风险等级: {risk}")
            
            # 显示价位信息
            current_price = result.get('current_price', 0)
            resistance = result.get('resistance', 0)
            support = result.get('support', 0)
            
            print(f"\n💰 价位信息:")
            print(f"当前价格: ${current_price:,.2f}")
            print(f"阻力位: ${resistance:,.2f}")
            print(f"支撑位: ${support:,.2f}")
            
            if current_price > 0 and resistance > 0 and support > 0:
                resistance_distance = ((resistance - current_price) / current_price) * 100
                support_distance = ((current_price - support) / current_price) * 100
                print(f"距离阻力位: {resistance_distance:.2f}%")
                print(f"距离支撑位: {support_distance:.2f}%")
            
            # 期货交易建议
            print(f"\n期货交易建议:")
            print("-" * 40)
            
            # 基于DeepSeek信号的建议
            if deepseek_signal == 1:
                print(" 🟢 DeepSeek信号: 多头信号")
            elif deepseek_signal == -1:
                print(" 🔴 DeepSeek信号: 空头信号")
            else:
                print(" ⏸️ DeepSeek信号: 观望信号")
            
            # 基于趋势的建议
            if trend == 'bullish':
                print(" 📈 趋势: 看涨趋势")
            elif trend == 'bearish':
                print(" 📉 趋势: 看跌趋势")
            else:
                print(" ↔️ 趋势: 横盘整理")
            
            # 基于操作建议的建议
            if action == 'long':
                print(" 🎯 操作建议: 做多")
            elif action == 'short':
                print(" 🎯 操作建议: 做空")
            else:
                print(" 🎯 操作建议: 观望等待")
            
            # 基于交易量的建议
            if volume:
                volume_trend = volume.get('volume_trend', 'normal')
                if volume_trend == 'high':
                    print(" 高成交量，趋势确认性强")
                elif volume_trend == 'low':
                    print(" 低成交量，可能假突破，等待确认")
                else:
                    print("正常成交量，可正常操作")
            
            # 基于波动率的建议
            if volatility:
                volatility_level = volatility.get('volatility_level', 'medium')
                if volatility_level == 'high':
                    print(" 高波动率，风险较大，需严格止损")
                elif volatility_level == 'low':
                    print("低波动率，可能积蓄能量，关注突破")
                else:
                    print(" 适中波动率，适合期货交易")
            
        else:
            print("❌ 无法获取市场数据1")
            
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(" 演示完成！")
    print("=" * 60)

if __name__ == "__main__":
    main() 