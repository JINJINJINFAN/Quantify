"""
夏普优化策略模块 - 重构优化版

核心功能：
- 基于夏普比率的动态风险调整策略
- 多因子信号评分系统
- 智能仓位管理
- 风险管理集成（代理模式）
- DeepSeek AI信号整合

架构设计：
├── 策略层：信号生成和评分
│   ├── _calculate_signal: 核心信号计算
│   ├── _calculate_direction: 方向判断
│   ├── _calculate_all_scores: 多维度评分
│   └── _calculate_weighted_score: 加权综合
├── 风险层：止盈止损管理（代理到RiskManager）
│   ├── should_stop_loss: 止损检查
│   ├── should_take_profit: 止盈检查
│   └── check_risk_management: 风险管理
├── 过滤层：信号质量过滤
│   ├── _filter_signal: 信号过滤
│   ├── _check_volatility_filter: 波动率过滤
│   ├── _check_trend_filter: 趋势过滤
│   └── _check_rsi_filter: RSI过滤
├── 整合层：AI信号融合
│   ├── _integrate_deepseek_analysis: AI整合
│   └── _update_investment_advice_with_deepseek: 建议更新
└── 输出层：结果构建和展示
    ├── _build_signal_result: 信号结果构建
    ├── _build_debug_info: 调试信息构建
    └── _print_signal_details: 详细信息输出

优化特点：
- 模块化设计，职责清晰
- 代理模式减少代码重复
- 简洁明了的注解
- 高性能计算逻辑
- 易于维护和扩展
"""

import numpy as np
import pandas as pd
import logging
from datetime import datetime
import warnings

from .feature_engineer import FeatureEngineer
from .cooldown import CooldownManager
from .siganal_filter import SignalFilter
from .risk import RiskManager

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)
  
class SharpeOptimizedStrategy:
    """夏普优化策略 - 基于多因子评分的智能交易策略"""
    
    def __init__(self, config=None, data_loader=None, mode='realtime'):
        """
        初始化策略
        
        Args:
            config: 策略配置
            data_loader: 数据加载器
            mode: 运行模式 ('realtime'|'backtest')
        """
        # 配置初始化
        self._init_config(config)
        
        # 核心组件初始化
        self._init_components(data_loader, mode)
        
        # 状态变量初始化
        self._init_state_variables()
        
        # 加载历史状态
        self.load_strategy_status()

    def _init_config(self, config):
        """初始化配置"""
        try:
            from config import OPTIMIZED_STRATEGY_CONFIG
            default_config = OPTIMIZED_STRATEGY_CONFIG
        except ImportError:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 无法导入配置，使用默认配置")
            default_config = {}
        
        self.config = self._deep_merge(default_config, config or {})

    def _init_components(self, data_loader, mode):
        """初始化核心组件"""
        # 运行模式
        self.mode = mode
        
        # 数据加载器
        self.data_loader = data_loader
        
        # 特征工程器
        self.feature_engineer = FeatureEngineer()
        
        # 信号过滤器
        self.signal_score_filter = SignalFilter(
            self.config.get('signal_score_filters', {}), 
            data_loader
        )
        
        # 冷却管理器
        cooldown_config = self.config.get('cooldown_treatment', {})
        self.cooldown_manager = CooldownManager(cooldown_config)
        
        # 风险管理器
        self.risk_manager = RiskManager(self.config)
        
        # DeepSeek整合器
        self._init_deepseek_integrator(mode)

    def _init_deepseek_integrator(self, mode):
        """初始化DeepSeek信号整合器"""
        self.deepseek_integrator = None
        
        if not self.config.get('enable_deepseek_integration', False):
            return
            
        deepseek_mode = self.config.get('deepseek_mode', 'realtime_only')
        
        # 判断是否启用
        should_enable = False
        if deepseek_mode == 'realtime_only':
            should_enable = (mode == 'realtime')
        elif deepseek_mode == 'backtest_only':
            should_enable = (mode == 'backtest')
        elif deepseek_mode == 'both':
            should_enable = True
        
        if should_enable:
            try:
                from deepseek.signal_integrator import DeepSeekSignalIntegrator
                self.deepseek_integrator = DeepSeekSignalIntegrator(self.config)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] DeepSeek整合器已启用")
            except Exception as e:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] DeepSeek整合器初始化失败: {e}")
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] DeepSeek整合器已禁用")

    def _init_state_variables(self):
        """初始化状态变量"""
        # 信号阈值
        signal_direction = self.config.get('signal_direction', {})
        self.long_threshold = signal_direction.get('long_threshold', 0.6)
        self.short_threshold = signal_direction.get('short_threshold', 0.25)
        
        # 只保留策略特有的状态变量
        # 盈亏状态已转移到 risk_manager 统一管理
        
        # 持仓跟踪 - 删除高低点维护，完全依赖 risk_manager
        # self.high_point 和 self.low_point 已删除，统一由 risk_manager 管理
        
        # 交易统计
        self.trade_count = 0
        self.win_count = 0
        
        # 历史数据
        self.returns = []
        self.portfolio_values = []
        
        # 当前数据
        self.current = {}
        self.current_deepseek_data = {}
        
        # 最新信号
        self.last_signal = {
            'timestamp': None,
            'signal': 0,
            'signal_text': '',
            'filter_info': {},
            'signal_score': 0.0,
            'base_score': 0.0,
            'trend_score': 0.0,
            'risk_score': 0.0,
            'drawdown_score': 0.0,
            'reason': '',
            'price': 0.0,
            'symbol': '',
            'indicators': {},
            'deepseek_analysis': {},
        }
        
        # 窗口配置
        from config import WINDOW_CONFIG
        self.short_window = WINDOW_CONFIG.get('SHORT_WINDOW', 30)
        self.long_window = WINDOW_CONFIG.get('LONG_WINDOW', 90)
        
        # 时间配置
        self.timeframe = "1h"
        
        # 冷却配置
        cooldown_config = self.config.get('cooldown_treatment', {})
        self.enable_cooldown_treatment = cooldown_config.get('enable_cooldown_treatment', True)
        
        # 风险管理配置已转移到risk_manager，无需重复维护

    def _deep_merge(self, default_config, user_config):
        """
        深度合并配置字典
        
        Args:
            default_config: 默认配置
            user_config: 用户配置
            
        Returns:
            dict: 合并后的配置
        """
        result = default_config.copy()
        
        for key, value in user_config.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
                
        return result

    def save_strategy_status(self):
        """保存策略状态到文件"""
        try:
            import json
            from pathlib import Path
            from datetime import datetime
            
            # 创建json目录
            json_dir = Path('json')
            json_dir.mkdir(exist_ok=True)
            
            # 策略状态数据
            strategy_status = {
                'position': self.risk_manager.position,#仓位
                'entry_price': self.risk_manager.entry_price,#开仓价格
                'position_quantity': self.risk_manager.position_quantity,#持仓数量
                'current_price': self.risk_manager.current_price,#当前价格
                'position_unrealized_pnl': self.risk_manager.position_unrealized_pnl,#持仓未实现盈亏
                'position_unrealized_pnl_percent': self.risk_manager.position_unrealized_pnl_percent,#持仓未实现盈亏百分比
                'high_point': self.risk_manager.high_point if self.risk_manager.high_point != float('-inf') else 0,#持仓期间的最高点
                'low_point': self.risk_manager.low_point if self.risk_manager.low_point != float('inf') else 0,#持仓期间的最低点
                'entry_time': self.risk_manager.entry_time.isoformat() if self.risk_manager.entry_time else None,
                'holding_periods': self.risk_manager.holding_periods,#持仓周期数
                'trade_count': self.trade_count,#交易次数
                'win_count': self.win_count,#盈利次数
                'consecutive_losses': self.cooldown_manager.consecutive_losses,#连续亏损次数
                'consecutive_wins': self.cooldown_manager.consecutive_wins,#连续盈利次数
                'cooldown_treatment_active': self.cooldown_manager.cooldown_treatment_active,#冷却处理状态
                'cooldown_treatment_level': self.cooldown_manager.cooldown_treatment_level,#冷却处理级别
                'position_size_reduction': self.cooldown_manager.position_size_reduction,#仓位大小减少比例
                'leverage': self.risk_manager.leverage,#杠杆倍数
                'position_value': self.risk_manager.position_value,#持仓价值
                'margin_value': self.risk_manager.margin_value,#保证金
                'timestamp': datetime.now().isoformat()#时间戳
            }
            
            # 保存到文件
            status_file = json_dir / 'strategy_status.json'
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump(strategy_status, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"策略状态已保存: {status_file}")
            
        except Exception as e:
            logger.error(f"保存策略状态失败: {e}")

    def load_strategy_status(self):
        """从文件加载策略状态"""
        try:
            import json
            from pathlib import Path
            from datetime import datetime
            
            # 检查策略状态文件是否存在
            status_file = Path('json') / 'strategy_status.json'
            
            if status_file.exists():
                with open(status_file, 'r', encoding='utf-8') as f:
                    strategy_status = json.load(f)
                
                # 恢复策略状态
                self.risk_manager.position = strategy_status.get('position', 0)
                self.risk_manager.entry_price = strategy_status.get('entry_price', 0)
                # 兼容旧版本的quantity字段
                self.risk_manager.position_quantity = strategy_status.get('position_quantity', strategy_status.get('quantity', 0.0))
                self.risk_manager.current_price = strategy_status.get('current_price', 0.0)
                
                # 恢复高低点，处理无穷大值
                high_point = strategy_status.get('high_point', 0)
                # 修复：直接使用加载的值，不在加载时进行转换
                self.risk_manager.high_point = float('-inf') if high_point == 0 else high_point
                
                low_point = strategy_status.get('low_point', 0)
                # 修复：直接使用加载的值，不在加载时进行转换
                self.risk_manager.low_point = float('inf') if low_point == 0 else low_point
                
                # 恢复时间
                entry_time_str = strategy_status.get('entry_time')
                if entry_time_str:
                    try:
                        # 解析时间字符串，确保时区一致性
                        parsed_time = datetime.fromisoformat(entry_time_str)
                        # 如果解析出的时间带时区，则移除时区信息
                        if parsed_time.tzinfo is not None:
                            self.risk_manager.entry_time = parsed_time.replace(tzinfo=None)
                        else:
                            self.risk_manager.entry_time = parsed_time
                    except Exception as e:
                        logger.warning(f"解析entry_time失败: {e}, 使用None")
                        self.risk_manager.entry_time = None
                
                self.risk_manager.holding_periods = strategy_status.get('holding_periods', 0)
                self.trade_count = strategy_status.get('trade_count', 0)
                self.win_count = strategy_status.get('win_count', 0)
                # 更新CooldownManager的状态
                self.cooldown_manager.consecutive_losses = strategy_status.get('consecutive_losses', 0)
                self.cooldown_manager.consecutive_wins = strategy_status.get('consecutive_wins', 0)
                self.cooldown_manager.cooldown_treatment_active = strategy_status.get('cooldown_treatment_active', False)
                self.cooldown_manager.cooldown_treatment_level = strategy_status.get('cooldown_treatment_level', 0)
                self.cooldown_manager.position_size_reduction = strategy_status.get('position_size_reduction', 1.0)
                # 盈亏状态已转移到 risk_manager，无需直接读取
                
                # 加载杠杆倍数和保证金信息
                self.risk_manager.set_leverage(self.risk_manager.leverage)
                self.risk_manager.position_value = strategy_status.get('position_value', 0.0)
                self.risk_manager.margin_value = strategy_status.get('margin_value', 0.0)
                
                position_desc = {1: '多头', -1: '空头', 0: '无仓位'}.get(self.risk_manager.position, '未知')
                logger.info(f"策略状态已加载: {position_desc} (仓位={self.risk_manager.position}, 杠杆={self.risk_manager.leverage}x, 持仓价值=${self.risk_manager.position_value:.2f}, 保证金=${self.risk_manager.margin_value:.2f})")
            else:
                logger.info("策略状态文件不存在，使用默认状态")
                
        except Exception as e:
            logger.error(f"加载策略状态失败: {e}")
            # 使用默认值
            self.risk_manager.position = 0
            self.risk_manager.entry_price = 0
            self.risk_manager.position_quantity = 0.0
            self.risk_manager.current_price = 0.0
            # 修复：使用与 risk.py 一致的默认值
            self.risk_manager.high_point = float('-inf')
            self.risk_manager.low_point = float('inf')
            self.risk_manager.entry_time = None
            self.risk_manager.holding_periods = 0
    def _calculate_direction(self, current, signal_score):
        """
        根据评分计算交易方向
        
        Args:
            current: 当前数据点
            signal_score: 信号评分
            
        Returns:
            int: 交易方向 (1=多头, -1=空头, 0=观望)
        """
        # 数据验证
        if signal_score is None or pd.isna(signal_score):
            return 0
            
        # 方向判断
        if signal_score > self.long_threshold:
            return 1  # 多头
        elif signal_score < self.short_threshold:
            return -1  # 空头
        else:
            return 0  # 观望
    def _calculate_signal(self, data, verbose=False):
        """
        计算交易信号 - 核心信号生成逻辑
        
        Args:
            data: 历史数据
            verbose: 是否输出详细信息
            
        Returns:
            dict: 完整的信号信息
        """
        # 数据验证
        min_required_data = max(200, self.config.get('short_window', 200))  # 至少需要短期窗口的数据
        if len(data) < min_required_data:
            return {'signal': 0, 'reason': f'数据不足 ({len(data)} 条，需要至少 {min_required_data} 条)'}
        
        # 特征工程处理
        data = self._ensure_features(data, verbose)
        if data is None:
            return {'signal': 0, 'reason': '特征工程处理失败'}
        
        # 获取当前数据点
        current = data.iloc[-1]
        
        # 计算各维度评分
        scores = self._calculate_all_scores(current, data)
        
        # 计算原始信号方向
        original_signal = self._calculate_direction(current, scores['base_score'])
        
        # 计算综合评分
        signal_score = self._calculate_weighted_score(scores)
        
        # 信号过滤
        filtered_signal, filter_reason = self._filter_signal(
            original_signal, data, scores, verbose
        )
        
        # 确定最终信号
        signal, reason = self._determine_final_signal(filtered_signal, signal_score, filter_reason)
        
        # 生成投资建议
        investment_advice = self._generate_investment_advice(
            signal, signal_score, scores['base_score'], scores['trend_score'], current
        )
        
        # 构建调试信息
        debug_info = self._build_debug_info(current, scores, signal, reason)
        
        # 更新持仓周期
        self.update_holding_periods()
        
        # 返回完整信号信息
        return self._build_signal_result(
            signal, signal_score, scores, investment_advice, 
            debug_info, reason, original_signal, filter_reason, current
        )

    def _ensure_features(self, data, verbose):
        """确保数据包含必要的特征"""
        if 'signal_score' not in data.columns or 'trend_score' not in data.columns:
            try:
                if verbose:
                    print("🔧 进行特征工程处理...")
                data = self.feature_engineer.generate_features(data)
                if verbose:
                    print(f"✅ 特征工程完成")
            except Exception as e:
                if verbose:
                    print(f"❌ 特征工程失败: {e}")
                return None
        return data

    def _calculate_all_scores(self, current, data):
        """计算所有维度的评分"""
        return {
            'base_score': current.get('signal_score', 0.0),
            'trend_score': current.get('trend_score', 0.0),
            'risk_score': self._calculate_risk_score(current, data),
            'drawdown_score': self._calculate_drawdown_score(current, data)
        }

    def _calculate_weighted_score(self, scores):
        """计算加权综合评分"""
        weights = self.config.get('score_weights', {
            'signal_weight': 0.6,
            'trend_weight': 0.4,
            'risk_weight': 0.0,
            'drawdown_weight': 0.0
        })
        
        # 数据清理
        cleaned_scores = {
            key: 0.0 if value is None or pd.isna(value) else float(value)
            for key, value in scores.items()
        }
        
        return (
            cleaned_scores['base_score'] * weights.get('signal_weight', 0.6) +
            cleaned_scores['trend_score'] * weights.get('trend_weight', 0.4) +
            cleaned_scores['risk_score'] * weights.get('risk_weight', 0.0) +
            cleaned_scores['drawdown_score'] * weights.get('drawdown_weight', 0.0)
        )

    def _filter_signal(self, original_signal, data, scores, verbose):
        """过滤信号"""
        if original_signal == 0:
            return original_signal, "原始信号为观望"
        else:
            return self.signal_score_filter.filter_signal(
                original_signal, data, len(data)-1, verbose,
                trend_score=scores['trend_score'], 
                base_score=scores['base_score']
            )

    def _determine_final_signal(self, filtered_signal, signal_score, filter_reason):
        """确定最终信号"""
        if filtered_signal > 0:
            return 1, f'做多信号 (评分: {signal_score:.2f})'
        elif filtered_signal < 0:
            return -1, f'空头信号 (评分: {signal_score:.2f})'
        else:
            return 0, "观望信号" if filter_reason == "原始信号为观望" else f'信号被过滤: {filter_reason}'

    def _build_debug_info(self, current, scores, signal, reason):
        """构建调试信息"""
        return {
            # 基础指标
            'adx': current.get('adx', 0.0),
            'rsi': current.get('rsi', 50.0),
            'macd': current.get('macd', 0.0),
            'lineWMA': current.get('lineWMA', 0.0),
            'openEMA': current.get('openEMA', 0.0),
            'closeEMA': current.get('closeEMA', 0.0),
            'obv': current.get('obv', 0),
            'vix_fear': current.get('vix_fear', 20.0),
            'greed_score': current.get('greed_score', 50.0),
            'sentiment_score': current.get('sentiment_score', 0.0),
            
            # 趋势指标
            'adx_trend_score': current.get('adx_trend_score', 0.0),
            'rsi_trend_score': current.get('rsi_trend_score', 0.0),
            'macd_trend_score': current.get('macd_trend_score', 0.0),
            'ema_trend_score': current.get('ema_trend_score', 0.0),
            'price_trend_score': current.get('price_trend_score', 0.0),
            'atr_trend_score': current.get('atr_trend_score', 0.0),
            'volume_trend_score': current.get('volume_trend_score', 0.0),
            'bb_trend_score': current.get('bb_trend_score', 0.0),
            'obv_trend_score': current.get('obv_trend_score', 0.0),
            
            # 评分信息
            'risk_score': scores['risk_score'],
            'drawdown_score': scores['drawdown_score'],
            'signal': signal,
            'signal_score': scores.get('signal_score', 0.0),
            'base_score': scores['base_score'],
            'trend_score': scores['trend_score'],
            'original_signal': scores.get('original_signal', 0),
            'sideways_score': current.get('sideways_score', 0.0),
            'position_size': 0.0,
            'signal_threshold': 0.0,
            'reason': reason,
            'signal_from': 'traditional'
        }

    def _build_signal_result(self, signal, signal_score, scores, investment_advice, 
                           debug_info, reason, original_signal, filter_reason, current):
        """构建信号结果"""
        return {
            'signal': signal,
            'signal_score': signal_score,
            'base_score': scores['base_score'],
            'trend_score': scores['trend_score'],
            'risk_score': scores['risk_score'],
            'drawdown_score': scores['drawdown_score'],
            'investment_advice': investment_advice,
            'position_size': {'size': 0.0, 'direction': 'neutral', 'dominant_score': 0.0, 'reason': '待计算'},
            'reason': reason,
            'original_signal': {'signal': original_signal},
            'debug_info': debug_info,
            'signal_from': 'traditional',
            'current_price': current.get('close', 0.0),
            'symbol': self.config.get('symbol', 'ETHUSDT'),
            'filters': {
                'signal_score_filter': {
                    'passed': signal != 0,
                    'reason': filter_reason
                },
            }
        }
    def _generate_investment_advice(self, signal, signal_score, base_score, trend_score, current_data=None):
        """
        生成投资建议文本
        
        Args:
            signal: 信号方向 (1=多头, -1=空头, 0=观望)
            signal_score: 综合信号评分
            base_score: 基础评分
            trend_score: 趋势评分
            current_data: 当前数据点
            
        Returns:
            str: 投资建议文本
        """
        try:
            # 参数验证和转换
            signal, signal_score, base_score, trend_score = self._validate_advice_params(
                signal, signal_score, base_score, trend_score
            )
            
            # 获取技术指标
            indicators = self._get_technical_indicators(current_data)
            
            # 确定信号强度
            strength = self._determine_signal_strength(signal_score)
            
            # 生成基础建议
            advice = self._build_base_advice(signal, signal_score, base_score, trend_score, indicators, strength)
            
            # 添加AI分析
            advice += self._add_ai_analysis()
            
            # 添加风险提示
            advice += self._add_risk_warnings(signal_score, indicators['adx'])
            
            # 添加操作建议
            advice += self._add_operation_advice(signal, signal_score)
            
            return advice
            
        except Exception as e:
            return f"投资建议生成失败: {str(e)}"

    def _validate_advice_params(self, signal, signal_score, base_score, trend_score):
        """验证投资建议参数"""
        try:
            return (
                int(signal),
                float(signal_score),
                float(base_score),
                float(trend_score)
            )
        except (ValueError, TypeError):
            return 0, 0.0, 0.0, 0.0

    def _get_technical_indicators(self, current_data):
        """获取技术指标数据"""
        def safe_get_float(data, key, default=0.0):
            """安全获取浮点数值"""
            try:
                if hasattr(data, 'get'):
                    value = data.get(key, default)
                elif hasattr(data, '__getitem__'):
                    value = data[key] if key in data else default
                else:
                    value = default
                
                return default if value is None or pd.isna(value) else float(value)
            except (ValueError, TypeError, KeyError):
                return default
        
        data_source = current_data if current_data is not None else self.current
        return {
            'rsi': safe_get_float(data_source, 'rsi', 50.0),
            'adx': safe_get_float(data_source, 'adx', 0.0),
            'macd': safe_get_float(data_source, 'macd', 0.0),
            'volume': safe_get_float(data_source, 'volume', 0.0),
            'price': safe_get_float(data_source, 'close', 0.0)
        }

    def _determine_signal_strength(self, signal_score):
        """确定信号强度"""
        if abs(signal_score) >= 0.7:
            return "强烈"
        elif abs(signal_score) >= 0.5:
            return "中等"
        elif abs(signal_score) >= 0.3:
            return "轻微"
        else:
            return "微弱"

    def _build_base_advice(self, signal, signal_score, base_score, trend_score, indicators, strength):
        """构建基础建议"""
        rsi, adx, macd = indicators['rsi'], indicators['adx'], indicators['macd']
        
        if signal == 1:  # 多头信号
            advice = f"📈 {strength}做多建议\n"
            advice += f"• 综合评分: {signal_score:.3f} (基础:{base_score:.3f}, 趋势:{trend_score:.3f})\n"
            advice += f"• 技术指标: RSI({rsi:.1f}) {'超买' if rsi > 70 else '正常' if rsi > 30 else '超卖'}, "
            advice += f"ADX({adx:.1f}) {'强趋势' if adx > 25 else '弱趋势'}, "
            advice += f"MACD({'正' if macd > 0 else '负'})\n"
            
            if rsi > 70:
                advice += "注意: RSI处于超买区域，建议谨慎操作\n"
            elif rsi < 30:
                advice += "优势: RSI处于超卖区域，反弹概率较大\n"
                
        elif signal == -1:  # 空头信号
            advice = f"📉 {strength}做空建议\n"
            advice += f"• 综合评分: {signal_score:.3f} (基础:{base_score:.3f}, 趋势:{trend_score:.3f})\n"
            advice += f"• 技术指标: RSI({rsi:.1f}) {'超买' if rsi > 70 else '正常' if rsi > 30 else '超卖'}, "
            advice += f"ADX({adx:.1f}) {'强趋势' if adx > 25 else '弱趋势'}, "
            advice += f"MACD({'正' if macd > 0 else '负'})\n"
            
            if rsi < 30:
                advice += "注意: RSI处于超卖区域，建议谨慎操作\n"
            elif rsi > 70:
                advice += "优势: RSI处于超买区域，回调概率较大\n"
                
        else:  # 观望信号
            advice = f"⏸️ 观望建议\n"
            advice += f"• 综合评分: {signal_score:.3f} (基础:{base_score:.3f}, 趋势:{trend_score:.3f})\n"
            advice += f"• 技术指标: RSI({rsi:.1f}), ADX({adx:.1f}), MACD({'正' if macd > 0 else '负'})\n"
            advice += "• 建议: 市场信号不明确，建议等待更明确的信号\n"
        
        return advice

    def _add_ai_analysis(self):
        """添加AI分析信息"""
        if not (hasattr(self, 'current_deepseek_data') and self.current_deepseek_data):
            return ""
        
        deepseek_trend = self.current_deepseek_data.get('trend', 'unknown')
        deepseek_action = self.current_deepseek_data.get('action', 'unknown')
        deepseek_risk = self.current_deepseek_data.get('risk', 'medium')
        
        return (f"\n🤖 DeepSeek AI分析:\n"
                f"• 趋势判断: {deepseek_trend}\n"
                f"• 操作建议: {deepseek_action}\n"
                f"• 风险等级: {deepseek_risk}\n")

    def _add_risk_warnings(self, signal_score, adx):
        """添加风险提示"""
        warnings = ""
        
        if abs(signal_score) < 0.3:
            warnings += "🔔 风险提示: 信号强度较弱，建议降低仓位或等待更强信号\n"
        
        if adx < 20:
            warnings += "🔔 风险提示: ADX较低，市场可能处于震荡状态\n"
        
        return warnings

    def _add_operation_advice(self, signal, signal_score):
        """添加操作建议"""
        if signal == 0:
            return ""
        
        if abs(signal_score) >= 0.7:
            return "💡 操作建议: 信号强度较高，可考虑较大仓位\n"
        elif abs(signal_score) >= 0.5:
            return "💡 操作建议: 信号强度中等，建议适中仓位\n"
        else:
            return "💡 操作建议: 信号强度较弱，建议小仓位或等待\n"
    # 风险管理方法已移至 core/risk.py 中的 RiskManager 类
    
    def should_stop_loss(self, current_price, current_features=None, current_time=None):
        """代理到风险管理器的止损检查"""
        # 同步风险管理器的状态
        self._sync_risk_manager_state()
        return self.risk_manager.should_stop_loss(current_price, current_features, current_time)

    def should_take_profit(self, current_price, current_features=None, current_time=None):
        """代理到风险管理器的止盈检查"""
        # 同步风险管理器的状态
        self._sync_risk_manager_state()
        return self.risk_manager.should_take_profit(current_price, current_features, current_time)
    
    def check_risk_management(self, current_price, current_features, current_time=None):
        """代理到风险管理器的风险管理检查"""
        # 同步风险管理器的状态
        self._sync_risk_manager_state()
        return self.risk_manager.check_risk_management(current_price, current_features, current_time)
    
    def _sync_risk_manager_state(self):
        """同步风险管理器的状态 - 确保策略和风险管理器状态一致"""
        # 仓位状态已统一由 risk_manager 管理，无需同步
        pass
    
    def validate_risk_management_config(self):
        """代理到风险管理器的配置验证"""
        return self.risk_manager.validate_risk_management_config()
    
    def get_position_status(self, current_price):
        """代理到风险管理器的持仓状态获取"""
        return self.risk_manager.get_position_status(current_price)
    
    def should_open_position(self, signal, current_features=None, current_time=None):
        """代理到风险管理器的开仓检查"""
        return self.risk_manager.should_open_position(signal, current_features, current_time)
    
    def _update_high_low_points(self, current_price):
        """代理到风险管理器的高低点更新"""
        self.risk_manager._update_high_low_points(current_price)
        # 高低点已由 risk_manager 统一管理，无需同步回策略
    
    def _update_margin_info(self):
        """代理到风险管理器的保证金信息更新"""
        self.risk_manager._update_margin_info()
        # 同步回策略状态
        self.risk_manager.position_value = self.risk_manager.position_value
        self.risk_manager.margin_value = self.risk_manager.margin_value
    
    def update_position_info(self, position, entry_price, current_price, current_time=None, entry_signal_score=0.0, leverage=None, margin_value=None):
        """代理到风险管理器的持仓信息更新"""
        self.risk_manager.update_position_info(position, entry_price, current_price, current_time, entry_signal_score, leverage, margin_value)
        # 仓位状态已统一由 risk_manager 管理，无需同步回策略状态
        
        # 自动保存策略状态
        self.save_strategy_status()
    
    def update_holding_periods(self):
        """代理到风险管理器的持仓周期更新"""
        self.risk_manager.update_holding_periods()
    
    def set_position_quantity(self, quantity):
        """代理到风险管理器的持仓数量设置"""
        self.risk_manager.set_position_quantity(quantity)
    
    def set_leverage(self, leverage):
        """代理到风险管理器的杠杆倍数设置"""
        self.risk_manager.set_leverage(leverage)
        logger.info(f"策略杠杆倍数已设置为: {leverage}x")
        # 自动保存策略状态
        self.save_strategy_status()
    
    def update_leverage_from_trading_system(self, trading_system):
        """从交易系统更新杠杆倍数"""
        if hasattr(trading_system, 'leverage'):
            new_leverage = trading_system.leverage
            if new_leverage != self.risk_manager.leverage:
                self.risk_manager.set_leverage(new_leverage)
                logger.info(f"策略杠杆倍数已从交易系统更新为: {new_leverage}x")
                # 自动保存策略状态
                self.save_strategy_status()
                return True
        return False
    
    def update_current_deepseek_data(self, deepseek_data):
        """
        更新当前的DeepSeek数据
        
        Args:
            deepseek_data: 当前的DeepSeek分析数据
        """
        # 回测模式下不更新DeepSeek数据
        if self.mode == 'backtest':
            return
        
        if deepseek_data:
            self.current_deepseek_data = deepseek_data.copy()
            
            # 确保DeepSeek数据包含技术指标
            if 'indicators' not in self.current_deepseek_data and self.current:
                # 如果DeepSeek数据中没有技术指标，尝试从当前数据中补充
                self.current_deepseek_data['indicators'] = {
                    'rsi': {'rsi': self.current.get('rsi', 50.0)},
                    'adx': {'adx': self.current.get('adx', 0.0)},
                    'macd': {'macd': self.current.get('macd', 0.0)},
                    'volume': {'volume': self.current.get('current_volume', 0.0)},
                    'price': {'price': self.current.get('price', 0.0)}
                }
            
            logger.debug(f"更新当前DeepSeek数据: {self.current_deepseek_data}")
    def get_current_deepseek_data(self):
        """
        获取当前的DeepSeek数据
        
        Returns:
            dict: 当前的DeepSeek数据
        """
        return self.current_deepseek_data.copy() if self.current_deepseek_data else {}
    
    def _integrate_deepseek_analysis(self, signal_info, verbose=False):
        """
        整合DeepSeek分析到信号中
        
        Args:
            signal_info: 原始信号信息
            verbose: 是否显示详细信息
            
        Returns:
            dict: 整合后的信号信息
        """
        # 检查是否启用DeepSeek整合
        if self.mode == 'backtest':
            signal_info['deepseek_status'] = 'disabled'
            signal_info['deepseek_message'] = '回测模式下DeepSeek功能已禁用'
            return signal_info
            
        if not self.deepseek_integrator or not self.deepseek_integrator.is_enabled():
            signal_info['deepseek_status'] = 'unavailable'
            return signal_info
        
        try:
            # 获取DeepSeek权重
            deepseek_weight = self.config.get('deepseek_weight', 0.3)
            
            # 整合DeepSeek分析
            signal_info = self.deepseek_integrator.integrate_with_traditional_signal(
                signal_info, deepseek_weight
            )
            
            # 处理整合成功的信号
            if signal_info.get('deepseek_status') == 'integrated':
                self._update_investment_advice_with_deepseek(signal_info, verbose)
                
                if verbose:
                    self._print_deepseek_integration_info(signal_info, deepseek_weight)
            
            return signal_info
            
        except Exception as e:
            logger.warning(f"DeepSeek信号整合失败: {e}")
            signal_info['deepseek_status'] = 'error'
            signal_info['deepseek_error'] = str(e)
            return signal_info
    
    def _update_investment_advice_with_deepseek(self, signal_info, verbose=False):
        """
        使用DeepSeek数据更新投资建议
        
        Args:
            signal_info: 信号信息
            verbose: 是否显示详细信息
        """
        # 更新DeepSeek数据
        deepseek_analysis = signal_info.get('deepseek_analysis', {})
        self.update_current_deepseek_data(deepseek_analysis)
        
        # 获取整合后的信号参数
        updated_signal = signal_info.get('signal', 0)
        updated_signal_score = signal_info.get('signal_score', 0.0)
        updated_base_score = signal_info.get('base_score', 0.0)
        updated_trend_score = signal_info.get('trend_score', 0.0)
        
        # 构建技术指标数据
        technical_data = self._build_technical_data_from_deepseek(deepseek_analysis)
        
        # 生成新的投资建议
        updated_investment_advice = self._generate_investment_advice(
            updated_signal, updated_signal_score, updated_base_score, updated_trend_score, technical_data
        )
        signal_info['investment_advice'] = updated_investment_advice
    
    def _build_technical_data_from_deepseek(self, deepseek_analysis):
        """
        从DeepSeek分析中构建技术指标数据
        
        Args:
            deepseek_analysis: DeepSeek分析结果
            
        Returns:
            dict: 技术指标数据
        """
        deepseek_indicators = deepseek_analysis.get('indicators', {})
        
        if deepseek_indicators:
            # 从DeepSeek指标中提取数据
            rsi_data = deepseek_indicators.get('rsi', {})
            adx_data = deepseek_indicators.get('adx', {})
            macd_data = deepseek_indicators.get('macd', {})
            volume_data = deepseek_indicators.get('volume', {})
            price_data = deepseek_indicators.get('price', {})
            
            return {
                'rsi': rsi_data.get('rsi', 50.0),
                'adx': adx_data.get('adx', 0.0),
                'macd': macd_data.get('macd', 0.0),
                'volume': volume_data.get('volume', 0.0),
                'price': price_data.get('price', 0.0)
            }
        else:
            # 如果没有DeepSeek指标，使用当前数据
            return self.current
    
    def _print_deepseek_integration_info(self, signal_info, deepseek_weight):
        """
        打印DeepSeek整合信息
        
        Args:
            signal_info: 信号信息
            deepseek_weight: DeepSeek权重
        """
        deepseek_analysis = signal_info.get('deepseek_analysis', {})
        investment_advice = signal_info.get('investment_advice', '')
        
        print(f"🤖 DeepSeek: 评分={deepseek_analysis.get('signal_score', 0):.3f}, "
              f"方向={deepseek_analysis.get('signal', 0)}, ")
        print(f"整合: 权重={deepseek_weight:.1%}, "
              f"方法={signal_info.get('deepseek_status', 'unknown')}")
        print(f"📋 更新投资建议: {investment_advice[:100]}...")
    
    
    

    
    def get_risk_status(self, data):
        """获取风险状态"""
        # 首先尝试使用历史投资组合数据
        if len(self.portfolio_values) >= 10:
            # 计算当前夏普率
            recent_returns = self.returns[-min(30, len(self.returns)):]
            if len(recent_returns) > 0:
                mean_return = np.mean(recent_returns)
                std_return = np.std(recent_returns)
                current_sharpe = mean_return / std_return * np.sqrt(252) if std_return > 0 else 0
            else:
                current_sharpe = 0
            
            # 计算平均回撤
            if len(self.portfolio_values) > 1:
                max_value = max(self.portfolio_values)
                current_value = self.portfolio_values[-1]
                current_drawdown = (max_value - current_value) / max_value
            else:
                current_drawdown = 0
            
            # 风险等级评估
            if current_sharpe > 1.0 and current_drawdown < 0.05:
                risk_level = 'low'
                status = 'excellent'
                message = f'优秀表现 - 夏普比率: {current_sharpe:.2f}, 平均回撤: {current_drawdown*100:.1f}%'
            elif current_sharpe > 0.5 and current_drawdown < 0.1:
                risk_level = 'medium'
                status = 'good'
                message = f'良好表现 - 夏普比率: {current_sharpe:.2f}, 平均回撤: {current_drawdown*100:.1f}%'
            elif current_sharpe > 0 and current_drawdown < 0.15:
                risk_level = 'medium'
                status = 'normal'
                message = f'正常风险状态 - 夏普比率: {current_sharpe:.2f}, 平均回撤: {current_drawdown*100:.1f}%'
            else:
                risk_level = 'high'
                status = 'warning'
                message = f'高风险状态 - 夏普比率: {current_sharpe:.2f}, 平均回撤: {current_drawdown*100:.1f}%'
            
            return {
                'risk_level': risk_level,
                'status': status,
                'message': message
            }
        
        # 如果没有历史数据，基于当前市场数据评估风险
        if len(data) < 5:
            return {
                'risk_level': 'low',
                'status': 'insufficient_data',
                'message': '数据不足，无法评估风险'
            }
        
        try:
            # 基于技术指标评估市场风险
            current = data.iloc[-1]
            
            # 获取关键指标
            rsi = current.get('rsi', 50)
            atr = current.get('atr', 0)
            bb_position = current.get('bb_position', 0.5)
            
            # 计算价格波动率
            if len(data) >= 20:
                price_changes = data['close'].pct_change().dropna()
                volatility = price_changes.std() * np.sqrt(252)  # 年化波动率
            else:
                volatility = 0.3  # 默认值
            
            # 风险评估逻辑
            risk_factors = []
            
            # RSI极端值检查
            if rsi > 80 or rsi < 20:
                risk_factors.append('RSI极端值')
            
            # 布林带位置检查
            if bb_position > 0.9 or bb_position < 0.1:
                risk_factors.append('价格接近布林带边界')
            
            # 波动率检查
            if volatility > 0.5:  # 50%年化波动率
                risk_factors.append('高波动率')
            
            # 综合风险评估
            if len(risk_factors) >= 2:
                risk_level = 'high'
                status = 'warning'
                message = f'高风险 - 风险因素: {", ".join(risk_factors)}'
            elif len(risk_factors) == 1:
                risk_level = 'medium'
                status = 'normal'
                message = f'中等风险 - 风险因素: {", ".join(risk_factors)}'
            else:
                risk_level = 'low'
                status = 'good'
                message = f'低风险 - 市场状态良好 (RSI: {rsi:.1f}, 波动率: {volatility*100:.1f}%)'
            
            return {
                'risk_level': risk_level,
                'status': status,
                'message': message
            }
            
        except Exception as e:
            return {
                'risk_level': 'medium',
                'status': 'unknown',
                'message': f'风险评估异常: {str(e)}'
            }
    
    def _calculate_position_size(self,signal, signal_score):
        """
        动态仓位管理 - 基于评分计算仓位大小
        
        Args:
            signal: 信号方向 (1=多头, -1=空头, 0=观望)
            signal_score: 综合评分
            
        Returns:
            dict: 包含仓位信息的字典
        """
        
        # 数据验证和清理
        if signal_score is None or pd.isna(signal_score):
            signal_score = 0.0
            logger.warning("signal_score为None或NaN，设置为0.0")
        
        # 确保signal_score是数值类型
        try:
            signal_score = float(signal_score)
        except (ValueError, TypeError):
            signal_score = 0.0
            logger.warning(f"signal_score转换失败: {signal_score}，设置为0.0")
        
        # 确定主导方向
        if signal == 1:
            direction = 'bullish'
        elif signal == -1:
            direction = 'bearish'
        else:
            # 信号为0时，返回零仓位
            return {
                'size': 0.0,
                'direction': 'neutral',
                'dominant_score': 0.0,
                'reason': '信号为零，无仓位'
            }
        
        # 从配置文件获取仓位管理参数
        position_config = self.config.get('position_config', {})
        full_position_threshold_min = position_config.get('full_position_threshold_min', -0.5)
        full_position_threshold_max = position_config.get('full_position_threshold_max', 0.5)
        full_position_size = position_config.get('full_position_size', 1.0)
        avg_adjusted_position = position_config.get('avg_adjusted_position', 0.2)
        max_adjusted_position = position_config.get('max_adjusted_position', 0.8)
        
        # 根据信号方向分别判断仓位大小
        if direction == 'bullish':
            # 多头信号：使用正分判断
            if signal_score >= full_position_threshold_max:
                # 强多头信号 - 使用全仓位
                position_size = full_position_size
                reason = f"强多头仓位 - 评分: {signal_score:.2f} >= {full_position_threshold_max}"
            else:
                # 一般多头信号 - 使用一般仓位
                position_size = avg_adjusted_position
                reason = f"一般多头仓位 - 评分: {signal_score:.2f} < {full_position_threshold_max}"
                
        elif direction == 'bearish':
            # 空头信号：使用负分判断
            if signal_score <= full_position_threshold_min:
                # 强空头信号 - 使用全仓位
                position_size = full_position_size
                reason = f"强空头仓位 - 评分: {signal_score:.2f} <= {full_position_threshold_min}"
            else:
                # 一般空头信号 - 使用一般仓位
                position_size = avg_adjusted_position
                reason = f"一般空头仓位 - 评分: {signal_score:.2f} > {full_position_threshold_min}"
        
        # 应用风险乘数调整
        if isinstance(self.get_risk_multiplier(), (int, float)):
            risk_mult = self.get_risk_multiplier()
        else:
            risk_mult = 1.0  # 默认值
            logger.warning(f"risk_multiplier不是数值类型: {type(self.get_risk_multiplier())}, 使用默认值1.0")
        
        adjusted_position_size = position_size * risk_mult
        
        # 应用冷却处理 - 在仓位计算时立即生效
        adjusted_position_size = self.cooldown_manager.apply_to_position_size(adjusted_position_size)
        if self.cooldown_manager.cooldown_treatment_active:
            reason += f" (冷却L{self.cooldown_manager.cooldown_treatment_level}减少{self.cooldown_manager.position_size_reduction:.2f})"
        
        # 确保仓位大小在合理范围内
        adjusted_position_size = max(0.0, min(max_adjusted_position, adjusted_position_size))
        
        return {
            'size': adjusted_position_size,
            'direction': direction,
            'dominant_score': signal_score,
            'reason': reason
        }
    

    
    def _build_filter_status(self, current_data, historical_data, filter_reason):
        """构建过滤器状态信息"""
        filters_status = {}
        current_row = historical_data.iloc[-1] if len(historical_data) > 0 else None
        
        if current_row is not None:
            # 波动率过滤器
            if self.signal_score_filter.enable_volatility_filter:
                filters_status['volatility'] = self._check_volatility_filter(historical_data)
            
            # 均线纠缠过滤器
            if self.signal_score_filter.enable_price_ma_entanglement:
                filters_status['ma_entanglement'] = self._check_ma_entanglement_filter(current_row)
            
            # 信号评分过滤器
            if self.signal_score_filter.enable_signal_score_filter:
                filters_status['trend'] = self._check_trend_filter(current_row)
            
            # RSI过滤器
            if self.signal_score_filter.enable_rsi_filter:
                filters_status['rsi'] = self._check_rsi_filter(current_row)
        
        # 总体过滤器状态
        filters_status['signal_score_filter'] = self._determine_overall_filter_status(filter_reason)
        
        return filters_status

    def _check_volatility_filter(self, historical_data):
        """检查波动率过滤器"""
        if 'returns' in historical_data.columns:
            returns_data = historical_data['returns']
        else:
            returns_data = historical_data['close'].pct_change().dropna()
        
        volatility = returns_data.tail(self.signal_score_filter.volatility_period).std() if len(historical_data) >= self.signal_score_filter.volatility_period else 0
        volatility_passed = self.signal_score_filter.min_volatility <= volatility <= self.signal_score_filter.max_volatility
        
        return {
            'passed': volatility_passed,
            'reason': f"波动率: {volatility:.4f} (范围: {self.signal_score_filter.min_volatility:.4f}-{self.signal_score_filter.max_volatility:.4f})"
        }

    def _check_ma_entanglement_filter(self, current_row):
        """检查均线纠缠过滤器"""
        ma_entanglement = current_row.get('ma_entanglement_score', 0)
        entanglement_passed = ma_entanglement >= self.signal_score_filter.entanglement_distance_threshold
        
        return {
            'passed': entanglement_passed,
            'reason': f"均线纠缠: {ma_entanglement:.3f}% (阈值: {self.signal_score_filter.entanglement_distance_threshold}%)"
        }

    def _check_trend_filter(self, current_row):
        """检查趋势过滤器"""
        trend_score = abs(current_row.get('trend_score', 0.5))
        trend_passed = (trend_score >= self.signal_score_filter.trend_filter_threshold_min and 
                       trend_score <= self.signal_score_filter.trend_filter_threshold_max)
        
        return {
            'passed': trend_passed,
            'reason': f"趋势评分: {trend_score:.2f} (有效范围: {self.signal_score_filter.trend_filter_threshold_min:.2f}-{self.signal_score_filter.trend_filter_threshold_max:.2f})"
        }

    def _check_rsi_filter(self, current_row):
        """检查RSI过滤器"""
        rsi = current_row.get('rsi', 50)
        rsi_passed = (rsi >= self.signal_score_filter.rsi_oversold_threshold and 
                     rsi <= self.signal_score_filter.rsi_overbought_threshold)
        
        return {
            'passed': rsi_passed,
            'reason': f"RSI: {rsi:.2f} (范围: {self.signal_score_filter.rsi_oversold_threshold:.2f}-{self.signal_score_filter.rsi_overbought_threshold:.2f})"
        }

    def _determine_overall_filter_status(self, filter_reason):
        """确定总体过滤器状态"""
        if filter_reason == "原始信号为观望":
            return {'passed': True, 'reason': "观望信号无需过滤"}
        elif "信号通过过滤" in filter_reason or "信号通过" in filter_reason:
            return {'passed': True, 'reason': filter_reason}
        elif "过滤" in filter_reason and "通过" not in filter_reason:
            return {'passed': False, 'reason': filter_reason}
        else:
            return {'passed': True, 'reason': filter_reason}
    
    def _build_filter_reason(self, original_signal, filtered_signal, filter_reason):
        """构建过滤原因"""
        if filtered_signal == 0:
            # 信号被过滤
            if filter_reason == "原始信号为观望":
                return "观望信号"
            elif "信号通过" in filter_reason:
                # 如果过滤原因包含"信号通过"，说明逻辑错误，应该显示为被过滤
                return f"信号被过滤: {filter_reason.replace('信号通过', '信号被')}"
            else:
                return f"信号被过滤: {filter_reason}"
        else:
            # 信号通过过滤
            signal_type = "多头" if original_signal == 1 else "空头"
            if "信号通过过滤" in filter_reason or "信号通过" in filter_reason:
                return filter_reason
            else:
                return f"{signal_type}信号通过过滤: {filter_reason}"

    
    

    def generate_signals(self, features, verbose=False):
        """
        生成交易信号 - 主入口方法
        
        Args:
            features: 历史数据
            verbose: 是否输出详细信息
            
        Returns:
            dict: 完整的信号信息
        """
        try:
            # 数据验证 - 需要足够的历史数据来计算技术指标
            min_required_data = max(200, self.config.get('short_window', 200))  # 至少需要短期窗口的数据
            if len(features) < min_required_data:
                return {'signal': 0, 'reason': f'数据不足 ({len(features)} 条，需要至少 {min_required_data} 条)'}
            
            # 更新当前数据
            self._update_current_data(features)
            
            # 计算基础信号
            signal_info = self._calculate_signal(features, verbose)
            
            # 整合AI分析
            signal_info = self._integrate_deepseek_analysis(signal_info, verbose)
            
            # 计算仓位大小
            signal_info = self._calculate_and_update_position_size(signal_info)
            
            # 保存信号信息
            self._save_signal_info(signal_info, features)
            
            # 输出详细信息
            if verbose:
                self._print_signal_details(signal_info)
            
            return signal_info
            
        except Exception as e:
            if verbose:
                print(f"信号生成异常: {e}")
                import traceback
                print(f"详细错误: {traceback.format_exc()}")
            return {'signal': 0, 'strength': 0, 'reason': f'信号计算异常: {e}'}

    def _update_current_data(self, features):
        """更新当前数据点"""
        current = features.iloc[-1]
        self.current = current.to_dict() if hasattr(current, 'to_dict') else dict(current)

    def _calculate_and_update_position_size(self, signal_info):
        """计算并更新仓位大小"""
        position_size = self._calculate_position_size(signal_info['signal'], signal_info['signal_score'])
        signal_info['position_size'] = position_size
        
        # 更新调试信息中的仓位大小
        if 'debug_info' in signal_info:
            signal_info['debug_info']['position_size'] = (
                position_size.get('size', 0.0) if isinstance(position_size, dict) else position_size
            )
        
        return signal_info

    def _save_signal_info(self, signal_info, features):
        """保存信号信息"""
        try:
            data_time = features.index[-1] if len(features) > 0 else None
            self.save_latest_signal(signal_info, data_time)
        except Exception as e:
            logger.warning(f"保存信号信息失败: {e}")

    def _print_signal_details(self, signal_info):
        """打印信号详细信息"""
        # 信号基本信息
        signal_type = "多头" if signal_info['signal'] == 1 else "空头" if signal_info['signal'] == -1 else "观望"
        print(f"信号: {signal_type}({signal_info['signal']}), 评分: {signal_info['signal_score']:.3f}")
        
        # 投资建议
        if 'investment_advice' in signal_info:
            print("\n📋 投资建议:")
            print(signal_info['investment_advice'])
        
        # 技术指标
        if 'debug_info' in signal_info:
            debug = signal_info['debug_info']
            print(f"指标: ADX={debug['adx']:.1f}, RSI={debug['rsi']:.1f}, MACD={debug['macd']:.1f}")
        
        # 仓位信息
        if 'position_size' in signal_info:
            pos_info = signal_info['position_size']
            if isinstance(pos_info, dict):
                print(f"💰 仓位: {pos_info.get('size', 0):.1%} ({pos_info.get('reason', 'N/A')})")
            else:
                print(f"💰 仓位: {pos_info:.1%}")
        
        # 过滤器状态
        if 'filters' in signal_info:
            filters = signal_info['filters']
            passed_filters = sum(1 for f in filters.values() if f['passed'])
            total_filters = len(filters)
            print(f"过滤器: {passed_filters}/{total_filters} 通过")
    
    
    def get_parameter(self, category, key=None):
        """
        获取参数值
        
        Args:
            category: 参数类别
            key: 参数键（可选）
            
        Returns:
            参数值
        """
        if category in self.config:
            if key is None:
                return self.config[category]
            elif key in self.config[category]:
                return self.config[category][key]
            else:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 参数键不存在: {category}.{key}")
                return None
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 参数类别不存在: {category}")
            return None
    

    

    
    def _deep_merge(self, default_config, user_config):
        """
        深度合并配置字典
        
        Args:
            default_config: 默认配置
            user_config: 用户配置
            
        Returns:
            dict: 合并后的配置
        """
        result = default_config.copy()
        
        for key, value in user_config.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
                
        return result

     


    def dynamic_weights(self, adx_value, last_close=None, atr_value=None):
        """动态权重调整
        Args:
            adx_value: 当前ADX值（标量）
            last_close: 最新收盘价（用于价格位置判断）
            atr_value: 当前ATR值（可选，用于波动率判断）
        Returns:
            dict: 各指标权重配置
        """
        # 输入标准化处理
        if hasattr(adx_value, '__len__') and len(adx_value) > 1:
            adx_value = adx_value.iloc[-1] if hasattr(adx_value, 'iloc') else adx_value[-1]
        
        # 基础权重配置
        strong_trend = {
            'adx': 0.35, 
            'ema': 0.30,
            'atr': 0.15,
            'volume': 0.05,
            'rsi': 0.10,
            'bb': 0.05
        }
        medium_trend = {
            'adx': 0.30,
            'ema': 0.30,
            'atr': 0.15,
            'volume': 0.10,
            'rsi': 0.10,
            'bb': 0.05
        }
        ranging = {
            'rsi': 0.30,
            'ema': 0.35,
            'adx': 0.10,
            'atr': 0.10,
            'volume': 0.10,
            'bb': 0.05
        }
        
        # 平滑过渡处理（避免参数突变）
        if adx_value > 40:
            # 强趋势市：如果接近边界则混合中等趋势配置
            if adx_value < 45:
                mix_factor = (adx_value - 40) / 5.0
                return self._mix_weights(strong_trend, medium_trend, mix_factor)
            return strong_trend
        elif adx_value > 25:
            # 中等趋势：可能在两个边界附近
            if adx_value > 35:  # 接近强趋势
                mix_factor = (adx_value - 35) / 5.0
                return self._mix_weights(medium_trend, strong_trend, mix_factor)
            elif adx_value < 30:  # 接近震荡市
                mix_factor = (30 - adx_value) / 5.0
                return self._mix_weights(medium_trend, ranging, mix_factor)
            return medium_trend
        else:
            # 震荡市：如果接近边界则混合中等趋势配置
            if adx_value > 20:
                mix_factor = (adx_value - 20) / 5.0
                return self._mix_weights(ranging, medium_trend, mix_factor)
            return ranging


    def _mix_weights(self, weights1, weights2, factor):
        """混合两种权重配置
        Args:
            weights1: 主配置
            weights2: 次配置
            factor: 混合因子(0-1)
        Returns:
            混合后的权重配置
        """
        mixed = {}
        for k in weights1.keys():
            mixed[k] = weights1[k] * (1-factor) + weights2[k] * factor
        return mixed

    def _calculate_trend_score(self, current):
        """计算趋势强度评分"""
        # 动态权重
        dynamic_weights = self.dynamic_weights(current.get('adx', 0))
        
        # 获取各指标趋势评分
        trend_scores = {
            'atr': current.get('atr_trend_score', 0.0),
            'volume': current.get('volume_trend_score', 0.0),
            'ema': current.get('ema_trend_score', 0.0),
            'adx': current.get('adx_trend_score', 0.0),
            'rsi': current.get('rsi_trend_score', 0.0),
            'bb': current.get('bb_trend_score', 0.0)
        }
        
        # 计算加权趋势评分
        trend_score = sum(
            trend_scores[key] * dynamic_weights.get(key, 0.0)
            for key in trend_scores
        )
        
        # 确保趋势评分在合理范围内（0-1）
        return max(0.0, min(1.0, trend_score))
            
         
    
    def _calculate_risk_score(self, current, data):
        """计算风险评分"""
        if len(data) < 30:
            return 0.5
        
        # 计算波动率
        returns = data['close'].pct_change().dropna()
        if len(returns) < 30:
            return 0.5
        
        volatility = returns.std()
        
        # 获取夏普比率
        short_window = getattr(self, 'short_window', 30)
        long_window = getattr(self, 'long_window', 90)
        
        sharpe_short = current.get(f"sharpe_ratio_{short_window}", 0.0)
        sharpe_long = current.get(f"sharpe_ratio_{long_window}", 0.0)
        
        # 风险评分计算
        volatility_score = max(0.0, 1.0 - volatility * 10)
        sharpe_score = min(1.0, max(0.0, (sharpe_short + sharpe_long) / 2))
        
        return max(0.0, min(1.0, (volatility_score + sharpe_score) / 2))

    def _calculate_drawdown_score(self, current, data):
        """计算回撤评分"""
        if len(data) < 30:
            return 0.5
        
        # 获取最大回撤
        short_window = getattr(self, 'short_window', 30)
        long_window = getattr(self, 'long_window', 90)
        
        max_dd_short = current.get(f'max_drawdown_{short_window}', 0.0)
        max_dd_long = current.get(f'max_drawdown_{long_window}', 0.0)
        
        # 回撤评分计算
        dd_short_score = max(0.0, 1.0 - abs(max_dd_short) * 2)
        dd_long_score = max(0.0, 1.0 - abs(max_dd_long) * 2)
        
        return max(0.0, min(1.0, (dd_short_score + dd_long_score) / 2))

    def save_latest_signal(self, signal_info, current_time=None):
        """
        保存最新信号信息
        
        Args:
            signal_info: 信号信息字典
            current_time: 数据时间（可选，默认为当前时间）
        """
        try:
            # 获取基础信息
            signal_value = signal_info.get('signal', 0)
            # 使用数据时间，如果没有则使用当前时间
            if current_time is None:
                current_time = datetime.now()
            elif hasattr(current_time, 'strftime'):
                # 如果已经是datetime对象，直接使用
                pass
            else:
                # 如果是其他类型的时间对象，转换为datetime
                current_time = pd.to_datetime(current_time)
            
            debug_info = signal_info.get('debug_info', {})
            
            # 构建信号数据
            signal_data = {
                'timestamp': current_time,
                'signal': signal_value,
                'signal_text': self._build_signal_text(signal_info),
                'filter_info': self._build_filter_info(signal_info),
                'signal_score': signal_info.get('signal_score', 0.0),
                'base_score': signal_info.get('base_score', 0.0),
                'trend_score': signal_info.get('trend_score', 0.0),
                'risk_score': signal_info.get('risk_score', 0.0),
                'drawdown_score': signal_info.get('drawdown_score', 0.0),
                'reason': signal_info.get('reason', ''),
                'position_size': signal_info.get('position_size', 0.0),
                'price': signal_info.get('current_price', 0.0),
                'symbol': signal_info.get('symbol', ''),
                'indicators': self._build_indicators(debug_info),
                'deepseek_analysis': self._build_deepseek_analysis(signal_info),
            }
            
            # 更新信号信息
            self.last_signal.update(signal_data)
            
            # 记录日志 - 使用数据时间
            signal_type = {1: "多头", -1: "空头", 0: "观望"}[signal_value]
            logger.debug(f"[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] 保存最新信号: {signal_type}, 评分: {signal_info.get('signal_score', 0):.3f}")
            
        except Exception as e:
            logger.error(f"保存最新信号时发生错误: {str(e)}")
    
    def get_latest_signal(self):
        """
        获取最新信号信息
        
        Returns:
            dict: 最新信号的完整信息
        """
        return self.last_signal.copy()
    
    
    
    def _build_signal_text(self, signal_info):
        """构建信号文本描述"""
        try:
            signal = signal_info.get('signal', 0)
            signal_score = signal_info.get('signal_score', 0.0)
            reason = signal_info.get('reason', '')
            
            if signal == 1:
                signal_text = f"做多信号 - 评分: {signal_score:.3f}"
            elif signal == -1:
                signal_text = f"做空信号 - 评分: {signal_score:.3f}"
            else:
                signal_text = f"观望信号 - 评分: {signal_score:.3f}"
            
            if reason:
                signal_text += f"({reason})"
            
            return signal_text
        except Exception as e:
            return f"信号文本构建失败: {str(e)}"
    
    def _build_filter_info(self, signal_info):
        """构建过滤信息"""
        try:
            filters = signal_info.get('filters', {})
            filter_info = {}
            
            for filter_name, filter_status in filters.items():
                if isinstance(filter_status, dict):
                    filter_info[filter_name] = {
                        'passed': filter_status.get('passed', False),
                        'reason': filter_status.get('reason', '')
                    }
                else:
                    filter_info[filter_name] = {
                        'passed': bool(filter_status),
                        'reason': str(filter_status)
                    }
            
            return filter_info
        except Exception as e:
            return {'error': f"过滤信息构建失败: {str(e)}"}
    

    def _build_indicators(self, debug_info):
        """构建技术指标信息"""
        try:
            # 验证输入参数
            if not debug_info:
                logger.warning("debug_info 为空，使用默认值")
                debug_info = {}
            
            # 构建技术指标字典
            indicators = {}
            
            # 基础技术指标
            indicators['adx'] = debug_info.get('adx', 0.0)
            indicators['rsi'] = debug_info.get('rsi', 50.0)
            indicators['macd'] = debug_info.get('macd', 0.0)
            indicators['lineWMA'] = debug_info.get('lineWMA', 0.0)
            indicators['openEMA'] = debug_info.get('openEMA', 0.0)
            indicators['closeEMA'] = debug_info.get('closeEMA', 0.0)
            indicators['bb_position'] = debug_info.get('bb_position', 0.5)
            indicators['obv'] = debug_info.get('obv', 0)
            
            # 市场情绪指标
            indicators['vix_fear'] = debug_info.get('vix_fear', 20.0)
            indicators['greed_score'] = debug_info.get('greed_score', 50.0)
            indicators['sentiment_score'] = debug_info.get('sentiment_score', 0.0)
             
            logger.debug(f"成功构建技术指标，共 {len(indicators)} 个指标")
            return indicators
            
        except Exception as e:
            logger.error(f"技术指标构建失败: {str(e)}")
            return {'error': f"技术指标构建失败: {str(e)}"}
    
    
    def _build_deepseek_analysis(self, signal_info):
        """构建DeepSeek分析信息"""
        try:
            deepseek_analysis = signal_info.get('deepseek_analysis', {})
            if not deepseek_analysis:
                return {}

            return {
                'signal': deepseek_analysis.get('signal', 0),
                'signal_score': deepseek_analysis.get('signal_score', 0.0),
                'trend_score': deepseek_analysis.get('trend_score', {}),
                'base_score': deepseek_analysis.get('base_score', {}),
                'sentiment_score': deepseek_analysis.get('sentiment_score', {}),
                'timestamp': deepseek_analysis.get('timestamp', ''),
                'current_price': deepseek_analysis.get('current_price', 0.0),
                'resistance': deepseek_analysis.get('resistance', 0.0),
                'support': deepseek_analysis.get('support', 0.0),
                'trend': deepseek_analysis.get('trend', 'unknown'),
                'risk': deepseek_analysis.get('risk', 'medium'),
                'action': deepseek_analysis.get('action', 'wait'),
                'advice': deepseek_analysis.get('advice', ''), 
            }
        except Exception as e:
            return {'error': f"DeepSeek分析构建失败: {str(e)}"}

    def _calculate_ratio(self, current_price, leverage=1.0):
        """代理到风险管理器的盈亏比例计算"""
        return self.risk_manager._calculate_ratio(current_price, leverage)
    
    def calculate_unrealized_pnl(self, current_price=None, leverage=1.0):
        """代理到风险管理器的未实现盈亏计算"""
        # 如果需要更新当前价格，先更新风险管理器的当前价格
        if current_price is not None:
            self.risk_manager.current_price = current_price
        
        # 同步风险管理器状态
        self._sync_risk_manager_state()
        
        # 计算未实现盈亏（盈亏状态已在risk_manager中自动更新）
        pnl = self.risk_manager.calculate_unrealized_pnl()
        
        return {
            'pnl': pnl,
            'percentage': self.risk_manager.position_unrealized_pnl_percent,
            'is_profitable': pnl > 0,
            'leverage_effect': f"杠杆{leverage}x计算",
            'position_value': self.risk_manager.get_position_value(),
            'margin_value': self.risk_manager.get_margin_value()
        }

    def get_high_point(self):
        """获取持仓期间的最高点"""
        return self.risk_manager.high_point
    
    def get_low_point(self):
        """获取持仓期间的最低点"""
        return self.risk_manager.low_point
    
    def get_high_low_points(self):
        """获取持仓期间的高低点信息"""
        return {
            'high_point': self.risk_manager.high_point,
            'low_point': self.risk_manager.low_point,
            'position': self.risk_manager.position,
            'entry_price': self.risk_manager.entry_price,
            'current_price': self.risk_manager.current_price
        }
    
    # 添加获取仓位信息的代理方法
    def get_position(self):
        """获取当前仓位"""
        return self.risk_manager.position
    
    def get_entry_price(self):
        """获取开仓价格"""
        return self.risk_manager.entry_price
    
    def get_position_quantity(self):
        """获取持仓数量"""
        return self.risk_manager.position_quantity
    
    def get_current_price(self):
        """获取当前价格"""
        return self.risk_manager.current_price
    
    def get_leverage(self):
        """获取杠杆倍数"""
        return self.risk_manager.leverage
    
    def get_entry_time(self):
        """获取开仓时间"""
        return self.risk_manager.entry_time
    
    def get_holding_periods(self):
        """获取持仓周期数"""
        return self.risk_manager.holding_periods
    
    def get_position_value(self):
        """获取持仓价值"""
        return self.risk_manager.position_value
    
    def get_margin_value(self):
        """获取保证金"""
        return self.risk_manager.margin_value

    def get_position_unrealized_pnl(self):
        """获取未实现盈亏"""
        return self.risk_manager.position_unrealized_pnl
    
    def get_position_unrealized_pnl_percent(self):
        """获取未实现盈亏百分比"""
        return self.risk_manager.position_unrealized_pnl_percent
    
    # 夏普比率相关参数代理方法
    def get_sharpe_lookback(self):
        """获取夏普比率回看期"""
        return self.risk_manager.sharpe_lookback
    
    def get_target_sharpe(self):
        """获取目标夏普比率"""
        return self.risk_manager.target_sharpe
    
    def get_max_risk_multiplier(self):
        """获取最大风险倍数"""
        return self.risk_manager.max_risk_multiplier
    
    def get_risk_multiplier(self):
        """获取当前风险倍数"""
        return self.risk_manager.risk_multiplier
    
    def set_risk_multiplier(self, value):
        """设置风险倍数"""
        self.risk_manager.risk_multiplier = value
    
    def reset_position(self):
        """重置策略持仓状态"""
        # 重置风险管理器状态
        if hasattr(self, 'risk_manager'):
            self.risk_manager.reset_state()
        
        # 重置冷却管理器状态
        if hasattr(self, 'cooldown_manager'):
            self.cooldown_manager.reset_state()
        
        # 重置策略特有的状态变量
        self.current = None
        self.current_deepseek_data = None
        
        logger.info("策略持仓状态已重置")

