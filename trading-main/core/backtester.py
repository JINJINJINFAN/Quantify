# -*- coding: utf-8 -*-
"""
期货交易回测器
支持多策略回测、资金管理、风险控制
"""

import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import logging

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)


class Backtester:
    """
    期货交易回测器
    功能：策略回测、资金管理、性能统计
    """
    
    def __init__(self):
        """初始化回测器"""
        # 基础配置
        self.initial_cash = 1000.0
        self.cash = 1000.0
        self.trading_fee = 0.001
        
        # 交易统计
        self.total_trades = 0
        self.profitable_trades = 0
        self.loss_trades = 0
        
        # 资金曲线
        self.total_assets = []
        self.asset_timestamps = []
        self.trade_log = []
        
        
        # 策略实例
        self.strategy = None
     
    
    def set_strategy(self, strategy):
        """
        设置策略实例
        
        Args:
            strategy: 策略实例
        """
        self.strategy = strategy
        print(f"策略已设置: {strategy.__class__.__name__}")
        
        # 杠杆倍数已由策略的risk_manager统一管理，无需重复维护
        print(f"杠杆倍数由策略统一管理: {self.strategy.get_leverage()}x")
    
    # 仓位管理已移至策略内部，不再需要此方法
    
    def open_position(self, signal, price, current_time, timeframe, signal_info=None):
        """开仓
        
        1. 计算仓位大小
        2. 计算实际投入资金
        3. 设置策略持仓数量
        4. 扣除保证金
        5. 更新策略持仓信息
        6. 记录开仓日志
        7. 记录交易
        8. 添加评分信息
        
        """
        if signal == 0:
            return
        
        # 计算仓位大小
        position_size_value = getattr(signal_info, 'position_size', 0.4) if signal_info and hasattr(signal_info, 'position_size') else 0.4
        
        # 获取应用冷却处理后的实际仓位大小
        actual_position_size = signal_info.get('position_size', {}).get('size', position_size_value) if signal_info and isinstance(signal_info.get('position_size'), dict) else position_size_value
        
        # 计算实际投入资金 - 使用应用冷却处理后的仓位大小
        actual_position_value = self.cash * actual_position_size
        usdt_amount = actual_position_value
        eth_amount = usdt_amount / price
        
        
        # 设置策略持仓数量
        if hasattr(self.strategy, 'set_position_quantity'):
            self.strategy.set_position_quantity(eth_amount)
        
        # 扣除保证金
        margin_used = usdt_amount
        self.cash -= margin_used

        
        # 更新策略持仓信息
        if hasattr(self.strategy, 'update_position_info'):
            entry_signal_score = signal_info.get('signal_score', 0.0) if signal_info else 0.0
            self.strategy.update_position_info(signal, price, price, current_time, entry_signal_score, margin_value=margin_used)
        
        # 记录开仓日志
        action = "开多" if signal == 1 else "开空"
        data_time = current_time.strftime('%Y-%m-%d %H:%M:%S') if current_time else "N/A"
        signal_reason = signal_info.get('reason', '信号开仓') if signal_info else '信号开仓'
        leverage = self.strategy.get_leverage() if hasattr(self.strategy, 'get_leverage') else 8.0
        position_value = self.strategy.risk_manager.get_position_value() # 持仓名义价值

        # 输出开仓日志
        log_message = f"[{data_time}] 开仓 [{action} ,价格: {price:.2f} ,数量: {eth_amount:.4f} ,杠杆: {leverage}x ,保证金: ${margin_used:.2f} ,原因: {signal_reason}]"
        logger.info(log_message)
        print(f"🔵 {log_message}")

        # 记录交易
        trade_record = {
            "date": current_time,
            "action": action,
            "price": price,
            "position_value": position_value,
            "cash": self.cash,
            "timeframe": timeframe,
            "pnl": 0,
            "reason": signal_reason,
            "trade_type": "open",
            "leverage": leverage,
            "multiplier": leverage
        }
        
        # 添加信号评分信息
        if signal_info:
            trade_record.update({
                "signal_score": signal_info.get('signal_score', 0),
                "base_score": signal_info.get('base_score', 0),
                "trend_score": signal_info.get('trend_score', 0),
                "risk_score": signal_info.get('risk_score', 0),
                "drawdown_score": signal_info.get('drawdown_score', 0),
                "position_size": signal_info.get('position_size', {}).get('size', 0) if isinstance(signal_info.get('position_size'), dict) else signal_info.get('position_size', 0)
            })
            
            # 添加过滤器信息
            if 'filters' in signal_info:
                trade_record['filters'] = signal_info['filters']
            else:
                trade_record['filters'] = {'signal_score_filter': {'passed': True, 'reason': '无过滤器信息'}}
        
        self.trade_log.append(trade_record)
        self.total_trades += 1
    
    def close_position(self, price, reason="信号平仓", current_time=None, timeframe="1h"):
        """平仓"""
        # 使用策略的仓位检查
        if not hasattr(self.strategy, 'get_position') or self.strategy.get_position() == 0:
            return
        
        # 使用策略的统计算法计算已实现盈亏
        realized_pnl = 0
        if hasattr(self, 'strategy') and hasattr(self.strategy, 'calculate_unrealized_pnl'):
            # 先更新策略的当前价格
            if hasattr(self.strategy, 'risk_manager'):
                self.strategy.risk_manager.current_price = price
            # 使用策略的统一计算方法
            
            realized_pnl = self.strategy.get_position_unrealized_pnl()
        else:
            # 如果策略没有盈亏计算方法，记录错误并返回
            logger.error("策略缺少calculate_unrealized_pnl方法，无法计算盈亏")
            return
        
        # 获取保证金 - 使用策略的统一方法
        margin_used = self.strategy.get_margin_value()
        
        # 更新资金
        self.cash += margin_used  # 加回保证金
        self.cash += realized_pnl  # 加上盈亏
        
        # 确保现金不为负数
        if self.cash < 0:
            self.cash = 0
        
        # 更新统计
        if realized_pnl > 0:
            self.profitable_trades += 1
        else:
            self.loss_trades += 1
        
        # 记录平仓日志
        data_time = current_time.strftime('%Y-%m-%d %H:%M:%S') if current_time else "N/A"
        is_take_profit = "止盈" in reason or "盈利" in reason
        current_position = self.strategy.get_position() if hasattr(self.strategy, 'get_position') else 0
        action = "平多" if current_position == 1 else "平空"
        
        # 计算盈亏百分比
        margin_pnl_percentage = (realized_pnl / margin_used * 100) if margin_used > 0 else 0
        
        # 获取杠杆倍数
        leverage = self.strategy.get_leverage() if hasattr(self.strategy, 'get_leverage') else 8.0
        
        if is_take_profit:
            log_message = f"[{data_time}] 止盈 [{action} ,价格: {price:.2f} ,盈亏: {realized_pnl:.0f} ({margin_pnl_percentage:.2f}%) ,杠杆: {leverage}x ,现金: {self.cash:.0f} ,原因: {reason}]"
            logger.info(log_message)
            print(f"🟢 {log_message}")
        else:
            log_message = f"[{data_time}] 止损 [{action} ,价格: {price:.2f} ,盈亏: {realized_pnl:.0f} ({margin_pnl_percentage:.1f}%) ,杠杆: {leverage}x ,现金: {self.cash:.0f} ,原因: {reason}]"
            print(log_message)
            logger.info(log_message)
        
        # 更新冷却处理状态
        if hasattr(self.strategy, 'cooldown_manager') and self.strategy.enable_cooldown_treatment:
            trade_result = {
                'pnl': realized_pnl,
                'timestamp': current_time,
                'reason': reason
            }
            self.strategy.cooldown_manager.update_status(trade_result, current_time)
        
        # 记录交易
        trade_record = {
            "date": current_time,
            "action": action,
            "price": price,
            "position_value": self.strategy.risk_manager.position_value, # 使用策略的risk_manager的position_value
            "cash": self.cash,
            "timeframe": timeframe,
            "pnl": realized_pnl,
            "reason": reason,
            "trade_type": "close",
            "leverage": leverage,
            "multiplier": leverage
        }
        
        # 添加评分信息
        if len(self.trade_log) > 0:
            for trade in reversed(self.trade_log):
                if trade.get('trade_type') == 'open':
                    trade_record.update({
                        "signal_score": trade.get('signal_score', 0),
                        "base_score": trade.get('base_score', 0),
                        "trend_score": trade.get('trend_score', 0),
                        "risk_score": trade.get('risk_score', 0),
                        "drawdown_score": trade.get('drawdown_score', 0),
                        "position_size": trade.get('position_size', 0)
                    })
                    
                    if 'filters' in trade:
                        trade_record['filters'] = trade['filters']
                    break
        
        self.trade_log.append(trade_record)
        
        # 重置仓位信息
        if hasattr(self.strategy, 'update_position_info'):
            self.strategy.update_position_info(0, 0, price, current_time, 0.0)
        
        if hasattr(self, 'strategy') and hasattr(self.strategy, 'set_position_quantity'):
            self.strategy.set_position_quantity(0.0)
        
        self.position = 0
        self.entry_price = 0
    
    def run_backtest(self, features, timeframe="1h"):
        """运行回测"""
        print(f"开始回测 ({len(features)} 条数据)")
        
        # 重置回测器状态
        self.cash = self.initial_cash
        self.trade_log = []
        self.total_assets = []
        self.asset_timestamps = []
        self.total_trades = 0
        self.profitable_trades = 0
        self.loss_trades = 0
        
        # 重置策略状态 - 使用策略的统一方法
        if hasattr(self.strategy, 'reset_position'):
            self.strategy.reset_position()
        
        # 预热期设置 - 确保有足够的历史数据
        min_required_data = max(200, getattr(self.strategy, 'config', {}).get('short_window', 200))
        
        # 主回测循环
        for i, (index, row) in enumerate(features.iterrows()):
            current_time = index
            current_price = row['close']
            
            
            
            # 创建增强的行数据
            enhanced_row = {'row_data': row.to_dict(), 'multi_timeframe_data': None}
            
            # 标记是否在当前时间点执行了平仓
            position_closed_this_time = False
            
            # 更新策略持仓信息
            if hasattr(self.strategy, 'update_position_info'):
                current_position = self.strategy.get_position() if hasattr(self.strategy, 'get_position') else 0
                entry_price = self.strategy.get_entry_price() if hasattr(self.strategy, 'get_entry_price') else 0
                self.strategy.update_position_info(current_position, entry_price, current_price, current_time, 0.0)
            
            # 风险管理检查
            current_position = self.strategy.get_position() if hasattr(self.strategy, 'get_position') else 0
            if current_position != 0 and hasattr(self.strategy, 'check_risk_management'):
                try:
                    risk_action, risk_reason = self.strategy.check_risk_management(
                        current_price, enhanced_row, current_time
                    )
                    
                    if risk_action == 'stop_loss':
                        self.close_position(current_price, reason=f"{risk_reason}", current_time=current_time, timeframe=timeframe)
                        position_closed_this_time = True
                    elif risk_action == 'take_profit':
                        self.close_position(current_price, reason=risk_reason, current_time=current_time, timeframe=timeframe)
                        position_closed_this_time = True
                        
                except Exception as e:
                    print(f"风险管理检查异常: {e}")
                    logger.error(f"风险管理检查异常: {e}")
            
            # 获取交易信号
            try:
                signal_info = self.strategy.generate_signals(features.iloc[:i+1], verbose=False)
                signal = signal_info.get('signal', 0)
                
                # 处理交易信号
                if signal != 0:
                    # 只在无持仓状态下执行开仓
                    current_position = self.strategy.get_position() if hasattr(self.strategy, 'get_position') else 0
                    if current_position == 0 and not position_closed_this_time:
                        # 使用策略的开仓检查方法
                        if hasattr(self.strategy, 'should_open_position'):
                            should_open = self.strategy.should_open_position(signal, enhanced_row, current_time)
                            if should_open is False:
                                continue
                        
                        # 开仓
                        self.open_position(signal, current_price, current_time, timeframe, signal_info)
                        
                        # 更新策略的持仓信息
                        if hasattr(self.strategy, 'update_position_info'):
                            current_position = self.strategy.get_position() if hasattr(self.strategy, 'get_position') else 0
                            entry_price = self.strategy.get_entry_price() if hasattr(self.strategy, 'get_entry_price') else 0
                            self.strategy.update_position_info(current_position, entry_price, current_price, current_time, 0.0)
                    
            except Exception as e:
                print(f"获取信号异常: {e}")
                logger.error(f"获取信号异常: {e}")
            
            # 记录资金曲线
            current_position = self.strategy.get_position() if hasattr(self.strategy, 'get_position') else 0
            if current_position != 0:
                # 获取持仓数量 - 使用策略的正确方法
                 
                position_quantity = self.strategy.get_position_quantity()
                
                # 获取开仓时投入的保证金
                margin_used = self.strategy.risk_manager.get_margin_value()
                # logger.info(f"保证金: {margin_used}")
                
                # 计算未实现盈亏
                unrealized_pnl = self.strategy.get_position_unrealized_pnl()
                
                # 总资产 = 现金 + 保证金 + 未实现盈亏
                total_asset = self.cash + margin_used + unrealized_pnl
            else:
                # 无持仓时，总资产就是现金
                total_asset = self.cash
            
            self.total_assets.append(total_asset)
            self.asset_timestamps.append(current_time)
            
            # 显示进度
            if (i + 1) % 2000 == 0:
                print(f"进度: {i+1}/{len(features)} | 资产: {total_asset:.0f}")
        
        # 回测结束处理
        current_position = self.strategy.get_position() if hasattr(self.strategy, 'get_position') else 0
        if current_position != 0:
            last_price = features['close'].iloc[-1]
            last_time = features.index[-1]
            self.close_position(last_price, reason="回测结束平仓", current_time=last_time, timeframe=timeframe)
        
        # 输出统计信息
        self._print_backtest_summary(features)
        
        # 返回回测结果
        final_cash = self.cash
        return_ratio = (final_cash - self.initial_cash) / self.initial_cash * 100
        
        # 保存结果数据用于绘图
        result_data = {
            'final_cash': final_cash,
            'return_ratio': return_ratio,
            'total_trades': self.total_trades,
            'total_assets': self.total_assets.copy(),  # 复制数据避免被清理影响
            'asset_timestamps': self.asset_timestamps.copy(),
            'trade_log': pd.DataFrame(self.trade_log)
        }
        
        # 清空维护数据（在返回结果之后）
        self._clear_backtest_data()
        
        return result_data
    
    def _print_backtest_summary(self, features):
        """打印回测摘要"""
        # 统计交易记录
        trade_df = pd.DataFrame(self.trade_log)
        
        print(f"\n回测结果")
        print(f"总交易: {self.total_trades} | 盈利: {self.profitable_trades} | 亏损: {self.loss_trades}")
        leverage = self.strategy.get_leverage() if hasattr(self.strategy, 'get_leverage') else 8.0
        print(f"杠杆倍数: {leverage}x")
        
        if self.total_trades > 0:
            win_rate = self.profitable_trades / self.total_trades * 100
            print(f"胜率: {win_rate:.1f}%")
        
        if len(trade_df) > 0 and 'pnl' in trade_df.columns:
            close_trades = trade_df[trade_df['trade_type'] == 'close']
            if len(close_trades) > 0:
                profitable_trades = close_trades[close_trades['pnl'] > 0]
                loss_trades = close_trades[close_trades['pnl'] < 0]
                
                avg_profit = profitable_trades['pnl'].mean() if len(profitable_trades) > 0 else 0
                avg_loss = loss_trades['pnl'].mean() if len(loss_trades) > 0 else 0
                profit_loss_ratio = abs(avg_profit / avg_loss) if avg_loss != 0 else 0
                
                print(f"平均盈亏: {avg_profit:.0f} / {avg_loss:.0f} | 盈亏比: {profit_loss_ratio:.1f}")
        
        final_cash = self.cash
        return_ratio = (final_cash - self.initial_cash) / self.initial_cash * 100
        print(f"最终资金: {final_cash:.0f} | 收益率: {return_ratio:.1f}%")
    
    def _clear_backtest_data(self):
        """清空回测过程中维护的所有数据"""
        # 重置回测器状态
        self.cash = self.initial_cash
        self.trade_log = []
        self.total_assets = []
        self.asset_timestamps = []
        self.total_trades = 0
        self.profitable_trades = 0
        self.loss_trades = 0
        self._margin_used = 0.0  # 清空保证金使用记录
        
        # 重置策略状态
        if hasattr(self, 'strategy') and self.strategy:
            # 重置策略持仓状态
            if hasattr(self.strategy, 'reset_position'):
                self.strategy.reset_position()
            
            # 重置风险管理器状态
            if hasattr(self.strategy, 'risk_manager'):
                self.strategy.risk_manager.reset_state()
            
            # 重置冷却管理器状态
            if hasattr(self.strategy, 'cooldown_manager'):
                self.strategy.cooldown_manager.reset_state()
            
            # 清空策略缓存数据
            if hasattr(self.strategy, 'current'):
                self.strategy.current = None
            if hasattr(self.strategy, 'current_deepseek_data'):
                self.strategy.current_deepseek_data = None
        
        logger.info("回测数据清理完成 - 所有持仓状态和维护数据已重置")

