"""
交易信号过滤器模块
负责过滤低质量交易信号，提高策略稳定性
"""

import logging
import pandas as pd

logger = logging.getLogger(__name__)


class SignalFilter:
    """
    交易信号过滤器
    
    功能：过滤低质量交易信号，提高策略稳定性
    
    核心过滤器：
    - 价格偏离过滤：防止追高追低
    - RSI过滤：避免超买超卖区域
    - 价格动量过滤：防止过度追涨杀跌
    - 成交量异常过滤：避免异常成交量
    - 相邻时间级别验证：多时间级别确认
    - 价格均线纠缠过滤：避免均线纠缠区域
    
    辅助过滤器：
    - 波动率过滤：控制风险
    - 时间过滤：避开低流动性时段
    """
    
    def __init__(self, config=None, data_loader=None):
        """初始化过滤器参数和开关"""
        # 从配置中获取过滤器参数
        if config is None:
            filter_config = {}
            print(f"🔍 使用空配置")
        else:
            # 检查配置结构，如果直接包含过滤器参数，则使用整个配置
            if 'enable_signal_score_filter' in config:
                filter_config = config
                print(f"🔍 使用扁平化配置，直接包含过滤器参数")
            else:
                filter_config = config.get('signal_score_filters', {})
                print(f"🔍 使用嵌套配置，从 signal_score_filters 获取")
            
            print(f"🔍 使用传入配置，config keys: {list(config.keys())}")
            print(f"🔍 filter_config keys: {list(filter_config.keys())}")
        
        print(f"🔍 filter_config 中的 enable_signal_score_filter: {filter_config.get('enable_signal_score_filter', 'NOT_FOUND')}")
        
        # ===== 核心过滤器开关 =====
        self.enable_price_deviation_filter = filter_config.get('enable_price_deviation_filter', False)
        self.enable_price_ma_entanglement = filter_config.get('enable_price_ma_entanglement', False)
        self.enable_rsi_filter = filter_config.get('enable_rsi_filter', False)
        self.enable_volatility_filter = filter_config.get('enable_volatility_filter', False)
        self.enable_volume_filter = filter_config.get('enable_volume_filter', False)
        self.enable_signal_score_filter = filter_config.get('enable_signal_score_filter', False)
        print(f"🔍 信号评分过滤器启用状态: {self.enable_signal_score_filter}")
        print(f"🔍 波动率过滤器启用状态: {self.enable_volatility_filter}")
        
        # ===== 核心过滤参数 =====
        self.price_deviation_threshold = filter_config.get('price_deviation_threshold', 2.0)
        self.rsi_overbought_threshold = filter_config.get('rsi_overbought_threshold', 85)
        self.rsi_oversold_threshold = filter_config.get('rsi_oversold_threshold', 25)
        
        # ===== 波动率过滤器参数 =====
        self.min_volatility = filter_config.get('min_volatility', 0.005)
        self.max_volatility = filter_config.get('max_volatility', 0.45)
        self.volatility_period = filter_config.get('volatility_period', 20)
        
        # ===== 价格均线纠缠过滤参数 =====
        self.entanglement_distance_threshold = filter_config.get('entanglement_distance_threshold', 0.2)
        
        # ===== 信号评分过滤器参数 =====
        self.trend_filter_threshold_min = filter_config.get('trend_filter_threshold_min', 0.3)
        self.trend_filter_threshold_max = filter_config.get('trend_filter_threshold_max', 0.7)
        
        # 信号评分过滤器具体阈值参数
        self.filter_long_base_score = filter_config.get('filter_long_base_score', 0.7)
        self.filter_short_base_score = filter_config.get('filter_short_base_score', 0.2)
        self.filter_long_trend_score = filter_config.get('filter_long_trend_score', 0.4)
        self.filter_short_trend_score = filter_config.get('filter_short_trend_score', 0.3)

        # 数据加载器
        self.data_loader = data_loader
         
    
    def filter_signal(self, signal, features, current_index, verbose=False, trend_score=None, base_score=None):
        """
        过滤交易信号
        
        Args:
            signal: 原始信号 (1=多头, -1=空头, 0=观望)
            features: 特征数据
            current_index: 当前索引
            verbose: 是否输出详细信息
            
        Returns:
            tuple: (过滤后信号, 过滤原因)
        """
        if signal == 0:  # 观望信号不需要过滤
            return signal, "原始信号为观望"
        
        # 获取当前数据
        current_data = features.iloc[:current_index+1]
        current_row = current_data.iloc[-1]
        
        # 获取当前数据时间用于日志
        current_time = current_row.name if hasattr(current_row, 'name') else None
        try:
            if current_time and pd.notna(current_time):
                time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                time_str = "N/A"
        except (ValueError, AttributeError):
            time_str = "N/A"
        
        # 记录开始过滤信号
        signal_type = "做多" if signal == 1 else "做空"
        #logger.info(f"[{time_str}] 开始过滤{signal_type}信号")
        
        # ===== 核心过滤器检查 =====
        
        # 1. 价格偏离过滤（核心）
        if self.enable_price_deviation_filter:
            filtered_signal, filter_reason = self._check_price_deviation(current_row, signal)
            if filtered_signal == 0:
                if verbose:
                    print(f"🔍 价格偏离过滤: {filter_reason}")
                return filtered_signal, filter_reason
        
        # 2. RSI过滤（核心）
        if self.enable_rsi_filter:
            filtered_signal, filter_reason = self._check_rsi_conditions(current_row, signal)
            if filtered_signal == 0:
                if verbose:
                    print(f"🔍 RSI过滤: {filter_reason}")
                return filtered_signal, filter_reason
        
        # 3. 波动率过滤（核心）
        if self.enable_volatility_filter:
            filtered_signal, filter_reason = self._check_volatility_filter(current_data, current_row)
            if filtered_signal == 0:
                if verbose:
                    print(f"🔍 波动率过滤: {filter_reason}")
                return filtered_signal, filter_reason
        

        

        
        # 5. 信号评分过滤器（核心）- 观望信号不进入此过滤器
        if self.enable_signal_score_filter:
            if verbose:
                logger.info(f"进入信号评分过滤器检查 - 原始信号: {signal}")
            filtered_signal, filter_reason = self._check_signal_score_filter(current_data, current_row, signal, trend_score, base_score)
            if filtered_signal == 0:
                if verbose:
                    logger.info(f"信号评分过滤: {filter_reason}")
                return filtered_signal, filter_reason
            else:
                if verbose:
                    logger.info(f"信号评分过滤器通过: {filter_reason}")
        
        # 6. 价格均线纠缠过滤（核心）
        if self.enable_price_ma_entanglement:
            is_entangled = self._check_price_ma_entanglement(current_row)
            if is_entangled:
                if verbose:
                    print("🔍 价格均线纠缠过滤: 价格均线纠缠")
                return 0, "价格均线纠缠"
        
        
        # 所有过滤器都通过
        return signal, f"{signal_type}信号通过过滤"
      
    def _check_price_deviation(self, current_row, signal):
        """价格偏离过滤：防止追高追低（动态阈值调整）"""
        
        signal_type = "做多" if signal == 1 else "做空"
        
        if 'lineWMA' in current_row and not pd.isna(current_row['lineWMA']):
            # 动态调整价格偏离阈值
            dynamic_threshold = self._get_dynamic_price_deviation_threshold(current_row, signal)
            
            # 根据信号类型选择不同的价格
            if signal == 1:  # 做多信号：使用low价格
                price = current_row.get('low', current_row['close'])
                line_wma = current_row['lineWMA']
                # 避免除零错误
                if line_wma != 0:
                    price_deviation = (price - line_wma) / line_wma * 100
                    
                    # 确保price_deviation是标量值
                    if hasattr(price_deviation, '__len__') and len(price_deviation) > 1:
                        price_deviation = price_deviation.iloc[-1] if hasattr(price_deviation, 'iloc') else price_deviation[-1]
                    
                    # 做多信号：low价格过度偏离WMA向上时过滤（使用动态阈值）
                    if price_deviation >= dynamic_threshold:
                        return 0, f"价格偏离过滤(做多信号，low价格偏离WMA{price_deviation:.1f}% >= 动态阈值{dynamic_threshold:.1f}%)"
                    
            elif signal == -1:  # 空头信号：使用high价格
                price = current_row.get('high', current_row['close'])
                line_wma = current_row['lineWMA']
                # 避免除零错误
                if line_wma != 0:
                    price_deviation = (price - line_wma) / line_wma * 100
                    
                    # 确保price_deviation是标量值
                    if hasattr(price_deviation, '__len__') and len(price_deviation) > 1:
                        price_deviation = price_deviation.iloc[-1] if hasattr(price_deviation, 'iloc') else price_deviation[-1]
                    
                    # 空头信号：high价格过度偏离WMA向下时过滤（使用动态阈值）
                    if price_deviation <= -dynamic_threshold:
                        return 0, f"价格偏离过滤(空头信号，high价格偏离WMA{price_deviation:.1f}% <= -动态阈值{-dynamic_threshold:.1f}%)"
        
        return signal, f"{signal_type}信号通过价格偏离过滤"
    
    def _get_dynamic_price_deviation_threshold(self, current_row, signal):
        """动态计算价格偏离阈值"""
        base_threshold = self.price_deviation_threshold  # 基础阈值2.0%
        
        # 1. 市场状态调整
        market_adjustment = self._get_market_state_adjustment(current_row)
        
        # 3. 波动率调整
        volatility_adjustment = self._get_volatility_adjustment(current_row)
        
        # 计算最终动态阈值
        dynamic_threshold = base_threshold + market_adjustment  + volatility_adjustment
        
        # 确保阈值在合理范围内
        min_threshold = 1.0  # 最小阈值1.0%
        max_threshold = 8.0  # 最大阈值8.0%
        dynamic_threshold = max(min_threshold, min(max_threshold, dynamic_threshold))
        
        return dynamic_threshold
    

    
    def _get_market_state_adjustment(self, current_row):
        """基于市场状态的阈值调整"""
        # 获取市场状态
        market_regime = current_row.get('market_regime', 0)
        # print(f"_get_market_state_adjustment_market_regime: {market_regime}")
        # 基于市场状态调整阈值
        if market_regime == 2:  # 强震荡市场
            return -0.5  # 降低阈值0.5%，震荡市场需要更严格过滤
        elif market_regime == 1:  # 强趋势市场
            return 5.0  # 提高阈值1.0%，趋势市场允许更大偏离
        else:  # 混合市场
            return 0.0
    
   
    
    def _get_volatility_adjustment(self, current_row):
        """基于波动率的阈值调整"""
        # 获取ATR或波动率指标
        atr = current_row.get('atr', 0)
        close_price = current_row.get('close', 1)
        
        if atr > 0 and close_price > 0:
            # 计算ATR相对价格的比例
            atr_ratio = atr / close_price * 100
            
            # 基于ATR比例调整阈值
            if atr_ratio > 5.0:  # 高波动率
                return 1.5  # 提高阈值1.5%
            elif atr_ratio > 3.0:  # 中等波动率
                return 0.5  # 提高阈值0.5%
            elif atr_ratio < 1.0:  # 低波动率
                return -0.5  # 降低阈值0.5%
        
        return 0.0
    
    def _check_rsi_conditions(self, current_row, signal):
        """RSI过滤：避免超买超卖区域"""
        rsi = current_row.get('rsi', 50)
        if pd.isna(rsi):
            signal_type = "做多" if signal == 1 else "做空"
            return signal, f"{signal_type}信号通过RSI过滤(RSI数据缺失)"
        
        if signal == 1 and rsi >= self.rsi_overbought_threshold:
            return 0, f"多头RSI超买过滤(RSI{rsi:.1f} >= 阈值{self.rsi_overbought_threshold})"
        elif signal == -1 and rsi <= self.rsi_oversold_threshold:
            return 0, f"空头RSI超卖过滤(RSI{rsi:.1f} <= 阈值{self.rsi_oversold_threshold})"
        
        signal_type = "做多" if signal == 1 else "做空"
        return signal, f"{signal_type}信号通过RSI过滤(RSI{rsi:.1f})"

    
    def _check_price_ma_entanglement(self, current_row):
        """价格均线纠缠过滤：基于价格与均线顺序关系的智能过滤"""
        current_price = current_row.get('close', 0)
        line_wma = current_row.get('lineWMA', 0)
        open_ema = current_row.get('openEMA', 0)
        close_ema = current_row.get('closeEMA', 0)
        
        # 检查数据有效性
        if (pd.isna(current_price) or pd.isna(line_wma) or 
            pd.isna(open_ema) or pd.isna(close_ema) or
            line_wma == 0 or open_ema == 0 or close_ema == 0):
            return False
        
        # 计算EMA的最大值和最小值
        ema_max = max(open_ema, close_ema)
        ema_min = min(open_ema, close_ema)
        
        # 定义价格与均线的顺序关系
        # 1. 完美多头排列：价格 > EMA最大 > LineWMA
        perfect_bullish = current_price > ema_max > line_wma
        
        # 2. 完美空头排列：价格 < EMA最小 < LineWMA
        perfect_bearish = current_price < ema_min < line_wma
        
        # 计算距离信息
        price_wma_distance = abs(current_price - line_wma) / line_wma * 100
        #print(f"price_wma_distance: {price_wma_distance}")
        ema_wma_distance = abs(ema_max - line_wma) / line_wma * 100
        ema_distance = abs(ema_max - ema_min) / ema_max * 100
        
        # 判断是否为纠缠状态
        is_entangled = False
        
        # 只有完美排列才不被过滤，其他所有排列都要被过滤
        if perfect_bullish or perfect_bearish:
            # 完美排列时，再判断距离
            if perfect_bullish:
                # 完美多头排列：检查距离是否过近
                if price_wma_distance < self.entanglement_distance_threshold:
                    is_entangled = True
            elif perfect_bearish:
                # 完美空头排列：检查距离是否过近
                if price_wma_distance < self.entanglement_distance_threshold:
                    is_entangled = True
        else:
            # 非完美排列：直接过滤
            is_entangled = True
        
        return is_entangled

    
    def _check_signal_score_filter(self, current_data, current_row, signal, trend_score=None, base_score=None):
        """
        信号评分过滤器：基于趋势强度和基础评分过滤信号
        
        Args:
            current_data: 当前数据
            current_row: 当前行数据
            signal: 信号 (1=多头, -1=空头, 0=观望)
            
        Returns:
            tuple: (过滤后信号, 过滤原因)
        """
        try:
            # 获取趋势强度和基础评分 - 优先使用传递的参数
            if trend_score is None:
                trend_score = current_row.get('trend_score')
            if base_score is None:
                base_score = current_row.get('base_score')

            # 检查数据有效性
            if trend_score is None or pd.isna(trend_score):
                signal_type = "做多" if signal == 1 else "做空"
                return signal, f"{signal_type}信号通过评分过滤(趋势评分数据缺失)"
            
            if base_score is None or pd.isna(base_score):
                signal_type = "做多" if signal == 1 else "做空"
                return signal, f"{signal_type}信号通过评分过滤(基础评分数据缺失)"
            
            # 获取过滤阈值 - 直接从当前实例的属性获取
            filter_long_base_score = getattr(self, 'filter_long_base_score')
            filter_short_base_score = getattr(self, 'filter_short_base_score')
            filter_long_trend_score = getattr(self, 'filter_long_trend_score')
            filter_short_trend_score = getattr(self, 'filter_short_trend_score')
            
            # 根据信号方向进行过滤
            if signal == 1:  # 多头信号
                # 多头过滤逻辑：trend_score < filter_long_short_trend_score 过滤，base_score < filter_long_base_score 过滤
                if trend_score < filter_long_trend_score:
                    return 0, f"多头趋势强度不足(趋势评分{trend_score:.3f} 必须大于 {filter_long_trend_score})"
                
                if base_score < filter_long_base_score:
                    return 0, f"多头基础评分不足(基础评分{base_score:.3f} 必须大于 {filter_long_base_score})"
                    
            elif signal == -1:  # 空头信号
                # 空头过滤逻辑：trend_score > filter_short_trend_score 过滤，base_score > filter_short_base_score 过滤
                if trend_score > filter_short_trend_score:
                    return 0, f"空头趋势强度不足(趋势评分{trend_score:.3f} 必须小于 {filter_short_trend_score})"
                
                if base_score > filter_short_base_score:
                    return 0, f"空头基础评分不足(基础评分{base_score:.3f} 必须小于 {filter_short_base_score})"
            
            elif signal == 0:  # 观望信号
                # 观望信号不需要进行评分过滤
                return signal, "观望信号通过评分过滤"
            
            signal_type = "做多" if signal == 1 else "做空"
            return signal, f"{signal_type}信号通过评分过滤(趋势评分{trend_score:.3f}, 基础评分{base_score:.3f})"
            
        except Exception as e:
            # 如果计算失败，返回原始信号
            return signal, f"信号评分过滤异常: {str(e)}"

    def _check_volatility_filter(self, current_data, current_row):
        """波动率过滤：控制风险"""
        try:
            if len(current_data) < self.volatility_period:
                return 1, "信号通过波动率过滤(数据不足)"
            
            # 计算历史波动率（基于收盘价的标准差）
            recent_prices = current_data['close'].tail(self.volatility_period).dropna()
            returns = recent_prices.pct_change().dropna()
            current_volatility = returns.std()
            
            # 检查波动率是否在合理范围内
            if current_volatility < self.min_volatility:
                return 0, f"波动率过低({current_volatility:.4f} < {self.min_volatility})"
            elif current_volatility > self.max_volatility:
                return 0, f"波动率过高({current_volatility:.4f} > {self.max_volatility})"
            
            return 1, f"信号通过波动率过滤(波动率{current_volatility:.4f})"
            
        except Exception as e:
            return 1, f"信号通过波动率过滤(计算异常: {str(e)})"
  