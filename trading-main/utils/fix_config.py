# -*- coding: utf-8 -*-
# ============================================================================
# 用户配置管理功能
# ============================================================================

import json
import os
from datetime import datetime

# 配置文件路径
def get_config_file_path():
    """获取配置文件路径"""
    import os
    from pathlib import Path
    
    # 获取当前文件所在目录
    current_dir = Path(__file__).parent
    
    # 尝试从当前目录开始查找json目录
    config_file = current_dir / 'json' / 'config.json'
    if config_file.exists():
        return str(config_file)
    
    # 如果当前目录下没有json目录，尝试上级目录
    config_file = current_dir.parent / 'json' / 'config.json'
    if config_file.exists():
        return str(config_file)
    
    # 如果都不存在，返回默认路径（相对于项目根目录）
    return str(current_dir.parent / 'json' / 'config.json')

CONFIG_FILE = get_config_file_path()

def save_user_config(config_data):
    """保存用户配置到文件"""
    try:
        from pathlib import Path
        
        config_to_save = {
            'timestamp': datetime.now().isoformat(),
            'description': '用户自定义配置',
            'config': config_data
        }
        
        # 确保目录存在
        config_path = Path(CONFIG_FILE)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_to_save, f, indent=2, ensure_ascii=False)
        
        return True, "配置保存成功"
    except Exception as e:
        return False, f"配置保存失败: {e}"

def load_user_config():
    """从文件加载用户配置"""
    try:
        if not os.path.exists(CONFIG_FILE):
            return False, "配置文件不存在", None
        
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            saved_config = json.load(f)
        
        return True, "配置加载成功", saved_config['config']
    except Exception as e:
        return False, f"配置加载失败: {e}", None

def get_default_config():
    """获取默认配置"""
    from config import (
        TRADING_CONFIG, WINDOW_CONFIG, BACKTEST_CONFIG, 
        EMA_CONFIG, PERIOD_CONFIG, LOGGING_CONFIG, 
        DEBUG_CONFIG, OPTIMIZED_STRATEGY_CONFIG
    )
    
    return {
        'TRADING_CONFIG': TRADING_CONFIG.copy(),
        'WINDOW_CONFIG': WINDOW_CONFIG.copy(),
        'BACKTEST_CONFIG': BACKTEST_CONFIG.copy(),
        'EMA_CONFIG': EMA_CONFIG.copy(),
        'PERIOD_CONFIG': PERIOD_CONFIG.copy(),
        'LOGGING_CONFIG': LOGGING_CONFIG.copy(),
        'DEBUG_CONFIG': DEBUG_CONFIG.copy(),
        'OPTIMIZED_STRATEGY_CONFIG': OPTIMIZED_STRATEGY_CONFIG.copy()
    }

def merge_configs(default_config, user_config):
    """合并默认配置和用户配置"""
    merged_config = default_config.copy()
    
    if user_config:
        for section, values in user_config.items():
            if section in merged_config:
                if isinstance(values, dict) and isinstance(merged_config[section], dict):
                    merged_config[section].update(values)
                else:
                    merged_config[section] = values
    
    return merged_config

def apply_user_config():
    """应用用户配置到全局变量"""
    success, message, user_config = load_user_config()
    
    if success and user_config:
        # 导入配置模块
        import config
        
        # 递归更新配置函数
        def deep_update(target_dict, source_dict):
            """递归更新字典，支持嵌套结构"""
            for key, value in source_dict.items():
                if key in target_dict and isinstance(target_dict[key], dict) and isinstance(value, dict):
                    deep_update(target_dict[key], value)
                else:
                    target_dict[key] = value
        
        # 更新全局配置变量
        if 'TRADING_CONFIG' in user_config:
            deep_update(config.TRADING_CONFIG, user_config['TRADING_CONFIG'])
        
        if 'WINDOW_CONFIG' in user_config:
            deep_update(config.WINDOW_CONFIG, user_config['WINDOW_CONFIG'])
        
        if 'BACKTEST_CONFIG' in user_config:
            deep_update(config.BACKTEST_CONFIG, user_config['BACKTEST_CONFIG'])
        
        if 'EMA_CONFIG' in user_config:
            deep_update(config.EMA_CONFIG, user_config['EMA_CONFIG'])
        
        if 'PERIOD_CONFIG' in user_config:
            deep_update(config.PERIOD_CONFIG, user_config['PERIOD_CONFIG'])
        
        if 'LOGGING_CONFIG' in user_config:
            deep_update(config.LOGGING_CONFIG, user_config['LOGGING_CONFIG'])
        
        if 'DEBUG_CONFIG' in user_config:
            deep_update(config.DEBUG_CONFIG, user_config['DEBUG_CONFIG'])
        
        if 'OPTIMIZED_STRATEGY_CONFIG' in user_config:
            deep_update(config.OPTIMIZED_STRATEGY_CONFIG, user_config['OPTIMIZED_STRATEGY_CONFIG'])
        
        return True, "用户配置已应用"
    
    return False, message

def reset_to_default_config():
    """重置为默认配置"""
    try:
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
        return True, "已重置为默认配置"
    except Exception as e:
        return False, f"重置配置失败: {e}"

def backup_config():
    """备份当前配置"""
    try:
        if not os.path.exists(CONFIG_FILE):
            return False, "配置文件不存在，无法备份"
        
        # 创建备份文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'user_config_backup_{timestamp}.json'
        
        # 复制配置文件
        import shutil
        shutil.copy2(CONFIG_FILE, backup_file)
        
        return True, f"配置已备份到 {backup_file}"
    except Exception as e:
        return False, f"备份配置失败: {e}"

def restore_config(backup_file):
    """从备份文件恢复配置"""
    try:
        if not os.path.exists(backup_file):
            return False, f"备份文件 {backup_file} 不存在"
        
        # 验证备份文件格式
        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        if 'config' not in backup_data:
            return False, "备份文件格式错误"
        
        # 恢复配置文件
        import shutil
        shutil.copy2(backup_file, CONFIG_FILE)
        
        return True, f"配置已从 {backup_file} 恢复"
    except Exception as e:
        return False, f"恢复配置失败: {e}"

def list_backup_files():
    """列出所有备份文件"""
    try:
        backup_files = []
        for file in os.listdir('.'):
            if file.startswith('user_config_backup_') and file.endswith('.json'):
                backup_files.append(file)
        
        backup_files.sort(reverse=True)  # 按时间倒序排列
        return True, "备份文件列表", backup_files
    except Exception as e:
        return False, f"获取备份文件列表失败: {e}", []

def validate_config(config_data):
    """验证配置数据的有效性"""
    try:
        required_sections = ['TRADING_CONFIG']
        
        for section in required_sections:
            if section not in config_data:
                return False, f"缺少必需的配置节: {section}"
        
        # 验证交易配置
        trading_config = config_data.get('TRADING_CONFIG', {})
        
        # 验证资金配置
        capital_config = trading_config.get('CAPITAL_CONFIG', {})
        if 'INITIAL_CAPITAL' in capital_config:
            if not isinstance(capital_config['INITIAL_CAPITAL'], (int, float)) or capital_config['INITIAL_CAPITAL'] <= 0:
                return False, "初始资金必须为正数"
        
        if 'LEVERAGE' in capital_config:
            if not isinstance(capital_config['LEVERAGE'], int) or capital_config['LEVERAGE'] <= 0:
                return False, "杠杆倍数必须为正整数"
        
        # 验证风险配置
        risk_config = trading_config.get('RISK_CONFIG', {})
        if 'MAX_DAILY_TRADES' in risk_config:
            if not isinstance(risk_config['MAX_DAILY_TRADES'], int) or risk_config['MAX_DAILY_TRADES'] <= 0:
                return False, "每日最大交易次数必须为正整数"
        
        return True, "配置验证通过"
    except Exception as e:
        return False, f"配置验证失败: {e}"

def export_config(export_file=None):
    """导出配置到指定文件"""
    try:
        if not export_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            export_file = f'user_config_export_{timestamp}.json'
        
        success, message, user_config = load_user_config()
        if not success:
            return False, f"无法加载配置: {message}"
        
        # 添加导出信息
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'export_description': '用户配置导出',
            'config': user_config
        }
        
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        return True, f"配置已导出到 {export_file}"
    except Exception as e:
        return False, f"导出配置失败: {e}"

def import_config(import_file):
    """从指定文件导入配置"""
    try:
        if not os.path.exists(import_file):
            return False, f"导入文件 {import_file} 不存在"
        
        with open(import_file, 'r', encoding='utf-8') as f:
            import_data = json.load(f)
        
        if 'config' not in import_data:
            return False, "导入文件格式错误"
        
        # 验证配置
        success, message = validate_config(import_data['config'])
        if not success:
            return False, f"配置验证失败: {message}"
        
        # 保存配置
        return save_user_config(import_data['config'])
    except Exception as e:
        return False, f"导入配置失败: {e}"

# 配置管理工具函数
def get_config_info():
    """获取配置信息"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            return {
                'exists': True,
                'timestamp': config_data.get('timestamp', 'N/A'),
                'description': config_data.get('description', 'N/A'),
                'size': os.path.getsize(CONFIG_FILE)
            }
        else:
            return {
                'exists': False,
                'timestamp': 'N/A',
                'description': 'N/A',
                'size': 0
            }
    except Exception as e:
        return {
            'exists': False,
            'timestamp': 'N/A',
            'description': f'错误: {e}',
            'size': 0
        }

def clean_old_backups(keep_count=5):
    """清理旧的备份文件，保留最新的几个"""
    try:
        success, message, backup_files = list_backup_files()
        if not success:
            return False, message
        
        if len(backup_files) <= keep_count:
            return True, f"备份文件数量({len(backup_files)})未超过保留数量({keep_count})"
        
        # 删除多余的备份文件
        files_to_delete = backup_files[keep_count:]
        deleted_count = 0
        
        for file in files_to_delete:
            try:
                os.remove(file)
                deleted_count += 1
            except Exception as e:
                print(f"删除备份文件 {file} 失败: {e}")
        
        return True, f"已删除 {deleted_count} 个旧备份文件"
    except Exception as e:
        return False, f"清理备份文件失败: {e}"

# ============================================================================
# 交易数据JSON文件管理
# ============================================================================

def save_trade_history(trade_history):
    """保存交易历史到JSON文件"""
    try:
        from pathlib import Path
        
        # 确保json目录存在
        json_dir = Path('json')
        json_dir.mkdir(exist_ok=True)
        
        # 转换datetime对象为字符串
        history_to_save = []
        for trade in trade_history:
            trade_copy = trade.copy()
            if 'timestamp' in trade_copy and hasattr(trade_copy['timestamp'], 'isoformat'):
                trade_copy['timestamp'] = trade_copy['timestamp'].isoformat()
            history_to_save.append(trade_copy)
        
        # 保存到文件
        history_file = json_dir / 'trade_history.json'
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history_to_save, f, indent=2, ensure_ascii=False)
        
        return True, f"交易历史已保存: {len(trade_history)} 条记录"
    except Exception as e:
        return False, f"保存交易历史失败: {e}"

def load_trade_history():
    """从JSON文件加载交易历史"""
    try:
        from pathlib import Path
        from datetime import datetime
        
        history_file = Path('json/trade_history.json')
        if not history_file.exists():
            return True, "未找到交易历史文件，将创建新的历史记录", []
        
        # 检查文件是否为空
        if history_file.stat().st_size == 0:
            return True, "交易历史文件为空，将创建新的历史记录", []
        
        with open(history_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return True, "交易历史文件为空，将创建新的历史记录", []
            
            history_data = json.loads(content)
        
        # 转换字符串为datetime对象
        for trade in history_data:
            if 'timestamp' in trade and isinstance(trade['timestamp'], str):
                try:
                    # 解析时间字符串，确保时区一致性
                    parsed_time = datetime.fromisoformat(trade['timestamp'])
                    # 如果解析出的时间带时区，则移除时区信息
                    if parsed_time.tzinfo is not None:
                        trade['timestamp'] = parsed_time.replace(tzinfo=None)
                    else:
                        trade['timestamp'] = parsed_time
                except Exception as e:
                    print(f"解析timestamp失败: {e}, 使用None")
                    trade['timestamp'] = None
        
        return True, f"交易历史已加载: {len(history_data)} 条记录", history_data
    except Exception as e:
        return False, f"加载交易历史失败: {e}", []

def save_trading_status(position_data):
    """保存交易系统状态到JSON文件"""
    try:
        from pathlib import Path
        
        # 确保json目录存在
        json_dir = Path('json')
        json_dir.mkdir(exist_ok=True)
        
        # 添加时间戳
        position_data['timestamp'] = datetime.now().isoformat()
        
        # 保存到文件
        trading_file = json_dir / 'trading_status.json'
        with open(trading_file, 'w', encoding='utf-8') as f:
            json.dump(position_data, f, indent=2, ensure_ascii=False)
        
        return True, "交易系统状态已保存"
    except Exception as e:
        return False, f"保存交易系统状态失败: {e}"

def load_trading_status():
    """从JSON文件加载交易系统状态"""
    try:
        from pathlib import Path
        from datetime import datetime
        
        trading_file = Path('json/trading_status.json')
        if not trading_file.exists():
            return True, "未找到交易系统状态文件", {}
        
        # 检查文件是否为空
        if trading_file.stat().st_size == 0:
            return True, "交易系统状态文件为空，将创建新的状态", {}
        
        with open(trading_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return True, "交易系统状态文件为空，将创建新的状态", {}
            
            position_data = json.loads(content)
        
        # 转换时间戳字符串为datetime对象
        if 'last_trade_time' in position_data and position_data['last_trade_time']:
            try:
                # 解析时间字符串，确保时区一致性
                parsed_time = datetime.fromisoformat(position_data['last_trade_time'])
                # 如果解析出的时间带时区，则移除时区信息
                if parsed_time.tzinfo is not None:
                    position_data['last_trade_time'] = parsed_time.replace(tzinfo=None)
                else:
                    position_data['last_trade_time'] = parsed_time
            except Exception as e:
                print(f"解析last_trade_time失败: {e}, 使用None")
                position_data['last_trade_time'] = None
        
        return True, "交易系统状态已加载", position_data
    except Exception as e:
        return False, f"加载交易系统状态失败: {e}", {}

 