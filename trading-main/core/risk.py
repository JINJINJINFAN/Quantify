#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风险管理模块 - 负责交易策略的风险控制和管理
"""

import logging
from math import log
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class RiskManager:
    """风险管理器 - 负责交易策略的风险控制"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化风险管理器"""
        self.config = config
        
        # 风险管理配置
        self.stop_loss_config = config.get('risk_management', {}).get('stop_loss', {})
        self.take_profit_config = config.get('risk_management', {}).get('take_profit', {})
        
        # 仓位状态
        self.position = 0  # 0=无仓位, 1=多仓, -1=空仓
        self.entry_price = 0.0
        self.position_quantity = 0.0  # 持仓数量
        self.current_price = 0.0  # 当前价格
        self.leverage = config.get('leverage', 8.0)  # 杠杆倍数
        
        # 持仓期间的高低点
        self.high_point = float('-inf')  # 持仓期间的最高点
        self.low_point = float('inf')  # 持仓期间的最低点
        self.entry_time = None  # 开仓时间
        self.holding_periods = 0  # 持仓周期数
        
        # 盈亏状态
        self.position_unrealized_pnl = 0.0
        self.position_unrealized_pnl_percent = 0.0
        
        # 保证金信息
        self.position_value = 0.0  # 持仓价值
        self.margin_value = 0.0  # 保证金
        
        # 夏普比率相关的风险参数
        sharpe_params = config.get('sharpe_params', {})
        self.sharpe_lookback = sharpe_params.get('sharpe_lookback', 30)
        self.target_sharpe = sharpe_params.get('target_sharpe', 1.0)
        self.max_risk_multiplier = sharpe_params.get('max_risk_multiplier', 2.0)
        self.risk_multiplier = sharpe_params.get('initial_risk_multiplier', 1.0)
    
    def should_stop_loss(self, current_price: float, current_features: Optional[Dict] = None, 
                        current_time: Optional[datetime] = None) -> Tuple[bool, Optional[str]]:
        """检查是否应该止损"""
        if self.position == 0:
            return False, None

        # 基础计算
        loss_ratio = self._calculate_ratio(current_price, self.leverage)
        if loss_ratio >= 0:  # 盈利状态不止损
            return False, None
            
        time_str = current_time.strftime('%Y-%m-%d %H:%M:%S') if current_time else "N/A"
        margin_value = self._get_margin_value()
        
        # 记录调试信息
        self._log_stop_loss_check(time_str, current_price, loss_ratio, margin_value)
        
        # 获取配置
        fixed_stop_ratio = abs(self.stop_loss_config.get('fixed_stop_loss', -0.08)) #获取的是负值，所以需要取绝对值
        

        logger.info(f"fixed_stop_ratio: {fixed_stop_ratio}")
        logger.info(f"loss_ratio: {loss_ratio}")

        # 1. 固定止损
        if self.stop_loss_config.get('enable_fixed_stop_loss', True) and loss_ratio <= -fixed_stop_ratio:
            return True, f"固定止损[亏损{abs(loss_ratio)*100:.1f}% 达到阈值 {fixed_stop_ratio*100:.1f}%]"

        # 2. 信号评分止损
        if self.stop_loss_config.get('enable_signal_score_stop_loss', True):
            result = self._check_signal_score_stop_loss(current_features, loss_ratio, time_str, margin_value)
            if result[0]:
                return result
        
        return False, None

    def should_take_profit(self, current_price: float, current_features: Optional[Dict] = None, 
                          current_time: Optional[datetime] = None) -> Tuple[bool, Optional[str]]:
        """检查是否应该止盈 - 盈利状态下的止盈逻辑"""
        if self.position == 0:
            return False, None
        
        # 计算当前盈亏比例和基本信息
        profit_ratio = self._calculate_ratio(current_price, self.leverage)
        time_str = current_time.strftime('%Y-%m-%d %H:%M:%S') if current_time else "N/A"
        position_desc = "多头" if self.position == 1 else "空头"
        position_value = self.position_quantity * self.entry_price if self.position_quantity > 0 else 0
        margin_value = position_value / self.leverage if self.leverage > 0 else 0
        
        # 记录止盈检查日志
        logger.debug(f"[{time_str}] 止盈检查 - {position_desc}持仓, 数量:{self.position_quantity:.4f}, 杠杆:{self.leverage}x, "
                   f"保证金:${margin_value:.2f}, 开仓价:{self.entry_price:.2f}, 当前价:{current_price:.2f}, 实际盈利:{profit_ratio*100:.2f}%")
        
        # 提取特征数据的辅助函数
        def get_feature_value(feature_name: str, default_value: float = 0.0) -> float:
            """从current_features中提取特征值，支持enhanced_row结构"""
            if not current_features:
                return default_value
            
            if isinstance(current_features, dict) and 'row_data' in current_features:
                return current_features.get('row_data', {}).get(feature_name, default_value)
            else:
                return current_features.get(feature_name, default_value)
        
        # 止盈触发函数
        def trigger_take_profit(reason: str) -> Tuple[bool, str]:
            """触发止盈并返回结果"""
            print(f"🟢 {reason} - 数量:{self.position_quantity:.4f}, 杠杆:{self.leverage}x, 保证金:${margin_value:.2f}")
            return True, reason
        
        
        # 确保只在盈利状态下执行回调止盈逻辑
        if profit_ratio > 0:
            # 1. 回调止盈（第一优先级 - 提前）
            if self.take_profit_config.get('enable_callback', True):
                callback_ratio = self.take_profit_config.get('callback_ratio', 0.03)
                if self.position == 1:  # 多仓
                    # 检查回调止盈（高低点已在check_risk_management中更新）

                    if current_price < self.high_point and self.high_point > 0:  # 确保有有效的高点
                        current_callback_ratio = (self.high_point - current_price) / self.high_point
                        if current_callback_ratio >= callback_ratio:
                            reason = f"多仓回调止盈(盈利{profit_ratio*100:.1f}%, 回调{current_callback_ratio*100:.1f}%)"
                            return trigger_take_profit(reason)
                elif self.position == -1:  # 空仓
                    # 检查回调止盈（高低点已在check_risk_management中更新）
                    
                    if self.low_point < float('inf'):  # 确保有有效的低点
                        # 空仓回调止盈：当价格从低点反弹超过阈值时触发
                        logger.debug(f"空仓回调检查 - 低点: {self.low_point}, 当前价: {current_price}")
                        if current_price > self.low_point:  # 价格反弹了
                            current_callback_ratio = (current_price - self.low_point) / self.low_point
                            logger.debug(f"[{time_str}] 空仓反弹检查: 低点{self.low_point:.2f}, 当前价{current_price:.2f}, 反弹比例{current_callback_ratio*100:.2f}%, 阈值{callback_ratio*100:.2f}%")
                            if current_callback_ratio >= callback_ratio:
                                reason = f"空仓回调止盈(盈利{profit_ratio*100:.1f}%, 反弹{current_callback_ratio*100:.1f}%)"
                                return trigger_take_profit(reason)
        
        # 2. LineWMA反转止盈（第二优先级 - 延后）
        linewma_take_profit_enabled = self.take_profit_config.get('linewma_take_profit_enabled', True)
        if linewma_take_profit_enabled:
            line_wma = get_feature_value('lineWMA', 0)
            current_signal_score = get_feature_value('signal_score', 0)
            
            if line_wma is not None and line_wma > 0:
                if self.position == 1 and current_price < line_wma and current_signal_score < 0.0:  # 多仓：价格跌破LineWMA
                    status = "盈利" if profit_ratio > 0 else "亏损"
                    reason = f"多仓LineWMA反转止盈({status}{profit_ratio*100:.1f}%)"
                    return trigger_take_profit(reason)
                elif self.position == -1 and current_price > line_wma and current_signal_score > 0.0:  # 空仓：价格突破LineWMA
                    status = "盈利" if profit_ratio > 0 else "亏损"
                    reason = f"空仓LineWMA反转止盈({status}{profit_ratio*100:.1f}%)"
                    return trigger_take_profit(reason)
        

        
        # 3. 时间止盈（第三优先级）
        time_based_take_profit_enabled = self.take_profit_config.get('time_based_take_profit', True)
        time_based_periods = self.take_profit_config.get('time_based_periods', 20)
        
        if time_based_take_profit_enabled and self.holding_periods >= time_based_periods and profit_ratio > 0:
            reason = f"时间止损止盈(持仓{self.holding_periods}周期, 盈利{profit_ratio*100:.1f}%)"
            return trigger_take_profit(reason)
        

        
        return False, None

    def check_risk_management(self, current_price: float, current_features: Optional[Dict] = None, 
                             current_time: Optional[datetime] = None) -> Tuple[str, str]:
        """
        检查风险管理 - 根据盈亏状态分别触发止盈或止损逻辑
        
        Returns:
            tuple: (action, reason)
        """
        if self.position == 0:
            return 'hold', '无持仓'
        
        # 计算当前盈亏比例
        profit_ratio = self._calculate_ratio(current_price, self.leverage)
        
        # 添加详细的调试信息
        time_str = current_time.strftime('%Y-%m-%d %H:%M:%S') if current_time else "N/A"
        position_desc = "多头" if self.position == 1 else "空头"
        
        # 计算保证金信息
        position_value = self.position_quantity * self.entry_price if self.position_quantity > 0 else 0
        margin_value = position_value / self.leverage if self.leverage > 0 else 0
        
        logger.debug(f"[{time_str}] 风险管理检查 - 持仓: {position_desc}, 数量: {self.position_quantity:.4f}, "
                   f"杠杆: {self.leverage}x, 保证金: ${margin_value:.2f}, 持仓价值: ${position_value:.2f}, "
                   f"开仓价: ${self.entry_price:.2f}, 当前价: ${current_price:.2f}, 盈亏: {profit_ratio*100:.2f}%")
        
        # 先更新高低点（确保在检查止盈止损之前更新）
        self._update_high_low_points(current_price)
        
        # 根据盈亏状态分别处理
        if profit_ratio > 0:  # 盈利状态 - 触发止盈逻辑
            should_take, take_reason = self.should_take_profit(current_price, current_features, current_time)
            if should_take:
                logger.debug(f"[{time_str}] 触发止盈: {take_reason}")
                return 'take_profit', take_reason
        else:  # 亏损状态 - 触发止损逻辑
            logger.debug(f"[{time_str}] 亏损状态检查止损 - 盈亏: {profit_ratio*100:.2f}%")
            should_stop, stop_reason = self.should_stop_loss(current_price, current_features, current_time)
            if should_stop:
                logger.debug(f"[{time_str}] 触发止损: {stop_reason}")
                return 'stop_loss', stop_reason
        
        return 'hold', '继续持仓'
    
    def validate_risk_management_config(self) -> Dict[str, Any]:
        """
        验证风险管理配置的一致性
        
        Returns:
            dict: 验证结果
        """
        validation_result = {
            'valid': True,
            'issues': [],
            'warnings': [],
            'config_summary': {}
        }
        
        try:
            # 检查止损配置
            stop_loss_config = self.stop_loss_config
            fixed_stop_loss = stop_loss_config.get('fixed_stop_loss', -0.08)
            validation_result['config_summary']['stop_loss'] = {
                'fixed_stop_loss': fixed_stop_loss,
                'fixed_stop_loss_percent': abs(fixed_stop_loss) * 100
            }
            
            # 检查止盈配置
            take_profit_config = self.take_profit_config
            validation_result['config_summary']['take_profit'] = {
                'callback_enabled': take_profit_config.get('enable_callback', True),
                'linewma_enabled': take_profit_config.get('linewma_take_profit_enabled', False),
                'time_based_enabled': take_profit_config.get('time_based_take_profit', False)
            }
            
            # 检查杠杆倍数
            validation_result['config_summary']['leverage'] = {
                'current_leverage': self.leverage,
                'leverage_effect': f"价格变动1% → 保证金盈亏{self.leverage}%"
            }
            
            # 验证配置合理性
            if abs(fixed_stop_loss) > 0.5:  # 止损超过50%
                validation_result['warnings'].append(f"固定止损比例过高: {abs(fixed_stop_loss)*100:.1f}%")
            

            
            if self.leverage > 20:  # 杠杆超过20倍
                validation_result['warnings'].append(f"杠杆倍数过高: {self.leverage}x")
            
            # 检查杠杆倍数合理性
            if self.leverage > 20:  # 杠杆超过20倍
                validation_result['warnings'].append(f"杠杆倍数过高: {self.leverage}x")
            
            logger.info(f"风险管理配置验证完成 - 杠杆:{self.leverage}x, 止损:{abs(fixed_stop_loss)*100:.1f}%")
            
        except Exception as e:
            validation_result['valid'] = False
            validation_result['issues'].append(f"配置验证异常: {str(e)}")
            logger.error(f"风险管理配置验证失败: {e}")
        
        return validation_result
    
    def get_position_status(self, current_price: float) -> Dict[str, Any]:
        """
        获取当前持仓状态信息
        
        Args:
            current_price: 当前价格
            
        Returns:
            dict: 包含盈亏状态、比例等信息
        """
        if self.position == 0:
            return {
                'position': 0,
                'profit_ratio': 0,
                'status': '无持仓',
                'is_profitable': False
            }
        
        # 计算盈亏比例
        profit_ratio = self._calculate_ratio(current_price, self.leverage)
        
        # 计算保证金信息
        position_value = self.position_quantity * self.entry_price if self.position_quantity > 0 else 0
        margin_value = position_value / self.leverage if self.leverage > 0 else 0
        
        return {
            'position': self.position,
            'profit_ratio': profit_ratio,
            'status': '盈利' if profit_ratio > 0 else '亏损',
            'is_profitable': profit_ratio > 0,
            'entry_price': self.entry_price,
            'current_price': current_price,
            'position_quantity': self.position_quantity,
            'leverage': self.leverage,
            'position_value': position_value,
            'margin_value': margin_value
        }
    
    def should_open_position(self, signal: int, current_features: Optional[Dict] = None, 
                           current_time: Optional[datetime] = None) -> bool:
        """
        检查是否应该开仓 - 防止同方向重复开仓
        
        Args:
            signal: 交易信号 (1=多头, -1=空头, 0=观望)
            current_features: 当前特征数据
            current_time: 当前时间
            
        Returns:
            bool: 是否应该开仓
        """
        # 添加调试信息
        logger.debug(f"[{current_time}] should_open_position检查 - signal: {signal}, position: {self.position}")
        
        # 无信号时不开仓
        if signal == 0:
            logger.info(f"[{current_time}] 无信号时不开仓 - signal: {signal}")
            return False
        
        # 检查是否已经持有相同方向的仓位
        if self.position == signal:
            position_name = "多头" if signal == 1 else "空头"
            logger.info(f"[{current_time}] 已持有{position_name}仓位，不允许重复开仓 - position: {self.position}, signal: {signal}")
            return False
         
        logger.debug(f"[{current_time}] 所有检查通过，允许开仓")
        return True
    
    def _update_high_low_points(self, current_price: float):
        """更新持仓期间的高低点"""
        if self.position == 1:  # 多仓
            if current_price > self.high_point:
                self.high_point = current_price
        elif self.position == -1:  # 空仓
            if current_price < self.low_point:
                self.low_point = current_price
    
    def _update_margin_info(self):
        """更新保证金信息"""
        if self.position != 0 and self.position_quantity > 0 and self.entry_price > 0:
            self.position_value = self.position_quantity * self.entry_price
            # 保证金应该由外部设置，这里不再自动计算
            # 如果margin_value为0，则使用传统计算方式作为后备
            if self.margin_value == 0:
                self.margin_value = self.position_value / self.leverage if self.leverage > 0 else 0
        else:
            self.position_value = 0.0
            self.margin_value = 0.0
    
    def set_margin_value(self, margin_value: float):
        """直接设置保证金值"""
        self.margin_value = margin_value
        logger.debug(f"保证金已设置为: ${margin_value:.2f}")
    
    def update_position_info(self, position: int, entry_price: float, current_price: float, 
                           current_time: Optional[datetime] = None, entry_signal_score: float = 0.0,
                           leverage: Optional[float] = None, margin_value: Optional[float] = None):
        """
        更新持仓信息
        
        Args:
            position: 仓位状态 (0=无仓位, 1=多仓, -1=空仓)
            entry_price: 开仓价格
            current_price: 当前价格
            current_time: 当前时间
            entry_signal_score: 开仓时的信号评分
            leverage: 杠杆倍数（可选，如果不提供则使用当前值）
            margin_value: 保证金值（可选，如果不提供则自动计算）
        """
        # 检查是否是新开仓（仓位发生变化）
        is_new_position = self.position != position
        
        # 更新基本持仓信息
        self.position = position
        self.entry_price = entry_price
        self.current_price = current_price
        
        # 更新杠杆倍数（如果提供）
        if leverage is not None:
            self.leverage = leverage
        
        # 更新保证金值（如果提供）
        if margin_value is not None:
            self.margin_value = margin_value
        
        # 更新持仓数量 - 确保数据一致性
        if position == 0:
            # 无持仓时，持仓数量为0
            self.position_quantity = 0.0
            # 重置盈亏状态
            self.position_unrealized_pnl = 0.0
            self.position_unrealized_pnl_percent = 0.0
        else:
            # 有持仓时，计算并更新未实现盈亏
            self.calculate_unrealized_pnl()
        
        # 记录开仓时间（当开仓时）
        if position != 0 and current_time:
            self.entry_time = current_time
            self.holding_periods = 0  # 重置持仓周期计数
            # 保存开仓时的信号评分
            self.entry_signal_score = entry_signal_score
        elif position == 0:
            self.entry_time = None
            self.holding_periods = 0  # 重置持仓周期计数
            self.entry_signal_score = 0.0
        
        # 只在开仓时重置高低点，避免频繁重置导致低点无法正确更新
        if is_new_position:
            if position == 1:  # 新开多仓
                self.high_point = current_price
                self.low_point = float('inf')
            elif position == -1:  # 新开空仓
                self.high_point = float('-inf')
                self.low_point = current_price
            else:  # 平仓
                self.high_point = float('-inf')
                self.low_point = float('inf')
        
        # 更新保证金信息 - 只有在没有明确设置保证金时才自动计算
        if margin_value is None:
            self._update_margin_info()
        else:
            # 如果明确设置了保证金，只更新持仓价值
            if self.position != 0 and self.position_quantity > 0 and self.entry_price > 0 and self.leverage > 0:
                self.position_value = self.position_quantity * self.entry_price * self.leverage
            else:
                self.position_value = 0.0
    
    def update_holding_periods(self):
        """更新持仓周期计数"""
        if self.position != 0:  # 有持仓时
            self.holding_periods += 1
    
    def set_position_quantity(self, quantity: float):
        """设置持仓数量"""
        self.position_quantity = quantity
        # 更新保证金信息
        self._update_margin_info()
    
    def set_leverage(self, leverage: float):
        """设置杠杆倍数"""
        self.leverage = leverage
        logger.info(f"风险管理器杠杆倍数已设置为: {leverage}x")
        # 更新保证金信息
        self._update_margin_info()
    
    def _calculate_ratio(self, current_price: float, leverage: float = 1.0) -> float:
        """
        计算盈亏比例 - 考虑杠杆和手续费
        
        Args:
            current_price: 当前价格
            leverage: 杠杆倍数
            
        Returns:
            float: 盈亏比例（正值为盈利，负值为亏损，已扣除手续费）
        """
        if self.position == 0 or self.entry_price == 0:
            return 0.0
        
        # 获取手续费率
        trading_fee = self.config.get('trading_fee', 0.001)
        
        # 计算当前交易手续费 - 基于当前价格的名义价值
        current_position_value = self.position_quantity * current_price
        current_fee = current_position_value * trading_fee
        
        # 计算价格变动比例
        if self.position == 1:  # 多头
            price_change_ratio = (current_price - self.entry_price) / self.entry_price
        else:  # 空头
            price_change_ratio = (self.entry_price - current_price) / self.entry_price
        
        # 考虑杠杆的毛盈亏比例
        gross_ratio = price_change_ratio * leverage
        
        # 计算手续费比例
        fee_ratio = current_fee / self.margin_value if self.margin_value > 0 else 0.0
        
        # 净盈亏比例 = 毛盈亏比例 - 手续费比例
        net_ratio = gross_ratio - fee_ratio
        
        return net_ratio
    
    def calculate_unrealized_pnl(self) -> float:
        """
        计算未实现盈亏 - 考虑手续费和杠杆倍数
        
        Returns:
            float: 未实现盈亏金额（扣除手续费）
        """
        if self.position == 0 or self.entry_price == 0 or self.position_quantity == 0:
            self.position_unrealized_pnl = 0.0
            self.position_unrealized_pnl_percent = 0.0
            return 0.0

        # 获取手续费率（从配置中获取，默认为0.001）
        trading_fee = self.config.get('trading_fee', 0.001)
        
        # 计算当前交易手续费 - 基于当前持仓的名义价值
        current_position_value = self.position_quantity * self.current_price
        current_fee = current_position_value * trading_fee
        
        # 使用当前价格计算价格变动比例
        if self.position == 1:  # 多头
            price_change_ratio = (self.current_price - self.entry_price) / self.entry_price
        else:  # 空头
            price_change_ratio = (self.entry_price - self.current_price) / self.entry_price
        
        # 计算基于保证金的盈亏（考虑杠杆）
        # 在合约交易中，盈亏 = 价格变动比例 × 杠杆倍数 × 保证金
        gross_pnl = price_change_ratio * self.leverage * self.margin_value
        
        # 扣除当前交易手续费得到净盈亏
        net_pnl = gross_pnl - current_fee
        
        # 更新盈亏状态
        self.position_unrealized_pnl = net_pnl
        
        # 计算盈亏百分比 - 使用实际的保证金值
        self.position_unrealized_pnl_percent = (net_pnl / self.margin_value) if self.margin_value > 0 else 0.0
        
        logger.debug(f"未实现盈亏计算 - 价格变动比例: {price_change_ratio*100:.2f}%, 杠杆: {self.leverage}x, 保证金: {self.margin_value:.2f}, 毛盈亏: {gross_pnl:.2f}, 当前交易手续费: {current_fee:.2f}, 净盈亏: {net_pnl:.2f}, 盈亏百分比: {self.position_unrealized_pnl_percent*100:.2f}%")
        
        return net_pnl

    def get_margin_value(self) -> float:
        """获取当前保证金价值"""
        return self.margin_value
    
    def get_position_value(self) -> float:
        """获取当前持仓价值"""
        return self.position_value 
    
    def reset_state(self):
        """重置风险管理器状态到初始值"""
        # 仓位状态
        self.position = 0  # 0=无仓位, 1=多仓, -1=空仓
        self.entry_price = 0.0
        self.position_quantity = 0.0  # 持仓数量
        self.current_price = 0.0  # 当前价格
        
        # 持仓期间的高低点
        self.high_point = float('-inf')  # 持仓期间的最高点
        self.low_point = float('inf')  # 持仓期间的最低点
        self.entry_time = None  # 开仓时间
        self.holding_periods = 0  # 持仓周期数
        
        # 盈亏状态
        self.position_unrealized_pnl = 0.0
        self.position_unrealized_pnl_percent = 0.0
        
        # 保证金信息
        self.position_value = 0.0  # 持仓价值
        self.margin_value = 0.0  # 保证金
        
        # 重置风险倍数到初始值
        self.risk_multiplier = self.config.get('sharpe_params', {}).get('initial_risk_multiplier', 1.0)
        
        logger.info("风险管理器状态已重置") 

    def _get_margin_value(self) -> float:
        """获取保证金价值"""
        position_value = self.position_quantity * self.entry_price if self.position_quantity > 0 else 0
        return position_value / self.leverage if self.leverage > 0 else 0
    
    def _log_stop_loss_check(self, time_str: str, current_price: float, loss_ratio: float, margin_value: float):
        """记录止损检查日志"""
        position_desc = "多头" if self.position == 1 else "空头"
        price_change_pct = (current_price - self.entry_price) / self.entry_price
        position_value = self.position_quantity * self.entry_price if self.position_quantity > 0 else 0
        
        logger.debug(f"[{time_str}] 止损检查 - {position_desc}持仓, 数量:{self.position_quantity:.4f}, 杠杆:{self.leverage}x, "
                   f"保证金:${margin_value:.2f}, 持仓价值:${position_value:.2f}, 开仓价:{self.entry_price:.2f}, "
                   f"当前价:{current_price:.2f}, 价格变动:{price_change_pct*100:.2f}%, 实际亏损:{loss_ratio*100:.2f}%")
    
    def _check_signal_score_stop_loss(self, current_features: Dict, loss_ratio: float, time_str: str, margin_value: float) -> Tuple[bool, Optional[str]]:
        """检查信号评分止损"""
        if not current_features:
            return False, None
            
        # 获取当前信号评分
        if isinstance(current_features, dict) and 'row_data' in current_features:
            current_signal_score = current_features.get('row_data', {}).get('signal_score', 0)
        else:
            current_signal_score = current_features.get('signal_score', 0)
        
        # 获取配置阈值
        signal_score_threshold = self.stop_loss_config.get('signal_score_threshold', 0.4)
        
        # 获取固定止损阈值
        fixed_stop_ratio = abs(self.stop_loss_config.get('fixed_stop_loss', -0.08))
        
        # 信号评分反转止损 - 需要达到固定止损的50%条件
        if loss_ratio <= -fixed_stop_ratio * 0.7:  # 达到固定止损的50%
            if self.position == 1 and current_signal_score < -signal_score_threshold:  # 多头持仓但实时评分偏低，说明信号反转
                reason = f"信号评分反转止损(多头持仓，实时评分{current_signal_score:.3f} < -{signal_score_threshold:.1f}，信号反转)"
                logger.info(f"[{time_str}] {reason}: 数量={self.position_quantity:.4f}, 杠杆={self.leverage}x, "
                            f"保证金=${margin_value:.2f}, 亏损{loss_ratio*100:.1f}%")
                return True, reason
            elif self.position == -1 and current_signal_score > signal_score_threshold:  # 空头持仓但实时评分偏高，说明信号反转
                reason = f"信号评分反转止损(空头持仓，实时评分{current_signal_score:.3f} > {signal_score_threshold:.1f}，信号反转)"
                logger.info(f"[{time_str}] {reason}: 数量={self.position_quantity:.4f}, 杠杆={self.leverage}x, "
                            f"保证金=${margin_value:.2f}, 亏损{loss_ratio*100:.1f}%")
                return True, reason
                
        return False, None 