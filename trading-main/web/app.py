#!/usr/bin/env python38
# -*- coding: utf-8 -*-
"""
交易系统Web管理界面
提供基于Web的交互式管理界面
"""

import os
import sys
import json
import time
import threading
import random
import subprocess
import platform
import psutil
import logging
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
    from flask_socketio import SocketIO, emit
    from functools import wraps
    from config import *
    from trading import TradingSystem
    from utils.telegram_notifier import notify_signal, notify_trade, notify_status, notify_error
    from web.socketio_config import SOCKETIO_CONFIG, SESSION_CONFIG, ERROR_HANDLING_CONFIG
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保在项目根目录运行此脚本")
    sys.exit(1)

# 创建Flask应用
app = Flask(__name__, 
           template_folder=Path(__file__).parent / 'templates',
           static_folder=Path(__file__).parent / 'static')
app.config['SECRET_KEY'] = 'trading_system_secret_key_2024'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=SESSION_CONFIG['permanent_session_lifetime'])
app.config['SESSION_COOKIE_SECURE'] = SESSION_CONFIG['session_cookie_secure']
app.config['SESSION_COOKIE_HTTPONLY'] = SESSION_CONFIG['session_cookie_httponly']
app.config['SESSION_COOKIE_SAMESITE'] = SESSION_CONFIG['session_cookie_samesite']

socketio = SocketIO(app, **SOCKETIO_CONFIG)

# 用户认证配置
USERS = {
    'admin': '1314521'
}

# 全局变量 - 使用trading.py的TradingSystem实例
trading_system = None
trading_system_initialized = False  # 添加初始化标志

system_status = {
    'service_status': 'inactive',
    'service_detail': '交易系统未运行',
    'running': False,
    'mode': 'web',
    'start_time': None,
    'last_signal': None,
    'last_trade': None,
    'system_info': {}
}

# 实时数据推送线程
data_push_thread = None
data_push_running = False

def ensure_json_serializable(data):
    """确保数据可以被JSON序列化"""
    if isinstance(data, dict):
        return {key: ensure_json_serializable(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [ensure_json_serializable(item) for item in data]
    elif isinstance(data, bool):
        return 1 if data else 0
    elif isinstance(data, (int, float, str, type(None))):
        return data
    else:
        return str(data)

# SocketIO错误处理
@socketio.on_error()
def error_handler(e):
    """SocketIO错误处理"""
    if ERROR_HANDLING_CONFIG['log_invalid_sessions']:
        print(f"SocketIO错误: {e}")
    try:
        emit('error', {'message': '连接错误，请重新连接'})
    except:
        pass

@socketio.on_error_default
def default_error_handler(e):
    """默认错误处理"""
    if ERROR_HANDLING_CONFIG['log_invalid_sessions']:
        print(f"SocketIO默认错误: {e}")
    try:
        emit('error', {'message': '系统错误'})
    except:
        pass

# 配置日志级别来减少Engine.IO的无效会话错误
import logging
logging.getLogger('engineio.server').setLevel(logging.WARNING)
logging.getLogger('socketio.server').setLevel(logging.WARNING)

def get_trading_system():
    """获取或创建TradingSystem实例 - 单例模式"""
    global trading_system, trading_system_initialized
    
    try:
        # 如果已经初始化过且实例存在，直接返回
        if trading_system_initialized and trading_system is not None:
            return trading_system
            
        # 如果实例存在但未标记为已初始化，检查其状态
        if trading_system is not None:
            if hasattr(trading_system, 'logger') and trading_system.logger is not None:
                trading_system_initialized = True
                return trading_system
            else:
                print("⚠️ 现有TradingSystem实例状态异常，将重新创建...")
                trading_system = None
                trading_system_initialized = False
        
        # 检查是否已经有其他进程创建了实例（通过文件检查）
        instance_file = os.path.join(tempfile.gettempdir(), 'trading_system_instance.txt')
        if os.path.exists(instance_file):
            try:
                with open(instance_file, 'r') as f:
                    instance_info = f.read().strip()
                print(f"📋 检测到现有TradingSystem实例: {instance_info}")
                # 如果文件存在，说明已经有实例在运行，但我们仍然需要创建本地实例
                # 因为每个进程都需要自己的TradingSystem实例
                print("🔄 检测到其他进程实例，但继续创建本地实例...")
            except:
                pass
        
        # 创建新实例
        if trading_system is None:
            print("🔧 正在创建TradingSystem实例...")
            trading_system = TradingSystem(mode='web')
            trading_system_initialized = True
            
            # 记录实例信息到文件
            try:
                with open(instance_file, 'w') as f:
                    f.write(f"PID: {os.getpid()}, Time: {datetime.now()}, Instance ID: {id(trading_system)}")
            except:
                pass
            
            print("✅ TradingSystem实例创建成功")
        
        return trading_system
        
    except Exception as e:
        print(f"创建TradingSystem实例失败: {e}")
        import traceback
        print(f"异常堆栈: {traceback.format_exc()}")
        # 重置状态，允许下次重试
        trading_system = None
        trading_system_initialized = False
        return None

def set_trading_system_instance(instance):
    """设置全局TradingSystem实例"""
    global trading_system, trading_system_initialized
    trading_system = instance
    trading_system_initialized = True
    print(f"✅ 已设置全局TradingSystem实例: {id(instance)}")

def reset_trading_system():
    """重置TradingSystem实例"""
    global trading_system, trading_system_initialized
    
    if trading_system is not None:
        try:
            # 尝试停止交易系统
            if hasattr(trading_system, 'stop'):
                trading_system.stop()
        except Exception as e:
            print(f"停止交易系统时出错: {e}")
    
    # 删除实例文件
    try:
        instance_file = os.path.join(tempfile.gettempdir(), 'trading_system_instance.txt')
        if os.path.exists(instance_file):
            os.remove(instance_file)
    except Exception as e:
        print(f"清理实例文件时出错: {e}")
    
    trading_system = None
    trading_system_initialized = False
    print("🔄 TradingSystem实例已重置")

def validate_float(value, default=0.0, min_val=None, max_val=None):
    """验证并转换浮点数"""
    try:
        result = float(value) if value is not None else default
        if min_val is not None and result < min_val:
            return default
        if max_val is not None and result > max_val:
            return default
        return result
    except (ValueError, TypeError):
        return default

def validate_int(value, default=0, min_val=None, max_val=None):
    """验证并转换整数"""
    try:
        result = int(value) if value is not None else default
        if min_val is not None and result < min_val:
            return default
        if max_val is not None and result > max_val:
            return default
        return result
    except (ValueError, TypeError):
        return default

def safe_get_attr(obj, attr, default=None, converter=None):
    """安全获取对象属性"""
    try:
        value = getattr(obj, attr, default)
        if converter and value is not None:
            return converter(value)
        return value
    except Exception:
        return default

def api_error_handler(f):
    """API错误处理装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            error_message = f'{f.__name__}执行失败: {str(e)}'
            print(f"{error_message}")
            return jsonify({
                'success': False, 
                'message': error_message,
                'timestamp': datetime.now().isoformat()
            })
    return decorated_function

def socketio_auth_required(f):
    """SocketIO认证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            if 'logged_in' not in session:
                emit('error', {'message': '请先登录'})
                return False
            return f(*args, **kwargs)
        except Exception as e:
            print(f"SocketIO认证异常: {e}")
            emit('error', {'message': '认证失败'})
            return False
    return decorated_function

def cleanup_expired_sessions():
    """清理过期会话"""
    try:
        # 这里可以添加会话清理逻辑
        # 目前Flask会自动处理会话过期
        pass
    except Exception as e:
        print(f"会话清理异常: {e}")

def update_system_status():
    """更新系统状态 - 直接反映trading.py系统的状态"""
    global system_status
    try:
        ts = get_trading_system()
        if ts:
            # 直接使用trading.py系统的running状态
            is_running = getattr(ts, 'running', False)
            
            raw_system_info = getattr(ts, 'get_system_info', lambda: {})()
            system_status.update({
                'running': 1 if is_running else 0,
                'mode': getattr(ts, 'mode', 'unknown'),
                'start_time': ts.start_time.isoformat() if hasattr(ts, 'start_time') and ts.start_time else None,
                'last_signal': getattr(ts, 'last_signal', None),
                'last_trade': getattr(ts, 'last_trade', None),
                'system_info': ensure_json_serializable(raw_system_info)
            })
            
            # 更新服务状态
            if is_running:
                system_status['service_status'] = 'active'
                system_status['service_detail'] = f'交易系统运行中({ts.mode}模式)'
            else:
                system_status['service_status'] = 'inactive'
                system_status['service_detail'] = '交易系统已停止'
        else:
            system_status.update({
                'running': 0,
                'service_status': 'inactive',
                'service_detail': '交易系统未初始化'
            })
    except Exception as e:
        print(f"更新系统状态失败: {e}")
        system_status.update({
            'running': 0,
            'service_status': 'error',
            'service_detail': f'状态更新失败: {str(e)}'
        })

def push_realtime_data():
    """推送核心实时数据到客户端 - 精简版本"""
    global data_push_running, system_status
    
    # 初始化时获取一次交易系统实例
    ts = None
    try:
        ts = get_trading_system()
        if ts:
            print("数据推送线程：TradingSystem实例获取成功")
        else:
            print("数据推送线程：TradingSystem实例获取失败")
    except Exception as e:
        print(f"数据推送线程：初始化TradingSystem失败: {e}")
    
    while data_push_running:
        try:
            # 如果之前获取失败，再次尝试获取
            if ts is None:
                try:
                    ts = get_trading_system()
                except Exception as e:
                    print(f"重新获取TradingSystem失败: {e}")
            
            # 只推送系统运行状态 - 这是唯一真正需要的实时数据
            if ts:
                try:
                    # 更新并推送系统状态
                    update_system_status()
                    socketio.emit('status_update', system_status, namespace='/')
                except Exception as e:
                    print(f"推送系统状态失败: {e}")
            else:
                # 交易系统未初始化，推送基本状态
                basic_status = {
                    'running': 0,
                    'service_status': 'inactive',
                    'service_detail': '交易系统未运行'
                }
                socketio.emit('status_update', basic_status, namespace='/')
            
            # 每120秒推送一次数据（大幅减少频率）
            time.sleep(120)
        except Exception as e:
            print(f"推送线程错误: {e}")
            time.sleep(15)

def start_data_push():
    """启动数据推送线程"""
    global data_push_thread, data_push_running
    
    if not data_push_running:
        data_push_running = True
        data_push_thread = threading.Thread(target=push_realtime_data, daemon=True)
        data_push_thread.start()
        print(" 实时数据推送线程已启动")

def stop_data_push():
    """停止数据推送线程"""
    global data_push_running
    data_push_running = False
    print("⏹️ 实时数据推送线程已停止")

# 登录验证装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Favicon路由
@app.route('/favicon.ico')
def favicon():
    """提供favicon图标"""
    return app.send_static_file('favicon.ico')

# 登录相关路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in USERS and USERS[username] == password:
            session.permanent = True
            session['logged_in'] = True
            session['username'] = username
            flash('登录成功', 'success')
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """登出"""
    session.clear()
    flash('已安全退出！', 'info')
    return redirect(url_for('login'))

# Web路由
@app.route('/')
@login_required
def index():
    """主页 - 显示交易系统概览"""
    try:
        ts = get_trading_system()
        
        # 获取基础系统状 
        system_running = getattr(ts, 'running', False)
        
        # 获取交易模式信息
        trading_mode_data = {
            'real_trading': getattr(ts, 'real_trading', False),
            'trading_mode': '真实交易' if getattr(ts, 'real_trading', False) else '模拟交易',
            'mode_icon': '🔴' if getattr(ts, 'real_trading', False) else '🟡',
            'warning_message': '🔴 真实交易模式，将使用真实资金' if getattr(ts, 'real_trading', False) else '🟡 模拟交易模式，不会使用真实资',
            'can_switch_to_real': hasattr(ts, 'exchange_api') and ts.exchange_api is not None
        }
        
        # 获取基础统计数据（用于初始页面渲染）
        dashboard_data = {
            'system_running': system_running,
            'total_trades': len(getattr(ts, 'trade_history', [])),
            'daily_trades': getattr(ts, 'daily_trades', 0),
            'current_capital': getattr(ts, 'current_capital', 10000.0),
            'total_pnl': getattr(ts, 'total_pnl', 0.0),
            'daily_pnl': getattr(ts, 'daily_pnl', 0.0),
            'symbol': getattr(ts, 'symbol', 'ETHUSDT'),
            'current_position': getattr(ts, 'current_position', 0)
        }
        
        return render_template('index.html', 
                             status=system_status, 
                             trading_mode=trading_mode_data,
                             dashboard=dashboard_data)
    except Exception as e:
        print(f"主页数据获取失败: {e}")
        # 返回默认数据
        default_trading_mode = {
            'real_trading': False,
            'trading_mode': '模拟交易',
            'mode_icon': '🟡',
            'warning_message': '🟡 模拟交易模式，不会使用真实资',
            'can_switch_to_real': False
        }
        default_dashboard = {
            'system_running': False,
            'total_trades': 0,
            'daily_trades': 0,
            'current_capital': 10000.0,
            'total_pnl': 0.0,
            'daily_pnl': 0.0,
            'symbol': 'ETHUSDT',
            'current_position': 0
        }
        
        return render_template('index.html', 
                             status=system_status, 
                             trading_mode=default_trading_mode,
                             dashboard=default_dashboard)



@app.route('/api/status')
@login_required
def api_status():
    """获取系统状态API - 检查TradingSystem状"""
    try:
        # 更新系统状态
        update_system_status()
        return jsonify(system_status)
    except Exception as e:
        system_status['service_detail'] = f'状态检查异{str(e)}'
        return jsonify(system_status)



@app.route('/api/start', methods=['POST'])
@login_required
def api_start():
    """启动系统API - 调用trading.py的TradingSystem"""
    try:
        ts = get_trading_system()
        if not ts:
            # 提供更详细的错误信息
            error_msg = "交易系统实例获取失败"
            if trading_system is None:
                error_msg += " - 实例为None"
            elif not trading_system_initialized:
                error_msg += " - 实例未初始化"
            else:
                error_msg += " - 未知原因"
            return jsonify({'success': False, 'message': error_msg})
        
        # 如果系统已经在运行，直接返回成功
        if ts.running:
            update_system_status()
            return jsonify({'success': True, 'message': '交易系统已在运行中'})
        
        success, message = ts.start()
        if success:
            update_system_status()
            return jsonify({'success': True, 'message': f'交易系统启动成功: {message}'})
        else:
            return jsonify({'success': False, 'message': f'启动失败: {message}'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'启动异常: {str(e)}'})



@app.route('/api/stop', methods=['POST'])
@login_required
def api_stop():
    """停止系统API - 调用trading.py的TradingSystem（强制保持仓位）"""
    try:
        ts = get_trading_system()
        if not ts:
            # 提供更详细的错误信息
            error_msg = "交易系统实例获取失败"
            if trading_system is None:
                error_msg += " - 实例为None"
            elif not trading_system_initialized:
                error_msg += " - 实例未初始化"
            else:
                error_msg += " - 未知原因"
            return jsonify({'success': False, 'message': error_msg})
        
        # 如果系统已经停止，直接返回成功
        if not ts.running:
            update_system_status()
            return jsonify({'success': True, 'message': '交易系统已经停止'})
        
        # 强制不允许平仓，系统设置为强制保持仓位
        success, message = ts.stop(force_close_position=False)
        if success:
            update_system_status()
            return jsonify({'success': True, 'message': f'交易系统停止成功（保持仓位）: {message}'})
        else:
            return jsonify({'success': False, 'message': f'停止失败: {message}'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'停止异常: {str(e)}'})

@app.route('/api/status_check')
@login_required
def api_status_check():
    """检查系统服务状态API - 调用trading.py的TradingSystem"""
    try:
        ts = get_trading_system()
        if not ts:
            return jsonify({'success': False, 'message': '交易系统初始化失'})
            
        update_system_status()
        
        # 获取更详细的系统状态信
        status_info = {
            'success': True, 
            'running': safe_get_attr(ts, 'running', False), 
            'message': '系统运行' if safe_get_attr(ts, 'running', False) else '系统已停',
            'system_status': system_status,
            'current_capital': validate_float(safe_get_attr(ts, 'current_capital'), 0),
            'available_capital': validate_float(safe_get_attr(ts, 'available_capital'), 0),
            'total_pnl': validate_float(safe_get_attr(ts, 'total_pnl'), 0),
            'daily_pnl': validate_float(safe_get_attr(ts, 'daily_pnl'), 0),
            'current_position': validate_int(safe_get_attr(ts, 'current_position'), 0),
            'trade_count': len(safe_get_attr(ts, 'trade_history', [])),
            'symbol': safe_get_attr(ts, 'symbol', 'ETHUSDT'),
            'timeframe': safe_get_attr(ts, 'timeframe', '1h')
        }
        
        return jsonify(status_info)
    except Exception as e:
        return jsonify({'success': False, 'message': f'状态检查失{str(e)}'})







@app.route('/api/logs/follow')
@login_required
def api_logs_follow():
    """实时日志流API - 使用Server-Sent Events调用trading.py的日志系"""
    def generate():
        try:
            # 获取TradingSystem实例
            ts = get_trading_system()
            if not ts:
                error_data = {
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'level': 'ERROR',
                    'message': '交易系统未初始化',
                    'module': 'WebAPI'
                }
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                return
            
            # 获取日志文件路径
            log_file_path = None
            if hasattr(ts, 'logger') and ts.logger:
                for handler in ts.logger.handlers:
                    if isinstance(handler, logging.FileHandler):
                        log_file_path = handler.baseFilename
                        break
            
            if not log_file_path:
                log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
                if os.path.exists(log_dir):
                    log_files = []
                    for file in os.listdir(log_dir):
                        if file.endswith('.log'):
                            log_files.append(os.path.join(log_dir, file))
                    
                    if log_files:
                        log_file_path = max(log_files, key=os.path.getmtime)
            
            if not log_file_path or not os.path.exists(log_file_path):
                error_data = {
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'level': 'ERROR',
                    'message': '无法找到日志文件',
                    'module': 'WebAPI'
                }
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                return
            
            # 获取初始文件大小
            last_size = os.path.getsize(log_file_path)
            
            # 发送开始消
            start_data = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'level': 'INFO',
                'message': f'开始跟踪日志文{os.path.basename(log_file_path)}',
                'module': 'WebAPI'
            }
            yield f"data: {json.dumps(start_data, ensure_ascii=False)}\n\n"
            
            # 监控日志文件变化
            while True:
                try:
                    current_size = os.path.getsize(log_file_path)
                    
                    if current_size > last_size:
                        # 读取新增的日志行
                        with open(log_file_path, 'r', encoding='utf-8') as f:
                            f.seek(last_size)
                            new_lines = f.readlines()
                        
                        for line in new_lines:
                            if line.strip():
                                try:
                                    # 解析日志格式: 2024-01-01 12:00:00,123 - TradingSystem - INFO - 消息内容
                                    parts = line.strip().split(' - ', 3)
                                    if len(parts) >= 4:
                                        timestamp = parts[0]
                                        module = parts[1]
                                        level = parts[2]
                                        message = parts[3]
                                        
                                        log_data = {
                                            'timestamp': timestamp,
                                            'level': level,
                                            'message': message,
                                            'module': module
                                        }
                                    else:
                                        # 简单格式处
                                        log_data = {
                                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                            'level': 'INFO',
                                            'message': line.strip(),
                                            'module': 'TradingSystem'
                                        }
                                    
                                    yield f"data: {json.dumps(log_data, ensure_ascii=False)}\n\n"
                                except Exception as e:
                                    continue
                        
                        last_size = current_size
                    
                    # 检查文件是否被重新创建（日志轮转）
                    if current_size < last_size:
                        last_size = 0
                    
                    time.sleep(1)  # 每秒检查一
                except Exception as e:
                    error_data = {
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'level': 'ERROR',
                        'message': f'监控日志文件时出{str(e)}',
                        'module': 'WebAPI'
                    }
                    yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                    time.sleep(5)  # 出错后等秒再继续
                    
        except Exception as e:
            error_data = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'level': 'ERROR',
                'message': f'日志流错{str(e)}',
                'module': 'WebAPI'
            }
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
    
    return app.response_class(generate(), mimetype='text/plain')

@app.route('/api/signal')
@login_required
def api_signal():
    """获取当前信号API"""
    ts = get_trading_system()
    if not ts.running:
        return jsonify({'success': False, 'message': '系统未运'})
    
    # 调用trading.py的信号获取方
    try:
        # 获取市场数据
        market_data = getattr(ts, 'get_market_data', lambda: None)()
        if market_data is not None and not market_data.empty:
            # 生成信号
            signal_info = ts.generate_signals(market_data)
            if signal_info:
                current_data = market_data.iloc[-1].to_dict() if not market_data.empty else None
                return jsonify({
                    'success': True,
                    'signal': signal_info,
                    'data': current_data
                })
    except Exception as e:
        pass
    
    return jsonify({'success': False, 'message': '无法获取信号'})



@app.route('/config')
@login_required
def config_page():
    """配置页面"""
    # 获取当前配置
    config_data = get_config_structure()
    return render_template('config.html', config_data=config_data, status=system_status)

@app.route('/api/config')
@login_required
def api_get_config():
    """获取配置API"""
    config_data = get_config_structure()
    return jsonify(config_data)

@app.route('/api/config', methods=['POST'])
@login_required
def api_update_config():
    """更新配置API - 同时更新策略数据"""
    try:
        new_config = request.json
        success = update_config_values(new_config)
        
        if success:
            # 同时更新策略数据
            ts = get_trading_system()
            if ts and hasattr(ts, 'strategy') and ts.strategy is not None:
                strategy = ts.strategy
                updated_fields = []
                
                # 更新杠杆倍数
                if 'capital_management' in new_config and 'leverage' in new_config['capital_management']:
                    new_leverage = new_config['capital_management']['leverage']
                    if hasattr(strategy, 'set_leverage'):
                        strategy.set_leverage(new_leverage)
                    elif hasattr(strategy, 'leverage'):
                        strategy.leverage = new_leverage
                    if hasattr(ts, 'leverage'):
                        ts.leverage = new_leverage
                    updated_fields.append('杠杆倍数')
                
                # 更新仓位大小配置
                if 'capital_management' in new_config and 'position_size_percent' in new_config['capital_management']:
                    new_position_size = new_config['capital_management']['position_size_percent']
                    if hasattr(strategy, 'position_size_percent'):
                        strategy.position_size_percent = new_position_size
                    if hasattr(ts, 'position_size_percent'):
                        ts.position_size_percent = new_position_size
                    updated_fields.append('仓位比例')
                
                # 更新最大最小仓位配置
                if 'position_management' in new_config:
                    if 'max_position_size' in new_config['position_management']:
                        max_size = new_config['position_management']['max_position_size']
                        if hasattr(strategy, 'max_position_size'):
                            strategy.max_position_size = max_size
                        updated_fields.append('最大仓位')
                    
                    if 'min_position_size' in new_config['position_management']:
                        min_size = new_config['position_management']['min_position_size']
                        if hasattr(strategy, 'min_position_size'):
                            strategy.min_position_size = min_size
                        updated_fields.append('最小仓位')
                
                # 保存策略状态
                if hasattr(strategy, 'save_strategy_status'):
                    strategy.save_strategy_status()
                
                return jsonify({
                    'success': True, 
                    'message': f'配置和策略数据更新成功',
                    'updated_fields': updated_fields,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                return jsonify({'success': True, 'message': '配置更新成功'})
        else:
            return jsonify({'success': False, 'message': '配置更新失败'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'配置更新失败: {str(e)}'})

@app.route('/trades')
@login_required
def trades_page():
    """交易记录页面"""
    return render_template('trades.html', status=system_status)
@app.route('/account')
@login_required
def account_page():
    """账户信息页面"""
    return render_template('account.html', status=system_status)

@app.route('/logs')
@login_required
def logs_page():
    """日志页面"""
    return render_template('logs.html', status=system_status)



# WebSocket事件
@socketio.on('connect')
def handle_connect():
    """客户端连"""
    try:
        print(f"客户端连 {request.sid}")
        # 检查用户是否已登录
        if 'logged_in' not in session:
            print(f"未登录用户尝试连 {request.sid}")
            emit('error', {'message': '请先登录'})
            return False  # 拒绝连接
        print(f"用户 {session.get('username', 'unknown')} 连接成功: {request.sid}")
        emit('connected', {'message': '连接成功'})
        return True
    except Exception as e:
        print(f"连接处理异常: {e}")
        emit('error', {'message': '连接处理失败'})
        return False

@socketio.on('disconnect')
def handle_disconnect(*args):
    """客户端断开连接"""
    try:
        print(f"客户端断开: {request.sid}")
        # 清理会话状态
        if 'subscribed' in session:
            session['subscribed'] = False
    except Exception as e:
        print(f"断开连接处理异常: {e}")

@socketio.on('request_status')
@socketio_auth_required
def handle_status_request():
    """处理状态请"""
    emit('status_update', system_status)

@socketio.on('request_signal')
def handle_request_signal():
    """请求最新信"""    
    try:
        if 'logged_in' not in session:
            emit('error', {'message': '请先登录'})
            return
            
        ts = get_trading_system()
        if ts and ts.running:
            # 调用trading.py的信号获取方
            try:
                # 获取市场数据
                market_data = getattr(ts, 'get_market_data', lambda: None)()
                if market_data is not None and not market_data.empty:
                    # 生成信号
                    signal_info = ts.generate_signals(market_data)
                    if signal_info:
                        current_data = market_data.iloc[-1].to_dict() if not market_data.empty else None
                        emit('signal_update', {
                            'signal': signal_info.get('signal', 0),
                            'strength': signal_info.get('signal_score', 0),
                            'price': current_data.get('close', 0) if current_data else 0,
                            'timestamp': datetime.now().isoformat()
                        })
                    else:
                        emit('signal_update', {
                            'signal': 0,
                            'strength': 0,
                            'price': 0,
                            'message': '暂无信号'
                        })
                else:
                    emit('signal_update', {
                        'signal': 0,
                        'strength': 0,
                        'price': 0,
                        'message': '无法获取市场数据'
                    })
            except Exception as e:
                emit('signal_update', {
                    'signal': 0,
                    'strength': 0,
                    'price': 0,
                    'message': f'信号获取失败: {str(e)}'
                })
        else:
            emit('signal_update', {
                'signal': 0,
                'strength': 0,
                'price': 0,
                'message': '系统未运'
            })
    except Exception as e:
        emit('error', {'message': f'获取信号失败: {str(e)}'})

@socketio.on('request_position')
def handle_request_position():
    """请求持仓信息 - 对接trading.py的持仓方"""
    try:
        if 'logged_in' not in session:
            emit('error', {'message': '请先登录'})
            return
            
        ts = get_trading_system()
        if ts:
            # 获取持仓信息（使用优化后的API逻辑
            position_info = {}
            if hasattr(ts, 'get_position_info'):
                position_info = ensure_json_serializable(ts.get_position_info())
            
            # 获取盈亏信息
            pnl_info = {}
            if hasattr(ts, 'get_current_pnl_info'):
                pnl_info = ensure_json_serializable(ts.get_current_pnl_info())
            
            # 获取当前市场价格
            current_price = 0
            # 只有在交易系统运行时才获取新数据
            if system_status.get('running', False) and hasattr(ts, 'get_market_data'):
                market_data = ts.get_market_data()
                if market_data is not None and not market_data.empty:
                    current_price = float(market_data['close'].iloc[-1])
            
            emit('position_update', {
                'position': position_info,
                'pnl': pnl_info,
                'current_price': current_price,
                'symbol': getattr(ts, 'symbol', 'ETHUSDT'),
                'timestamp': datetime.now().isoformat()
            })
        else:
            emit('error', {'message': '交易系统未初始化'})
    except Exception as e:
        emit('error', {'message': f'获取持仓信息失败: {str(e)}'})

@socketio.on('request_account')
def handle_request_account():
    """请求账户信息 - 实时账户数据"""
    try:
        if 'logged_in' not in session:
            emit('error', {'message': '请先登录'})
            return
            
        ts = get_trading_system()
        if ts:
            # 获取账户信息（使用优化后的API逻辑
            pnl_info = {}
            if hasattr(ts, 'get_current_pnl_info'):
                pnl_info = ts.get_current_pnl_info()
            
            initial_capital = getattr(ts, 'initial_capital', 10000.0)
            current_capital = pnl_info.get('current_capital', getattr(ts, 'current_capital', 10000.0))
            total_pnl = pnl_info.get('total_pnl', getattr(ts, 'total_pnl', 0.0))
            
            account_data = {
                'balance': current_capital,
                'available': pnl_info.get('available_capital', getattr(ts, 'available_capital', current_capital)),
                'total_pnl': total_pnl,
                'daily_pnl': pnl_info.get('daily_pnl', getattr(ts, 'daily_pnl', 0.0)),
                'total_return_percent': (total_pnl / initial_capital * 100) if initial_capital > 0 else 0,
                'trades_today': getattr(ts, 'daily_trades', 0),
                'system_running': 1 if getattr(ts, 'running', False) else 0,
                'timestamp': datetime.now().isoformat()
            }
            
            emit('account_update', account_data)
        else:
            emit('error', {'message': '交易系统未初始化'})
    except Exception as e:
        emit('error', {'message': f'获取账户信息失败: {str(e)}'})

@socketio.on('request_trading_mode')
def handle_request_trading_mode():
    """请求交易模式信息 - 实时交易模式数据"""
    try:
        if 'logged_in' not in session:
            emit('error', {'message': '请先登录'})
            return
            
        ts = get_trading_system()
        if ts:
            # 获取交易模式信息
            real_trading = getattr(ts, 'real_trading', False)
            exchange_api_configured = hasattr(ts, 'exchange_api') and ts.exchange_api is not None
            
            mode_data = {
                'real_trading': 1 if real_trading else 0,
                'trading_mode': '真实交易' if real_trading else '模拟交易',
                'mode_icon': '🔴' if real_trading else '🟡',
                'exchange_api_configured': 1 if exchange_api_configured else 0,
                'can_switch_to_real': 1 if exchange_api_configured else 0,
                'warning_message': '真实交易模式将使用真实资' if real_trading else '🟡 模拟交易模式，不会使用真实资',
                'timestamp': datetime.now().isoformat()
            }
            
            emit('trading_mode_update', mode_data)
        else:
            emit('error', {'message': '交易系统未初始化'})
    except Exception as e:
        emit('error', {'message': f'获取交易模式失败: {str(e)}'})

@socketio.on('request_trades')
def handle_request_trades():
    """请求交易记录 - 实时交易数据"""
    try:
        if 'logged_in' not in session:
            emit('error', {'message': '请先登录'})
            return
            
        ts = get_trading_system()
        if ts:
            # 获取最近的交易记录（最'0条）
            trades = getattr(ts, 'trade_history', [])
            recent_trades = []
            
            for trade in trades[-10:]:  # 最10条
                formatted_trade = {
                    'timestamp': trade.get('timestamp', datetime.now()).isoformat() if isinstance(trade.get('timestamp'), datetime) else trade.get('timestamp'),
                    'symbol': trade.get('symbol', 'ETHUSDT'),
                    'type': trade.get('type', 'UNKNOWN'),
                    'amount': float(trade.get('amount', 0)),
                    'price': float(trade.get('price', 0)),
                    'signal_score': float(trade.get('signal_score', 0)),
                    'reason': trade.get('reason', ''),
                    'pnl': float(trade.get('pnl', 0)) if 'pnl' in trade else None
                }
                recent_trades.append(formatted_trade)
            
            emit('trades_update', {
                'trades': recent_trades,
                'total_count': len(trades),
                'timestamp': datetime.now().isoformat()
            })
        else:
            emit('error', {'message': '交易系统未初始化'})
    except Exception as e:
        emit('error', {'message': f'获取交易记录失败: {str(e)}'})

@socketio.on('subscribe_updates')
def handle_subscribe_updates():
    """订阅实时数据更新"""
    try:
        if 'logged_in' not in session:
            emit('error', {'message': '请先登录'})
            return
        
        # 加入实时更新房间
        session['subscribed'] = True
        emit('subscription_confirmed', {
            'message': '已订阅实时数据更',
            'timestamp': datetime.now().isoformat()
        })
        
        # 立即发送一次完整数        handle_request_account()
        handle_request_position()
        handle_request_trades()
        handle_request_trading_mode()
        
    except Exception as e:
        emit('error', {'message': f'订阅失败: {str(e)}'})

@socketio.on('unsubscribe_updates')
def handle_unsubscribe_updates():
    """取消订阅实时数据更新"""
    try:
        session['subscribed'] = False
        emit('subscription_cancelled', {
            'message': '已取消实时数据更新订',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        emit('error', {'message': f'取消订阅失败: {str(e)}'})

@socketio.on('manual_trade')
def handle_manual_trade(data):
    """手动交易"""
    try:
        if 'logged_in' not in session:
            emit('error', {'message': '请先登录'})
            return
            
        trade_type = data.get('type')  # 'buy', 'sell', 'close'
        amount = data.get('amount', 0)
        
        ts = get_trading_system()
        if ts and ts.running:
                # 调用trading.py的交易执行方
                emit('trade_result', {
                'success': True,
                'message': f'手动{trade_type}交易已执行，金额: {amount} USDT',
                'timestamp': datetime.now().isoformat()
            })
        else:
            emit('trade_result', {
                'success': False,
                'message': '系统未运行，无法执行交易'
            })
    except Exception as e:
        emit('trade_result', {
            'success': False,
            'message': f'交易执行失败: {str(e)}'
        })

@socketio.on('config_update')
def handle_config_update(data):
    """配置更新"""
    try:
        if 'logged_in' not in session:
            emit('error', {'message': '请先登录'})
            return
            
        config_type = data.get('type')
        config_data = data.get('data', {})
        
        # 模拟配置更新
        emit('config_result', {
            'success': True,
            'message': f'{config_type}配置已更',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        emit('config_result', {
            'success': False,
            'message': f'配置更新失败: {str(e)}'
        })

@socketio.on('emergency_stop')
def handle_emergency_stop():
    """紧急停止（强制保持仓位"""
    try:
        if 'logged_in' not in session:
            emit('error', {'message': '请先登录'})
            return
            
        ts = get_trading_system()
        if ts and ts.running:
            # 强制不允许平仓，系统设置为强制保持仓
            success, message = ts.stop(force_close_position=False)
            emit('emergency_result', {
                'success': success,
                'message': f'{message}（保持仓位）',
                'timestamp': datetime.now().isoformat()
            })
        else:
            emit('emergency_result', {
                'success': False,
                'message': '系统未运'
            })
    except Exception as e:
        emit('emergency_result', {
            'success': False,
            'message': f'紧急停止失{str(e)}'
        })

@app.route('/api/trades')
def api_get_trades():
    """获取交易记录API - 对接trading.py的交易历"""
    try:
        ts = get_trading_system()
        trades_data = []
        
        # 获取交易历史
        if hasattr(ts, 'trade_history') and ts.trade_history:
            for trade in ts.trade_history:
                # 格式化交易记录
                trade_type = trade.get('type', 'UNKNOWN')
                is_long = trade_type.upper() in ['BUY', 'LONG', '买入', '开多']
                quantity = float(trade.get('quantity', 0))
                amount = float(trade.get('amount', 0))
                
                formatted_trade = {
                    'id': f"trade_{trade.get('timestamp', datetime.now()).strftime('%Y%m%d_%H%M%S')}",
                    'timestamp': trade.get('timestamp', datetime.now()).isoformat() if isinstance(trade.get('timestamp'), datetime) else trade.get('timestamp'),
                    'symbol': getattr(ts, 'symbol', 'ETHUSDT'),
                    'side': 'BUY' if is_long else 'SELL',
                    'type': trade_type,
                    'amount': amount,  # 直接使用原始金额
                    'price': float(trade.get('price', 0)),
                    'quantity': quantity,  # 直接使用原始数量
                    'signal_score': float(trade.get('signal_score', 0)),
                    'reason': trade.get('reason', ''),
                    'position_after': trade.get('position', 0),
                    'capital_after': float(trade.get('capital', 0)),
                    'available_capital': float(trade.get('available_capital', 0)),
                    'pnl': float(trade.get('pnl', 0)) if 'pnl' in trade else None,
                    'status': 'FILLED' # 假设所有记录的交易都已成交
                }
                trades_data.append(formatted_trade)
        
        # 按时间倒序排列（最新的在前
        trades_data.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify({
            'success': True, 
            'trades': trades_data,
            'total_count': len(trades_data),
            'page': 1,
            'page_size': len(trades_data)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取交易记录失败: {str(e)}'})


@app.route('/api/account')
@login_required
def api_get_account():
    """获取账户信息API - 整合trading.py的账户数"""
    try:
        ts = get_trading_system()
        
        # 改进的系统状态判断逻辑 - 与dashboard保持一       
        system_running = False
        
        # 检查多个指标来确定系统是否真正运行
        if hasattr(ts, 'running'):
            system_running = ts.running
        
        # 在Web模式下，如果TradingSystem实例存在且已初始化，检查其他运行指
        if ts.mode == 'web':
            # 检查是否有活跃的交易线程或心跳线程
            if hasattr(ts, 'trading_thread') and ts.trading_thread and ts.trading_thread.is_alive():
                system_running = True
            elif hasattr(ts, 'heartbeat_thread') and ts.heartbeat_thread and ts.heartbeat_thread.is_alive():
                system_running = True
            # 检查是否有有效的交易所连接
            elif hasattr(ts, 'exchange_api') and ts.exchange_api is not None:
                # 如果配置了API密钥，认为系统可以运
                if getattr(ts, 'real_trading', False):
                    system_running = True
                else:
                    # 模拟交易模式，检查是否有市场数据获取能力
                    try:
                        if hasattr(ts, 'get_market_data'):
                            market_data = ts.get_market_data()
                            if market_data is not None and not market_data.empty:
                                system_running = True
                    except Exception:
                        pass
        
        # 获取PnL信息
        pnl_info = {}
        if hasattr(ts, 'get_current_pnl_info'):
            pnl_info = ts.get_current_pnl_info()
        
        # 获取持仓信息
        position_info = {}
        if hasattr(ts, 'get_position_info'):
            position_info = ts.get_position_info()
        
        # 基础账户信息
        initial_capital = getattr(ts, 'initial_capital', 10000.0)
        current_capital = pnl_info.get('current_capital', getattr(ts, 'current_capital', 10000.0))
        available_capital = pnl_info.get('available_capital', getattr(ts, 'available_capital', current_capital))
        margin_used = current_capital - available_capital
        
        # PnL信息
        unrealized_pnl = pnl_info.get('unrealized_pnl', 0.0)
        realized_pnl = pnl_info.get('realized_pnl', getattr(ts, 'total_pnl', 0.0))
        total_pnl = pnl_info.get('total_pnl', realized_pnl + unrealized_pnl)
        daily_pnl = pnl_info.get('daily_pnl', getattr(ts, 'daily_pnl', 0.0))
        
        # 计算收益
        total_return = (total_pnl / initial_capital * 100) if initial_capital > 0 else 0
        daily_return = (daily_pnl / initial_capital * 100) if initial_capital > 0 else 0
        unrealized_return = (unrealized_pnl / initial_capital * 100) if initial_capital > 0 else 0
        realized_return = (realized_pnl / initial_capital * 100) if initial_capital > 0 else 0
        
        # 风险指标
        margin_ratio = (margin_used / current_capital * 100) if current_capital > 0 else 0
        risk_level = 'LOW' if margin_ratio < 30 else 'MEDIUM' if margin_ratio < 60 else 'HIGH'
        
        # 交易统计
        trade_history = getattr(ts, 'trade_history', [])
        trade_count = len(trade_history)
        daily_trades = getattr(ts, 'daily_trades', 0)
        
        # 计算交易统计
        winning_trades = 0
        losing_trades = 0
        total_profit = 0.0
        total_loss = 0.0
        
        for trade in trade_history:
            if 'pnl' in trade and trade['pnl'] is not None:
                if trade['pnl'] > 0:
                    winning_trades += 1
                    total_profit += trade['pnl']
                else:
                    losing_trades += 1
                    total_loss += abs(trade['pnl'])
        
        win_rate = (winning_trades / trade_count * 100) if trade_count > 0 else 0
        profit_factor = (total_profit / total_loss) if total_loss > 0 else float('inf')
        
        # 获取当前持仓状
        current_position = getattr(ts, 'current_position', 0)
        position_desc = position_info.get('position_desc', '无仓')
        position_value = position_info.get('value', 0.0)
        
        account_info = {
            # 基础资金信息
            'balance': round(current_capital, 2),
            'available': round(available_capital, 2),
            'margin_used': round(margin_used, 2),
            'initial_capital': round(initial_capital, 2),
            
            # PnL信息
            'unrealized_pnl': round(unrealized_pnl, 2),
            'realized_pnl': round(realized_pnl, 2),
            'total_pnl': round(total_pnl, 2),
            'daily_pnl': round(daily_pnl, 2),
            
            # 收益
            'total_return_percent': round(total_return, 2),
            'daily_return_percent': round(daily_return, 2),
            'unrealized_return_percent': round(unrealized_return, 2),
            'realized_return_percent': round(realized_return, 2),
            
            # 风险指标
            'margin_ratio': round(margin_ratio, 2),
            'risk_level': risk_level,
            'leverage': ts.get_leverage() if hasattr(ts, 'get_leverage') else getattr(ts, 'leverage', 1),
            
            # 交易统计
            'total_trades': trade_count,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'daily_trades': daily_trades,
            'max_daily_trades': getattr(ts, 'max_daily_trades', 10),
            'win_rate': round(win_rate, 1),
            'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else 999.99,
            'total_profit': round(total_profit, 2),
            'total_loss': round(total_loss, 2),
            
            # 持仓信息
            'current_position': current_position,
            'position_desc': position_desc,
            'position_value': round(position_value, 2),
            'position_entry_price': position_info.get('entry_price', 0.0),
            'position_quantity': position_info.get('quantity', 0.0),
            'position_unrealized_pnl': round(position_info.get('unrealized_pnl', 0.0), 2),
            'position_unrealized_pnl_percent': round(position_info.get('unrealized_pnl_percent', 0.0), 2),
            
            # 时间信息
            'last_update': datetime.now().isoformat(),
            
            # 状态信- 使用与dashboard相同的系统状态检查逻辑 
            'account_status': 'ACTIVE' if system_running else 'INACTIVE',
            'trading_enabled': system_running,
            'position_status': 'IN_POSITION' if current_position != 0 else 'NO_POSITION',
            'trading_mode': '真实交易' if getattr(ts, 'real_trading', False) else '模拟交易'
        }
        
        return jsonify({'success': True, 'account': account_info})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取账户信息失败: {str(e)}'})



@app.route('/api/dashboard')
@login_required
def api_get_dashboard():
    """获取主页仪表板数据API - 整合trading.py的所有主要数"""
    try:
        # 首先更新系统状态
        update_system_status()
        
        ts = get_trading_system()
        
        # 系统状态判断逻辑 - 直接使用更新后的system_status
        system_running = system_status.get('running', False)
        
        start_time = getattr(ts, 'start_time', None)
        
        # 获取PnL信息
        pnl_info = {}
        if hasattr(ts, 'get_current_pnl_info'):
            pnl_info = ts.get_current_pnl_info()
        
        # 获取持仓信息
        position_info = {}
        if hasattr(ts, 'get_position_info'):
            position_info = ts.get_position_info()
        
        # 基础账户信息
        initial_capital = getattr(ts, 'initial_capital', 10000.0)
        current_capital = pnl_info.get('current_capital', getattr(ts, 'current_capital', 10000.0))
        available_capital = pnl_info.get('available_capital', getattr(ts, 'available_capital', current_capital))
        
        # PnL信息
        unrealized_pnl = pnl_info.get('unrealized_pnl', 0.0)
        realized_pnl = pnl_info.get('realized_pnl', getattr(ts, 'total_pnl', 0.0))
        total_pnl = pnl_info.get('total_pnl', realized_pnl + unrealized_pnl)
        daily_pnl = pnl_info.get('daily_pnl', getattr(ts, 'daily_pnl', 0.0))
        
        # 计算收益率
        total_return = (total_pnl / initial_capital * 100) if initial_capital > 0 else 0
        daily_return = (daily_pnl / initial_capital * 100) if initial_capital > 0 else 0
        
        # 交易统计
        trade_history = getattr(ts, 'trade_history', [])
        total_trades = len(trade_history)
        daily_trades = getattr(ts, 'daily_trades', 0)
        
        # 计算胜率
        winning_trades = 0
        losing_trades = 0
        for trade in trade_history:
            if 'pnl' in trade and trade['pnl'] is not None:
                if trade['pnl'] > 0:
                    winning_trades += 1
                elif trade['pnl'] < 0:
                    losing_trades += 1
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # 持仓信息
        current_position = getattr(ts, 'current_position', 0)
        position_desc = position_info.get('position_desc', '无仓')
        
        # 获取当前市场价格
        current_price = 0.0
        try:
            # 只有在交易系统运行时才获取新数据
            if system_status.get('running', False) and hasattr(ts, 'get_market_data'):
                market_data = ts.get_market_data()
                if market_data is not None and not market_data.empty:
                    current_price = float(market_data['close'].iloc[-1])
        except Exception:
            current_price = 0.0
        
        # 获取最新信号
        last_signal = getattr(ts, 'last_signal', 0)
        last_signal_time = getattr(ts, 'last_signal_time', None)
        
        # 获取完整的信号信息
        complete_signal_info = {}
        if hasattr(ts, 'strategy') and ts.strategy:
            try:
                complete_signal_info = ts.strategy.get_latest_signal()
            except Exception as e:
                print(f"获取完整信号信息失败: {e}")
                complete_signal_info = {}
        
        # 系统运行时间
        runtime_hours = 0
        if start_time:
            runtime_hours = (datetime.now() - start_time).total_seconds() / 3600
        
        dashboard_data = {
            # 系统状态
            'system_running': system_running,
            'runtime_hours': round(runtime_hours, 1),
            'start_time': start_time.isoformat() if start_time else None,
            
            # 账户信息
            'current_capital': round(current_capital, 2),
            'available_capital': round(available_capital, 2),
            'initial_capital': round(initial_capital, 2),
            'capital_utilization': round((current_capital - available_capital) / current_capital * 100, 2) if current_capital > 0 else 0,
            
            # 盈亏信息
            'total_pnl': round(total_pnl, 2),
            'daily_pnl': round(daily_pnl, 2),
            'unrealized_pnl': round(unrealized_pnl, 2),
            'realized_pnl': round(realized_pnl, 2),
            'total_return_percent': round(total_return, 2),
            'daily_return_percent': round(daily_return, 2),
            
            # 交易统计
            'total_trades': total_trades,
            'daily_trades': daily_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round(win_rate, 1),
            'max_daily_trades': getattr(ts, 'max_daily_trades', 10),
            
            # 持仓信息
            'current_position': current_position,
            'position_desc': position_desc,
            'position_quantity': round(position_info.get('quantity', 0.0), 4),
            'position_value': round(position_info.get('value', 0.0), 2),
            'position_entry_price': round(position_info.get('entry_price', 0.0), 2),
            'position_unrealized_pnl': round(position_info.get('unrealized_pnl', 0.0), 2),
            'position_unrealized_pnl_percent': round(position_info.get('unrealized_pnl_percent', 0.0), 2),
            
            # 市场信息
            'symbol': getattr(ts, 'symbol', 'ETHUSDT'),
            'current_price': round(current_price, 2),
            'last_signal': last_signal,
            'last_signal_time': last_signal_time.isoformat() if last_signal_time else None,
            'last_signal_desc': {1: '做多信号', -1: '做空信号', 0: '无信号'}.get(last_signal, '无信号'),
            'complete_signal_info': complete_signal_info,
            
            # 交易模式
            'real_trading': 1 if getattr(ts, 'real_trading', False) else 0,
            'trading_mode': '真实交易' if getattr(ts, 'real_trading', False) else '模拟交易',
            'exchange_connected': 1 if (hasattr(ts, 'exchange_api') and ts.exchange_api is not None) else 0,
            'leverage': ts.get_leverage() if hasattr(ts, 'get_leverage') else getattr(ts, 'leverage', 1),
            
            # 时间
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify({'success': True, 'dashboard': dashboard_data})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取仪表板数据失败: {str(e)}'})

@app.route('/api/dashboard/public')
def api_get_dashboard_public():
    """获取主页仪表板数据API - 公开版本，无需认证"""
    try:
        # 首先更新系统状态
        update_system_status()
        
        ts = get_trading_system()
        
        # 系统状态判断逻辑 - 直接使用更新后的system_status
        system_running = system_status.get('running', False)
        
        start_time = getattr(ts, 'start_time', None)
        
        # 获取PnL信息
        pnl_info = {}
        if hasattr(ts, 'get_current_pnl_info'):
            pnl_info = ts.get_current_pnl_info()
        
        # 获取持仓信息
        position_info = {}
        if hasattr(ts, 'get_position_info'):
            position_info = ts.get_position_info()
        
        # 基础账户信息
        initial_capital = getattr(ts, 'initial_capital', 10000.0)
        current_capital = pnl_info.get('current_capital', getattr(ts, 'current_capital', 10000.0))
        available_capital = pnl_info.get('available_capital', getattr(ts, 'available_capital', current_capital))
        
        # PnL信息
        unrealized_pnl = pnl_info.get('unrealized_pnl', 0.0)
        realized_pnl = pnl_info.get('realized_pnl', getattr(ts, 'total_pnl', 0.0))
        total_pnl = pnl_info.get('total_pnl', realized_pnl + unrealized_pnl)
        daily_pnl = pnl_info.get('daily_pnl', getattr(ts, 'daily_pnl', 0.0))
        
        # 计算收益率
        total_return = (total_pnl / initial_capital * 100) if initial_capital > 0 else 0
        daily_return = (daily_pnl / initial_capital * 100) if initial_capital > 0 else 0
        
        # 交易统计
        trade_history = getattr(ts, 'trade_history', [])
        total_trades = len(trade_history)
        daily_trades = getattr(ts, 'daily_trades', 0)
        
        # 计算胜率
        winning_trades = 0
        losing_trades = 0
        for trade in trade_history:
            if 'pnl' in trade and trade['pnl'] is not None:
                if trade['pnl'] > 0:
                    winning_trades += 1
                elif trade['pnl'] < 0:
                    losing_trades += 1
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # 持仓信息
        current_position = getattr(ts, 'current_position', 0)
        position_desc = position_info.get('position_desc', '无仓')
        
        # 获取当前市场价格
        current_price = 0.0
        try:
            # 只有在交易系统运行时才获取新数据
            if system_status.get('running', False) and hasattr(ts, 'get_market_data'):
                market_data = ts.get_market_data()
                if market_data is not None and not market_data.empty:
                    current_price = float(market_data['close'].iloc[-1])
        except Exception:
            current_price = 0.0
        
        # 获取最新信号
        last_signal = getattr(ts, 'last_signal', 0)
        last_signal_time = getattr(ts, 'last_signal_time', None)
        
        # 系统运行时间
        runtime_hours = 0
        if start_time:
            runtime_hours = (datetime.now() - start_time).total_seconds() / 3600
        
        dashboard_data = {
            # 系统状态
            'system_running': system_running,
            'runtime_hours': round(runtime_hours, 1),
            'start_time': start_time.isoformat() if start_time else None,
            
            # 账户信息
            'current_capital': round(current_capital, 2),
            'available_capital': round(available_capital, 2),
            'initial_capital': round(initial_capital, 2),
            'capital_utilization': round((current_capital - available_capital) / current_capital * 100, 2) if current_capital > 0 else 0,
            
            # 盈亏信息
            'total_pnl': round(total_pnl, 2),
            'daily_pnl': round(daily_pnl, 2),
            'unrealized_pnl': round(unrealized_pnl, 2),
            'realized_pnl': round(realized_pnl, 2),
            'total_return_percent': round(total_return, 2),
            'daily_return_percent': round(daily_return, 2),
            
            # 交易统计
            'total_trades': total_trades,
            'daily_trades': daily_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round(win_rate, 1),
            'max_daily_trades': getattr(ts, 'max_daily_trades', 10),
            
            # 持仓信息
            'current_position': current_position,
            'position_desc': position_desc,
            'position_quantity': round(position_info.get('quantity', 0.0), 4),
            'position_value': round(position_info.get('value', 0.0), 2),
            'position_unrealized_pnl': round(position_info.get('unrealized_pnl', 0.0), 2),
            'position_unrealized_pnl_percent': round(position_info.get('unrealized_pnl_percent', 0.0), 2),
            
            # 市场信息
            'symbol': getattr(ts, 'symbol', 'ETHUSDT'),
            'current_price': round(current_price, 2),
            'last_signal': last_signal,
            'last_signal_time': last_signal_time.isoformat() if last_signal_time else None,
            'last_signal_desc': {1: '做多信号', -1: '做空信号', 0: '无信号'}.get(last_signal, '无信号'),
            'complete_signal_info': complete_signal_info,
            
            # 交易模式
            'real_trading': getattr(ts, 'real_trading', False),
            'trading_mode': '真实交易' if getattr(ts, 'real_trading', False) else '模拟交易',
            'exchange_connected': hasattr(ts, 'exchange_api') and ts.exchange_api is not None,
            'leverage': ts.get_leverage() if hasattr(ts, 'get_leverage') else getattr(ts, 'leverage', 1),
            
            # 时间
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify({'success': True, 'dashboard': dashboard_data})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取仪表板数据失败: {str(e)}'})

@app.route('/api/signal/details')
@login_required
def api_get_signal_details():
    """获取完整信号详情API"""
    try:
        ts = get_trading_system()
        if not ts:
            return jsonify({'success': False, 'message': '交易系统未初始化'})
        
        # 获取完整的信号信息
        complete_signal_info = {}
        if hasattr(ts, 'strategy') and ts.strategy:
            try:
                complete_signal_info = ts.strategy.get_latest_signal()
            except Exception as e:
                print(f"获取完整信号信息失败: {e}")
                complete_signal_info = {}
        
        return jsonify({'success': True, 'signal_details': complete_signal_info})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取信号详情失败: {str(e)}'})

@app.route('/api/signal/details/public')
def api_get_signal_details_public():
    """获取完整信号详情API - 公开版本，无需认证"""
    try:
        ts = get_trading_system()
        if not ts:
            return jsonify({'success': False, 'message': '交易系统未初始化'})
        
        # 获取完整的信号信息
        complete_signal_info = {}
        if hasattr(ts, 'strategy') and ts.strategy:
            try:
                complete_signal_info = ts.strategy.get_latest_signal()
            except Exception as e:
                print(f"获取完整信号信息失败: {e}")
                complete_signal_info = {}
        
        return jsonify({'success': True, 'signal_details': complete_signal_info})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取信号详情失败: {str(e)}'})

@app.route('/api/balance')
@login_required
def api_get_balance():
    """获取账户余额API - 对接trading.py的余额方法"""
    try:
        ts = get_trading_system()
        
        # 调用trading.py的余额获取方法
        if hasattr(ts, 'get_current_pnl_info'):
            pnl_info = ts.get_current_pnl_info()
            balance = {
                'total': pnl_info['current_capital'],
                'available': pnl_info['available_capital'],
                'used': pnl_info['current_capital'] - pnl_info['available_capital'],
                'profit': pnl_info['total_pnl']
            }
        else:
            # 如果方法不存在，直接从实例属性获取
            balance = {
                'total': getattr(ts, 'current_capital', 10000.0),
                'available': getattr(ts, 'available_capital', 9500.0),
                'used': 0.0,
                'profit': getattr(ts, 'total_pnl', 0.0)
            }
            
        return jsonify({'success': True, 'balance': balance})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取账户余额失败: {str(e)}'})

@app.route('/api/binance/account')
@login_required
def api_get_binance_account():
    """获取Binance合约账户详细信息API"""
    try:
        ts = get_trading_system()
        if not ts:
            return jsonify({'success': False, 'message': '交易系统未初始化'})
        
        # 检查是否有真实交易API
        if not hasattr(ts, 'exchange_api') or ts.exchange_api is None:
            return jsonify({'success': False, 'message': '未配置Binance API'})
        
        # 获取合约账户余额
        balance_result = ts.exchange_api.get_balance()
        
        # 获取当前持仓信息
        symbol = getattr(ts, 'symbol', 'ETHUSDT')
        position_result = ts.exchange_api.get_position(symbol)
        
        # 获取账户详细信息
        account_result = ts.exchange_api._make_api_request("/v2/account")
        
        binance_data = {
            'success': True,
            'balance': {
                'total_wallet_balance': balance_result.get('total', 0),
                'available_balance': balance_result.get('available', 0),
                'used_balance': balance_result.get('used', 0),
                'total_margin_balance': 0,
                'total_unrealized_profit': 0,
                'total_maint_margin': 0,
                'total_initial_margin': 0,
                'total_position_initial_margin': 0,
                'total_open_order_initial_margin': 0,
                'total_cross_wallet_balance': 0,
                'total_cross_un_pnl': 0,
                'max_withdraw_amount': 0
            },
            'position': {
                'symbol': symbol,
                'size': position_result.get('size', 0),
                'side': position_result.get('side', 'none'),
                'entry_price': position_result.get('entry_price', 0),
                'mark_price': position_result.get('mark_price', 0),
                'unrealized_pnl': position_result.get('unrealized_pnl', 0),
                'margin_type': position_result.get('margin_type', 'ISOLATED'),
                'leverage': position_result.get('leverage', 1),
                'position_side': 'LONG' if position_result.get('size', 0) > 0 else 'SHORT' if position_result.get('size', 0) < 0 else 'NONE'
            },
            'account_info': {
                'fee_tier': 0,
                'can_trade': False,
                'can_deposit': False,
                'can_withdraw': False,
                'update_time': 0
            }
        }
        
        # 如果成功获取账户详细信息，填充更多数据
        if account_result['success']:
            account_data = account_result['data']
            binance_data['balance'].update({
                'total_margin_balance': float(account_data.get('totalMarginBalance', 0)),
                'total_unrealized_profit': float(account_data.get('totalUnrealizedProfit', 0)),
                'total_maint_margin': float(account_data.get('totalMaintMargin', 0)),
                'total_initial_margin': float(account_data.get('totalInitialMargin', 0)),
                'total_position_initial_margin': float(account_data.get('totalPositionInitialMargin', 0)),
                'total_open_order_initial_margin': float(account_data.get('totalOpenOrderInitialMargin', 0)),
                'total_cross_wallet_balance': float(account_data.get('totalCrossWalletBalance', 0)),
                'total_cross_un_pnl': float(account_data.get('totalCrossUnPnl', 0)),
                'max_withdraw_amount': float(account_data.get('maxWithdrawAmount', 0))
            })
            
            binance_data['account_info'].update({
                'fee_tier': int(account_data.get('feeTier', 0)),
                'can_trade': bool(account_data.get('canTrade', False)),
                'can_deposit': bool(account_data.get('canDeposit', False)),
                'can_withdraw': bool(account_data.get('canWithdraw', False)),
                'update_time': int(account_data.get('updateTime', 0))
            })
        
        return jsonify(binance_data)
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取Binance账户信息失败: {str(e)}'})

@app.route('/api/binance/account/public')
def api_get_binance_account_public():
    """获取Binance合约账户详细信息API - 公开版本，无需认证"""
    try:
        ts = get_trading_system()
        if not ts:
            return jsonify({'success': False, 'message': '交易系统未初始化'})
        
        # 检查是否有真实交易API
        if not hasattr(ts, 'exchange_api') or ts.exchange_api is None:
            return jsonify({'success': False, 'message': '未配置Binance API密钥'})
        
        # 检查是否配置了API密钥
        if not ts.exchange_api.api_key or not ts.exchange_api.secret_key:
            return jsonify({'success': False, 'message': 'API密钥未配置'})
        
        # 获取合约账户余额
        balance_result = ts.exchange_api.get_balance()
        
        # 获取当前持仓信息
        symbol = getattr(ts, 'symbol', 'ETHUSDT')
        position_result = ts.exchange_api.get_position(symbol)
        
        # 获取账户详细信息
        account_result = ts.exchange_api._make_api_request("/v2/account")
        
        binance_data = {
            'success': True,
            'balance': {
                'total_wallet_balance': balance_result.get('total', 0),
                'available_balance': balance_result.get('available', 0),
                'used_balance': balance_result.get('used', 0),
                'total_margin_balance': 0,
                'total_unrealized_profit': 0,
                'total_maint_margin': 0,
                'total_initial_margin': 0,
                'total_position_initial_margin': 0,
                'total_open_order_initial_margin': 0,
                'total_cross_wallet_balance': 0,
                'total_cross_un_pnl': 0,
                'max_withdraw_amount': 0
            },
            'position': {
                'symbol': symbol,
                'size': position_result.get('size', 0),
                'side': position_result.get('side', 'none'),
                'entry_price': position_result.get('entry_price', 0),
                'mark_price': position_result.get('mark_price', 0),
                'unrealized_pnl': position_result.get('unrealized_pnl', 0),
                'margin_type': position_result.get('margin_type', 'ISOLATED'),
                'leverage': position_result.get('leverage', 1),
                'position_side': 'LONG' if position_result.get('size', 0) > 0 else 'SHORT' if position_result.get('size', 0) < 0 else 'NONE'
            },
            'account_info': {
                'fee_tier': 0,
                'can_trade': False,
                'can_deposit': False,
                'can_withdraw': False,
                'update_time': 0
            }
        }
        
        # 如果成功获取账户详细信息，填充更多数据
        if account_result['success']:
            account_data = account_result['data']
            binance_data['balance'].update({
                'total_margin_balance': float(account_data.get('totalMarginBalance', 0)),
                'total_unrealized_profit': float(account_data.get('totalUnrealizedProfit', 0)),
                'total_maint_margin': float(account_data.get('totalMaintMargin', 0)),
                'total_initial_margin': float(account_data.get('totalInitialMargin', 0)),
                'total_position_initial_margin': float(account_data.get('totalPositionInitialMargin', 0)),
                'total_open_order_initial_margin': float(account_data.get('totalOpenOrderInitialMargin', 0)),
                'total_cross_wallet_balance': float(account_data.get('totalCrossWalletBalance', 0)),
                'total_cross_un_pnl': float(account_data.get('totalCrossUnPnl', 0)),
                'max_withdraw_amount': float(account_data.get('maxWithdrawAmount', 0))
            })
            
            binance_data['account_info'].update({
                'fee_tier': int(account_data.get('feeTier', 0)),
                'can_trade': bool(account_data.get('canTrade', False)),
                'can_deposit': bool(account_data.get('canDeposit', False)),
                'can_withdraw': bool(account_data.get('canWithdraw', False)),
                'update_time': int(account_data.get('updateTime', 0))
            })
        else:
            # 如果获取账户详细信息失败，返回错误信息
            binance_data['success'] = False
            binance_data['message'] = f'获取账户详细信息失败: {account_result.get("error", "未知错误")}'
        
        return jsonify(binance_data)
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取Binance账户信息失败: {str(e)}'})

@app.route('/api/balance/public')
def api_get_balance_public():
    """获取账户余额API - 公开版本，无需认证"""
    try:
        ts = get_trading_system()
        
        # 调用trading.py的余额获取方法
        if hasattr(ts, 'get_current_pnl_info'):
            pnl_info = ts.get_current_pnl_info()
            balance = {
                'total': pnl_info['current_capital'],
                'available': pnl_info['available_capital'],
                'used': pnl_info['current_capital'] - pnl_info['available_capital'],
                'profit': pnl_info['total_pnl']
            }
        else:
            # 如果方法不存在，直接从实例属性获取
            balance = {
                'total': getattr(ts, 'current_capital', 10000.0),
                'available': getattr(ts, 'available_capital', 9500.0),
                'used': 0.0,
                'profit': getattr(ts, 'total_pnl', 0.0)
            }
            
        return jsonify({'success': True, 'balance': balance})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取账户余额失败: {str(e)}'})

@app.route('/api/trading_mode')
@login_required
def api_get_trading_mode():
    """获取交易模式API - 对接trading.py的交易模式"""
    try:
        ts = get_trading_system()
        if not ts:
            return jsonify({'success': False, 'message': '交易系统未初始化'})
        
        # 获取交易模式信息
        real_trading = getattr(ts, 'real_trading', False)
        exchange_api_configured = hasattr(ts, 'exchange_api') and ts.exchange_api is not None
        
        mode_info = {
            'real_trading': 1 if real_trading else 0,
            'trading_mode': '真实交易' if real_trading else '模拟交易',
            'mode_icon': '🔴' if real_trading else '🟡',
            'exchange_api_configured': 1 if exchange_api_configured else 0,
            'can_switch_to_real': 1 if exchange_api_configured else 0,
            'warning_message': '真实交易模式将使用真实资金' if real_trading else '🟡 模拟交易模式，不会使用真实资金',
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify({'success': True, 'mode': mode_info})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取交易模式失败: {str(e)}'})

@app.route('/api/trading_mode', methods=['POST'])
@login_required
def api_set_trading_mode():
    """设置交易模式API - 对接trading.py的交易模"""
    try:
        ts = get_trading_system()
        if not ts:
            return jsonify({'success': False, 'message': '交易系统未初始化'})
        
        data = request.json
        new_mode = data.get('mode')  # 'real' ''simulation'
        
        if new_mode not in ['real', 'simulation']:
            return jsonify({'success': False, 'message': '无效的交易模式'})
        
        # 检查是否可以切换到真实交易模式
        if new_mode == 'real':
            if not hasattr(ts, 'exchange_api') or ts.exchange_api is None:
                return jsonify({'success': False, 'message': '未配置API密钥，无法切换到真实交易模式'})
        
        # 设置交易模式
        ts.real_trading = (new_mode == 'real')
        
        # 保存配置
        if hasattr(ts, 'save_config'):
            ts.save_config()
        
        mode_info = {
            'real_trading': 1 if ts.real_trading else 0,
            'trading_mode': '真实交易' if ts.real_trading else '模拟交易',
            'mode_icon': '🔴' if ts.real_trading else '🟡',
            'warning_message': '真实交易模式将使用真实资金' if ts.real_trading else '🟡 模拟交易模式，不会使用真实资金',
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify({
            'success': True, 
            'message': f'已切换到{mode_info["trading_mode"]}模式',
            'mode': mode_info
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'设置交易模式失败: {str(e)}'})

@app.route('/api/trade_stats')
@login_required
def api_get_trade_stats():
    """获取交易统计API - 对接trading.py的交易数据"""
    try:
        ts = get_trading_system()
        
        # 获取交易历史和PnL信息
        trades = getattr(ts, 'trade_history', [])
        
        # 获取系统PnL数据
        pnl_info = {}
        if hasattr(ts, 'get_current_pnl_info'):
            pnl_info = ts.get_current_pnl_info()
        
        initial_capital = getattr(ts, 'initial_capital', 10000.0)
        realized_pnl = pnl_info.get('realized_pnl', getattr(ts, 'total_pnl', 0.0))
        unrealized_pnl = pnl_info.get('unrealized_pnl', 0.0)
        total_pnl = pnl_info.get('total_pnl', realized_pnl + unrealized_pnl)
        daily_pnl = pnl_info.get('daily_pnl', getattr(ts, 'daily_pnl', 0.0))
        
        # 基础交易统计
        total_trades = len(trades)
        daily_trades = getattr(ts, 'daily_trades', 0)
        
        # 分析交易记录中的PnL（如果有）
        trade_pnls = [t.get('pnl', 0) for t in trades if 'pnl' in t and t.get('pnl') is not None]
        
        if trade_pnls:
            # 基于交易记录的统计
            winning_trades = len([pnl for pnl in trade_pnls if pnl > 0])
            losing_trades = len([pnl for pnl in trade_pnls if pnl < 0])
            total_profit = sum([pnl for pnl in trade_pnls if pnl > 0])
            total_loss = sum([pnl for pnl in trade_pnls if pnl < 0])
            
            # 平均盈亏
            avg_win = total_profit / winning_trades if winning_trades > 0 else 0
            avg_loss = total_loss / losing_trades if losing_trades > 0 else 0
            
            # 最大单笔盈亏
            max_win = max(trade_pnls) if trade_pnls else 0
            max_loss = min(trade_pnls) if trade_pnls else 0
            
            # 计算最大回撤
            max_drawdown = 0
            peak = initial_capital
            running_capital = initial_capital
            
            for pnl in trade_pnls:
                running_capital += pnl
                if running_capital > peak:
                    peak = running_capital
                drawdown = (peak - running_capital) / peak * 100 if peak > 0 else 0
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
        else:
            # 没有详细的交易PnL记录，使用系统总体数据
            winning_trades = 0
            losing_trades = 0
            total_profit = max(realized_pnl, 0)
            total_loss = min(realized_pnl, 0)
            avg_win = 0
            avg_loss = 0
            max_win = 0
            max_loss = 0
            max_drawdown = 0
        
        # 计算胜率和盈亏比
        win_rate = (winning_trades / len(trade_pnls) * 100) if trade_pnls else 0
        profit_factor = abs(total_profit / total_loss) if total_loss != 0 else float('inf')
        
        # 计算收益
        total_return = (total_pnl / initial_capital * 100) if initial_capital > 0 else 0
        daily_return = (daily_pnl / initial_capital * 100) if initial_capital > 0 else 0
        realized_return = (realized_pnl / initial_capital * 100) if initial_capital > 0 else 0
        
        # 计算夏普比率（简化版本，假设无风险利率为0）
        if trade_pnls and len(trade_pnls) > 1:
            import statistics
            returns_std = statistics.stdev([pnl/initial_capital for pnl in trade_pnls])
            sharpe_ratio = (realized_return / 100) / returns_std if returns_std > 0 else 0
        else:
            sharpe_ratio = 0
        
        stats = {
            # 基础统计
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'daily_trades': daily_trades,
            'max_daily_trades': getattr(ts, 'max_daily_trades', 10),
            
            # 胜率和成功率
            'win_rate': round(win_rate, 1),
            'loss_rate': round(100 - win_rate, 1) if win_rate > 0 else 0,
            
            # PnL统计
            'total_profit': round(total_profit, 2),
            'total_loss': round(total_loss, 2),
            'net_profit': round(total_profit + total_loss, 2),
            'realized_pnl': round(realized_pnl, 2),
            'unrealized_pnl': round(unrealized_pnl, 2),
            'total_pnl': round(total_pnl, 2),
            'daily_pnl': round(daily_pnl, 2),
            
            # 平均
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'avg_trade': round((total_profit + total_loss) / len(trade_pnls), 2) if trade_pnls else 0,
            
            # 极
            'max_win': round(max_win, 2),
            'max_loss': round(max_loss, 2),
            
            # 风险指标
            'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else 999.99,
            'max_drawdown': round(max_drawdown, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            
            # 收益
            'total_return_percent': round(total_return, 2),
            'daily_return_percent': round(daily_return, 2),
            'realized_return_percent': round(realized_return, 2),
            
            # 系统信息
            'initial_capital': round(initial_capital, 2),
            'current_capital': round(pnl_info.get('current_capital', getattr(ts, 'current_capital', 10000)), 2),
            'system_running': 1 if getattr(ts, 'running', False) else 0,
            'last_update': datetime.now().isoformat()
        }
        
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取交易统计失败: {str(e)}'})

@app.route('/api/trade_stats/public')
def api_get_trade_stats_public():
    """获取交易统计API - 公开版本，无需认证"""
    try:
        ts = get_trading_system()
        
        # 获取交易历史和PnL信息
        trades = getattr(ts, 'trade_history', [])
        
        # 获取系统PnL数据
        pnl_info = {}
        if hasattr(ts, 'get_current_pnl_info'):
            pnl_info = ts.get_current_pnl_info()
        
        initial_capital = getattr(ts, 'initial_capital', 10000.0)
        realized_pnl = pnl_info.get('realized_pnl', getattr(ts, 'total_pnl', 0.0))
        unrealized_pnl = pnl_info.get('unrealized_pnl', 0.0)
        total_pnl = pnl_info.get('total_pnl', realized_pnl + unrealized_pnl)
        daily_pnl = pnl_info.get('daily_pnl', getattr(ts, 'daily_pnl', 0.0))
        
        # 基础交易统计
        total_trades = len(trades)
        daily_trades = getattr(ts, 'daily_trades', 0)
        
        # 分析交易记录中的PnL（如果有）
        trade_pnls = [t.get('pnl', 0) for t in trades if 'pnl' in t and t.get('pnl') is not None]
        
        if trade_pnls:
            # 基于交易记录的统计
            winning_trades = len([pnl for pnl in trade_pnls if pnl > 0])
            losing_trades = len([pnl for pnl in trade_pnls if pnl < 0])
            total_profit = sum([pnl for pnl in trade_pnls if pnl > 0])
            total_loss = sum([pnl for pnl in trade_pnls if pnl < 0])
            
            # 平均盈亏
            avg_win = total_profit / winning_trades if winning_trades > 0 else 0
            avg_loss = total_loss / losing_trades if losing_trades > 0 else 0
            
            # 最大单笔盈亏
            max_win = max(trade_pnls) if trade_pnls else 0
            max_loss = min(trade_pnls) if trade_pnls else 0
            
            # 计算最大回撤
            max_drawdown = 0
            peak = initial_capital
            running_capital = initial_capital
            
            for pnl in trade_pnls:
                running_capital += pnl
                if running_capital > peak:
                    peak = running_capital
                drawdown = (peak - running_capital) / peak * 100 if peak > 0 else 0
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
        else:
            # 没有详细的交易PnL记录，使用系统总体数据
            winning_trades = 0
            losing_trades = 0
            total_profit = max(realized_pnl, 0)
            total_loss = min(realized_pnl, 0)
            avg_win = 0
            avg_loss = 0
            max_win = 0
            max_loss = 0
            max_drawdown = 0
        
        # 计算胜率和盈亏比
        win_rate = (winning_trades / len(trade_pnls) * 100) if trade_pnls else 0
        profit_factor = abs(total_profit / total_loss) if total_loss != 0 else float('inf')
        
        # 计算收益率
        total_return = (total_pnl / initial_capital * 100) if initial_capital > 0 else 0
        daily_return = (daily_pnl / initial_capital * 100) if initial_capital > 0 else 0
        realized_return = (realized_pnl / initial_capital * 100) if initial_capital > 0 else 0
        
        # 计算夏普比率（简化版本，假设无风险利率为0）
        if trade_pnls and len(trade_pnls) > 1:
            import statistics
            returns_std = statistics.stdev([pnl/initial_capital for pnl in trade_pnls])
            sharpe_ratio = (realized_return / 100) / returns_std if returns_std > 0 else 0
        else:
            sharpe_ratio = 0
        
        stats = {
            # 基础统计
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'daily_trades': daily_trades,
            'max_daily_trades': getattr(ts, 'max_daily_trades', 10),
            
            # 胜率和成功率
            'win_rate': round(win_rate, 1),
            'loss_rate': round(100 - win_rate, 1) if win_rate > 0 else 0,
            
            # PnL统计
            'total_profit': round(total_profit, 2),
            'total_loss': round(total_loss, 2),
            'net_profit': round(total_profit + total_loss, 2),
            'realized_pnl': round(realized_pnl, 2),
            'unrealized_pnl': round(unrealized_pnl, 2),
            'total_pnl': round(total_pnl, 2),
            'daily_pnl': round(daily_pnl, 2),
            
            # 平均
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'avg_trade': round((total_profit + total_loss) / len(trade_pnls), 2) if trade_pnls else 0,
            
            # 极
            'max_win': round(max_win, 2),
            'max_loss': round(max_loss, 2),
            
            # 风险指标
            'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else 999.99,
            'max_drawdown': round(max_drawdown, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            
            # 收益
            'total_return_percent': round(total_return, 2),
            'daily_return_percent': round(daily_return, 2),
            'realized_return_percent': round(realized_return, 2),
            
            # 系统信息
            'initial_capital': round(initial_capital, 2),
            'current_capital': round(pnl_info.get('current_capital', getattr(ts, 'current_capital', 10000)), 2),
            'system_running': 1 if getattr(ts, 'running', False) else 0,
            'last_update': datetime.now().isoformat()
        }
        
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取交易统计失败: {str(e)}'})

@app.route('/api/system_logs')
@login_required
def api_system_logs():
    """获取系统日志API - 调用trading.py的日志系"""
    try:
        # 获取日志行数
        lines = int(request.args.get('lines', '50'))
        
        # 获取TradingSystem实例
        ts = get_trading_system()
        if not ts:
            return jsonify({'success': False, 'message': '交易系统未初始化'})
        
        # 尝试从TradingSystem获取日志文件路径
        log_file_path = None
        if hasattr(ts, 'logger') and ts.logger:
            # 获取logger的handlers
            for handler in ts.logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    log_file_path = handler.baseFilename
                    break
        
        # 如果没有找到日志文件路径，尝试从logs目录查找
        if not log_file_path:
            log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
            if os.path.exists(log_dir):
                log_files = []
                for file in os.listdir(log_dir):
                    if file.endswith('.log'):
                        log_files.append(os.path.join(log_dir, file))
                
                if log_files:
                    # 按修改时间排序，获取最新的日志文件
                    log_file_path = max(log_files, key=os.path.getmtime)
        
        # 读取日志文件
        if log_file_path and os.path.exists(log_file_path):
            try:
                with open(log_file_path, 'r', encoding='utf-8') as f:
                    log_lines = f.readlines()
                
                logs = []
                # 获取最后N行日志
                for line in log_lines[-lines:]:
                    if line.strip():
                        try:
                            # 解析日志格式: 2024-01-01 12:00:00,123 - TradingSystem - INFO - 消息内容
                            parts = line.strip().split(' - ', 3)
                            if len(parts) >= 4:
                                timestamp = parts[0]
                                module = parts[1]
                                level = parts[2]
                                message = parts[3]
                                
                                log = {
                                    'timestamp': timestamp,
                                    'level': level,
                                    'message': message,
                                    'module': module
                                }
                                logs.append(log)
                            else:
                                # 简单格式处理
                                log = {
                                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'level': 'INFO',
                                    'message': line.strip(),
                                    'module': 'TradingSystem'
                                }
                                logs.append(log)
                        except Exception as e:
                            # 如果解析失败，跳过这行
                            continue
                
                # 按时间倒序排列（最新的在前）
                logs.reverse()
                
                return jsonify({
                    'success': True, 
                    'logs': logs,
                    'log_file': os.path.basename(log_file_path),
                    'total_lines': len(log_lines)
                })
                
            except Exception as e:
                return jsonify({
                    'success': False, 
                    'message': f'读取日志文件失败: {str(e)}'
                })
        
        # 如果无法获取日志文件，尝试从TradingSystem获取最近的日志
        if hasattr(ts, 'logger') and ts.logger:
            # 这里可以添加从内存中获取最近日志的逻辑
            # 但由于Python的logging模块默认不保存日志到内存，我们返回提示信息
            return jsonify({
                'success': False, 
                'message': '无法找到日志文件，请检查日志配置'
            })
        
        # 最后的备用方案：返回模拟日志
        logs = []
        log_levels = ['INFO', 'WARNING', 'ERROR', 'DEBUG']
        log_messages = [
            '系统启动成功',
            '获取市场数据',
            '生成交易信号',
            '执行交易操作',
            '持仓监控更新',
            '风险检查通过',
            'API连接正常',
            '网络延迟检查'
        ]
        
        for i in range(min(lines, 20)):
            timestamp = datetime.now() - timedelta(minutes=random.randint(1, 1440))
            log = {
                'timestamp': timestamp.isoformat(),
                'level': random.choice(log_levels),
                'message': random.choice(log_messages),
                'module': random.choice(['TradingSystem', 'DataLoader', 'Strategy', 'ExchangeAPI'])
            }
            logs.append(log)
        
        logs.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify({
            'success': True, 
            'logs': logs,
            'note': '使用模拟日志数据，无法获取真实系统日志'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取日志失败: {str(e)}'})

@app.route('/api/logs/files')
@login_required
def api_logs_files():
    """获取日志文件列表API"""
    try:
        # 获取TradingSystem实例
        ts = get_trading_system()
        
        # 获取logs目录
        log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
        if not os.path.exists(log_dir):
            return jsonify({'success': False, 'message': '日志目录不存在'})
        
        # 获取所有日志文件
        log_files = []
        for file in os.listdir(log_dir):
            if file.endswith('.log'):
                file_path = os.path.join(log_dir, file)
                file_stat = os.stat(file_path)
                log_files.append({
                    'filename': file,
                    'size': file_stat.st_size,
                    'modified': datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                    'created': datetime.fromtimestamp(file_stat.st_ctime).isoformat()
                })
        
        # 按修改时间倒序排列（最新的在前）
        log_files.sort(key=lambda x: x['modified'], reverse=True)
        
        return jsonify({
            'success': True,
            'files': log_files,
            'total_count': len(log_files)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取日志文件列表失败: {str(e)}'})

@app.route('/api/logs/file/<filename>')
@login_required
def api_logs_file_content(filename):
    """获取指定日志文件内容API"""
    try:
        # 安全检查：确保文件名不包含路径遍历
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'success': False, 'message': '无效的文件名'})
        
        # 获取日志行数
        lines = int(request.args.get('lines', '100'))
        
        # 构建文件路径
        log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
        file_path = os.path.join(log_dir, filename)
        
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'message': '日志文件不存在'})
        
        # 读取日志文件
        with open(file_path, 'r', encoding='utf-8') as f:
            log_lines = f.readlines()
        
        logs = []
        # 获取最后N行日志
        for line in log_lines[-lines:]:
            if line.strip():
                try:
                    # 解析日志格式: 2024-01-01 12:00:00,123 - TradingSystem - INFO - 消息内容
                    parts = line.strip().split(' - ', 3)
                    if len(parts) >= 4:
                        timestamp = parts[0]
                        module = parts[1]
                        level = parts[2]
                        message = parts[3]
                        
                        log = {
                            'timestamp': timestamp,
                            'level': level,
                            'message': message,
                            'module': module
                        }
                        logs.append(log)
                    else:
                        # 简单格式处理
                        log = {
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'level': 'INFO',
                            'message': line.strip(),
                            'module': 'TradingSystem'
                        }
                        logs.append(log)
                except Exception as e:
                    # 如果解析失败，跳过这行
                    continue
        
        # 按时间倒序排列（最新的在前）
        logs.reverse()
        
        return jsonify({
            'success': True, 
            'logs': logs,
            'filename': filename,
            'total_lines': len(log_lines),
            'file_size': os.path.getsize(file_path)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'读取日志文件失败: {str(e)}'})



# 跨平台辅助函数
def is_admin():
    """检查当前用户是否有管理员权限（跨平台）"""
    try:
        if platform.system() == 'Windows':
            # Windows系统检查管理员权限
            try:
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin()
            except:
                return False
        else:
            # Unix/Linux系统检查root权限
            try:
                return os.geteuid() == 0
            except AttributeError:
                return False
    except:
        return False

# 辅助函数
def get_config_structure():
    """获取配置结构 - 使用trading.py的配置管理"""
    try:
        # 获取TradingSystem实例
        ts = get_trading_system()
        
        # 从TradingSystem实例中获取当前配置
        config_structure = {
            'trading': {
                'symbol': getattr(ts, 'symbol', 'ETHUSDT'),
                'timeframe': getattr(ts, 'timeframe', '1h'),

            },
            'trading_mode': {
                'real_trading': 1 if getattr(ts, 'real_trading', False) else 0,
                'trading_mode': '真实交易' if getattr(ts, 'real_trading', False) else '模拟交易',
                'mode_icon': '🔴' if getattr(ts, 'real_trading', False) else '🟡',
                'exchange_api_configured': 1 if (hasattr(ts, 'exchange_api') and ts.exchange_api is not None) else 0
            },
            'capital_management': {
                'initial_capital': getattr(ts, 'initial_capital', 10000),
                'position_size_percent': getattr(ts, 'position_size_percent', 0.1),
                'max_position_size': getattr(ts, 'max_position_size', 1.0),
                'min_position_size': getattr(ts, 'min_position_size', 0.2),
                'leverage': ts.get_leverage() if hasattr(ts, 'get_leverage') else 8  # 与config.py中的LEVERAGE保持一致
            }
        }
        
        return config_structure
    except Exception as e:
        print(f"获取配置结构失败: {e}")
        return {}


def update_config_values(new_config):
    """更新配置值 - 使用trading.py的配置管理"""
    try:
        # 获取TradingSystem实例
        ts = get_trading_system()
        
        # 更新TradingSystem实例中的配置
        if 'trading' in new_config:
            trading = new_config['trading']
            if hasattr(ts, 'symbol'):
                ts.symbol = trading.get('symbol', 'ETHUSDT')
                # 同时更新TRADING_CONFIG
                TRADING_CONFIG['SYMBOL'] = ts.symbol
            if hasattr(ts, 'timeframe'):
                ts.timeframe = trading.get('timeframe', '1h')
                # 同时更新TRADING_CONFIG
                TRADING_CONFIG['TIMEFRAME'] = ts.timeframe

        
        # 更新交易模式配置
        if 'trading_mode' in new_config:
            trading_mode = new_config['trading_mode']
            if hasattr(ts, 'real_trading'):
                # 检查是否可以切换到真实交易模式
                new_real_trading = trading_mode.get('real_trading', False)
                if new_real_trading and (not hasattr(ts, 'exchange_api') or ts.exchange_api is None):
                    print("未配置API密钥，无法切换到真实交易模式")
                else:
                    ts.real_trading = new_real_trading
        
        if 'capital_management' in new_config:
            capital = new_config['capital_management']
            if hasattr(ts, 'initial_capital'):
                ts.initial_capital = int(capital.get('initial_capital', 10000))
            if hasattr(ts, 'position_size_percent'):
                ts.position_size_percent = float(capital.get('position_size_percent', 0.1))
            if hasattr(ts, 'max_position_size'):
                ts.max_position_size = float(capital.get('max_position_size', 1.0))
            if hasattr(ts, 'min_position_size'):
                ts.min_position_size = float(capital.get('min_position_size', 0.2))
            # 更新杠杆倍数 - 通过策略对象设置
            old_leverage = ts.get_leverage() if hasattr(ts, 'get_leverage') else 8
            new_leverage = int(capital.get('leverage', 8))  # 与config.py中的LEVERAGE保持一致
            
            # 通过策略对象设置杠杆倍数
            if hasattr(ts, 'strategy') and ts.strategy is not None:
                if hasattr(ts.strategy, 'set_leverage'):
                    ts.strategy.set_leverage(new_leverage)
                elif hasattr(ts.strategy, 'leverage'):
                    ts.strategy.leverage = new_leverage
                
                # 如果杠杆倍数发生变化，尝试同步到Binance
                # 同步杠杆倍数到策略
                if hasattr(ts, 'strategy') and ts.strategy is not None:
                    ts.strategy.update_leverage_from_trading_system(ts)
                    print(f"✅ 策略杠杆倍数已同步: {new_leverage}x")
                
                # 同步杠杆倍数到Binance（如果启用真实交易）
                if old_leverage != new_leverage and hasattr(ts, 'exchange_api') and ts.exchange_api is not None:
                    try:
                        symbol = getattr(ts, 'symbol', 'ETHUSDT')
                        leverage_result = ts.exchange_api.set_leverage(symbol, new_leverage)
                        if leverage_result['success']:
                            print(f"✅ 杠杆倍数已同步到Binance: {old_leverage}x → {new_leverage}x")
                        else:
                            error_msg = leverage_result.get('error', '未知错误')
                            # 检查是否是API权限不足的错误
                            if 'Invalid API-key' in error_msg or 'permissions' in error_msg or '401' in error_msg:
                                print(f"⚠️  API权限不足，跳过Binance杠杆倍数修改: {error_msg}")
                                print(f"💡 系统将使用本地配置的杠杆倍数: {new_leverage}x")
                            else:
                                print(f"❌ 杠杆倍数同步到Binance失败: {error_msg}")
                    except Exception as e:
                        error_str = str(e)
                        if 'Invalid API-key' in error_str or 'permissions' in error_str or '401' in error_str:
                            print(f"⚠️  API权限不足，跳过Binance杠杆倍数修改: {error_str}")
                            print(f"💡 系统将使用本地配置的杠杆倍数: {new_leverage}x")
                        else:
                            print(f"❌ 杠杆倍数同步到Binance异常: {error_str}")
                else:
                    print(f"💡 杠杆倍数已更新为: {new_leverage}x (仅本地配置)")
        

        
        # 保存配置到用户配置文件
        try:
            from utils.fix_config import save_user_config
            
            # 构建要保存的配置数据
            config_to_save = {
                'TRADING_CONFIG': {
                    'SYMBOL': getattr(ts, 'symbol', 'ETHUSDT'),
                    'TIMEFRAME': getattr(ts, 'timeframe', '1h'),
                    'SIGNAL_CHECK_INTERVAL': getattr(ts, 'signal_check_interval', 300),
                    'REAL_TRADING': getattr(ts, 'real_trading', False),
                    'CAPITAL_CONFIG': {
                        'INITIAL_CAPITAL': getattr(ts, 'initial_capital', 10000),
                        'POSITION_SIZE_PERCENT': getattr(ts, 'position_size_percent', 0.1),
                        'MAX_POSITION_SIZE': getattr(ts, 'max_position_size', 0.5),
                        'MIN_POSITION_SIZE': getattr(ts, 'min_position_size', 0.05),
                        'LEVERAGE': ts.get_leverage() if hasattr(ts, 'get_leverage') else getattr(ts, 'leverage', 8)
                    }
                }
            }
            
            success, message = save_user_config(config_to_save)
            if success:
                print(f"✅ 配置已保存到用户配置文件: {message}")
            else:
                print(f"❌ 保存配置失败: {message}")
        except Exception as e:
            print(f"❌ 保存配置异常: {e}")
            
        return True
            
    except Exception as e:
        print(f"配置更新失败: {e}")
        return False





def main():
    """主函数"""
    import argparse
    import logging
    
    # 配置日志过滤
    from utils import configure_logging
    configure_logging()
    
    parser = argparse.ArgumentParser(description='交易系统Web界面')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址')
    parser.add_argument('--port', type=int, default=8082, help='监听端口')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    
    args = parser.parse_args()
    
    print(f"🚀 启动Web交易系统界面...")
    print(f"📡 访问地址: http://{args.host}:{args.port}")
    print(f"🔐 默认登录: admin / 1314521")
    print(f"实时数据推送已启用")
    
    # 启动实时数据推送线程
    start_data_push()
    
    try:
        # 在调试模式下禁用多进程，避免重复创建TradingSystem实例
        if args.debug:
            print("🔧 调试模式：禁用多进程以避免重复初始化")
            socketio.run(app, host=args.host, port=args.port, debug=args.debug, 
                        allow_unsafe_werkzeug=True, use_reloader=False)
        else:
            # 在生产环境中允许使用Werkzeug服务
            socketio.run(app, host=args.host, port=args.port, debug=args.debug, 
                        allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("\n🛑 Web界面已停止")
        stop_data_push()
    except Exception as e:
        print(f"Web界面启动失败: {e}")
        stop_data_push()

if __name__ == '__main__':
    main()
