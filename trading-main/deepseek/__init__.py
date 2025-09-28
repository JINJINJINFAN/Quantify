"""
DeepSeek集成模块

包含DeepSeek AI分析器和信号集成器，用于增强交易决策。
"""

# 导入DeepSeek模块
from .analyzer import DeepSeekAnalyzer
from .signal_integrator import DeepSeekSignalIntegrator
from .quick_demo import main as run_quick_demo

# 导出主要类
__all__ = [
    'DeepSeekAnalyzer',
    'DeepSeekSignalIntegrator',
    'run_quick_demo'
]

# 版本信息
__version__ = '1.0.0'
__author__ = 'xniu.io'
__description__ = 'DeepSeek AI集成模块' 