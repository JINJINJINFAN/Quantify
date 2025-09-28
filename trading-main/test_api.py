#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API连接测试脚本
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

try:
    from core.exchange_api import RealExchangeAPI
    from config import *
except ImportError as e:
    print(f"导入模块失败: {e}")
    sys.exit(1)

def test_api_connection():
    """测试API连接"""
    print("🔍 开始测试Binance API连接...")
    
    # 获取API密钥
    api_key = os.getenv('BINANCE_API_KEY', '')
    secret_key = os.getenv('BINANCE_SECRET_KEY', '')
    
    if not api_key or not secret_key:
        print("❌ API密钥未配置")
        return False
    
    print(f"✅ API密钥已配置: {api_key[:10]}...{api_key[-4:]}")
    
    # 初始化API
    try:
        exchange_api = RealExchangeAPI(api_key=api_key, secret_key=secret_key)
        print("✅ API对象创建成功")
    except Exception as e:
        print(f"❌ API对象创建失败: {e}")
        return False
    
    # 测试基础连接
    print("\n📡 测试基础连接...")
    success, message = exchange_api.test_connection()
    if success:
        print(f"✅ {message}")
    else:
        print(f"❌ {message}")
        return False
    
    # 测试账户信息
    print("\n💰 测试账户信息...")
    balance_result = exchange_api.get_balance()
    if balance_result['success']:
        print(f"✅ 账户余额: 总={balance_result['total']:.2f} USDT, 可用={balance_result['available']:.2f} USDT")
    else:
        print(f"❌ 获取账户信息失败: {balance_result['error']}")
        return False
    
    # 测试持仓信息
    print("\n📊 测试持仓信息...")
    position = exchange_api.get_position('ETHUSDT')
    if position:
        print(f"✅ 当前持仓: {position['size']} ETH, 杠杆: {position['leverage']}x")
    else:
        print("❌ 获取持仓信息失败")
        return False
    
    # 测试保证金类型设置（如果没有持仓）
    if position['size'] == 0:
        print("\n🔧 测试保证金类型设置...")
        margin_result = exchange_api.set_margin_type('ETHUSDT', 'ISOLATED')
        if margin_result['success']:
            print(f"✅ {margin_result['message']}")
        else:
            print(f"⚠️ {margin_result['error']}")
    
    # 测试杠杆设置（如果没有持仓）
    if position['size'] == 0:
        print("\n⚡ 测试杠杆设置...")
        leverage_result = exchange_api.set_leverage('ETHUSDT', 8)
        if leverage_result['success']:
            print(f"✅ {leverage_result['message']}")
        else:
            print(f"⚠️ {leverage_result['error']}")
    
    print("\n🎉 API连接测试完成！")
    return True

if __name__ == '__main__':
    test_api_connection()