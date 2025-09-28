#!/usr/bin/env python38
# -*- coding: utf-8 -*-
"""
Web界面启动脚本
快速启动交易系统Web管理界面
"""

import sys
import os
import webbrowser
import time
from threading import Timer
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def main():
    """启动Web界面"""
    try:
        # 配置日志过滤
        from utils import configure_logging
        configure_logging()
        
        # 检查Flask依赖
        try:
            import flask
            import flask_socketio
        except ImportError:
            print(" 缺少Web界面依赖")
            print("请运行以下命令安装:")
            print("pip install Flask Flask-SocketIO Werkzeug")
            return
        
        print("🚀 启动Web管理界面...")
        print("=" * 50)
        
        # 设置环境变量
        os.environ['FLASK_ENV'] = 'development'
        
        # 检查是否在正确目录
        if not os.path.exists('web/app.py'):
            print(" 错误：请在项目根目录运行此脚本")
            print("当前目录应该包含 web/app.py 文件")
            return
        
        print("📡 Web服务器启动中...")
        print("🌐 管理界面地址:http://exchange1.vivanest.cc:8082")
        print("🌐 配置界面地址: http://exchange1.vivanest.cc:8082/config")
        print("💡 3秒后将自动打开配置页面")
        print("📋 按 Ctrl+C 停止服务器")
        print("=" * 50)
        
        # 导入并启动Web界面
        from web.app import main as web_main
        web_main()
        
    except KeyboardInterrupt:
        print("\n🛑 Web界面已停止")
    except Exception as e:
        print(f"Web界面启动失败: {e}")
        import traceback
        print(f"异常堆栈: {traceback.format_exc()}")

if __name__ == '__main__':
    main() 