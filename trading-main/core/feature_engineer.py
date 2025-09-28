import numpy as np
import pandas as pd
from scipy.stats import linregress
from dotenv import load_dotenv
from config import *

load_dotenv()

# 技术指标参数
RSI_PERIOD = PERIOD_CONFIG['RSI_PERIOD']
LINEWMA_PERIOD = EMA_CONFIG['LINEEMA_PERIOD']
OPENEMA_PERIOD = EMA_CONFIG['OPENEMA_PERIOD']
CLOSEEMA_PERIOD = EMA_CONFIG['CLOSEEMA_PERIOD']
EMA9_PERIOD = EMA_CONFIG['EMA9_PERIOD']
EMA20_PERIOD = EMA_CONFIG['EMA20_PERIOD']
EMA50_PERIOD = EMA_CONFIG['EMA50_PERIOD']
EMA104_PERIOD = EMA_CONFIG['EMA104_PERIOD']

# 策略窗口期参数 - 统一使用配置
SHORT_WINDOW = WINDOW_CONFIG['SHORT_WINDOW']
LONG_WINDOW = WINDOW_CONFIG['LONG_WINDOW']

class FeatureEngineer:
    @staticmethod
    def calculate_rsi(prices, period=RSI_PERIOD):
        """计算 RSI 指标 - 优化版本"""
        delta = prices.diff(1)
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=period, min_periods=1).mean()
        avg_loss = loss.rolling(window=period, min_periods=1).mean()
        
        # 避免除零错误
        rs = np.where(avg_loss != 0, avg_gain / avg_loss, 0)
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def calculate_ema(prices, period):
        """计算指数移动平均线 (EMA)"""
        return prices.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def calculate_sma(prices, period):
        """计算简单移动平均线 (SMA)"""
        return prices.rolling(window=period, min_periods=1).mean()
    
    @staticmethod
    def calculate_wma(prices, period):
        """计算加权移动平均线 (WMA) - 优化版本"""
        if len(prices) < period:
            return pd.Series([np.nan] * len(prices), index=prices.index)
        
        # 使用向量化操作提高性能
        weights = np.arange(1, period + 1)
        weights_sum = weights.sum()
        
        # 预计算权重数组
        weight_array = np.tile(weights, (len(prices), 1))
        
        # 使用rolling window的向量化操作
        def wma_func(x):
            return np.dot(x, weights) / weights_sum
        
        return prices.rolling(window=period).apply(wma_func, raw=True)
    
    @staticmethod
    def calculate_macd(prices, fast=12, slow=26, signal=9):
        """计算MACD指标"""
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        return macd_line, signal_line, macd_line - signal_line
    
    @staticmethod
    def calculate_bollinger_bands(prices, period=10, std_dev=2):
        """计算布林带 - 优化版本"""
        sma = prices.rolling(window=period, min_periods=1).mean()
        std = prices.rolling(window=period, min_periods=1).std()
        return sma + (std * std_dev), sma, sma - (std * std_dev)
    
    @staticmethod
    def calculate_atr(high, low, close, period=14):
        """计算ATR（平均真实波动幅度） - 优化版本"""
        tr = pd.concat([high - low, abs(high - close.shift(1)), abs(low - close.shift(1))], axis=1).max(axis=1)
        return tr.rolling(window=period, min_periods=1).mean()
    
    @staticmethod
    def calculate_sharpe_ratio(returns, risk_free_rate=0.02, window=30):
        """计算夏普比率"""
        try:
            period_risk_free_rate = risk_free_rate / (365 * 24)
            excess_returns = returns - period_risk_free_rate
            rolling_std = returns.rolling(window=window, min_periods=1).std()
            
            # 避免除以零，当标准差为0时返回0
            sharpe_ratio = excess_returns.rolling(window=window, min_periods=1).mean() / (rolling_std + 1e-8)
            
            # 处理NaN值
            sharpe_ratio = sharpe_ratio.fillna(0.0)
            
            return sharpe_ratio
        except Exception as e:
            print(f"夏普比率计算错误: {e}")
            # 返回默认值
            return pd.Series(0.0, index=returns.index)
    
    @staticmethod
    def calculate_max_drawdown(prices, window=30):
        """计算最大回撤"""
        rolling_max = prices.rolling(window=window).max()
        drawdown = (prices - rolling_max) / rolling_max
        return drawdown.rolling(window=window).min()
    
    @staticmethod
    def calculate_drawdown_duration(prices, window=30):
        """计算回撤持续时间"""
        rolling_max = prices.rolling(window=window).max()
        is_drawdown = prices < rolling_max
        # 计算连续回撤的持续时间
        duration = pd.Series(index=prices.index, dtype=float)
        current_duration = 0
        
        for i in range(len(prices)):
            if is_drawdown.iloc[i]:
                current_duration += 1
            else:
                current_duration = 0
            duration.iloc[i] = current_duration
        return duration
    
    @staticmethod
    def calculate_obv_data(obv, window=20):
        """增强版OBV趋势评分系统 - 返回信号、震荡评分、趋势评分 (-1至1分区间)
        
        Args:
            obv: OBV序列 (pd.Series)
            window: 计算窗口期 (至少为2)
            
        Returns:
            tuple: (信号, 震荡评分, 趋势评分)
                信号: 1(多头)/-1(空头)/0(中性)
                评分范围: -1到1
        """
        try:
            # 输入验证
            if len(obv) < max(window, 2) or window < 2:
                return (
                    pd.Series(0, index=obv.index), 
                    pd.Series(0, index=obv.index), 
                    pd.Series(0, index=obv.index)
                )
            
            # 1. 计算OBV趋势斜率 (更稳健的方法)
            def safe_slope(x):
                if len(x) < 2:
                    return 0
                return np.polyfit(range(len(x)), x, 1)[0]
            
            obv_slope = obv.rolling(window=window).apply(safe_slope, raw=True).fillna(0)
            
            # 2. 计算OBV相对强度和波动率
            obv_mean = obv.rolling(window).mean().replace(0, 1e-6)  # 防止除零
            obv_relative = (obv / obv_mean).fillna(1)
            obv_volatility = (obv.rolling(window).std() / obv_mean).fillna(0)
            
            # 3. 趋势强度计算 (使用Z-score标准化)
            slope_mean = obv_slope.rolling(window).mean()
            slope_std = obv_slope.rolling(window).std().replace(0, 1e-6)
            obv_zscore = (obv_slope - slope_mean) / slope_std
            trend_strength = np.clip(obv_zscore, -3, 3) / 3  # 归一化到[-1,1]
            
            # 4. 信号生成
            signal = np.where(
                np.abs(trend_strength) > 0.3,  # 强度阈值
                np.sign(trend_strength),
                0
            )
            
            # 5. 震荡评分 (0-1范围)
            volatility_factor = np.clip(obv_volatility, 0, 1)
            sideways_score = (1 - np.abs(trend_strength)) * volatility_factor
            
            # 6. 趋势评分 (-1到1范围)
            trend_score = trend_strength * (1 - sideways_score)  # 震荡时减弱趋势评分
            
            # 7. 平滑处理
            smooth_window = max(3, window // 3)
            signal = pd.Series(signal, index=obv.index).rolling(smooth_window).mean().fillna(0)
            sideways_score = pd.Series(sideways_score, index=obv.index).rolling(smooth_window).mean().fillna(0)
            trend_score = pd.Series(trend_score, index=obv.index).rolling(smooth_window).mean().fillna(0)
            
            return signal, sideways_score, trend_score
            
        except Exception as e:
            print(f"OBV评分计算错误: {str(e)}")
            # 返回默认值并保持相同索引
            default_series = pd.Series(0, index=obv.index)
            return default_series, default_series, default_series
    @staticmethod
    def calculate_macd_data(macd_line, signal_line, histogram, close):
        """MACD综合评分系统（返回信号、震荡评分、趋势评分）
        
        Args:
            macd_line (pd.Series): MACD主线
            signal_line (pd.Series): MACD信号线
            histogram (pd.Series): MACD柱状图
            close (pd.Series): 收盘价
            
        Returns:
            tuple: (信号, 震荡评分, 趋势评分)
                - 信号: -1到1，正值表示多头信号，负值表示空头信号
                - 震荡评分: 0到1，表示震荡强度
                - 趋势评分: -1到1，正值表示多头趋势强度，负值表示空头趋势强度
        """
        # 标准化因子
        norm_factor = close.std() * 0.05
        
        # 1. 计算MACD方向信号 (-1到1)
        # MACD主线与信号线的位置关系
        macd_position = np.where(macd_line > signal_line, 1, -1)
        
        # MACD主线斜率（趋势方向）
        macd_slope = macd_line.diff(3).fillna(0)
        slope_direction = np.where(macd_slope > 0, 1, -1)
        
        # 柱状图方向
        hist_direction = np.where(histogram > 0, 1, -1)
        
        # 综合方向信号
        direction_signal = (macd_position + slope_direction + hist_direction) / 3
        
        # 2. 计算趋势强度 (0-1)
        # MACD主线强度
        line_strength = np.abs(np.tanh(macd_line / norm_factor))
        
        # 主线与信号线分离度
        separation = np.abs(macd_line - signal_line) / norm_factor
        separation_strength = np.tanh(separation)
        
        # 柱状图强度
        hist_strength = np.abs(np.tanh(histogram / (norm_factor * 0.3)))
        
        # 趋势强度综合评分 (0-1)
        trend_strength = (line_strength * 0.4 + separation_strength * 0.4 + hist_strength * 0.2)
        
        # 3. 计算震荡强度 (0-1)
        # MACD主线接近零轴（震荡特征）
        near_zero = 1 - np.abs(np.tanh(macd_line / (norm_factor * 0.5)))
        
        # 主线与信号线接近（震荡特征）
        lines_close = 1 - np.tanh(separation)
        
        # 柱状图接近零轴（震荡特征）
        hist_near_zero = 1 - np.abs(np.tanh(histogram / (norm_factor * 0.2)))
        
        # 震荡强度综合评分
        sideways_strength = (near_zero * 0.4 + lines_close * 0.4 + hist_near_zero * 0.2)
        
        # 4. 交叉信号增强
        # 金叉信号
        golden_cross = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
        # 死叉信号
        death_cross = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))
        
        # 计算延续天数
        consecutive_days = pd.Series(0, index=close.index)
        current_streak = 0
        
        for i in range(1, len(close)):
            if (macd_line[i] > signal_line[i]) == (macd_line[i-1] > signal_line[i-1]):
                current_streak += 1
            else:
                current_streak = 0
            consecutive_days[i] = current_streak
        
        # 交叉后的延续增强
        cross_enhancement = 0.1 * np.minimum(consecutive_days.where(golden_cross | death_cross, 0), 5) / 5
        
        # 5. 最终信号计算
        # 基础方向信号
        base_signal = direction_signal * trend_strength
        
        # 交叉增强
        cross_signal = np.where(golden_cross, cross_enhancement, 
                               np.where(death_cross, -cross_enhancement, 0))
        
        # 最终信号
        final_signal = np.clip(base_signal + cross_signal, -1, 1)
        
        # 6. 计算有方向的趋势评分 (-1到1)
        # 多头趋势强度
        bullish_trend = np.where(
            (macd_line > signal_line) & (macd_line > 0),  # 主线在信号线上方且为正
            trend_strength,  # 返回正值趋势强度
            0
        )
        
        # 空头趋势强度
        bearish_trend = np.where(
            (macd_line < signal_line) & (macd_line < 0),  # 主线在信号线下方且为负
            trend_strength,  # 返回正值趋势强度
            0
        )
        
        # 有方向的趋势评分
        directional_trend = bullish_trend - bearish_trend
        
        # 7. 调整震荡评分
        # 当有强信号时，降低震荡评分
        signal_strength = np.abs(final_signal)
        adjusted_sideways = sideways_strength * (1 - signal_strength * 0.5)
        
        return final_signal, adjusted_sideways, directional_trend

   
    
    def calculate_adx_data(self, adx, plus_di, minus_di):
        """整合版ADX评分系统（返回信号、震荡评分、趋势评分）
        
        整合了ADX趋势强度、DI方向判断和动态权重调整，提供完整的ADX分析。
        
        Args:
            adx (pd.Series): 平均趋向指数（趋势强度）
            plus_di (pd.Series): 正向指示器（看涨动量）
            minus_di (pd.Series): 负向指示器（看跌动量）
            
        Returns:
            tuple: (信号, 震荡评分, 趋势评分)
                - 信号: -1到1，正值表示多头信号，负值表示空头信号
                - 震荡评分: 0到1，表示震荡强度
                - 趋势评分: 0到1，表示趋势强度
        """
        # 输入验证
        if not all(len(x) == len(adx) for x in [plus_di, minus_di]):
            raise ValueError("所有输入序列长度必须相同")
        
        # 1. 计算ADX趋势强度得分 (0-1)
        def _adx_strength_score(adx_value):
            """ADX值转换为趋势强度评分（0-1）"""
            if pd.isna(adx_value):
                return 0
            if adx_value < 20:
                return 0.3 * (adx_value / 20)          # 无趋势阶段：0-0.3分
            elif adx_value < 25:
                return 0.3 + 0.2 * ((adx_value - 20)/5)  # 弱趋势：0.3-0.5分
            elif adx_value < 40:
                return 0.5 + 0.3 * ((adx_value - 25)/15) # 中等趋势：0.5-0.8分
            else:
                return 0.8 + 0.2 * ((min(adx_value, 50) - 40)/10) # 强趋势：0.8-1.0分
        
        adx_strength = adx.apply(_adx_strength_score)
        
        # 2. 计算DI方向得分 (-1到1)
        def _di_direction_score(plus_di_val, minus_di_val):
            """DI差值转换为方向评分（-1到+1）"""
            if pd.isna(plus_di_val) or pd.isna(minus_di_val):
                return 0
            di_diff = plus_di_val - minus_di_val
            # 归一化到-1到1范围
            normalized_diff = np.clip(di_diff / 50, -1, 1)  # 假设最大差值为50
            return normalized_diff
        
        di_direction = np.array([_di_direction_score(pd, md) for pd, md in zip(plus_di, minus_di)])
        
        # 3. 计算震荡评分 (0-1)
        # ADX < 20时，市场处于震荡状态
        sideways_score = np.where(
            adx < 20,  # 无趋势阶段
            0.8 - 0.3 * (adx / 20),  # ADX越低，震荡评分越高 (0.8-0.5)
            0.0  # 有趋势时，震荡评分为0
        )
        
        # 4. 计算趋势评分 (-1到1)
        # ADX >= 20时，市场处于趋势状态，结合DI方向
        trend_score = np.where(
            adx >= 20,  # 有趋势阶段
            di_direction,  # 直接使用DI方向，范围-1到1
            0.0  # 无趋势时，趋势评分为0
        )
        
        # 5. 计算综合信号 (-1到1)
        # 结合DI方向和趋势强度
        signal = np.where(
            adx < 20,  # 无趋势阶段
            di_direction * 0.3,  # 震荡时信号强度降低
            di_direction * adx_strength  # 有趋势时，方向与强度相乘
        )
        
        # 转换为pandas Series并返回
        signal_series = pd.Series(signal, index=adx.index)
        sideways_series = pd.Series(sideways_score, index=adx.index)
        trend_series = pd.Series(trend_score, index=adx.index)
        
        return signal_series, sideways_series, trend_series
    
#===============================================指标趋势评分===============================================
    @staticmethod
    def calculate_volatility(returns, window=30):
        """计算波动率"""
        return returns.rolling(window=window).std() * np.sqrt(252)  # 年化波动率
    @staticmethod
    def calculate_volume_obv(volume, price):
        """
        计算能量潮指标 (On-Balance Volume, OBV)
        
        Args:
            volume: 交易量序列
            price: 价格序列
            
        Returns:
            Series: OBV值
        """
        try:
            # 确保输入是pandas Series
            if not isinstance(volume, pd.Series):
                volume = pd.Series(volume)
            if not isinstance(price, pd.Series):
                price = pd.Series(price)
            
            # 向量化计算OBV
            price_change = price.diff()
            
            # 使用numpy的where进行向量化条件判断
            volume_change = np.where(price_change > 0, volume, 
                                   np.where(price_change < 0, -volume, 0))
            
            # 计算累积和
            obv = pd.Series(volume_change, index=volume.index).cumsum()
            
            # 处理NaN值
            obv = obv.fillna(0)
            
            return obv
        except Exception as e:
            print(f"OBV计算错误: {e}")
            # 返回默认值
            return pd.Series(0, index=volume.index)
    
    @staticmethod
    def calculate_adx(high, low, close, period=14):
        """
        计算平均方向指数 (Average Directional Index, ADX)
        
        Args:
            high: 最高价序列
            low: 最低价序列
            close: 收盘价序列
            period: 计算周期
            
        Returns:
            tuple: (ADX, +DI, -DI)
        """
        # 计算真实波幅 (True Range)
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # 计算方向移动 (Directional Movement) - 向量化优化
        high_diff = high.diff()
        low_diff = -low.diff()
        
        # 使用numpy的where进行向量化条件判断
        dm_plus = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
        dm_minus = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)
        
        # 计算平滑值 - 使用pandas的ewm提高性能
        tr_smooth = pd.Series(tr, index=high.index).ewm(span=period, adjust=False).mean()
        dm_plus_smooth = pd.Series(dm_plus, index=high.index).ewm(span=period, adjust=False).mean()
        dm_minus_smooth = pd.Series(dm_minus, index=high.index).ewm(span=period, adjust=False).mean()
        
        # 计算方向指标 (+DI, -DI) - 避免除零错误
        di_plus = np.where(tr_smooth != 0, 100 * (dm_plus_smooth / tr_smooth), 0)
        di_minus = np.where(tr_smooth != 0, 100 * (dm_minus_smooth / tr_smooth), 0)
        
        # 计算方向指数 (DX) - 避免除零错误
        denominator = di_plus + di_minus
        dx = np.where(denominator != 0, 100 * np.abs(di_plus - di_minus) / denominator, 0)
        
        # 计算平均方向指数 (ADX) - 使用ewm提高性能
        adx = pd.Series(dx, index=high.index).ewm(span=period, adjust=False).mean()
        
        return adx, di_plus, di_minus
    
     
    @staticmethod
    def calculate_ema_data(close: pd.Series,minEMA: pd.Series, midEMA: pd.Series, maxEMA: pd.Series,window: int = 20) -> tuple:
        """
        增强版EMA趋势评分系统 - 返回信号、震荡评分、趋势评分
        
        参数:
            close: 收盘价
            minEMA/midEMA/maxEMA: 短/中/长周期EMA
            window: 分析窗口(默认20)
        
        返回: 
            (信号, 震荡评分, 趋势评分) - 信号: 1(多头)/-1(空头)/0(中性), 评分范围从-1到1
        """
        
        # 1. 计算斜率 (简化版线性回归)
        def _slope(s):
            return s.rolling(window).apply(
                lambda x: linregress(np.arange(len(x)), x)[0] if len(x) == window else np.nan
            )
        
        slope_min, slope_mid = _slope(minEMA), _slope(midEMA)

        # 2. 趋势排列检测 (保留5‰容差)
        trend_direction = np.select(
            [
                (minEMA > midEMA) & (midEMA > maxEMA * 0.995),  # 多头
                (minEMA < midEMA) & (midEMA < maxEMA * 1.005)   # 空头
            ],
            [1, -1],  # 1:多头, -1:空头
            default=0  # 0:无趋势
        )

        # 3. 价格位置分析
        price_position = np.where(
            (close > minEMA) & (close > midEMA), 1,  # 多头
            np.where(
                (close < minEMA) & (close < midEMA), -1,  # 空头
                0  # 中性
            )
        )

        # 4. 均线离散度 (简化计算)
        avg_dist = (abs(minEMA-midEMA)/midEMA + abs(midEMA-maxEMA)/maxEMA) / 2
        is_divergent = avg_dist > 0.005  # 0.5%作为发散阈值

        # 5. 趋势评分 (满足2/3条件，区分多空方向)
        trend_cond = (
            (trend_direction != 0).astype(int) +      # 趋势排列
            (price_position == trend_direction) +     # 价格同向
            (is_divergent.astype(int))                # 均线发散
        )
        
        # 基础趋势强度 (0-1范围)
        base_trend_strength = (trend_cond >= 2).astype(float) * (0.6 + 0.4 * np.clip(avg_dist/0.01, 0, 1))
        
        # 根据趋势方向调整评分 (-1到1范围)
        trend_score = np.where(
            trend_direction == 1,  # 多头趋势
            base_trend_strength,   # 返回正值 (0-1)
            np.where(
                trend_direction == -1,  # 空头趋势
                -base_trend_strength,   # 返回负值 (-1-0)
                0  # 无趋势
            )
        )

        # 6. 震荡评分 (放宽条件，提高灵敏度)
        # 条件1: 趋势方向不明确 (放宽到趋势强度较弱)
        weak_trend = (trend_direction == 0) | (abs(trend_score) < 0.3)
        
        # 条件2: 均线收敛 (放宽到0.5%)
        ma_convergence = avg_dist < 0.005
        
        # 条件3: 价格在均线附近 (放宽到价格接近均线)
        price_near_ma = (abs(close - midEMA) / midEMA) < 0.02  # 价格偏离中均线不超过2%
        
        # 综合震荡评分
        sideways_score = (
            weak_trend.astype(float) * 0.4 +
            ma_convergence.astype(float) * 0.4 +
            price_near_ma.astype(float) * 0.2
        ) * 0.8

        # 7. 生成交易信号
        # 信号生成逻辑：基于趋势强度和震荡评分
        signal = np.where(
            (trend_score > 0.3) & (sideways_score < 0.3), 1,    # 多头信号：趋势强且震荡弱
            np.where(
                (trend_score < -0.3) & (sideways_score < 0.3), -1,  # 空头信号：趋势强且震荡弱
                0  # 中性信号：震荡或趋势不明确
            )
        )

        # 8. 简单平滑处理
        smooth = lambda s: pd.Series(s, index=close.index).rolling(max(3, window//3)).mean().fillna(0)
        final_signal = pd.Series(signal, index=close.index)
        final_sideways, final_trend = smooth(sideways_score), smooth(trend_score)
        
        return final_signal, final_sideways, final_trend

    @staticmethod
    def calculate_bollinger_data(close, bb_upper, bb_middle, bb_lower, window=20, smoothing=True):
        """
        增强版布林带趋势强度评分 - 返回信号、震荡评分、趋势评分 (-1至1分区间)
        
        Args:
            close: 收盘价序列 (pd.Series)
            bb_upper: 布林带上轨 (pd.Series)
            bb_middle: 布林带中轨 (pd.Series)
            bb_lower: 布林带下轨 (pd.Series)
            window: 计算窗口期 (int)
            smoothing: 是否启用平滑处理 (bool)
            
        Returns:
            tuple: (信号, 震荡评分, 趋势评分) 三个pd.Series
                - 信号: 1(多头)/-1(空头)/0(中性)
                - 震荡评分: 0-1分
                - 趋势评分: -1到1分
        """
        # 输入校验
        if not all(len(x) == len(close) for x in [bb_upper, bb_middle, bb_lower]):
            raise ValueError("All input series must have same length")
        
        # 1. 计算核心指标 ---------------------------------------------------
        bb_position = (close - bb_lower) / (bb_upper - bb_lower).replace(0, 1e-10)
        bb_width = (bb_upper - bb_lower) / bb_middle.replace(0, 1e-10)
        price_middle_dist = abs(close - bb_middle) / bb_middle.replace(0, 1e-10)
        
        # 2. 震荡/趋势特征识别 -----------------------------------------------
        # 震荡特征 (0-1分)
        near_middle = (price_middle_dist < 0.02).astype(float)  # 价格接近中轨(2%)
        moderate_width = ((bb_width > 0.03) & (bb_width < 0.08)).astype(float)  # 适中宽度(3%-8%)
        sideways_score = near_middle * moderate_width
        
        # 趋势特征 (0-1分) - 区分多空方向
        near_upper = (bb_position > 0.85).astype(float)  # 价格接近上轨(85%以上)
        near_lower = (bb_position < 0.15).astype(float)  # 价格接近下轨(15%以下)
        wide_bands = (bb_width > 0.03).astype(float)  # 布林带较宽(降低到>3%)
        
        # 多头趋势特征
        bullish_trend = near_upper * wide_bands
        # 空头趋势特征
        bearish_trend = near_lower * wide_bands
        
        # 3. 动态加权调整 ---------------------------------------------------
        # 基于波动率的动态调整 (布林带宽度越宽，趋势特征权重越高)
        width_factor = np.clip(bb_width / 0.05, 0.5, 2.0)
        sideways_score = sideways_score * (1.5 - width_factor/2)
        bullish_trend = bullish_trend * width_factor
        bearish_trend = bearish_trend * width_factor
        
        # 4. 价格斜率增强 (趋势持续性的辅助判断) ------------------------------
        if len(close) > window:
            price_slope = close.rolling(window).apply(
                lambda x: np.polyfit(range(len(x)), x, 1)[0], raw=False)
            # 处理标准差，避免除零错误
            slope_std = price_slope.std()
            if slope_std == 0:
                slope_std = 1e-10
            slope_factor = np.abs(price_slope) / slope_std
            
            # 根据斜率方向调整趋势强度
            bullish_trend = bullish_trend * np.where(price_slope > 0, np.clip(1 + slope_factor, 1, 2), 1)
            bearish_trend = bearish_trend * np.where(price_slope < 0, np.clip(1 + slope_factor, 1, 2), 1)
        
        # 5. 平滑处理 ------------------------------------------------------
        if smoothing:
            sideways_score = sideways_score.rolling(window, min_periods=1).mean()
            bullish_trend = bullish_trend.rolling(window, min_periods=1).mean()
            bearish_trend = bearish_trend.rolling(window, min_periods=1).mean()
        
        # 6. 合并多空趋势为单一趋势评分 (-1到1范围)
        trend_score = bullish_trend - bearish_trend
        
        # 7. 生成交易信号 ---------------------------------------------------
        # 信号生成逻辑：基于趋势强度和震荡评分
        signal = np.where(
            (trend_score > 0.3) & (sideways_score < 0.3), 1,    # 多头信号：趋势强且震荡弱
            np.where(
                (trend_score < -0.3) & (sideways_score < 0.3), -1,  # 空头信号：趋势强且震荡弱
                0  # 中性信号：震荡或趋势不明确
            )
        )
        
        # 8. 归一化处理 (确保震荡评分在0-1范围，趋势评分在-1到1范围)
        # 震荡评分保持不变 (0-1)
        # 趋势评分已经通过多空相减得到 (-1到1)
        
        return pd.Series(signal, index=close.index), sideways_score, trend_score
     
    
    @staticmethod
    def calculate_volume_vwap(volume, price, window=20):
        """
        计算成交量加权平均价格 (Volume Weighted Average Price, VWAP)
        
        Args:
            volume: 交易量序列
            price: 价格序列
            window: 计算窗口期
            
        Returns:
            Series: VWAP值
        """
        typical_price = price  # 使用收盘价作为典型价格
        vwap = (typical_price * volume).rolling(window=window).sum() / volume.rolling(window=window).sum()
        return vwap
    
    @staticmethod
    def calculate_bull_bear_status(prices, wma_line):
        """
        计算牛熊分界线状态
        
        Args:
            prices: 价格序列
            wma_line: WMA线序列
            
        Returns:
            Series: 1表示牛市(价格>WMA)，-1表示熊市(价格<WMA)
        """
        return np.where(prices > wma_line, 1, -1)
    
   
    @staticmethod
    def calculate_atr_data(atr, window=None, close_prices=None, trend_confirmation=False):
        """
        增强版ATR趋势强度评分（-1至1分区间）
        
        Args:
            atr: ATR序列
            window: 计算窗口期（默认自适应）
            close_prices: 价格序列（用于趋势确认）
            trend_confirmation: 是否启用趋势方向确认
            
        Returns:
            tuple: (信号, 震荡评分, 趋势评分)
                - 信号: 1(多头), -1(空头), 0(中性)
                - 震荡评分: 0-1分，表示震荡强度
                - 趋势评分: -1到1分，正值表示多头趋势，负值表示空头趋势
        """
        # 输入校验
        if len(atr) < 2:
            return pd.Series(0, index=atr.index), pd.Series(0, index=atr.index), pd.Series(0, index=atr.index)
        
        # 动态窗口设置
        if window is None:
            window = max(5, len(atr) // 10)  # 自适应窗口
        
        # 1. 计算ATR变化率和趋势方向
        atr_change = atr.pct_change()
        atr_ma_short = atr.rolling(max(3, window//3)).mean()
        atr_ma_long = atr.rolling(window).mean()
        
        # 2. 趋势信号判断
        if close_prices is not None:
            price_trend = np.sign(close_prices.diff(window))
            # 结合价格趋势和ATR变化判断方向
            trend_signal = np.where(
                (atr_change > 0) & (price_trend > 0), 1,  # 多头：ATR上升且价格上涨
                np.where(
                    (atr_change > 0) & (price_trend < 0), -1,  # 空头：ATR上升且价格下跌
                    0  # 中性
                )
            )
        else:
            # 仅基于ATR变化判断
            trend_signal = np.where(
                atr_change > 0, 1,  # ATR上升
                np.where(
                    atr_change < 0, -1,  # ATR下降
                    0  # ATR稳定
                )
            )
        
        # 3. 震荡评分计算 (0-1分)
        # 震荡特征：ATR相对稳定，变化率较小
        atr_stability = (1 - abs(atr_change)).clip(0, 1)  # ATR稳定性
        ma_convergence = (1 - abs(atr_ma_short - atr_ma_long) / (atr_ma_long + 1e-6)).clip(0, 1)  # 均线收敛度
        
        # 震荡评分 = ATR稳定性 * 均线收敛度
        sideways_score = atr_stability * ma_convergence
        
        # 4. 趋势评分计算 (-1到1分)
        # 动态阈值计算（基于历史波动水平）
        atr_median = atr.rolling(window*2).median()
        dynamic_threshold = atr_median * 0.05  # 基准阈值
        
        # 计算标准化波动强度
        normalized_strength = abs(atr_change) / (dynamic_threshold + 1e-6)
        
        # 趋势方向确认（可选）
        if trend_confirmation and close_prices is not None:
            price_trend = np.sign(close_prices.diff(window))
            # 趋势同向时增强评分，反向时减弱
            trend_factor = np.where(
                atr.diff() * price_trend > 0, 
                1.2,  # 波动扩大且趋势同向
                0.8    # 波动与趋势反向
            )
            normalized_strength *= trend_factor
        
        # 非线性转换（S型曲线）
        trend_strength = np.tanh(normalized_strength * 0.5)  # 0-1范围
        
        # 根据趋势方向调整评分
        trend_score = np.where(
            trend_signal == 1,  # 多头趋势
            trend_strength,     # 返回正值
            np.where(
                trend_signal == -1,  # 空头趋势
                -trend_strength,     # 返回负值
                0  # 中性
            )
        )
        
        # 5. 平滑处理
        smooth_window = max(3, window//3)
        final_signal = pd.Series(trend_signal, index=atr.index).rolling(smooth_window, min_periods=1).apply(
            lambda x: np.round(x.mean())  # 取最接近的整数
        )
        final_sideways = sideways_score.rolling(smooth_window, min_periods=1).mean()
        final_trend = pd.Series(trend_score, index=atr.index).rolling(smooth_window, min_periods=1).mean()
        
        return final_signal, final_sideways, final_trend
    
    @staticmethod
    def calculate_volume_data(volume, window=None, price_series=None, volatility_adjusted=False):
        """
        增强版成交量趋势强度评分（-1至1分区间）
        
        Args:
            volume: 成交量序列
            window: 计算窗口期（默认自适应）
            price_series: 价格序列（用于量价确认）
            volatility_adjusted: 是否进行波动率调整
            
        Returns:
            tuple: (信号, 震荡评分, 趋势评分)
                - 信号: 1(多头), -1(空头), 0(中性)
                - 震荡评分: 0-1分，表示震荡强度
                - 趋势评分: -1到1分，正值表示多头趋势，负值表示空头趋势
        """
        # 输入校验
        if len(volume) < 2:
            return pd.Series(0, index=volume.index), pd.Series(0, index=volume.index), pd.Series(0, index=volume.index)
        
        # 动态窗口设置
        if window is None:
            window = max(5, len(volume) // 10)  # 自适应窗口
        
        # 1. 计算动态基准（EMA+标准差通道）
        volume_ema = volume.ewm(span=window).mean()
        volume_std = volume.ewm(span=window).std()
        
        # 动态倍数上限（3倍或2.5个标准差）
        upper_bound = np.minimum(volume_ema * 3, volume_ema + 2.5*volume_std)
        lower_bound = np.maximum(volume_ema * 0.3, volume_ema - 2.5*volume_std)  # 添加下界
        
        # 2. 计算标准化量能
        volume_ratio = (volume - volume_ema) / (upper_bound - volume_ema + 1e-6)
        volume_ratio = volume_ratio.clip(-1, 1)  # 限制在-1到1
        
        # 3. 趋势信号判断
        if price_series is not None:
            price_trend = np.sign(price_series.diff(window))
            # 量价同向时判断趋势方向
            trend_signal = np.where(
                (volume_ratio > 0.2) & (price_trend > 0), 1,  # 多头：放量上涨
                np.where(
                    (volume_ratio > 0.2) & (price_trend < 0), -1,  # 空头：放量下跌
                    np.where(
                        (volume_ratio < -0.2) & (price_trend < 0), -1,  # 空头：缩量下跌
                        np.where(
                            (volume_ratio < -0.2) & (price_trend > 0), 1,  # 多头：缩量上涨
                            0  # 中性
                        )
                    )
                )
            )
        else:
            # 仅基于成交量变化判断
            trend_signal = np.where(
                volume_ratio > 0.2, 1,  # 放量
                np.where(
                    volume_ratio < -0.2, -1,  # 缩量
                    0  # 正常量能
                )
            )
        
        # 4. 震荡评分计算 (0-1分)
        # 震荡特征：成交量相对稳定，变化幅度较小
        volume_stability = (1 - abs(volume_ratio)).clip(0, 1)  # 成交量稳定性
        volume_ma_short = volume.rolling(max(3, window//3)).mean()
        volume_ma_long = volume.rolling(window).mean()
        ma_convergence = (1 - abs(volume_ma_short - volume_ma_long) / (volume_ma_long + 1e-6)).clip(0, 1)  # 均线收敛度
        
        # 震荡评分 = 成交量稳定性 * 均线收敛度
        sideways_score = volume_stability * ma_convergence
        
        # 5. 趋势评分计算 (-1到1分)
        # 量价确认（增强版，支持多空方向）
        if price_series is not None:
            price_trend = np.sign(price_series.diff(window))
            # 量价同向时增强评分，反向时减弱评分
            volume_ratio *= (1 + 0.3 * price_trend)  # 增强量价确认的影响
            volume_ratio = volume_ratio.clip(-1, 1)  # 重新限制范围
        
        # 波动率调整（可选）
        if volatility_adjusted and price_series is not None:
            volatility = price_series.pct_change().rolling(window).std()
            adj_factor = 1 / (1 + volatility * 10)
            volume_ratio *= adj_factor
            volume_ratio = volume_ratio.clip(-1, 1)  # 重新限制范围
        
        # 趋势确认（二次平滑）
        short_term = volume_ratio.rolling(max(3, window//3)).mean()
        long_term = short_term.rolling(window).mean()
        
        # 根据趋势方向调整评分
        trend_score = np.where(
            trend_signal == 1,  # 多头趋势
            long_term.clip(0, 1),  # 返回正值
            np.where(
                trend_signal == -1,  # 空头趋势
                long_term.clip(-1, 0),  # 返回负值
                0  # 中性
            )
        )
        
        # 6. 平滑处理
        smooth_window = max(3, window//3)
        final_signal = pd.Series(trend_signal, index=volume.index).rolling(smooth_window, min_periods=1).apply(
            lambda x: np.round(x.mean())  # 取最接近的整数
        )
        final_sideways = sideways_score.rolling(smooth_window, min_periods=1).mean()
        final_trend = pd.Series(trend_score, index=volume.index).rolling(smooth_window, min_periods=1).mean()
        
        return final_signal, final_sideways, final_trend
    
    @staticmethod
    def calculate_rsi_data(rsi, window=None):
        """
        改进版RSI趋势强度评分系统（-1至1分区间）
        
        Args:
            rsi: RSI序列
            window: 计算窗口期
            
        Returns:
            tuple: (信号, 震荡评分, 趋势评分)
                - 信号: 1(多头), -1(空头), 0(中性)
                - 震荡评分: 0-1分，表示震荡强度
                - 趋势评分: -1到1分，正值表示多头趋势，负值表示空头趋势
        """
        # 参数设置
        if window is None:
            window_short, window_long = 3, 7
        else:
            window_short = max(3, window // 2)
            window_long = window
        
        # 1. 趋势方向判断
        rsi_ma_short = rsi.rolling(window_short).mean()
        rsi_ma_long = rsi.rolling(window_long).mean()
        
        # 趋势信号：1(多头), -1(空头), 0(中性)
        trend_signal = np.where(
            (rsi_ma_short > rsi_ma_long) & (rsi > 50), 1,  # 多头趋势
            np.where(
                (rsi_ma_short < rsi_ma_long) & (rsi < 50), -1,  # 空头趋势
                0  # 中性
            )
        )
        
        # 2. 震荡评分计算 (0-1分)
        # 震荡特征：RSI在40-60区间，短期和长期均线接近
        rsi_neutral = ((rsi >= 40) & (rsi <= 60)).astype(float)  # RSI中性区间
        ma_convergence = (1 - abs(rsi_ma_short - rsi_ma_long) / 10).clip(0, 1)  # 均线收敛度
        rsi_stability = (1 - abs(rsi.diff()) / 5).clip(0, 1)  # RSI稳定性
        
        # 震荡评分 = 中性位置 * 均线收敛 * RSI稳定性
        sideways_score = rsi_neutral * ma_convergence * rsi_stability
        
        # 3. 趋势评分计算 (-1到1分)
        # 趋势强度计算
        rsi_trend_strength = abs(rsi_ma_short - rsi_ma_long) / 10  # 归一化趋势强度
        
        # 位置权重
        rsi_position_weight = np.select(
            [rsi > 70, (rsi >= 60) & (rsi <= 70), (rsi >= 40) & (rsi <= 60), (rsi >= 30) & (rsi <= 40), rsi < 30],
            [1.0, 0.8, 0.5, 0.8, 1.0],  # 极值区域权重更高
            default=0.5
        )
        
        # 变化率权重
        rsi_change = rsi.diff()
        rsi_std = rsi_change.rolling(20).std()
        rsi_change_weight = np.tanh(abs(rsi_change)/(rsi_std + 1e-6))
        
        # 综合趋势强度
        trend_strength = rsi_trend_strength * rsi_position_weight * (0.7 + 0.3 * rsi_change_weight)
        
        # 根据趋势方向调整评分
        trend_score = np.where(
            trend_signal == 1,  # 多头趋势
            trend_strength,     # 返回正值
            np.where(
                trend_signal == -1,  # 空头趋势
                -trend_strength,     # 返回负值
                0  # 中性
            )
        )
        
        # 4. 平滑处理
        smooth_window = max(3, window_short)
        final_signal = pd.Series(trend_signal, index=rsi.index).rolling(smooth_window, min_periods=1).apply(
            lambda x: np.round(x.mean())  # 取最接近的整数
        )
        final_sideways = sideways_score.rolling(smooth_window, min_periods=1).mean().fillna(0)
        final_trend = pd.Series(trend_score, index=rsi.index).rolling(smooth_window, min_periods=1).mean().fillna(0)
        
        return final_signal, final_sideways, final_trend
    
    @staticmethod
    def calculate_ma_entanglement(close_price, line_wma, open_ema, close_ema, window=10):
        """
        计算均线纠缠指标，只返回距离相关信息
        
        Args:
            close_price: 收盘价序列
            line_wma: lineWMA序列
            open_ema: OPENEMA序列
            close_ema: CloseEMA序列
            window: 计算窗口期
            
        Returns:
            tuple: (价格与LineWMA距离百分比, 是否纠缠, 纠缠强度, 建议过滤)
        """
        # 计算价格与LineWMA的距离百分比
        price_wma_distance = abs(close_price - line_wma) / line_wma * 100
        
        # 计算EMA的最大值和最小值
        max_ema = pd.concat([open_ema, close_ema], axis=1).max(axis=1)
        min_ema = pd.concat([open_ema, close_ema], axis=1).min(axis=1)
        
        # 判断排列类型 - 修复Series布尔值错误
        # 使用标量比较，避免Series布尔值歧义
        try:
            # 获取最新的标量值进行比较
            current_price = float(close_price.iloc[-1]) if len(close_price) > 0 else 0.0
            current_max_ema = float(max_ema.iloc[-1]) if len(max_ema) > 0 else 0.0
            current_min_ema = float(min_ema.iloc[-1]) if len(min_ema) > 0 else 0.0
            current_line_wma = float(line_wma.iloc[-1]) if len(line_wma) > 0 else 0.0
            
            # 使用标量进行布尔比较
            perfect_bullish = (current_price > current_max_ema) and (current_max_ema > current_line_wma)
            perfect_bearish = (current_price < current_min_ema) and (current_min_ema < current_line_wma)
            
            # 只有完美排列才不被过滤
            is_entangled = not (perfect_bullish or perfect_bearish)
        except Exception as e:
            print(f"均线纠缠计算错误: {e}")
            is_entangled = True  # 出错时默认过滤
        
        # 纠缠强度（简化版本，只基于距离）
        entanglement_intensity = (1 - price_wma_distance / 10).clip(0, 1)  # 距离越小，强度越高
        
        # 建议过滤（非完美排列或距离过近）
        should_filter = is_entangled | (price_wma_distance < 0.2)  # 0.2%阈值
        
        return price_wma_distance, is_entangled, entanglement_intensity, should_filter

    def generate_features(self, klines, short_window=None, long_window=None, multi_tf_data=None, external_fear_greed=None, external_vix_fear=None):
        """
        给 K 线数据添加技术指标特征
        
        Args:
            klines: 主时间级别的K线数据
            short_window: 短期窗口（如果为None，使用环境变量SHORT_WINDOW）
            long_window: 长期窗口（如果为None，使用环境变量LONG_WINDOW）
            multi_tf_data: 多时间级别数据字典，用于计算真实的时间级别一致性
            external_fear_greed: 外部贪婪指数数据（可选）
            external_vix_fear: 外部VIX恐慌指数数据（可选）
        """
        # 使用环境变量中的默认窗口期
        if short_window is None:
            short_window = SHORT_WINDOW
        if long_window is None:
            long_window = LONG_WINDOW
        
        #周期窗口
        period_window=14
        period_window_min=5
            
        df = klines.copy()
        df['returns'] = df['close'].pct_change()
        
        # ================================================
        # 1. 基础技术指标计算
        # ================================================
        # 移动平均线
        df['lineWMA'] = self.calculate_wma(df['close'], LINEWMA_PERIOD)
        df['openEMA'] = self.calculate_ema(df['open'], OPENEMA_PERIOD)
        df['closeEMA'] = self.calculate_ema(df['close'], CLOSEEMA_PERIOD)
        df['ema9'] = self.calculate_ema(df['close'], EMA9_PERIOD)
        df['ema20'] = self.calculate_ema(df['close'], EMA20_PERIOD)
        df['ema50'] = self.calculate_ema(df['close'], EMA50_PERIOD)
        df['ema104'] = self.calculate_sma(df['close'], EMA104_PERIOD)

         
            
        # 振荡指标
        df['rsi'] = self.calculate_rsi(df['close'])
        df['macd'], df['macd_signal'], df['macd_histogram'] = self.calculate_macd(df['close'])
        
        # 波动指标
        df['atr'] = self.calculate_atr(df['high'], df['low'], df['close'])
        
        # 趋势指标
        if len(df) >= period_window:
            df['adx'], df['di_plus'], df['di_minus'] = self.calculate_adx(df['high'], df['low'], df['close'], period_window)
        else:
            df['adx'] = df['di_plus'] = df['di_minus'] = 0.0
        
        # 布林带
        df['bb_upper'], df['bb_middle'], df['bb_lower'] = self.calculate_bollinger_bands(df['close'])
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]
        df["bb_position"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

        df['volume_obv'] = self.calculate_volume_obv(df['volume'], df['close'])
        
        
          # ================================================
        # 2. 计算技术指标信号和评分
        # ================================================
        # 技术指标评分,基本判断方向,不考虑趋势
        if len(df) >= period_window:
            df['adx_signal'], df['adx_sideways_score'], df['adx_trend_score'] = self.calculate_adx_data(df['adx'], df['di_plus'], df['di_minus'])
            df['ema_signal'], df['ema_sideways_score'], df['ema_trend_score'] = self.calculate_ema_data(df['close'], df['ema20'],df['ema50'], df['ema104'],window=short_window)
            df['rsi_signal'], df['rsi_sideways_score'], df['rsi_trend_score'] = self.calculate_rsi_data(df['rsi'],window=period_window)
            df['macd_signal'], df['macd_sideways_score'], df['macd_trend_score'] = self.calculate_macd_data(df['macd'], df['macd_signal'], df['macd_histogram'], df['close'])
            df['price_signal'], df['price_sideways_score'], df['price_trend_score'] = FeatureEngineer.calculate_price_data(df, lookback=5)
            df['atr_signal'], df['atr_sideways_score'], df['atr_trend_score'] = self.calculate_atr_data(df['atr'], window=period_window, close_prices=df['close']) 
            df['volume_signal'], df['volume_sideways_score'], df['volume_trend_score'] = self.calculate_volume_data(df['volume'], window=20, price_series=df['close'])
            df['bb_signal'], df['bb_sideways_score'], df['bb_trend_score'] = FeatureEngineer.calculate_bollinger_data(df['close'], df['bb_upper'], df['bb_middle'], df['bb_lower'], window=20)
            df['obv_signal'], df['obv_sideways_score'], df['obv_trend_score'] = self.calculate_obv_data(df['volume_obv'], window=period_window)
        else:
            df['adx_signal'] = df['adx_sideways_score'] = df['adx_trend_score'] = 0.0
            df['ema_signal'] = df['ema_sideways_score'] = df['ema_trend_score'] = 0.0
            df['rsi_signal'] = df['rsi_sideways_score'] = df['rsi_trend_score'] = 0.0
            df['macd_signal'] = df['macd_sideways_score'] = df['macd_trend_score'] = 0.0
            df['price_signal'] = df['price_sideways_score'] = df['price_trend_score'] = 0.0
            df['atr_signal'] = df['atr_sideways_score'] = df['atr_trend_score'] = 0.0
            df['volume_signal'] = df['volume_sideways_score'] = df['volume_trend_score'] = 0.0
            df['bb_signal'] = df['bb_sideways_score'] = df['bb_trend_score'] = 0.0
            df['obv_signal'] = df['obv_sideways_score'] = df['obv_trend_score'] = 0.0
        

        # 计算信号评分
        weights = self.calculate_dynamic_weights(df, mode='dynamic')
        
        # 确保权重是有效的字典
        if weights is None or not isinstance(weights, dict):
            weights = {
                'adx': 0.1, 'ema': 0.1, 'macd': 0.1, 'price': 0.1, 'rsi': 0.1,
                'sentiment': 0.1, 'atr': 0.1, 'volume': 0.1, 'bb': 0.1, 'obv': 0.1
            }
        
        df['signal_score'] = (
            weights.get('adx', 0.0) * df.get('adx_signal', 0.0) +
            weights.get('ema', 0.0) * df.get('ema_signal', 0.0) +
            weights.get('macd', 0.0) * df.get('macd_signal', 0.0) +
            weights.get('price', 0.0) * df.get('price_signal', 0.0) +
            weights.get('rsi', 0.0) * df.get('rsi_signal', 0.0) +
            weights.get('sentiment', 0.0) * df.get('sentiment_signal', 0.0) +
            weights.get('atr', 0.0) * df.get('atr_signal', 0.0) +
            weights.get('volume', 0.0) * df.get('volume_signal', 0.0) +
            weights.get('bb', 0.0) * df.get('bb_signal', 0.0) +
            weights.get('obv', 0.0) * df.get('obv_signal', 0.0)
        )


        # ================================================
        # 9. 外部情绪指数
        # ================================================
        try:
            vix_fear_value = external_vix_fear.get('value', 20.0) if external_vix_fear else 20.0
            greed_score_value = external_fear_greed.get('value', 50.0) if external_fear_greed else 50.0
            sentiment_signal, sentiment_score = self.calculate_sentiment_data(vix_fear_value, greed_score_value, 0.4, 0.5)
            df['vix_fear'] = vix_fear_value
            df['greed_score'] = greed_score_value
            df['sentiment_signal'] = sentiment_signal
            df['sentiment_score'] = sentiment_score
            # 添加情感趋势评分，与情感信号保持一致，范围-1到1
            df['sentiment_trend_score'] = sentiment_score
        except Exception as e:
            df['vix_fear'] = 20.0
            df['greed_score'] = 50.0
            df['sentiment_signal'] = 0
            df['sentiment_score'] = 0.0
            df['sentiment_trend_score'] = 0.0
        
        df['trend_score'] = (
            df.get('adx_trend_score', 0.0) * weights.get('adx', 0.0) +
            df.get('ema_trend_score', 0.0) * weights.get('ema', 0.0) +
            df.get('rsi_trend_score', 0.0) * weights.get('rsi', 0.0) +
            df.get('macd_trend_score', 0.0) * weights.get('macd', 0.0) +
            df.get('price_trend_score', 0.0) * weights.get('price', 0.0) +
            df.get('atr_trend_score', 0.0) * weights.get('atr', 0.0) +
            df.get('volume_trend_score', 0.0) * weights.get('volume', 0.0) +
            df.get('bb_trend_score', 0.0) * weights.get('bb', 0.0) +
            df.get('obv_trend_score', 0.0) * weights.get('obv', 0.0) +
            df.get('sentiment_trend_score', 0.0) * weights.get('sentiment', 0.0)
        )
        
        
        df['sideways_score'] = (
            df['adx_sideways_score'] * weights.get('adx', 0.0) +
            df['ema_sideways_score'] * weights.get('ema', 0.0) +
            df['rsi_sideways_score'] * weights.get('rsi', 0.0) +
            df['macd_sideways_score'] * weights.get('macd', 0.0) +
            #df['price_sideways_score'] * weights.get('price', 0.0) +
            df['atr_sideways_score'] * weights.get('atr', 0.0) +
            df['volume_sideways_score'] * weights.get('volume', 0.0) +
            df['bb_sideways_score'] * weights.get('bb', 0.0) +
            df['obv_sideways_score'] * weights.get('obv', 0.0)
        )
            
        # ================================================
        # 4. 风险指标计算
        # ================================================
        # 短期风险指标
        if len(df) >= short_window:
            df[f"sharpe_ratio_{short_window}"] = self.calculate_sharpe_ratio(df["returns"], window=short_window)
            df[f"max_drawdown_{short_window}"] = self.calculate_max_drawdown(df["close"], window=short_window)
            df[f"drawdown_duration_{short_window}"] = self.calculate_drawdown_duration(df["close"], window=short_window)
            df["volatility"] = self.calculate_volatility(df["returns"], window=short_window)
        else:
            df[f"sharpe_ratio_{short_window}"] = df[f"max_drawdown_{short_window}"] = df[f"drawdown_duration_{short_window}"] = df["volatility"] = 0.0
        
        # 长期风险指标
        if len(df) >= long_window:
            df[f"sharpe_ratio_{long_window}"] = self.calculate_sharpe_ratio(df["returns"], window=long_window)
            df[f"max_drawdown_{long_window}"] = self.calculate_max_drawdown(df["close"], window=long_window)
        else:
            df[f"sharpe_ratio_{long_window}"] = df[f"max_drawdown_{long_window}"] = 0.0
        
        # 市场状态指标
        df['bull_bear_status'] = self.calculate_bull_bear_status(df['close'], df['lineWMA'])
        
       
       
        # ================================================
        # 5. 市场分析指标
        # ================================================
        # 均线纠缠分析
        if len(df) >= period_window:
            df['ma_entanglement_score'], df['is_ma_entangled'], df['ma_entanglement_intensity'], df['should_ma_filter'] = \
                self.calculate_ma_entanglement(df['close'], df['lineWMA'], df['openEMA'], df['closeEMA'], window=short_window)
        else:
            df['ma_entanglement_score'] = df['ma_entanglement_intensity'] = 0.0
            df['is_ma_entangled'] = df['should_ma_filter'] = False

        # ================================================
        # 11. 数据清理
        # ================================================
        original_length = len(df)
        key_columns = ['close', 'lineWMA', 'openEMA', 'closeEMA', 'rsi', 'macd', 'macd_signal']
        df = df.dropna(subset=key_columns)
        final_length = len(df)
        removed_count = original_length - final_length
        
        if removed_count > 0:
            print(f"特征工程中删除了 {removed_count} 条包含NaN的数据")
            print(f"  原始数据: {original_length} 条")
            print(f"  处理后数据: {final_length} 条")
            print(f"  数据保留率: {final_length/original_length*100:.1f}%")
        
        if len(df) == 0:
            print("警告：删除关键指标NaN后数据为空")
            return None
        
        # ================================================
        # 5. 基于sideways_score计算市场状态
        # ================================================
        try:
            sideways_columns = [col for col in df.columns if 'sideways_score' in col]
            if len(sideways_columns) > 0:
                # 计算综合震荡评分
                df['combined_sideways_score'] = df[sideways_columns].mean(axis=1)
                # 市场状态：2=强震荡，1=强趋势，0=混合
                df['market_regime'] = np.where(
                    df['combined_sideways_score'] >= 0.7, 2,  # 强震荡市场
                    np.where(df['combined_sideways_score'] <= 0.35, 1, 0)  # 强趋势市场，混合市场
                )
        except Exception as e:
            # 失败时降级为默认混合市场
            df['combined_sideways_score'] = 0.0
            df['market_regime'] = 0
        
        # 设置多时间级别数据标志
        df._multi_timeframe_data = None
        print("🕐 多时间级别数据将在回测过程中实时获取")
        
        return df
    
    

    @staticmethod
    def calculate_price_data(df, lookback=5, k=15, m=8, volatility_window=10):
        """
        增强版价格数据评分系统（信号+震荡/趋势评分）
        
        改进点：
        1. 增加自适应波动率阈值
        2. 改进量价背离检测逻辑
        3. 添加趋势持续性判断
        4. 优化极端行情处理
        
        参数:
        -----------
        df : pd.DataFrame
            包含OHLCV数据的DataFrame，需有列:
            ['open', 'high', 'low', 'close', 'volume']
        lookback : int, 可选
            背离检测的回看周期 (默认: 5)
        k : float, 可选
            价格偏离敏感度 (默认: 15)
        m : float, 可选
            成交量偏离敏感度 (默认: 8)
        volatility_window : int, 可选
            波动率计算窗口 (默认: 10)

        返回:
        --------
        tuple: (信号, 震荡评分, 趋势评分)
            - 信号: 1(买入), -1(卖出), 0(持有)
            - 震荡评分: 0-1分
            - 趋势评分: -1到1分
        """
        # ===== 1. 数据预处理 =====
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            raise ValueError(f"DataFrame需包含列: {required_cols}")
        
        df = df.copy()
        close = df['close']
        volume = df['volume']
        
        # ===== 2. 核心指标计算 =====
        # 多周期均线系统
        df['ma12'] = close.ewm(span=12, adjust=False).mean()
        df['ma24'] = close.ewm(span=24, adjust=False).mean()
        df['ma_vol24'] = volume.ewm(span=24, adjust=False).mean()
        
        # 动态波动率计算（带自适应阈值）
        returns = close.pct_change()
        df['volatility'] = returns.rolling(volatility_window).std()
        volatility_ratio = df['volatility'] / df['volatility'].rolling(50).mean()
        
        # 动量指标（改进版）
        df['price_momentum'] = close.pct_change(3) * np.log1p(volume)  # 量价复合动量
        df['volume_momentum'] = volume.pct_change(3)
        
        # ===== 3. 偏离度计算（抗除零处理） =====
        with np.errstate(divide='ignore', invalid='ignore'):
            price_dev = (close - df['ma24']) / df['ma24']
            vol_dev = (volume - df['ma_vol24']) / (df['ma_vol24'] + 1e-6)
        
        price_dev = price_dev.replace([np.inf, -np.inf], np.nan).fillna(0)
        vol_dev = vol_dev.replace([np.inf, -np.inf], np.nan).fillna(0)
        
        # ===== 4. 趋势评分增强版 =====
        # 趋势方向判定（三因素加权）
        trend_direction = (
            0.4 * np.sign(df['price_momentum']) +
            0.3 * np.where(close > df['ma24'], 1, -1) +
            0.3 * np.where(df['ma12'] > df['ma24'], 1, -1)
        )
        
        # 趋势强度计算（动态标准化）
        raw_strength = abs(price_dev) * np.log1p(abs(df['price_momentum'])*100)
        trend_strength = np.tanh(raw_strength / k)  # 使用tanh压缩到0-1
        
        # 综合趋势评分（保留方向）
        df['trend_score'] = trend_direction * trend_strength
        
        # ===== 5. 震荡评分增强版 =====
        # 多条件联合判断
        cond_volatility = (df['volatility'] < 0.015 * volatility_ratio).astype(float)
        cond_volume = ((volume / df['ma_vol24']).between(0.8, 1.2)).astype(float)
        cond_price_range = ((close.rolling(5).max() - close.rolling(5).min()) < 0.02 * close).astype(float)
        
        df['sideways_score'] = (cond_volatility * 0.4 + 
                            cond_volume * 0.3 + 
                            cond_price_range * 0.3)
        
        # ===== 6. 量价背离检测增强 =====
        # 价格极值点检测
        peak_condition = (close == close.rolling(lookback, center=True).max())
        trough_condition = (close == close.rolling(lookback, center=True).min())
        
        # 顶背离（价格新高+动量减弱）
        top_divergence = peak_condition & (df['price_momentum'] < df['price_momentum'].shift(lookback//2))
        # 底背离（价格新低+动量增强）
        bottom_divergence = trough_condition & (df['price_momentum'] > df['price_momentum'].shift(lookback//2))
        
        # 背离影响因子（动态调整）
        df['trend_score'] = np.where(top_divergence, 
                                df['trend_score'] * 0.6, 
                                np.where(bottom_divergence, 
                                        df['trend_score'] * 0.6, 
                                        df['trend_score']))
        
        # ===== 7. 信号生成逻辑 =====
        # 趋势确认条件
        uptrend = (df['trend_score'] > 0.25) & (df['sideways_score'] < 0.4)
        downtrend = (df['trend_score'] < -0.25) & (df['sideways_score'] < 0.4)
        
        # 过滤假突破（要求成交量配合）
        valid_buy = uptrend & (volume > df['ma_vol24'] * 0.9)
        valid_sell = downtrend & (volume > df['ma_vol24'] * 0.9)
        
        df['signal'] = np.select(
            [valid_buy, valid_sell],
            [1, -1],
            default=0
        )
        
        # ===== 8. 后处理 =====
        # 信号平滑（避免频繁切换）
        df['signal'] = df['signal'].rolling(3, center=True, min_periods=1).mean().round()
        
        # 极端波动市场禁用信号
        df.loc[volatility_ratio > 2, 'signal'] = 0
        
        return (
            df['signal'].astype(int), 
            df['sideways_score'].clip(0, 1), 
            df['trend_score'].clip(-1, 1)
        )
        
    @staticmethod
    def calculate_sentiment_data(vix_fear, greed_score, fear_level, greed_level):
        """
        增强版市场情绪评分系统 - 返回信号和评分 (-1至1分区间)
        
        Args:
            vix_fear: VIX恐慌指数 (外部API数据)
            greed_score: 贪婪指数 (外部API数据)
            fear_level: 恐慌程度 (0-1)
            greed_level: 贪婪程度 (0-1)
            
        Returns:
            tuple: (信号, 情绪评分) - 信号: 1(乐观)/-1(悲观)/0(中性), 评分范围从-1到1
        """
        # 确保输入是标量值
        try:
            vix_fear = float(vix_fear) if hasattr(vix_fear, '__iter__') else float(vix_fear)
            greed_score = float(greed_score) if hasattr(greed_score, '__iter__') else float(greed_score)
            fear_level = float(fear_level) if hasattr(fear_level, '__iter__') else float(fear_level)
            greed_level = float(greed_level) if hasattr(greed_level, '__iter__') else float(greed_level)
        except (ValueError, TypeError):
            # 如果转换失败，使用默认值
            vix_fear = 20.0
            greed_score = 50.0
            fear_level = 0.4
            greed_level = 0.5
        
        # 1. 贪婪指数评分 (-1到1)
        # 贪婪指数0-100，转换为-1到1
        greed_normalized = (greed_score - 50) / 50  # -1到1范围
        greed_normalized = max(-1, min(1, greed_normalized))  # 限制范围
        
        # 2. VIX恐慌指数评分 (-1到1，反向)
        # VIX越高越恐慌，所以用负值
        # 假设VIX正常范围10-50，极端情况可达80
        vix_normalized = -((vix_fear - 20) / 30)  # 20为中性值，50为高恐慌
        vix_normalized = max(-1, min(1, vix_normalized))  # 限制范围
        
        # 3. 综合情绪评分 (-1到1)
        # 贪婪指数权重60%，VIX权重40%
        sentiment_score = 0.6 * greed_normalized + 0.4 * vix_normalized
        
        # 4. 信号生成（确保返回标量-1/0/1）
        # 基于情绪评分生成交易信号
        if sentiment_score > 0.3:
            signal = 1
        elif sentiment_score < -0.3:
            signal = -1
        else:
            signal = 0
        # 确保评分在-1到1范围内
        sentiment_score = max(-1, min(1, sentiment_score))
        
        return int(signal), float(sentiment_score)
 
    def calculate_dynamic_weights(self, df: pd.DataFrame, mode: str = 'dynamic'):
        
        """
        根据市场状态动态计算技术指标权重
        
        参数:
        df: 包含价格数据的DataFrame，需要以下列:
            - 'open', 'high', 'low', 'close', 'volume'
            - 可选: 'sentiment' (情感分析分数)
        mode: 权重计算模式，'dynamic'或'fixed'
        
        返回:
        包含各指标权重的字典
        """
        if mode == 'fixed':
            # 固定权重配置（先定义，再规范化为和为1）
            fixed_weights = {
                'adx': 0.14,
                'ema': 0.14,
                'macd': 0.14,
                'rsi': 0.14,
                'price': 0.09,
                'atr': 0.10,
                'volume': 0.10,
                'bb': 0.05,
                'obv': 0.05,
                'sentiment': 0.05,
            }
            total_fw = sum(fixed_weights.values())
            if total_fw > 0:
                fixed_weights = {k: v / total_fw for k, v in fixed_weights.items()}
            return fixed_weights
        
        # 动态权重计算
        weights = {}
        
        # 获取当前市场状态指标
        current_adx = df['adx'].iloc[-1] if 'adx' in df.columns else 25
        
        # 计算RSI
        if 'close' in df.columns:
            rsi_result = FeatureEngineer.calculate_rsi(df['close'])
            if hasattr(rsi_result, 'iloc'):
                current_rsi = rsi_result.iloc[-1]
            else:
                current_rsi = rsi_result[-1] if len(rsi_result) > 0 else 50
        else:
            current_rsi = 50
        
        # 计算成交量比率
        if 'volume' in df.columns and len(df) >= 20:
            volume_ma = df['volume'].rolling(window=20).mean()
            if not volume_ma.isna().iloc[-1]:
                current_volume_ratio = df['volume'].iloc[-1] / volume_ma.iloc[-1]
            else:
                current_volume_ratio = 1.0
        else:
            current_volume_ratio = 1.0
        
        # 计算波动率
        if 'close' in df.columns:
            returns = df['close'].pct_change().dropna()
            current_volatility = returns.rolling(window=20).std().iloc[-1] if len(returns) >= 20 else 0.02
        else:
            current_volatility = 0.02
        
        # 市场状态分析
        market_state = self._analyze_market_state(current_adx, current_rsi, current_volume_ratio, current_volatility)
        
        # 打印市场状态信息
        print(f"🔍 市场状态分析:")
        print(f" ADX: {current_adx:.1f} -> 趋势强度: {market_state['trend_strength']}")
        print(f" RSI: {current_rsi:.1f} -> 状态: {market_state['rsi_state']}")
        print(f" 成交量比率: {current_volume_ratio:.2f} -> 状态: {market_state['volume_state']}")
        print(f" 波动率: {current_volatility:.4f} -> 状态: {market_state['volatility_state']}")
        
        # 根据市场状态动态调整权重
        weights = self._adjust_weights_by_market_state(market_state, df)
        
        # 归一化权重
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        
        return weights
    
    def _analyze_market_state(self, adx, rsi, volume_ratio, volatility):
        """
        分析市场状态
        
        返回:
        市场状态字典
        """
        # ADX趋势强度分析
        if adx > 25:
            trend_strength = 'strong'
        elif adx > 20:
            trend_strength = 'moderate'
        else:
            trend_strength = 'weak'
        
        # RSI超买超卖分析
        if rsi > 70:
            rsi_state = 'overbought'
        elif rsi < 30:
            rsi_state = 'oversold'
        else:
            rsi_state = 'neutral'
        
        # 成交量分析
        if volume_ratio > 1.5:
            volume_state = 'high'
        elif volume_ratio < 0.7:
            volume_state = 'low'
        else:
            volume_state = 'normal'
        
        # 波动率分析
        if volatility > 0.03:  # 3%以上为高波动
            volatility_state = 'high'
        elif volatility < 0.01:  # 1%以下为低波动
            volatility_state = 'low'
        else:
            volatility_state = 'normal'
        
        return {
            'trend_strength': trend_strength,
            'rsi_state': rsi_state,
            'volume_state': volume_state,
            'volatility_state': volatility_state
        }
    
    def _adjust_weights_by_market_state(self, market_state, df):
        """
        根据市场状态调整权重
        
        参数:
        market_state: 市场状态字典
        df: 数据DataFrame
        
        返回:
        调整后的权重字典
        """
        weights = {}
        
        # 基础权重配置（定义为直觉比例，后续统一归一化）
        base_weights = {
            'adx': 0.14,
            'ema': 0.14,
            'macd': 0.14,
            'rsi': 0.14,
            'price': 0.09,
            'atr': 0.10,
            'volume': 0.10,
            'bb': 0.05,
            'obv': 0.05,
            'sentiment': 0.05,
        }
        # 规范化 base_weights，使其默认和为1
        total_bw = sum(base_weights.values())
        if total_bw > 0:
            base_weights = {k: v / total_bw for k, v in base_weights.items()}
        
        # 根据趋势强度调整权重
        if market_state['trend_strength'] == 'strong':
            # 强趋势时，增加趋势指标权重
            weights['adx'] = base_weights['adx'] * 1.5
            weights['ema'] = base_weights['ema'] * 1.3
            weights['macd'] = base_weights['macd'] * 1.2
            weights['price'] = base_weights['price'] * 0.8  # 减少价格权重
            weights['rsi'] = base_weights['rsi'] * 0.7      # 减少RSI权重
            weights['bb'] = base_weights['bb'] * 0.6        # 减少布林带权重
        elif market_state['trend_strength'] == 'weak':
            # 弱趋势时，增加震荡指标权重
            weights['rsi'] = base_weights['rsi'] * 1.4
            weights['bb'] = base_weights['bb'] * 1.3
            weights['price'] = base_weights['price'] * 1.2
            weights['adx'] = base_weights['adx'] * 0.7      # 减少ADX权重
            weights['ema'] = base_weights['ema'] * 0.8      # 减少EMA权重
            weights['macd'] = base_weights['macd'] * 0.9    # 减少MACD权重
        else:
            # 中等趋势，使用基础权重
            weights.update(base_weights)
        
        # 根据RSI状态调整权重
        if market_state['rsi_state'] == 'overbought':
            weights['rsi'] = weights.get('rsi', base_weights['rsi']) * 1.3
            weights['bb'] = weights.get('bb', base_weights['bb']) * 1.2
        elif market_state['rsi_state'] == 'oversold':
            weights['rsi'] = weights.get('rsi', base_weights['rsi']) * 1.3
            weights['bb'] = weights.get('bb', base_weights['bb']) * 1.2
        
        # 根据成交量状态调整权重
        if market_state['volume_state'] == 'high':
            weights['volume'] = base_weights['volume'] * 1.4
            weights['obv'] = base_weights['obv'] * 1.3
            weights['price'] = weights.get('price', base_weights['price']) * 1.1
        elif market_state['volume_state'] == 'low':
            weights['volume'] = base_weights['volume'] * 0.6
            weights['obv'] = base_weights['obv'] * 0.7
            weights['price'] = weights.get('price', base_weights['price']) * 0.9
        else:
            weights['volume'] = weights.get('volume', base_weights['volume'])
            weights['obv'] = weights.get('obv', base_weights['obv'])
        
        # 根据波动率状态调整权重
        if market_state['volatility_state'] == 'high':
            weights['atr'] = base_weights['atr'] * 1.4
            weights['bb'] = weights.get('bb', base_weights['bb']) * 1.2
            weights['price'] = weights.get('price', base_weights['price']) * 0.8
        elif market_state['volatility_state'] == 'low':
            weights['atr'] = base_weights['atr'] * 0.6
            weights['price'] = weights.get('price', base_weights['price']) * 1.2
            weights['rsi'] = weights.get('rsi', base_weights['rsi']) * 1.1
        else:
            weights['atr'] = weights.get('atr', base_weights['atr'])
        
        # 确保所有指标都有权重
        for key in base_weights.keys():
            if key not in weights:
                weights[key] = base_weights[key]
        
        # 添加情感分析权重（如果有）
        if 'sentiment' in df.columns:
            weights['sentiment'] = base_weights['sentiment']
        
        return weights