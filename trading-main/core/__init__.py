"""
量化交易系统核心模块

包含策略实现、数据加载、特征工程、回测引擎和交易所API等核心功能。
"""

# 导入核心模块
from .strategy import SharpeOptimizedStrategy
from .data_loader import DataLoader
from .feature_engineer import FeatureEngineer
from .backtester import Backtester
from .exchange_api import RealExchangeAPI
from .siganal_filter import SignalFilter
from .risk import RiskManager

# 导出主要类
__all__ = [
    'SharpeOptimizedStrategy',
    'DataLoader',
    'FeatureEngineer',
    'Backtester',
    'RealExchangeAPI',
    'SignalFilter',
    'RiskManager'
]

# 版本信息
__version__ = '1.0.0'
__author__ = 'xniu.io'
__description__ = '量化交易系统核心模块' 