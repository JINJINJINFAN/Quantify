# DeepSeek ETHUSDT实时技术指标分析器

## 📋 功能概述

这个模块使用DeepSeek API对ETHUSDT进行实时技术指标分析，包括：

- **技术指标计算**: MACD、ADX、ATR、布林带、RSI等
- **支撑阻力位分析**: 自动识别关键支撑和阻力位
- **市场趋势分析**: 实时判断上涨/下跌/震荡行情
- **AI深度分析**: 使用DeepSeek API进行智能分析
- **JSON格式输出**: 强制返回结构化的JSON数据

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install requests pandas numpy python-dotenv
```

### 2. 设置API密钥

**方法1: 使用.env文件（推荐）**

创建`.env`文件并添加：
```bash
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

**方法2: 使用环境变量**
```bash
# Linux/Mac
export DEEPSEEK_API_KEY="your_deepseek_api_key_here"

# Windows
set DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

### 3. 基本使用

```python
from deepseek_analyzer import DeepSeekAnalyzer

# 创建分析器（API密钥将从.env文件中自动读取）
analyzer = DeepSeekAnalyzer()

# 获取实时分析
result = analyzer.get_real_time_analysis()

# 获取JSON格式
json_result = analyzer.get_analysis_json()
print(json_result)
```

## 技术指标说明

### MACD (移动平均收敛发散)
- **MACD线**: 12日和26日EMA的差值
- **信号线**: MACD的9日EMA
- **柱状图**: MACD线与信号线的差值
- **趋势判断**: MACD > 信号线 = 看涨，反之看跌

### ADX (平均方向指数)
- **ADX值**: 趋势强度指标
- **DI+**: 正向动量指标
- **DI-**: 负向动量指标
- **趋势强度**: ADX > 25 = 强趋势，< 25 = 弱趋势

### ATR (平均真实波幅)
- **ATR值**: 波动率指标
- **ATR%**: 相对于价格的波动率百分比
- **用途**: 设置止损位和判断市场波动性

### 布林带
- **上轨**: 20日SMA + 2倍标准差
- **中轨**: 20日简单移动平均线
- **下轨**: 20日SMA - 2倍标准差
- **挤压**: 带宽 < 10% = 低波动率

### RSI (相对强弱指数)
- **RSI值**: 0-100之间的动量指标
- **超买**: RSI > 70
- **超卖**: RSI < 30
- **中性**: 30-70之间

## 输出格式

### 完整分析结果结构

```json
{
  "timestamp": "2024-01-01T12:00:00",
  "symbol": "ETHUSDT",
  "current_price": 2500.00,
  "indicators": {
    "macd": {
      "macd": 0.1234,
      "signal": 0.0987,
      "histogram": 0.0247,
      "trend": "bullish"
    },
    "adx": {
      "adx": 28.5,
      "di_plus": 32.1,
      "di_minus": 15.3,
      "trend_strength": "strong",
      "trend_direction": "bullish"
    },
    "atr": {
      "atr": 45.67,
      "atr_percent": 1.83
    },
    "bollinger_bands": {
      "upper": 2550.00,
      "middle": 2500.00,
      "lower": 2450.00,
      "position": 0.5,
      "squeeze": "no"
    },
    "rsi": {
      "rsi": 65.4,
      "status": "neutral"
    },
    "support_resistance": {
      "resistance": [2550.00, 2600.00, 2650.00],
      "support": [2450.00, 2400.00, 2350.00],
      "current_price": 2500.00
    }
  },
  "market_analysis": {
    "market_condition": "strong_uptrend",
    "trend": "bullish",
    "volatility": "medium",
    "recommendation": "buy",
    "confidence": 0.8
  },
  "scores": {
    "trend_score": {
      "trend_score": 0.75,
      "trend_level": "bullish",
      "details": {
        "macd_score": 0.9,
        "adx_score": 0.8,
        "position_score": 0.6,
        "momentum_score": 0.7
      }
    },
    "indicator_score": {
      "indicator_score": 0.82,
      "indicator_level": "good",
      "details": {
        "macd_line_score": 0.9,
        "signal_score": 0.8,
        "macd_score": 0.85,
        "rsi_score": 0.7,
        "bollinger_bands_score": 0.8,
        "atr_score": 0.8
      }
    },
    "sentiment_score": {
      "sentiment_score": 0.65,
      "sentiment_level": "neutral",
      "details": {
        "rsi_sentiment": 0.5,
        "bollinger_bands_sentiment": 0.6,
        "macd_sentiment": 0.7,
        "momentum_sentiment": 0.7
      }
    },
    "overall_score": 0.74
  },
  "summary": {
    "trend": "bullish",
    "condition": "strong_uptrend",
    "recommendation": "buy",
    "confidence": 0.8,
    "trend_level": "bullish",
    "indicator_level": "good",
    "sentiment_level": "neutral"
  },
  "deepseek_analysis": {
    "trend_analysis": {
      "trend": "上涨",
      "strength": "强",
      "duration": "中期"
    },
    "support_resistance": {
      "key_support_levels": [2450.00, 2400.00],
      "key_resistance_levels": [2550.00, 2600.00],
      "breakout_levels": [2550.00]
    },
    "risk_assessment": {
      "risk_level": "中",
      "risk_factors": ["市场波动性较高"],
      "stop_loss_suggestions": ["2450.00"]
    },
    "trading_recommendation": {
      "action": "买入",
      "entry_price": 2500.00,
      "target_price": 2600.00,
      "stop_loss": 2450.00,
      "confidence": 0.8
    }
  }
}
```

## 评分系统

### 趋势评分 (Trend Score)
- **评分范围**: 0.0 - 1.0
- **等级分类**: 
  - `strong_bullish` (0.7-1.0): 强烈看涨
  - `bullish` (0.6-0.7): 看涨
  - `neutral` (0.4-0.6): 中性
  - `bearish` (0.3-0.4): 看跌
  - `strong_bearish` (0.0-0.3): 强烈看跌
- **计算因素**: MACD趋势、ADX强度、价格位置、RSI动量

### 指标评分 (Indicator Score)
- **评分范围**: 0.0 - 1.0
- **等级分类**:
  - `excellent` (0.8-1.0): 优秀
  - `good` (0.7-0.8): 良好
  - `fair` (0.6-0.7): 一般
  - `poor` (0.4-0.6): 较差
  - `very_poor` (0.0-0.4): 很差
- **计算因素**: MACD、RSI、布林带、ATR等技术指标的综合表现

### 市场情绪评分 (Sentiment Score)
- **评分范围**: 0.0 - 1.0
- **等级分类**:
  - `very_bullish` (0.8-1.0): 极度乐观
  - `bullish` (0.6-0.8): 乐观
  - `neutral` (0.4-0.6): 中性
  - `bearish` (0.2-0.4): 悲观
  - `very_bearish` (0.0-0.2): 极度悲观
- **计算因素**: RSI情绪、布林带位置、MACD情绪、价格动量情绪

### 综合评分 (Overall Score)
- **计算方式**: (趋势评分 + 指标评分 + 情绪评分) / 3
- **用途**: 整体市场条件的综合评估

## 🔧 配置选项

### 缓存配置
```python
analyzer.cache_duration = 60  # 缓存60秒
```

### 时间级别
```python
# 获取不同时间级别的数据
df = analyzer.get_ethusdt_data(timeframe='1h')  # 1小时
df = analyzer.get_ethusdt_data(timeframe='4h')  # 4小时
df = analyzer.get_ethusdt_data(timeframe='1d')  # 1天
```

### 强制刷新
```python
# 强制刷新缓存
result = analyzer.get_real_time_analysis(force_refresh=True)
```

## 📝 使用示例

### 示例1: 基本分析
```python
from deepseek_analyzer import DeepSeekAnalyzer

analyzer = DeepSeekAnalyzer("your_api_key")
result = analyzer.get_real_time_analysis()

print(f"当前价格: ${result['current_price']:,.2f}")
print(f"趋势: {result['summary']['trend']}")
print(f"建议: {result['summary']['recommendation']}")
```

### 示例2: 获取支撑阻力位
```python
result = analyzer.get_real_time_analysis()
sr = result['indicators']['support_resistance']

print("阻力位:", [f"${price:,.2f}" for price in sr['resistance']])
print("支撑位:", [f"${price:,.2f}" for price in sr['support']])
```

### 示例3: 技术指标分析
```python
result = analyzer.get_real_time_analysis()
indicators = result['indicators']

# MACD分析
macd = indicators['macd']
print(f"MACD趋势: {macd['trend']}")

# ADX分析
adx = indicators['adx']
print(f"趋势强度: {adx['trend_strength']}")

# RSI分析
rsi = indicators['rsi']
print(f"RSI状态: {rsi['status']}")
```

### 示例4: 评分系统分析
```python
result = analyzer.get_real_time_analysis()
scores = result['scores']

# 趋势评分
trend_score = scores['trend_score']
print(f"趋势评分: {trend_score['trend_score']:.3f}")
print(f"趋势等级: {trend_score['trend_level']}")

# 指标评分
indicator_score = scores['indicator_score']
print(f"指标评分: {indicator_score['indicator_score']:.3f}")
print(f"指标等级: {indicator_score['indicator_level']}")

# 情绪评分
sentiment_score = scores['sentiment_score']
print(f"情绪评分: {sentiment_score['sentiment_score']:.3f}")
print(f"情绪等级: {sentiment_score['sentiment_level']}")

# 综合评分
overall_score = scores['overall_score']
print(f"综合评分: {overall_score:.3f}")
```

### 示例5: 基于评分的交易决策
```python
result = analyzer.get_real_time_analysis()
scores = result['scores']

# 设置评分阈值
TREND_THRESHOLD = 0.6
INDICATOR_THRESHOLD = 0.7
SENTIMENT_THRESHOLD = 0.5

# 判断交易条件
trend_ok = scores['trend_score']['trend_score'] > TREND_THRESHOLD
indicator_ok = scores['indicator_score']['indicator_score'] > INDICATOR_THRESHOLD
sentiment_ok = scores['sentiment_score']['sentiment_score'] > SENTIMENT_THRESHOLD

if trend_ok and indicator_ok and sentiment_ok:
    print(" 满足交易条件，可以考虑交易")
else:
    print(" 不满足交易条件，建议观望")
```

## 🧪 测试功能

运行测试脚本：

```bash
# 测试不依赖API的功能
python test_deepseek_analysis.py

# 设置API密钥后测试完整功能
export DEEPSEEK_API_KEY="your_key"
python test_deepseek_analysis.py

# 测试评分系统功能
python score_analysis_example.py

# 快速演示功能
python quick_deepseek_demo.py
```

## 注意事项

1. **API密钥安全**: 请妥善保管您的DeepSeek API密钥
2. **请求频率**: 建议不要过于频繁地调用API
3. **数据准确性**: 技术分析仅供参考，不构成投资建议
4. **网络连接**: 确保网络连接稳定以获取实时数据

## 🔍 故障排除

### 常见问题

1. **API密钥错误**
   ```
   错误: DeepSeek API请求失败
   解决: 检查API密钥是否正确设置
   ```

2. **网络连接问题**
   ```
   错误: 获取ETHUSDT数据失败
   解决: 检查网络连接和防火墙设置
   ```

3. **JSON解析错误**
   ```
   错误: JSON解析失败
   解决: DeepSeek API可能返回了非JSON格式的响应
   ```

### 调试模式

启用详细日志：
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📞 支持

如有问题，请检查：
1. API密钥是否正确设置
2. 网络连接是否正常
3. 依赖包是否正确安装
4. 查看日志输出获取详细错误信息 