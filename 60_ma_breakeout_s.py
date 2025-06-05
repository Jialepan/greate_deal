from jqdatasdk import *
from datetime import datetime, timedelta

# 认证
auth("13128743087", "2025GoGoGo")

# 策略参数设置
class Config:
    # 均线参数
    MA_DAYS = 60
    # 成交量倍数阈值
    VOLUME_INCREASE_RATIO = 2.0
    # 涨幅阈值
    PRICE_INCREASE_RATIO = 0.05
    # 缩量阈值
    VOLUME_DECREASE_RATIO = 0.5
    # 尾盘买入时间
    BUY_TIME = "14:55:00"
    # 上影线比例阈值
    UPPER_SHADOW_RATIO = 0.3
    # 前期涨幅过滤阈值
    RECENT_INCREASE_RATIO = 0.5
    # 前期涨幅计算天数
    RECENT_DAYS = 20

def initialize(context):
    # 初始化函数，设定基准、股票池等
    set_benchmark('000300.XSHG')  # 以沪深300为基准
    set_option('use_real_price', True)  # 使用真实价格
    log.info("策略初始化完成")
    
    # 设置交易参数
    g.security = '000001.XSHE'  # 默认股票
    g.is_breakout = False  # 是否出现突破信号
    g.breakout_date = None  # 突破日期
    g.buy_price = 0  # 买入价格

def handle_data(context, data):
    # 主逻辑函数，每个交易日运行
    security = g.security
    
    # 获取历史数据
    hist_data = get_price(security, end_date=context.current_dt, 
                          count=Config.MA_DAYS + 2, 
                          fields=['close', 'volume', 'high', 'low'])
    
    if len(hist_data) < Config.MA_DAYS + 2:
        log.info("数据不足，跳过当前交易日")
        return
    
    # 计算60日均线
    current_ma = hist_data['close'][-Config.MA_DAYS:].mean()
    previous_ma = hist_data['close'][-Config.MA_DAYS-1:-1].mean()
    
    # 获取当日和前一日数据
    today_data = hist_data.iloc[-1]
    yesterday_data = hist_data.iloc[-2]
    
    # 获取当前持仓
    position = context.portfolio.positions.get(security, None)
    
    # 过滤条件：前期涨幅过大
    recent_days_data = hist_data[-Config.RECENT_DAYS-1:-1]
    recent_increase = (recent_days_data['close'].iloc[-1] / 
                      recent_days_data['close'].iloc[0] - 1)
    
    if recent_increase > Config.RECENT_INCREASE_RATIO:
        log.info(f"{security}前期涨幅过大，跳过: {recent_increase:.2%}")
        return
    
    # 止损条件判断
    if position and position.amount > 0:
        # 跌破60日均线止损
        if today_data['close'] < current_ma:
            print(f"触发止损：{security}收盘价跌破60日均线")
            order_target_value(security, 0)
            return
            
        # 放量上引线止盈
        upper_shadow = today_data['high'] - max(today_data['close'], today_data['open'])
        k_line_height = today_data['high'] - today_data['low']
        if k_line_height > 0:
            shadow_ratio = upper_shadow / k_line_height
            volume_ratio = today_data['volume'] / yesterday_data['volume']
            
            if shadow_ratio > Config.UPPER_SHADOW_RATIO and volume_ratio > 1.5:
                print(f"触发止盈：{security}出现放量上引线，上影线比例{shadow_ratio:.2%}")
                order_target_value(security, 0)
                return
    
    # 判断是否为突破次日
    if g.is_breakout and context.current_dt.date() == (g.breakout_date + timedelta(days=1)).date():
        # 次日阴线缩倍量尾盘买入
        if today_data['close'] < today_data['open']:  # 阴线
            volume_ratio = today_data['volume'] / hist_data['volume'].iloc[-2]
            if volume_ratio < Config.VOLUME_DECREASE_RATIO:  # 缩量
                current_time = context.current_dt.strftime("%H:%M:%S")
                if current_time >= Config.BUY_TIME:  # 尾盘买入
                    log.info(f"触发买入：{security}突破次日阴线缩量，尾盘买入")
                    order_value(security, context.portfolio.cash * 0.9)  # 使用90%资金买入
                    g.buy_price = today_data['close']
                    g.is_breakout = False  # 重置突破标记
                else:
                    log.info(f"等待尾盘买入时机，当前时间：{current_time}")
            else:
                log.info(f"成交量未达到缩量要求：{volume_ratio:.2f}")
        else:
            log.info(f"{security}突破次日未收阴线，取消买入计划")
            g.is_breakout = False  # 重置突破标记
    
    # 判断是否为倍量涨突破
    price_increase = (today_data['close'] / yesterday_data['close'] - 1)
    volume_increase = today_data['volume'] / yesterday_data['volume']
    
    if (price_increase > Config.PRICE_INCREASE_RATIO and  # 涨幅超过阈值
        volume_increase > Config.VOLUME_INCREASE_RATIO and  # 成交量超过阈值
        today_data['close'] > current_ma and  # 收盘价突破60日均线
        current_ma > previous_ma):  # 60日均线拐头向上
        
        log.info(f"发现倍量涨突破：{security}")
        log.info(f"涨幅：{price_increase:.2%}，成交量倍数：{volume_increase:.2f}")
        log.info(f"收盘价：{today_data['close']}，60日均线：{current_ma}")
        
        g.is_breakout = True
        g.breakout_date = context.current_dt.date()
