# -*- coding: utf-8 -*-
"""
DeepSeek API ETHUSDT实时技术指标分析器
使用DeepSeek API获取ETHUSDT的实时技术指标，包括MACD、ADX、ATR、布林带等
强制返回JSON格式的趋势分析、支撑阻力位等信息
"""

import requests
import json
import time
import logging
import os
import sys
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd
import numpy as np
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TRADING_CONFIG, DEBUG_CONFIG

# 尝试导入python-dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("警告: 未安装python-dotenv，请运行: pip install python-dotenv")

# 配置日志
logging.basicConfig(level=getattr(logging, DEBUG_CONFIG['LOG_LEVEL']))
logger = logging.getLogger(__name__)

class DeepSeekAnalyzer:
    """
    DeepSeek AI分析器 - 使用DeepSeek API进行市场分析
    """
    
    def __init__(self, api_key: str = None, base_url: str = "https://api.deepseek.com/v1/chat/completions"):
        """
        初始化DeepSeek分析器
        
        Args:
            api_key: DeepSeek API密钥
            base_url: DeepSeek API基础URL
        """
        if api_key is None:
            api_key = os.getenv('DEEPSEEK_API_KEY')
            if api_key is None:
                logger.warning("未找到DEEPSEEK_API_KEY，DeepSeek API功能将不可用")
                api_key = "dummy_key"  # 使用占位符以支持基础功能
        
        self.api_key = api_key
        self.base_url = base_url
        self.session = self._create_session()
        
        # 缓存配置 - 从配置文件读取
        try:
            from config import OPTIMIZED_STRATEGY_CONFIG
            self.cache_duration = OPTIMIZED_STRATEGY_CONFIG.get('cache_timeout', 3600)  # 默认1小时
        except ImportError:
            self.cache_duration = 3600  # 默认1小时
        
        # 改进的缓存机制
        self.cache = {}  # 使用字典存储多个缓存项
        self.last_api_call_time = 0  # 添加API调用时间记录
        
    def _create_session(self) -> requests.Session:
        """
        创建配置了重试机制和连接池的requests session
        
        Returns:
            配置好的requests.Session对象
        """
        session = requests.Session()
        
        # 配置重试策略
        retry_strategy = Retry(
            total=3,  # 总重试次数
            backoff_factor=1,  # 退避因子
            status_forcelist=[429, 500, 502, 503, 504],  # 需要重试的HTTP状态码
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )
        
        # 配置连接适配器
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,  # 连接池大小
            pool_maxsize=20,     # 最大连接数
            pool_block=False     # 连接池满时不阻塞
        )
        
        # 将适配器应用到http和https
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # 只有在有有效API密钥时才设置认证头
        if self.api_key != "dummy_key":
            session.headers.update({
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'User-Agent': 'TradingBot/1.0'
            })
        
        return session
    
    def _generate_cache_key(self, df: pd.DataFrame = None, indicators: Dict[str, Any] = None) -> str:
        """
        生成精确到分钟的缓存键值
        
        Args:
            df: 市场数据DataFrame
            indicators: 技术指标数据
            
        Returns:
            缓存键值字符串
        """
        # 获取当前时间，精确到分钟
        current_time = datetime.now()
        minute_key = current_time.strftime("%Y%m%d_%H%M")
        
        # 添加调试日志
        logger.debug(f"生成缓存键值: deepseek_{minute_key}")
        
        # 只使用时间结构，不包含价格和技术指标指纹
        return f"deepseek_{minute_key}"
    
    def _is_cache_valid(self, cache_key: str, force_refresh: bool = False) -> bool:
        """
        检查缓存是否有效
        
        Args:
            cache_key: 缓存键值
            force_refresh: 是否强制刷新
            
        Returns:
            缓存是否有效
        """
        if force_refresh:
            logger.debug(f"强制刷新缓存，跳过缓存检查 (缓存键: {cache_key})")
            return False
        
        if cache_key not in self.cache:
            logger.debug(f"缓存键不存在: {cache_key}")
            return False
        
        cache_data = self.cache[cache_key]
        current_time = time.time()
        cache_age = current_time - cache_data['timestamp']
        
        # 检查缓存是否过期
        if cache_age > self.cache_duration:
            logger.debug(f"缓存已过期: {cache_key}, 缓存时间: {cache_age:.0f}秒, 过期时间: {self.cache_duration}秒")
            return False
        
        logger.debug(f"缓存有效: {cache_key}, 缓存时间: {cache_age:.0f}秒")
        return True
    
    def _get_cached_analysis(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存的分析结果
        
        Args:
            cache_key: 缓存键值
            
        Returns:
            缓存的分析结果
        """
        if cache_key in self.cache:
            cache_data = self.cache[cache_key]
            age = time.time() - cache_data['timestamp']
            logger.debug(f"使用DeepSeek分析缓存 (缓存键: {cache_key}, 缓存时间: {age:.0f}秒)")
            return cache_data['data']
        return None
    
    def _update_cache(self, cache_key: str, analysis_result: Dict[str, Any]):
        """
        更新缓存
        
        Args:
            cache_key: 缓存键值
            analysis_result: 分析结果
        """
        self.cache[cache_key] = {
            'data': analysis_result,
            'timestamp': time.time()
        }
        
        # 清理过期缓存（保留最近10个缓存项）
        if len(self.cache) > 10:
            # 按时间戳排序，删除最旧的缓存
            sorted_cache = sorted(self.cache.items(), key=lambda x: x[1]['timestamp'])
            for old_key, _ in sorted_cache[:-10]:
                del self.cache[old_key]
        
        logger.debug(f"更新DeepSeek分析缓存 (缓存键: {cache_key})")
    
    def get_cache_status(self) -> Dict[str, Any]:
        """
        获取缓存状态信息
        
        Returns:
            缓存状态字典
        """
        current_time = time.time()
        cache_info = {
            'total_cache_items': len(self.cache),
            'cache_keys': [],
            'last_api_call': self.last_api_call_time,
            'time_since_last_api_call': current_time - self.last_api_call_time if self.last_api_call_time > 0 else 0
        }
        
        for key, data in self.cache.items():
            age = current_time - data['timestamp']
            cache_info['cache_keys'].append({
                'key': key,
                'age_seconds': age,
                'age_minutes': age / 60,
                'is_valid': age < self.cache_duration
            })
        
        return cache_info
    
    def clear_cache(self):
        """
        清空所有缓存
        """
        self.cache.clear()
        logger.info("DeepSeek分析缓存已清空")
    
    def get_ethusdt_data(self, timeframe: str = '1h', limit: int = 100) -> Optional[pd.DataFrame]:
        """
        获取ETHUSDT的K线数据
        
        Args:
            timeframe: 时间级别 (1m, 5m, 15m, 1h, 4h, 1d)
            limit: 获取的K线数量
            
        Returns:
            DataFrame包含OHLCV数据
        """
        try:
            # 使用Binance API获取数据
            url = "https://api.binance.com/api/v3/klines"
            params = {
                'symbol': 'ETHUSDT',
                'interval': timeframe,
                'limit': limit
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # 转换为DataFrame
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # 数据类型转换
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"获取ETHUSDT数据失败: {e}")
            return None
    
    # 计算动态权重
    def calculate_dynamic_weights(self, df: pd.DataFrame, mode: str = 'dynamic'):
        
        """
       计算动态权重
       
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
                'trend_weight': 0.4,#趋势权重
                'indicator_weight': 0.3,#指标权重
                'sentiment_weight': 0.2#情绪权重
            }
            total_fw = sum(fixed_weights.values())
            if total_fw > 0:
                fixed_weights = {k: v / total_fw for k, v in fixed_weights.items()}
            return fixed_weights
        
        # 动态权重计算
        weights = {}
        
        # 获取当前市场状态指标
        current_adx = df['adx'].iloc[-1] if 'adx' in df.columns else 25

        if current_adx > 25:
             weights['trend_weight'] = 0.3
             weights['indicator_weight'] = 0.3
             weights['sentiment_weight'] = 0.40
        else:
            weights['trend_weight'] = 0.4
            weights['indicator_weight'] = 0.3
            weights['sentiment_weight'] = 0.2
       
        return weights

    def calculate_technical_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        计算技术指标
        
        Args:
            df: 包含OHLCV数据的DataFrame
            
        Returns:
            包含所有技术指标的字典
        """
        try:
            indicators = {}
            
            # 计算MACD
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=9, adjust=False).mean()
            histogram = macd - signal
            
            indicators['macd'] = {
                'macd': float(macd.iloc[-1]),
                'signal': float(signal.iloc[-1]),
                'histogram': float(histogram.iloc[-1]),
                'trend': 'bullish' if macd.iloc[-1] > signal.iloc[-1] else 'bearish'
            }
            
            # 计算ADX (Average Directional Index) - 改进版本
            high = df['high']
            low = df['low']
            close = df['close']
            indicators['price'] = df['close']
            
            # 检查数据是否足够
            if len(df) < 28:  # 需要至少28个数据点来计算ADX
                logger.warning(f"数据不足，无法计算ADX。需要至少28个数据点，当前只有{len(df)}个")
                indicators['adx'] = {
                    'adx': None,
                    'di_plus': None,
                    'di_minus': None,
                    'trend_strength': 'unknown',
                    'trend_direction': 'unknown',
                    'status': 'insufficient_data'
                }
            else:
                # True Range
                tr1 = high - low
                tr2 = abs(high - close.shift(1))
                tr3 = abs(low - close.shift(1))
                tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                atr = tr.rolling(window=14).mean()
                
                # Directional Movement
                dm_plus = (high - high.shift(1)).clip(lower=0)
                dm_minus = (low.shift(1) - low).clip(lower=0)
                
                # 当DM+ > DM- 且 DM+ > 0时，DM+ = DM+，否则DM+ = 0
                dm_plus = np.where((dm_plus > dm_minus) & (dm_plus > 0), dm_plus, 0)
                dm_minus = np.where((dm_minus > dm_plus) & (dm_minus > 0), dm_minus, 0)
                
                # 平滑处理 - 使用指数移动平均，避免除零
                dm_plus_smoothed = pd.Series(dm_plus, index=atr.index).ewm(span=14, adjust=False).mean()
                dm_minus_smoothed = pd.Series(dm_minus, index=atr.index).ewm(span=14, adjust=False).mean()
                
                # 避免除零错误 - 确保所有操作数都是pandas Series且索引一致
                di_plus = pd.Series(np.where(atr > 0, 100 * dm_plus_smoothed / atr, 0), index=atr.index)
                di_minus = pd.Series(np.where(atr > 0, 100 * dm_minus_smoothed / atr, 0), index=atr.index)
                
                # ADX计算 - 改进版本
                # 避免除零错误，使用更稳定的计算方式
                denominator = di_plus + di_minus
                dx = np.where(denominator > 0, 100 * abs(di_plus - di_minus) / denominator, 0)
                adx = pd.Series(dx).ewm(span=14, adjust=False).mean()
                
                # 获取最新值并处理NaN
                adx_value = adx.iloc[-1]
                di_plus_value = di_plus.iloc[-1]
                di_minus_value = di_minus.iloc[-1]
                
                # 检查是否为NaN
                if pd.isna(adx_value) or pd.isna(di_plus_value) or pd.isna(di_minus_value):
                    # 尝试使用最近的有效值
                    adx_valid = adx.dropna()
                    di_plus_valid = di_plus.dropna()
                    di_minus_valid = di_minus.dropna()
                    
                    if len(adx_valid) > 0:
                        adx_value = adx_valid.iloc[-1]
                    else:
                        adx_value = 0.0
                        
                    if len(di_plus_valid) > 0:
                        di_plus_value = di_plus_valid.iloc[-1]
                    else:
                        di_plus_value = 0.0
                        
                    if len(di_minus_valid) > 0:
                        di_minus_value = di_minus_valid.iloc[-1]
                    else:
                        di_minus_value = 0.0
                
                # 确保值在合理范围内
                adx_value = max(0.0, min(100.0, adx_value))
                di_plus_value = max(0.0, min(100.0, di_plus_value))
                di_minus_value = max(0.0, min(100.0, di_minus_value))
                
                indicators['adx'] = {
                    'adx': float(adx_value),
                    'di_plus': float(di_plus_value),
                    'di_minus': float(di_minus_value),
                    'trend_strength': 'strong' if adx_value > 25 else 'weak',
                    'trend_direction': 'bullish' if di_plus_value > di_minus_value else 'bearish',
                    'status': 'calculated'
                }
            
            # 计算ATR
            indicators['atr'] = {
                'atr': float(atr.iloc[-1]),
                'atr_percent': float(atr.iloc[-1] / close.iloc[-1] * 100)
            }
            
            # 计算布林带
            sma = close.rolling(window=20).mean()
            std = close.rolling(window=20).std()
            upper_band = sma + (std * 2)
            lower_band = sma - (std * 2)
            
            current_price = float(close.iloc[-1])
            current_sma = float(sma.iloc[-1])
            current_upper = float(upper_band.iloc[-1])
            current_lower = float(lower_band.iloc[-1])
            
            # 计算布林带位置
            bb_position = (current_price - current_lower) / (current_upper - current_lower)
            
            indicators['bollinger_bands'] = {
                'upper': current_upper,
                'middle': current_sma,
                'lower': current_lower,
                'position': float(bb_position),
                'squeeze': 'yes' if (current_upper - current_lower) / current_sma < 0.1 else 'no'
            }
            
            # 计算RSI
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            indicators['rsi'] = {
                'rsi': float(rsi.iloc[-1]),
                'status': 'overbought' if rsi.iloc[-1] > 70 else 'oversold' if rsi.iloc[-1] < 30 else 'neutral'
            }
            
            # 计算交易量指标
            volume = df['volume']
            volume_sma = volume.rolling(window=20).mean()
            volume_ratio = volume.iloc[-1] / volume_sma.iloc[-1] if volume_sma.iloc[-1] > 0 else 1.0
            
            # 计算价格波动指标
            price_change = close.pct_change()
            price_volatility = price_change.rolling(window=20).std() * 100  # 转换为百分比
            
            # 计算价格动量
            price_momentum = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100  # 5周期价格变化百分比
            
            indicators['volume'] = {
                'current_volume': float(volume.iloc[-1]),
                'avg_volume': float(volume_sma.iloc[-1]),
                'volume_ratio': float(volume_ratio),
                'volume_trend': 'high' if volume_ratio > 1.5 else 'normal' if volume_ratio > 0.8 else 'low'
            }
            
            indicators['price_volatility'] = {
                'volatility': float(price_volatility.iloc[-1]),
                'volatility_level': 'high' if price_volatility.iloc[-1] > 3.0 else 'medium' if price_volatility.iloc[-1] > 1.5 else 'low',
                'price_momentum': float(price_momentum),
                'momentum_direction': 'up' if price_momentum > 0 else 'down'
            }
            
            
            return indicators
            
        except Exception as e:
            logger.error(f"计算技术指标失败: {e}")
            return {}
    
   
   
    def query_deepseek_api(self, prompt: str) -> Optional[str]:
        """
        查询DeepSeek API
        
        Args:
            prompt: 查询提示
            
        Returns:
            API响应内容
        """
        # 检查是否有有效的API密钥
        if self.api_key == "dummy_key":
            logger.info("DeepSeek API密钥未配置，跳过API调用")
            return None
            
        try:
            url = self.base_url
            
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的加密货币技术分析师。请分析实时ETHUSDT1小时时间框架的技术指标，并返回JSON格式的分析结果。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 2000
            }
            
            # 使用更长的超时时间和连接超时
            timeout_config = (10, 60)  # (连接超时, 读取超时)
            
            # 记录请求参数
            logger.info(f"🔍 DeepSeek API请求:")
            logger.info(f" URL: {url}")
            logger.info(f" 模型: {payload['model']}")
            logger.info(f" 温度: {payload['temperature']}")
            logger.info(f" 最大令牌: {payload['max_tokens']}")
            logger.info(f" 系统提示: {payload['messages'][0]['content'][:100]}...")
            logger.info(f" 用户提示: {payload['messages'][1]['content'][:200]}...")
            
            response = self.session.post(url, json=payload, timeout=timeout_config)
            response.raise_for_status()
            
            result = response.json()
            
            # 记录响应数据
            logger.info(f"DeepSeek API响应:")
            logger.info(f" 状态码: {response.status_code}")
            logger.info(f" 响应时间: {response.elapsed.total_seconds():.2f}秒")
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content']
                logger.info(f" 响应内容长度: {len(content)} 字符")
                logger.info(f" 响应内容预览: {content[:300]}...")
                if len(content) > 300:
                    logger.info(f" 完整响应内容: {content}")
            else:
                logger.warning(f" 响应格式异常: {result}")
            
            return result['choices'][0]['message']['content']
            
        except requests.exceptions.Timeout as e:
            logger.error(f"⏰ DeepSeek API超时: {e}")
            logger.info("  💡 建议: 检查网络连接或稍后重试")
            logger.info(f" 超时配置: 连接={timeout_config[0]}秒, 读取={timeout_config[1]}秒")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"🌐 DeepSeek API连接错误: {e}")
            logger.info("  💡 建议: 检查网络连接或API服务状态")
            logger.info(f" 🔗 目标URL: {url}")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"DeepSeek API HTTP错误: {e}")
            if hasattr(e.response, 'status_code'):
                logger.error(f" HTTP状态码: {e.response.status_code}")
                logger.error(f" 响应头: {dict(e.response.headers)}")
                try:
                    error_detail = e.response.json()
                    logger.error(f" 错误详情: {error_detail}")
                except:
                    logger.error(f" 响应内容: {e.response.text[:500]}...")
                
                if e.response.status_code == 401:
                    logger.error("  💡 建议: API密钥可能无效或已过期")
                elif e.response.status_code == 429:
                    logger.error("  💡 建议: API调用频率过高，请稍后重试")
                elif e.response.status_code >= 500:
                    logger.error("  💡 建议: 服务器内部错误，请稍后重试")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"📄 DeepSeek API响应JSON解析失败: {e}")
            logger.error(f" 📍 错误位置: 行{e.lineno}, 列{e.colno}")
            logger.error(f" 📝 原始响应: {response.text[:500]}...")
            return None
        except Exception as e:
            logger.error(f"❓ DeepSeek API查询失败: {e}")
            logger.error(f" 🔍 异常类型: {type(e).__name__}")
            import traceback
            logger.error(f" 📋 详细堆栈: {traceback.format_exc()}")
            return None
    

 
    
    def get_real_time_analysis(self, df=None, force_refresh: bool = False) -> Dict[str, Any]:
        """
        获取实时分析结果（精简版）
        
        Args:
            df: 市场数据DataFrame，如果为None则自动获取
            force_refresh: 是否强制刷新缓存
            
        Returns:
            精简的分析结果，只包含信号整合器需要的核心数据
        """
        try:
            # 首先检查是否有有效的缓存（不依赖具体数据）
            if not force_refresh and self.cache:
                # 获取最新的缓存数据
                latest_cache = max(self.cache.items(), key=lambda x: x[1]['timestamp'])
                cache_key, cache_data = latest_cache
                cache_age = time.time() - cache_data['timestamp']
                
                # 如果缓存仍然有效，直接返回缓存数据
                if cache_age < self.cache_duration:
                    logger.info(f"✅ 直接使用现有缓存 (缓存键: {cache_key}, 缓存时间: {cache_age:.0f}秒)")
                    return cache_data['data']
                else:
                    logger.debug(f"缓存已过期: {cache_key}, 缓存时间: {cache_age:.0f}秒")
            
            # 如果没有有效缓存，才进行新的分析
            logger.debug("开始新的DeepSeek分析")
            
            # 获取基础数据
            if df is None:
                df = self.get_ethusdt_data()
                if df is None:
                    return {'error': '无法获取市场数据'}
            
            # 计算技术指标
            indicators = self.calculate_technical_indicators(df)
            if not indicators:
                return {'error': '无法计算技术指标'}

            # 生成精确到分钟的缓存键值
            cache_key = self._generate_cache_key(df, indicators)
            
            # 检查缓存是否有效
            if self._is_cache_valid(cache_key, force_refresh):
                cached_result = self._get_cached_analysis(cache_key)
                if cached_result:
                    logger.info(f"✅ 使用DeepSeek分析缓存 (缓存键: {cache_key})")
                    return cached_result
                else:
                    logger.debug(f"缓存检查通过但未找到缓存数据: {cache_key}")
            else:
                logger.debug(f"缓存无效或不存在: {cache_key}")
            
            # 检查API调用频率限制
            current_time = time.time()
            time_since_last_call = current_time - self.last_api_call_time
            min_interval = 1800  # 最少30分钟间隔
            if time_since_last_call < min_interval:
                logger.info(f"⏰ DeepSeek API调用过于频繁，使用缓存数据 (距离上次调用: {time_since_last_call:.0f}秒)")
                # 尝试使用最近的缓存数据
                if self.cache:
                    # 获取最新的缓存数据
                    latest_cache = max(self.cache.items(), key=lambda x: x[1]['timestamp'])
                    return latest_cache[1]['data']
                else:
                    return {'note': 'DeepSeek分析暂不可用，请稍后重试'}

            # 获取DeepSeek API分析
            deepseek_analysis = self.get_deepseek_analysis(indicators)

            # 提取评分数据（优先使用API，备用本地计算）
            if deepseek_analysis and 'confidence_score' in deepseek_analysis:
                api_scores = deepseek_analysis['confidence_score']
                trend_score = api_scores.get('trend_score', 0)
                base_score =  api_scores.get('indicator_score', 0)
                signal_score = api_scores.get('sentiment_score', 0)

                # 计算动态权重
                weights = self.calculate_dynamic_weights(df)
                signal_score = (trend_score * weights['trend_weight'] +
                                base_score * weights['indicator_weight'] +
                                signal_score * weights['sentiment_weight'])
 
                # 构建精简的分析结果
                analysis_result = {
                    'signal': 1 if signal_score > 0 else -1 if signal_score < 0 else 0,
                    'timestamp': datetime.now().isoformat(),
                    'current_price': deepseek_analysis.get('level', {}).get('current', 0.0),
                    'resistance': deepseek_analysis.get('level', {}).get('resistance', 0.0),
                    'support': deepseek_analysis.get('level', {}).get('support', 0.0),
                    'trend': deepseek_analysis.get('trend', 'sideways'),
                    'risk': deepseek_analysis.get('risk', 'medium'),
                    'action': deepseek_analysis.get('action', 'wait'),
                    'advice': deepseek_analysis.get('advice', '观望等待突破'),
                    'trend_score': trend_score,
                    'base_score': base_score,
                    'signal_score': signal_score,  # 综合评分(权重)
                    'indicators': indicators,
                    'cache_key': cache_key  # 添加缓存键值用于调试
                }
            else:
                # 如果API分析失败，返回错误信息
                analysis_result = {
                    'error': 'DeepSeek API分析失败',
                    'cache_key': cache_key
                }
            
            # 记录API调用时间
            if deepseek_analysis:
                self.last_api_call_time = current_time
            
            # 更新缓存
            self._update_cache(cache_key, analysis_result)
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"获取实时分析失败: {e}")
            return {'error': f'分析失败: {str(e)}'}
    
    def get_deepseek_analysis(self, indicators: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        使用DeepSeek API进行深度分析，包括趋势、指标和情绪评分计算
        
        Args:
            indicators: 技术指标
            
        Returns:
            DeepSeek分析结果，包含趋势、指标和情绪评分
        """
        try:
            # 构建提示词
            prompt = f"""
请分析以下ETHUSDT的技术指标数据，并返回JSON格式的分析结果：

技术指标：
- MACD: {indicators.get('macd', {})}
- ADX: {indicators.get('adx', {})}
- ATR: {indicators.get('atr', {})}
- 布林带: {indicators.get('bollinger_bands', {})}
- RSI: {indicators.get('rsi', {})}

请基于以上技术指标，计算趋势评分、指标评分和情绪评分并返回精简的JSON格式：

{{
  "trend": "sideways",
  "level": {{
    "resistance": 4817.4,
    "support": 4692.81,
    "current": 4768.17
  }},
  "risk": "medium",
  "action": "wait",
  "advice": "观望等待突破",
  "confidence_score": {{
    "trend_score": -0.15,
    "indicator_score": 0.05,
    "sentiment_score": -0.10
  }}
}}

注意：level中的resistance和support应该是最近1天内的关键价位，基于当前价格附近的支撑阻力位计算得出。

注意：
- trend: 趋势方向 (bullish/bearish/sideways)
- level: 最近1天的关键价位，包含支撑和阻力位
- risk: 风险等级 (low/medium/high)
- action: 操作建议 (long/short/wait)
- advice: 投资建议文本，限制10个中文文字以内
- confidence_score必须包含三个评分字段，范围-1到1

请确保返回的是有效的JSON格式。
"""
            
            response = self.query_deepseek_api(prompt)
            if not response:
                return None
            
            # 尝试解析JSON响应
            try:
                # 查找JSON内容
                start_idx = response.find('{')
                end_idx = response.rfind('}') + 1
                
                if start_idx != -1 and end_idx != -1:
                    json_str = response[start_idx:end_idx]
                    return json.loads(json_str)
                else:
                    # 如果没有找到JSON，返回文本分析
                    return {
                        'analysis_text': response,
                        'format': 'text'
                    }
                    
            except json.JSONDecodeError:
                # 如果JSON解析失败，返回文本分析
                return {
                    'analysis_text': response,
                    'format': 'text'
                }
                
        except Exception as e:
            logger.error(f"DeepSeek深度分析失败: {e}")
            return None
    
 