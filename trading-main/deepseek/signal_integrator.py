#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek信号整合器

功能：
1. 将DeepSeek API分析的实时技术指标整合到交易策略中
2. 提供综合评分系统，结合传统技术指标和AI分析
3. 支持期货交易的多空方向判断
4. 提供可配置的权重系统
"""

import logging
from re import S
import time
from typing import Dict, Any, Optional
from .analyzer import DeepSeekAnalyzer

logger = logging.getLogger(__name__)

class DeepSeekSignalIntegrator:
    """
    DeepSeek信号整合器
    将AI分析结果整合到传统交易策略中
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化DeepSeek信号整合器
        
        Args:
            config: 配置字典，包含权重和参数设置
        """
        self.config = config or {}
        
        # 初始化DeepSeek分析器
        try:
            self.deepseek_analyzer = DeepSeekAnalyzer()
            self.enabled = True
            logger.info(" DeepSeek信号整合器初始化成功")
        except Exception as e:
            logger.warning(f"DeepSeek分析器初始化失败: {e}")
            self.deepseek_analyzer = None
            self.enabled = False
         
        # 权重配置
        self.weights = self.config.get('deepseek_weights', {
            'trend_score_weight': 0.40,      # 趋势评分权重
            'indicator_score_weight': 0.35,   # 指标评分权重
            'sentiment_score_weight': 0.25,   # 市场情绪权重
        })
        
        # 信号阈值配置
        self.thresholds = self.config.get('deepseek_thresholds', {
            'strong_bullish': 0.7,   # 强看涨阈值
            'bullish': 0.6,          # 看涨阈值
            'neutral': 0.5,          # 中性阈值
            'bearish': -0.4,         # 看跌阈值（负值）
            'strong_bearish': -0.7   # 强看跌阈值（负值）
        })
    
    def get_deepseek_analysis(self, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        获取DeepSeek分析结果
        
        Args:
            force_refresh: 是否强制刷新缓存
            
        Returns:
            DeepSeek分析结果字典，包含各项指标和评分
        """
        if not self.enabled:
            return None
        
        try:
            # 直接调用analyzer的方法，缓存逻辑已在analyzer中处理
            analysis = self.deepseek_analyzer.get_real_time_analysis(force_refresh=force_refresh)
            
            if analysis and 'trend_score' in analysis:
                logger.debug("✅ 成功获取DeepSeek分析结果")
                return analysis
            else:
                logger.warning("❌ DeepSeek分析结果为空或格式错误")
                return None
                
        except Exception as e:
            logger.error(f"获取DeepSeek分析失败: {e}")
            return None
    
    
   
    def integrate_with_traditional_signal(self, traditional_signal: Dict[str, Any], 
                                        deepseek_weight: float = 0.3) -> Dict[str, Any]:
        """
        将DeepSeek分析结果与传统信号整合
        
        Args:
            traditional_signal: 传统策略生成的信号
            deepseek_weight: DeepSeek信号的权重 (0-1)
            
        Returns:
            整合后的信号字典
        """
        try:
            # 获取DeepSeek分析
            deepseek_analysis = self.get_deepseek_analysis()

            print(f"deepseek_analysis: {deepseek_analysis}")
            
            if not deepseek_analysis:
                logger.warning("无法获取DeepSeek分析，使用传统信号")
                traditional_signal['deepseek_status'] = 'unavailable'
                return traditional_signal

            # 传统信号信息
            t_signal = traditional_signal.get('signal', 0)
            t_signal_score = traditional_signal.get('signal_score', 0)
            t_trend_score = traditional_signal.get('trend_score', 0)
            t_base_score = traditional_signal.get('base_score', 0)
            
            # 提取DeepSeek信号信息
            d_signal = deepseek_analysis.get('signal', 0)
            d_signal_score = deepseek_analysis.get('signal_score', 0)
            d_trend_score = deepseek_analysis.get('trend_score', 0)
            d_base_score = deepseek_analysis.get('base_score', 0)
            
            # 添加调试日志
            logger.debug(f"原始评分数据 - 传统信号: signal_score={t_signal_score}({type(t_signal_score)}), "
                        f"trend_score={t_trend_score}({type(t_trend_score)}), "
                        f"base_score={t_base_score}({type(t_base_score)})")
            logger.debug(f"原始评分数据 - DeepSeek信号: signal_score={d_signal_score}({type(d_signal_score)}), "
                        f"trend_score={d_trend_score}({type(d_trend_score)}), "
                        f"base_score={d_base_score}({type(d_base_score)})")
           
 
   
            # DeepSeek评分过滤：多头评分>0.25，空头评分<-0.2
            reason = 'DeepSeek信号过滤器通过'
            if d_signal == 1 and d_signal_score <= 0.3:
                # 多头信号但评分不够，转为观望
                d_signal = 0
                reason = '多头信号被过滤：评分必须大于0.3分'
                logger.debug(f"DeepSeek多头信号被过滤：评分{d_signal_score:.3f} <= 0.3")
            elif d_signal == -1 and d_signal_score >= -0.3:
                # 空头信号但评分不够，转为观望
                d_signal = 0
                reason = '空头信号被过滤：评分必须小于-0.3分'
                logger.debug(f"DeepSeek空头信号被过滤：评分{d_signal_score:.3f} >= -0.3")

            # 计算综合评分
            if t_signal == 0 and d_signal != 0:
                # 传统信号为观望时，主要参考DeepSeek信号
                integrated_score = d_signal_score
                integrated_direction = d_signal
                integrated_trend_score = d_trend_score
                integrated_base_score = d_base_score
                integrated_signal_from = 'deepseek'
            elif d_signal == 0 and t_signal != 0:
                # DeepSeek信号为观望时，主要参考传统信号
                integrated_score = t_signal_score
                integrated_direction = t_signal
                integrated_trend_score = t_trend_score
                integrated_base_score = t_base_score
                integrated_signal_from = 'traditional'
            else:
                # 两个信号都有方向时，进行加权整合
                integrated_signal_from = 'integrated'
                integrated_score = (t_signal_score * (1 - deepseek_weight) + d_signal_score * deepseek_weight)
                integrated_trend_score = (t_trend_score * (1 - deepseek_weight) + d_trend_score * deepseek_weight)
                integrated_base_score = (t_base_score * (1 - deepseek_weight) + d_base_score * deepseek_weight)
                
                # 方向整合
                if t_signal == d_signal:
                    # 方向一致，加强信号
                    integrated_direction = t_signal
                    integrated_score = min(1.0, integrated_score * 1.1)  # 轻微加强
                    integrated_trend_score = min(1.0, integrated_trend_score * 1.1) 
                    integrated_base_score = min(1.0, integrated_base_score * 1.1)
                else:
                    # 方向冲突，降低信号强度
                    if deepseek_weight > 0.5:
                        integrated_direction = d_signal
                        integrated_score = min(1.0, d_signal_score * 1.1)  # 轻微加强
                        integrated_trend_score = min(1.0, d_trend_score * 1.1) 
                        integrated_base_score = min(1.0, d_base_score * 1.1)
                    else:
                        integrated_direction = t_signal
                        integrated_score = t_signal_score * 0.8  # 降低强度
                        integrated_trend_score = t_trend_score * 0.8
                        integrated_base_score = t_base_score * 0.8 

            # 如果两个信号都为观望，则最终为观望
            if t_signal == 0 and d_signal == 0:
                integrated_direction = 0
                integrated_signal_from = 'integrated'
                
            # 构建整合后的信号增加项
            integrated_signal = traditional_signal.copy()
            integrated_signal.update({
                'signal': integrated_direction,
                'signal_score': integrated_score,
                'trend_score': integrated_trend_score,
                'base_score': integrated_base_score,
                'deepseek_status': 'integrated',
                'deepseek_analysis': deepseek_analysis,
                'signal_from': integrated_signal_from,
                'reason': reason,
                'indicators': deepseek_analysis.get('indicators', {})
            })
            
            logger.debug(f"信号整合完成: 传统={t_signal}({t_signal_score:.3f}), "
                        f"DeepSeek={d_signal}({d_signal_score:.3f})[过滤后], "
                        f"整合={integrated_direction}({integrated_score:.3f})")
            
            return integrated_signal
            
        except Exception as e:
            logger.error(f"信号整合失败: {e}")
            traditional_signal['deepseek_status'] = 'error'
            traditional_signal['deepseek_error'] = str(e)
            return traditional_signal
    
     
    def get_market_analysis(self) -> Optional[Dict[str, Any]]:
        """
        获取市场分析结果（精简版）
        
        Returns:
            精简的市场分析字典
        """
        try:
            analysis = self.get_deepseek_analysis()
            if analysis:
                return {
                    'trend': analysis.get('trend', 'unknown'),
                    'action': analysis.get('action', 'wait'),
                    'advice': analysis.get('advice', '')
                }
            return None
        except Exception as e:
            logger.error(f"获取市场分析失败: {e}")
            return None
    
    def is_enabled(self) -> bool:
        """
        检查DeepSeek整合器是否可用
        
        Returns:
            是否可用
        """
        return self.enabled and self.deepseek_analyzer is not None
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取整合器状态信息
        
        Returns:
            状态信息字典
        """
        return {
            'enabled': self.enabled,
            'analyzer_available': self.deepseek_analyzer is not None
        }