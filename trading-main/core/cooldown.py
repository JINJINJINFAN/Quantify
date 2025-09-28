#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
冷却处理管理器 - 基于连续亏损的风险控制机制
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class CooldownManager:
    """冷却处理管理器 - 管理交易策略的风险控制"""
    
    def __init__(self, cooldown_config: Dict[str, Any]):
        """初始化冷却处理管理器"""
        self.cooldown_config = cooldown_config
        self.cooldown_threshold = cooldown_config.get('consecutive_loss_threshold', 2)
        self.cooldown_treatment_mode = cooldown_config.get('mode', 'backtest')
        
        # 状态变量
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.cooldown_treatment_active = False
        self.cooldown_treatment_level = 0
        self.cooldown_treatment_start_time = None
        self.position_size_reduction = 1.0
        self.trade_history = []
        self.skipped_trades_count = 0
        self.max_skip_trades = 0
    
    def update_status(self, trade_result: Optional[Dict[str, Any]] = None, trade_time: Optional[datetime] = None):
        """更新冷却处理状态"""
        if trade_result:
            self.trade_history.append(trade_result)
        
        self._calculate_consecutive_results()
        self._check_activation(trade_time)
        self._check_recovery(trade_time)
    
    def _calculate_consecutive_results(self):
        """计算连续亏损和盈利次数"""
        if not self.trade_history:
            self.consecutive_losses = self.consecutive_wins = 0
            return
        
        consecutive_losses = consecutive_wins = 0
        
        for trade in reversed(self.trade_history):
            pnl = trade.get('pnl', 0)
            if pnl < 0:  # 亏损
                if consecutive_wins > 0:
                    break
                consecutive_losses += 1
            elif pnl > 0:  # 盈利
                if consecutive_losses > 0:
                    break
                consecutive_wins += 1
            else:  # 平局
                break
        
        self.consecutive_losses = consecutive_losses
        self.consecutive_wins = consecutive_wins
    
    def _check_activation(self, trade_time: Optional[datetime] = None):
        """检查是否需要启动冷却处理"""
        if self.consecutive_losses >= self.cooldown_threshold:
            if self.cooldown_treatment_active:
                self._check_level_upgrade(trade_time)
            else:
                if self.cooldown_treatment_mode == 'backtest':
                    self._activate_backtest_mode(trade_time)
                else:
                    self._activate_realtime_mode(trade_time)
        else:
            # 添加调试信息
            time_str = self._get_time_string(trade_time)
            logger.debug(f"[{time_str}] 冷却检查 - 连续亏损: {self.consecutive_losses}次 < 阈值: {self.cooldown_threshold}次，未触发冷却处理")
    
    def _check_level_upgrade(self, trade_time: Optional[datetime] = None):
        """检查是否需要升级冷却处理级别"""
        old_level = self.cooldown_treatment_level
        new_level = self._get_cooldown_level()
        
        if new_level > old_level:
            self.cooldown_treatment_level = new_level
            self._update_parameters()
            time_str = self._get_time_string(trade_time)
            logger.info(f"[{time_str}] 冷却处理级别升级 - L{old_level} → L{new_level}, 连续亏损: {self.consecutive_losses}次")
    
    def _get_cooldown_level(self) -> int:
        """根据连续亏损次数确定冷却处理级别"""
        if self.consecutive_losses >= self.cooldown_threshold + 2:
            return 3  # 重度冷却
        elif self.consecutive_losses >= self.cooldown_threshold + 1:
            return 2  # 中度冷却
        else:
            return 1  # 轻度冷却
    
    def _activate_backtest_mode(self, trade_time: Optional[datetime] = None):
        """激活回测模式冷却处理"""
        self.cooldown_treatment_level = self._get_cooldown_level()
        self.cooldown_treatment_active = True
        self.cooldown_treatment_start_time = self._normalize_time(trade_time)
        self._update_parameters()
        
        time_str = self._get_time_string(trade_time)
        logger.info(f"[{time_str}] 🔥 触发冷却处理 - 连续亏损: {self.consecutive_losses}次 >= 阈值: {self.cooldown_threshold}次")
        logger.info(f"[{time_str}] 📉 冷却处理已激活 - 级别: L{self.cooldown_treatment_level}, 仓位降级: {self.position_size_reduction:.1%}")
        logger.info(f"[{time_str}] ⚠️  未触发冷却仓位降级 - 连续{self.consecutive_losses}次止损")
    
    def _activate_realtime_mode(self, trade_time: Optional[datetime] = None):
        """激活实盘模式冷却处理"""
        realtime_config = self.cooldown_config.get('realtime_mode', {})
        cold_levels = realtime_config.get('cooldown_treatment_levels', {})
        
        # 根据连续亏损次数确定级别
        if self.consecutive_losses >= cold_levels.get('level_3', {}).get('consecutive_losses', 6):
            self.cooldown_treatment_level = 3
        elif self.consecutive_losses >= cold_levels.get('level_2', {}).get('consecutive_losses', 4):
            self.cooldown_treatment_level = 2
        else:
            self.cooldown_treatment_level = 1
        
        self.cooldown_treatment_active = True
        self.cooldown_treatment_start_time = self._normalize_time(trade_time)
        self._update_parameters()
        
        time_str = self._get_time_string(trade_time)
        logger.info(f"[{time_str}] 🔥 触发冷却处理 - 连续亏损: {self.consecutive_losses}次 >= 阈值: {self.cooldown_threshold}次")
        logger.info(f"[{time_str}] 📉 冷却处理已激活 - 级别: L{self.cooldown_treatment_level}, 仓位降级: {self.position_size_reduction:.1%}")
        logger.info(f"[{time_str}] ⚠️  未触发冷却仓位降级 - 连续{self.consecutive_losses}次止损")
    
    def _check_recovery(self, trade_time: Optional[datetime] = None):
        """检查是否可以恢复冷却处理"""
        if not self.cooldown_treatment_active:
            return
        
        can_recover = (self._check_backtest_recovery() if self.cooldown_treatment_mode == 'backtest' 
                      else self._check_realtime_recovery())
        
        if can_recover:
            self._reset_cooldown_treatment(trade_time)
    
    def _check_backtest_recovery(self) -> bool:
        """检查回测模式恢复条件"""
        backtest_config = self.cooldown_config.get('backtest_mode', {})
        recovery_conditions = backtest_config.get('recovery_conditions', {})
        required_wins = recovery_conditions.get('consecutive_wins', 1)
        
        return self.consecutive_wins >= required_wins
    
    def _check_realtime_recovery(self) -> bool:
        """检查实盘模式恢复条件"""
        if not self.cooldown_treatment_start_time:
            return False
        
        realtime_config = self.cooldown_config.get('realtime_mode', {})
        max_duration = realtime_config.get('max_cooldown_treatment_duration', 72)
        
        try:
            start_time = self._normalize_time(self.cooldown_treatment_start_time)
            current_time = self._normalize_time(datetime.now())
            elapsed_hours = (current_time - start_time).total_seconds() / 3600
            return elapsed_hours >= max_duration
        except Exception as e:
            logger.warning(f"计算冷却时间失败: {e}")
            return False
    
    def _reset_cooldown_treatment(self, trade_time: Optional[datetime] = None):
        """重置冷却处理状态"""
        old_level = self.cooldown_treatment_level
        old_reduction = self.position_size_reduction
        
        self.cooldown_treatment_active = False
        self.cooldown_treatment_level = 0
        self.cooldown_treatment_start_time = None
        self.position_size_reduction = 1.0
        
        time_str = self._get_time_string(trade_time)
        if self.cooldown_treatment_mode == 'backtest':
            logger.info(f"[{time_str}] ✅ 冷却处理已恢复 - 连续盈利: {self.consecutive_wins}次")
            logger.info(f"[{time_str}] 🔄 仓位降级已重置 - L{old_level}({old_reduction:.1%}) → L0(100%)")
        else:
            logger.info(f"[{time_str}] ✅ 冷却处理已恢复 - 时间到期")
            logger.info(f"[{time_str}] 🔄 仓位降级已重置 - L{old_level}({old_reduction:.1%}) → L0(100%)")
    
    def _update_parameters(self):
        """更新冷却处理参数"""
        if self.cooldown_treatment_mode == 'backtest':
            self._update_backtest_parameters()
        else:
            self._update_realtime_parameters()
    
    def _update_backtest_parameters(self):
        """更新回测模式冷却处理参数"""
        backtest_config = self.cooldown_config.get('backtest_mode', {})
        position_reduction_levels = backtest_config.get('position_reduction_levels', {})
        
        level_mapping = {
            3: position_reduction_levels.get('level_3', 0.4),
            2: position_reduction_levels.get('level_2', 0.6),
            1: position_reduction_levels.get('level_1', 0.8)
        }
        self.position_size_reduction = level_mapping.get(self.cooldown_treatment_level, 1.0)
    
    def _update_realtime_parameters(self):
        """更新实盘模式冷却处理参数"""
        realtime_config = self.cooldown_config.get('realtime_mode', {})
        position_reduction_levels = realtime_config.get('position_reduction_levels', {})
        
        level_mapping = {
            3: position_reduction_levels.get('level_3', 0.4),
            2: position_reduction_levels.get('level_2', 0.6),
            1: position_reduction_levels.get('level_1', 0.8)
        }
        self.position_size_reduction = level_mapping.get(self.cooldown_treatment_level, 1.0)
    
    def apply_to_position_size(self, position_size: float) -> float:
        """对仓位大小应用冷却处理减少"""
        return position_size * self.position_size_reduction if self.cooldown_treatment_active else position_size
    
    def get_status(self) -> Dict[str, Any]:
        """获取冷却处理状态"""
        return {
            'cooldown_treatment_active': self.cooldown_treatment_active,
            'cooldown_treatment_level': self.cooldown_treatment_level,
            'consecutive_losses': self.consecutive_losses,
            'consecutive_wins': self.consecutive_wins,
            'position_size_reduction': self.position_size_reduction,
            'skipped_trades_count': self.skipped_trades_count,
            'max_skip_trades': self.max_skip_trades,
            'cooldown_treatment_start_time': self.cooldown_treatment_start_time,
            'trade_history_count': len(self.trade_history)
        }
    
    def reset_state(self):
        """重置冷却管理器状态到初始值"""
        # 状态变量
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.cooldown_treatment_active = False
        self.cooldown_treatment_level = 0
        self.cooldown_treatment_start_time = None
        self.position_size_reduction = 1.0
        self.trade_history = []
        self.skipped_trades_count = 0
        self.max_skip_trades = 0
        
        logger.info("冷却管理器状态已重置")
    
    def should_skip_trade(self, enable_cooldown_treatment=True):
        """检查是否应该跳过交易（冷却处理期间）"""
        return enable_cooldown_treatment and self.cooldown_treatment_active
    
    def reset(self):
        """重置冷却处理状态"""
        self.cooldown_treatment_active = False
        self.cooldown_treatment_level = 0
        self.cooldown_treatment_start_time = None
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.position_size_reduction = 1.0
        self.trade_history = []
    
    def _get_time_string(self, trade_time: Optional[datetime] = None) -> str:
        """获取时间字符串"""
        time_obj = trade_time if trade_time else datetime.now()
        return time_obj.strftime('%Y-%m-%d %H:%M:%S')
    
    def _normalize_time(self, time_obj: datetime) -> datetime:
        """标准化时间对象，统一处理时区问题"""
        if time_obj is None:
            return datetime.now()
        
        # 如果时间对象带时区，将其转换为本地时间
        if time_obj.tzinfo is not None:
            return time_obj.replace(tzinfo=None)
        
        return time_obj 