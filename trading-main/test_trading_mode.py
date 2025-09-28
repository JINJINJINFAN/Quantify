#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试交易模式配置
"""

import os
from dotenv import load_dotenv
load_dotenv()

def test_config():
    print("=== 交易系统配置测试 ===")
    
    # 1. 检查API密钥
    api_key = os.getenv('BINANCE_API_KEY', '')
    secret_key = os.getenv('BINANCE_SECRET_KEY', '')
    print(f"API密钥状态: {'已配置' if api_key and secret_key else '未配置'}")
    
    # 2. 检查用户配置文件
    try:
        from utils.fix_config import load_user_config
        success, message, config = load_user_config()
        if success:
            print(f"用户配置: 加载成功")
            real_trading = config.get('TRADING_CONFIG', {}).get('REAL_TRADING', False)
            print(f"配置中的交易模式: {'真实交易' if real_trading else '模拟交易'}")
        else:
            print(f"用户配置: 加载失败 - {message}")
    except Exception as e:
        print(f"用户配置: 检查失败 - {e}")
    
    # 3. 测试交易系统初始化
    try:
        from trading import TradingSystem
        ts = TradingSystem(mode='service')
        
        real_trading_mode = getattr(ts, 'real_trading', False)
        api_configured = hasattr(ts, 'exchange_api') and ts.exchange_api is not None
        
        print(f"交易系统模式: {'真实交易' if real_trading_mode else '模拟交易'}")
        print(f"API对象状态: {'已创建' if api_configured else '未创建'}")
        
        if api_configured:
            # 测试API连接
            success, message = ts.exchange_api.test_connection()
            print(f"API连接测试: {'成功' if success else '失败'} - {message}")
            
            # 测试账户信息
            balance = ts.exchange_api.get_balance()
            if balance['success']:
                print(f"账户余额: 总={balance['total']:.2f} USDT, 可用={balance['available']:.2f} USDT")
            else:
                print(f"账户余额获取失败: {balance['error']}")
        
        return real_trading_mode
        
    except Exception as e:
        print(f"交易系统初始化失败: {e}")
        return False

if __name__ == '__main__':
    is_real_trading = test_config()
    print("\n=== 测试结果 ===")
    if is_real_trading:
        print("✅ 真实交易模式已启用")
    else:
        print("⚠️ 当前为模拟交易模式")
        print("请检查:")
        print("1. API密钥是否正确配置")
        print("2. API密钥是否有期货交易权限")
        print("3. json/config.json文件是否正确设置")