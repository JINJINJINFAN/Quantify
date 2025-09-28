# -*- coding: utf-8 -*-
"""
修复matplotlib字体识别问题
专门解决CentOS下字体文件存在但matplotlib无法识别的问题
"""

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os
import shutil

def check_font_files():
    """
    检查字体文件
    """
    print("=" * 50)
    print("检查字体文件")
    print("=" * 50)
    
    import platform
    system = platform.system()
    
    if system == "Windows":
        # Windows字体路径
        font_paths = [
            'C:/Windows/Fonts/simhei.ttf',  # 黑体
            'C:/Windows/Fonts/msyh.ttc',    # 微软雅黑
            'C:/Windows/Fonts/simsun.ttc',  # 宋体
        ]
    elif system == "Linux":
        # Linux/CentOS字体路径
        font_paths = [
            '/usr/share/fonts/wqy-microhei/wqy-microhei.ttc',
            '/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc',
            '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        ]
    else:
        # macOS字体路径
        font_paths = [
            '/System/Library/Fonts/PingFang.ttc',
            '/System/Library/Fonts/STHeiti Light.ttc',
        ]
    
    found_fonts = []
    for font_path in font_paths:
        if os.path.exists(font_path):
            found_fonts.append(font_path)
            print(f"找到字体文件: {font_path}")
        else:
            print(f"字体文件不存在: {font_path}")
    
    return found_fonts

def force_add_fonts():
    """
    强制添加字体到matplotlib
    """
    print("\n" + "=" * 50)
    print("强制添加字体到matplotlib")
    print("=" * 50)
    
    font_files = check_font_files()
    
    if not font_files:
        print(" 没有找到字体文件")
        return False
    
    # 清除matplotlib缓存
    cache_dir = os.path.expanduser('~/.matplotlib')
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir, ignore_errors=True)
            print(f"已清除matplotlib缓存: {cache_dir}")
        except Exception as e:
            print(f"清除缓存失败: {e}")
    
    # 强制添加字体文件
    for font_file in font_files:
        try:
            # 使用addfont方法添加字体
            fm.fontManager.addfont(font_file)
            print(f"成功添加字体: {font_file}")
        except Exception as e:
            print(f"添加字体失败: {font_file} - {e}")
    
    # 重建字体管理器（兼容旧版本）
    try:
        # 尝试使用rebuild方法（新版本）
        if hasattr(fm.fontManager, 'rebuild'):
            fm.fontManager.rebuild()
            print(" 使用rebuild方法重建字体管理器")
        else:
            # 旧版本：重新创建字体管理器
            fm._rebuild()
            print(" 使用_rebuild方法重建字体管理器")
    except Exception as e:
        print(f"重建字体管理器失败: {e}")
        # 尝试其他方法
        try:
            fm.findfont.cache_clear()
            print(" 清除字体查找缓存")
        except:
            pass
    
    return True

def configure_fonts():
    """
    配置字体
    """
    print("\n" + "=" * 50)
    print("配置字体")
    print("=" * 50)
    
    import platform
    system = platform.system()
    
    if system == "Windows":
        # Windows字体配置
        font_families = ['SimHei', 'Microsoft YaHei', 'SimSun', 'DejaVu Sans']
    elif system == "Linux":
        # Linux/CentOS字体配置
        font_families = ['WenQuanYi Micro Hei', 'WenQuanYi Zen Hei', 'DejaVu Sans']
    else:
        # macOS字体配置
        font_families = ['PingFang SC', 'STHeiti', 'DejaVu Sans']
    
    # 设置字体配置
    plt.rcParams['font.sans-serif'] = font_families
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['font.size'] = 12
    
    print(f"当前字体族: {plt.rcParams['font.sans-serif']}")
    print(f"Unicode负号: {plt.rcParams['axes.unicode_minus']}")
    
    print(" 字体配置完成")
    print(f"当前字体族: {plt.rcParams['font.sans-serif']}")
    print(f"Unicode负号: {plt.rcParams['axes.unicode_minus']}")
    
    return True

def test_font_recognition():
    """
    测试字体识别
    """
    print("\n" + "=" * 50)
    print("测试字体识别")
    print("=" * 50)
    
    test_fonts = ['WenQuanYi Micro Hei', 'WenQuanYi Zen Hei']
    
    for font_name in test_fonts:
        try:
            font_path = fm.findfont(fm.FontProperties(family=font_name))
            if font_path and 'DejaVuSans' not in font_path and os.path.exists(font_path):
                print(f"{font_name}: {font_path}")
            else:
                print(f"{font_name}: 未找到或使用默认字体")
        except Exception as e:
            print(f"{font_name}: 检查失败 - {e}")

def test_chinese_display():
    """
    测试中文显示
    """
    print("\n" + "=" * 50)
    print("测试中文显示")
    print("=" * 50)
    
    try:
        # 创建测试图表
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # 测试中文标题和标签
        ax.set_title('CentOS中文测试\nCentOS Chinese Test', fontsize=16, fontweight='bold')
        ax.set_xlabel('时间轴 - Time Axis', fontsize=12)
        ax.set_ylabel('数值轴 - Value Axis', fontsize=12)
        
        # 添加测试数据
        x = [1, 2, 3, 4, 5]
        y = [10, 20, 15, 25, 30]
        
        ax.plot(x, y, 'o-', linewidth=2, markersize=8, label='测试数据 - Test Data')
        ax.legend(fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # 添加中文注释
        ax.text(3, 20, '这是中文测试\nThis is Chinese test', 
                fontsize=12, ha='center', va='center',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.7))
        
        plt.tight_layout()
        
        # 保存测试图片
        test_filename = 'fix_matplotlib_test.png'
        plt.savefig(test_filename, dpi=150, bbox_inches='tight')
        print(f"中文显示测试完成，图片已保存: {test_filename}")
        
        # 显示图片
        try:
            plt.show()
            print(" 图片显示成功")
        except Exception as e:
            print(f"无法显示图片: {e}")
        
        return True
        
    except Exception as e:
        print(f"中文显示测试失败: {e}")
        return False

def main():
    """
    主函数
    """
    print("修复matplotlib字体识别问题")
    print("=" * 60)
    
    # 步骤1: 强制添加字体
    step1_ok = force_add_fonts()
    
    # 步骤2: 配置字体
    step2_ok = configure_fonts()
    
    # 步骤3: 测试字体识别
    test_font_recognition()
    
    # 步骤4: 测试中文显示
    step3_ok = test_chinese_display()
    
    # 总结
    print("\n" + "=" * 60)
    print("执行结果总结")
    print("=" * 60)
    print(f"步骤1 (强制添加字体): {' 成功' if step1_ok else ' 失败'}")
    print(f"步骤2 (配置字体): {' 成功' if step2_ok else ' 失败'}")
    print(f"步骤3 (测试显示): {' 成功' if step3_ok else ' 失败'}")
    
    if all([step1_ok, step2_ok, step3_ok]):
        print("\n🎉 字体识别问题修复成功！")
    else:
        print("\n部分步骤失败，请检查错误信息。")
    
    print("=" * 60)

if __name__ == "__main__":
    main() 