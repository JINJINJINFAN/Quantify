# -*- coding: utf-8 -*-
"""
SocketIO配置管理
"""

# SocketIO配置
SOCKETIO_CONFIG = {
    'cors_allowed_origins': "*",
    'ping_timeout': 60,           # ping超时时间（秒）
    'ping_interval': 25,          # ping间隔（秒）
    'max_http_buffer_size': 1e8,  # 最大HTTP缓冲区大小
    'logger': True,               # 启用日志
    'engineio_logger': True,      # 启用Engine.IO日志
    'async_mode': 'threading',    # 异步模式
    'cors_credentials': True,     # 允许跨域凭证
}

# 会话配置
SESSION_CONFIG = {
    'permanent_session_lifetime': 24 * 60 * 60,  # 24小时
    'session_cookie_secure': False,               # 开发环境设为False
    'session_cookie_httponly': True,              # 防止XSS攻击
    'session_cookie_samesite': 'Lax',            # 防止CSRF攻击
}

# 错误处理配置
ERROR_HANDLING_CONFIG = {
    'log_invalid_sessions': True,     # 记录无效会话
    'max_retry_attempts': 3,          # 最大重试次数
    'retry_delay': 5,                 # 重试延迟（秒）
    'session_cleanup_interval': 300,  # 会话清理间隔（秒）
} 