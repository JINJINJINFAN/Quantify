# -*- coding: utf-8 -*-
"""
Telegram通知模块

功能：
1. 发送交易信号通知
2. 发送交易执行结果通知
3. 发送系统状态通知
4. 发送错误警告通知
"""

import asyncio
import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import requests
import json
from config import TELEGRAM_CONFIG

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """Telegram通知器"""
    
    def __init__(self, bot_token: str = None, chat_id: str = None):
        """初始化Telegram通知器"""
        self.bot_token = bot_token or TELEGRAM_CONFIG.get('BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or TELEGRAM_CONFIG.get('CHAT_ID') or os.getenv('TELEGRAM_CHAT_ID')
        
        self.enabled = bool(self.bot_token and self.chat_id)
        
        # 添加评分缓存，用于避免重复发送相同评分的消息
        self.last_signal_score = None
        self.last_signal_time = None
        
        if not self.enabled:
            logger.warning("Telegram通知未配置：缺少BOT_TOKEN或CHAT_ID")
        else:
            logger.info(" Telegram通知器初始化成功")
    
    def _clean_html_text(self, text: str) -> str:
        """清理文本中的HTML特殊字符"""
        if not text:
            return ""
        
        # 移除所有HTML标签（先处理）
        import re
        text = re.sub(r'<[^>]*>', '', text)
        
        # 替换HTML特殊字符
        text = text.replace('<', '&lt;').replace('>', '&gt;')
        text = text.replace('&', '&amp;')
        
        # 移除多余的空格和换行
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _format_signal_message(self, signal_data: Dict[str, Any]) -> str:
        """格式化信号消息"""
        signal_type = signal_data.get('signal', 0)
        price = signal_data.get('price', 0)
        score = signal_data.get('score', 0)
        reason = signal_data.get('reason', '')
        investment_advice = signal_data.get('investment_advice', '')
        signal_from = signal_data.get('signal_from', 'unknown')  # 新增：信号来源
        
        # 清理所有文本字段
        clean_reason = self._clean_html_text(reason)
        clean_advice = self._clean_html_text(investment_advice)
        
        # 信号图标
        if signal_type == 1:
            signal_icon = "🟢"
            signal_text = "多头信号"
        elif signal_type == -1:
            signal_icon = "🔴"
            signal_text = "空头信号"
        else:
            signal_icon = "⚪"
            signal_text = "观望信号"
        
        # 信号来源图标和文本
        if signal_from == 'traditional':
            source_icon = "📊"
            source_text = "指标分析"
        elif signal_from == 'deepseek':
            source_icon = "🤖"
            source_text = "DeepSeek AI分析"
        elif signal_from == 'integrated':
            source_icon = "🔄"
            source_text = "指标+AI整合"
        else:
            source_icon = "❓"
            source_text = "未知来源"
        
        # 构建消息 - 使用更安全的HTML格式
        message = f"🚨 <b>ETHUSDT交易信号</b>\n\n"
        message += f"{signal_icon} <b>{signal_text}</b>\n"
        message += f"{source_icon} <b>信号来源: {source_text}</b>\n"
        message += f"💰 当前价格: <code>${price:,.2f}</code>\n"
        message += f"综合评分: <code>{score:.3f}</code>\n"
        message += f"🔍 信号原因: {clean_reason}\n"
        
        # 添加投资建议
        if clean_advice:
            message += f"\n📋 <b>投资建议:</b>\n{clean_advice}\n"
        
        message += f"\n🕐 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += f"时间级别: 1h"
        
        return message
    
    def _format_trade_message(self, trade_data: Dict[str, Any]) -> str:
        """格式化交易消息"""
        action = trade_data.get('action')  # 'open', 'close'
        side = trade_data.get('side')      # 'long', 'short'
        price = trade_data.get('price', 0)
        quantity = trade_data.get('quantity', 0)
        pnl = trade_data.get('pnl')  # 允许为None
        reason = trade_data.get('reason', '')  # 平仓原因
        
        if action == 'open':
            action_icon = "📈" if side == 'long' else "📉"
            action_text = f"开仓 - {'做多' if side == 'long' else '做空'}"
        else:
            action_icon = "💰" if pnl is not None and pnl > 0 else "💸"
            action_text = "平仓"
        
        # 构建消息 - 使用更安全的HTML格式
        message = f"{action_icon} <b>ETHUSDT交易执行</b>\n\n"
        message += f"操作: <b>{action_text}</b>\n"
        message += f"💰 价格: <code>${price:,.2f}</code>\n"
        message += f"数量: <code>{quantity:.4f} ETH</code>\n"
        message += f"💵 价值: <code>${quantity * price:,.2f} USDT</code>\n"
        
        if action == 'close' and pnl is not None:
            pnl_icon = "📈" if pnl > 0 else "📉"
            message += f"{pnl_icon} 盈亏: <code>${pnl:,.2f}</code>\n"
        
        # 添加交易原因
        if reason:
            # 清理原因中的特殊字符
            clean_reason = self._clean_html_text(reason)
            if action == 'open':
                message += f"🔍 开仓原因: {clean_reason}\n"
            else:
                message += f"🔍 平仓原因: {clean_reason}\n"
        
        message += f"\n🕐 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return message
    
    def _format_status_message(self, status_data: Dict[str, Any]) -> str:
        """格式化状态消息"""
        status_type = status_data.get('type', 'info')
        title = status_data.get('title', '系统状态')
        content = status_data.get('content', '')
        
        # 状态图标
        status_icons = {
            'info': "ℹ️",
            'success': "✅", 
            'warning': "⚠️",
            'error': "❌",
            'start': "🚀",
            'stop': "⏹️"
        }
        
        icon = status_icons.get(status_type, "ℹ️")
        
        # 清理内容中的特殊字符
        clean_content = self._clean_html_text(content)
        
        message = f"{icon} <b>{title}</b>\n\n"
        message += f"{clean_content}\n\n"
        message += f"🕐 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return message
    
    def send_message(self, message: str, parse_mode: str = 'HTML') -> bool:
        """发送消息到Telegram"""
        if not self.enabled:
            logger.debug("Telegram通知未启用")
            return False
        
        try:
            # 调试：检查消息长度和内容
            if len(message) > 200:
                logger.debug(f"消息长度: {len(message)} 字符")
                logger.debug(f"消息前200字符: {message[:200]}")
            
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info(" Telegram消息发送成功")
                return True
            else:
                logger.error(f"Telegram消息发送失败: {response.status_code} - {response.text}")
                # 调试：如果失败，尝试不使用HTML格式
                if parse_mode == 'HTML':
                    logger.debug("尝试使用纯文本格式发送...")
                    return self.send_message(message, parse_mode=None)
                return False
                
        except Exception as e:
            logger.error(f"Telegram消息发送异常: {e}")
            return False
    
    def send_signal_notification(self, signal_data: Dict[str, Any]) -> bool:
        """发送交易信号通知"""
        if not self.enabled:
            return False
        
        # 获取当前信号评分
        current_score = signal_data.get('score', 0)
        current_time = datetime.now()
        
        # 检查是否与上次发送的评分相同
        if (self.last_signal_score is not None and 
            abs(self.last_signal_score - current_score) < 0.001):  # 使用小阈值避免浮点数精度问题
            
            # 计算距离上次发送的时间间隔
            if self.last_signal_time:
                time_diff = (current_time - self.last_signal_time).total_seconds()
                logger.debug(f"评分相同 ({current_score:.3f})，距离上次发送 {time_diff:.1f} 秒，跳过通知")
            else:
                logger.debug(f"评分相同 ({current_score:.3f})，跳过通知")
            
            return True  # 返回True表示"成功"（跳过发送）
        
        # 评分不同，发送通知
        message = self._format_signal_message(signal_data)
        success = self.send_message(message)
        
        if success:
            # 更新缓存
            self.last_signal_score = current_score
            self.last_signal_time = current_time
            logger.debug(f"发送信号通知，评分: {current_score:.3f}")
        
        return success
    
    def send_trade_notification(self, trade_data: Dict[str, Any]) -> bool:
        """发送交易执行通知"""
        if not self.enabled:
            return False
        
        message = self._format_trade_message(trade_data)
        return self.send_message(message)
    
    def send_status_notification(self, status_data: Dict[str, Any]) -> bool:
        """发送状态通知"""
        if not self.enabled:
            return False
        
        message = self._format_status_message(status_data)
        return self.send_message(message)
    
    def send_error_notification(self, error_msg: str, context: str = "") -> bool:
        """发送错误通知"""
        if not self.enabled:
            return False
        
        status_data = {
            'type': 'error',
            'title': '系统错误',
            'content': f"错误信息: {error_msg}\n上下文: {context}" if context else error_msg
        }
        
        return self.send_status_notification(status_data)
    
    def reset_score_cache(self):
        """重置评分缓存"""
        self.last_signal_score = None
        self.last_signal_time = None
        logger.debug("评分缓存已重置")
    
    def get_last_score_info(self) -> Dict[str, Any]:
        """获取上次发送的评分信息"""
        return {
            'score': self.last_signal_score,
            'time': self.last_signal_time
        }
    
    def test_connection(self) -> bool:
        """测试Telegram连接"""
        if not self.enabled:
            print(" Telegram通知未配置")
            return False
        
        test_message = f"🔧 <b>Telegram通知测试</b>\n\n"
        test_message += f"✅ 连接测试成功！\n"
        test_message += f"🚀 交易系统已准备就绪\n\n"
        test_message += f"🕐 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        success = self.send_message(test_message)
        
        if success:
            print(" Telegram通知测试成功")
        else:
            print(" Telegram通知测试失败")
        
        return success

# 全局通知器实例
telegram_notifier = TelegramNotifier()

def notify_signal(signal: int, price: float, score: float, reason: str = "", investment_advice: str = "",
 signal_from: str = "unknown", notify_neutral: bool = None) -> bool:
    """快速发送信号通知"""
    # 如果未指定notify_neutral，从配置中读取
    if notify_neutral is None:
        notify_neutral = TELEGRAM_CONFIG.get('NOTIFICATION_TYPES', {}).get('NEUTRAL_SIGNALS', False)
    
    # 观望信号不发送通知（除非明确要求）
    if signal == 0 and not notify_neutral:
        return True
    
    signal_data = {
        'signal': signal,
        'price': price, 
        'score': score,
        'reason': reason,
        'investment_advice': investment_advice,
        'signal_from': signal_from  # 新增：信号来源
    }
    return telegram_notifier.send_signal_notification(signal_data)

def notify_trade(action: str, side: str, price: float, quantity: float, pnl: float = None, reason: str = "") -> bool:
    """快速发送交易通知"""
    trade_data = {
        'action': action,
        'side': side,
        'price': price,
        'quantity': quantity,
        'pnl': pnl,
        'reason': reason
    }
    return telegram_notifier.send_trade_notification(trade_data)

def notify_status(status_type: str, title: str, content: str) -> bool:
    """快速发送状态通知"""
    status_data = {
        'type': status_type,
        'title': title,
        'content': content
    }
    return telegram_notifier.send_status_notification(status_data)

def notify_error(error_msg: str, context: str = "") -> bool:
    """快速发送错误通知"""
    return telegram_notifier.send_error_notification(error_msg, context)

def reset_signal_score_cache():
    """重置信号评分缓存"""
    telegram_notifier.reset_score_cache()

def get_last_signal_score_info() -> Dict[str, Any]:
    """获取上次发送的信号评分信息"""
    return telegram_notifier.get_last_score_info()

if __name__ == "__main__":
    # 测试Telegram通知
    notifier = TelegramNotifier()
    notifier.test_connection()