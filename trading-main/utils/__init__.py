# -*- coding: utf-8 -*-
"""
工具模块
包含各种实用工具和辅助功能
"""

import logging

def configure_logging():
    """配置日志系统，过滤 werkzeug 的 INFO 和 ERROR 级别日志"""
    # 过滤 werkzeug 的所有日志（包括 ERROR）
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.CRITICAL)
    
    # 过滤其他可能产生过多 INFO 日志的库
    urllib3_logger = logging.getLogger('urllib3')
    urllib3_logger.setLevel(logging.WARNING)
    
    requests_logger = logging.getLogger('requests')
    requests_logger.setLevel(logging.WARNING)

from .fix_matplotlib_fonts import force_add_fonts, configure_fonts
from .fix_config import save_user_config, load_user_config, get_default_config, merge_configs, apply_user_config, reset_to_default_config
from .telegram_notifier import TelegramNotifier, notify_signal, notify_trade, notify_status, notify_error

__all__ = [
    'force_add_fonts',
    'configure_fonts',
    'save_user_config',
    'load_user_config', 
    'get_default_config',
    'merge_configs',
    'apply_user_config',
    'reset_to_default_config',
    'TelegramNotifier',
    'notify_signal',
    'notify_trade', 
    'notify_status',
    'notify_error'
] 