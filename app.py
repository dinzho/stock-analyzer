import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import time
from functools import wraps
import plotly.graph_objects as go

# === 重試裝飾器 ===
def retry_on_rate_limit(max_retries=3, delay=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except yf.exceptions.YFRateLimitError:
                    if attempt < max_retries - 1:
                        wait_time = delay * (2 ** attempt)
                        st.warning(f"⚠️ Yahoo Finance 請求限制，等待 {wait_time} 秒後重試... ({attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                    else:
                        raise
            return None
        return wrapper
    return decorator

# === 頁面配置 ===
st.set_page_config(page_title="股票深度分析", page_icon="📊", layout="wide")
st.title("📊 股票完整深度分析報告")

# === 側邊欄 ===
with st.sidebar:
    st.header("🔍 查詢設置")
    ticker_input = st.text_input("股票代碼", value="NOW", placeholder="例如：NOW, NVDA, TSLA")
    exchange = st.selectbox("交易所", ["NYSE", "NASDAQ", "HKEX"], index=0)
    analyze_btn = st.button("🚀 開始深度分析", type="primary", use_container_width=True)
    st.markdown("---")
    st.info("💡 **提示**：如果出現請求限制，請稍後再試。")

# === 指標計算函數 ===
def calculate_indicators(df):
    """計算 MACD, RSI, 均線"""
    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['Histogram'] = df['MACD'] - df['Signal']
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # 均線
    df['SMA20'] = df['Close'].rolling(20).mean()
    df['SMA200'] = df['Close'].rolling(200).mean()
    
    return df

# === 簡潔版圖表生成 (復刻圖2風格) ===
def generate_clean_chart(df, fib_levels):
    plot_df = df.tail(250) # 取最近250天
    if plot_df.empty: return None
    
    fig = go.Figure()

    # 1. K線 (紅綠蠟)
    fig.add_trace(go.Candlestick(
        x=plot_df.index,
        open=plot_df['Open'], high=plot_df['High'],
        low=plot_df['Low'], close=plot_df['Close'],
        name='K線',
        increasing_line_color='#26a69a', # 綠
        decreasing_line_color='#ef5350', # 紅
        increasing_fillcolor='#26a69a',
        decreasing_fillcolor='#ef5350'
    ))

    # 2. Fibonacci 水平虛線 (只畫線，不畫色塊)
    # 顏色用淡橙色/金色，虛線
    fib_ratios = ['0.000', '0.236', '0.382', '0.500', '0.618', '0.786', '1.000']
    
    for ratio in fib_ratios:
        if ratio in fib_levels:
            y_val = fib_levels[ratio]
            # 添加水平線
            fig.add_hline(y=y_val, line_dash="dot", line_color="orange", line_width=1, opacity=0.6)
            # 在右側添加文字標註
            fig.add_annotation(
                y=y_val, x=1.02, # x=1.02 放在圖表外右側
                text=f"{float(ratio)*100:.1f}%",
                showarrow=False,
                font=dict(size=10, color="orange"),
                xref="paper", yref="y",
                xanchor="left", yanchor="middle"
            )

    # 佈局設置 (極簡風格)
    fig.update_layout(
        title="K线与FIB",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False, # 隱藏底部縮放條
        height=500,
        margin=dict(l=0, r=40, t=30, b=0), # 右邊留空間給標註
        plot_bgcolor='white',
        paper_bgcolor='white',
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.05), # 圖例放右側
        hovermode='x unified'
    )
    
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor='lightgray', gridwidth=0.5)
    
    return fig

# === 數據獲取 ===
@retry_on_rate_limit(max_retries=3, delay=3)
def fetch_stock_data(ticker):
    stock = yf.Ticker(ticker)
    df = None
    info = {}
    news_data = []
    
    try:
        df = stock.history(period="2y", interval="1d")
        if df.empty: return None, None, None, "無法獲取歷史數據"
    except Exception as e: return None, None, None, f"歷史數據失敗：{e}"
    
    # 計算指標
    df = calculate_indicators(df)
    
    # 獲取基本面
    try:
        time.sleep(1)
        info = stock.info
    except: pass
    
    # 獲取新聞
    try:
        time.sleep(0.5)
        news_data = stock.news if hasattr(stock, 'news') else []
    except: pass
    
    return stock, df, info, news_data, None

# === 核心報告生成 ===
def generate_report(ticker, df, info, news_data):
    current_price = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2]
    change_pct = ((current_price - prev_close) / prev_close) * 100
    
    # 獲取高低點
    recent_high = df['High'].max()
    recent_low = df['Low'].min()
    high_date = df['High'].idxmax().strftime('%Y-%m')
    low_date = df['Low'].idxmin().strftime('%Y-%m-%d')
    
    # 當前指標值
    macd = df['MACD'].iloc[-1]
    signal = df['Signal'].iloc[-1]
    rsi = df['RSI'].iloc[-1]
    sma20 = df['SMA20'].iloc[-1]
    sma200 = df['SMA200'].iloc[-1]
    
    # 計算 FIB (基於近期波段)
    drop_range = recent_high - recent_low
    fib_levels = {
        '1.000': recent_high,
        '0.786': recent_low + drop_range * 0.214,
        '0.618': recent_low + drop_range * 0.618,
        '0.500': recent_low + drop_range * 0.500,
        '0.382': recent_low + drop_range * 0.382,
        '0.236': recent_low + drop_range * 0.236,
        '0.000': recent_low
    }
    
    # --- 1. 技術結構分析 ---
    # 趨勢判斷
    trend_text = ""
    if macd > signal and macd > 0:
        trend_text = "MACD多頭排列，代表短線動能相對偏強；"
    elif macd < signal and macd < 0:
        trend_text = "MACD空頭排列，代表短線空頭動能仍相對佔優；"
    else:
        trend_text = "MACD糾結，方向不明；"
        
    rsi_text = ""
    if 40 < rsi < 60:
        rsi_text = f"RSI落在{rsi:.1f}的性偏多區間，未進入超買區，顯示當前下殺動能尚未極化，整體處於多空爭奪的關鍵節點。"
    elif rsi > 70:
        rsi_text = f"RSI達到{rsi:.1f}進入超買區，需警惕回調風險。"
    else:
        rsi_text = f"RSI處於{rsi:.1f}低位，存在超賣反彈需求。"
    
    # 波浪判斷
    wave_text = f"當前價格貼近本輪上升波段的{((current_price - recent_low)/drop_range)*100:.1f}%回撤位，屬於上升浪後的深度回測階段，若守住該支撐則有機會開啟反彈浪，跌破則確認走勢轉空。"
    
    # 均線判斷
    ma_text = "均線：本次未提供均線相關數據，暫無判斷依據。" # 簡化處理，或者根據實際判斷
    if current_price > sma20: ma_text = "均線：股價站上SMA20，短線偏多。"
    elif current_price < sma200: ma_text = "均線：股價低於SMA200，長線偏空。"

    # --- 2. 關鍵位 (壓力/支撐) ---
    # 壓力位 (由近至遠 -> 價格由低到高，如果在低位反彈)
    # 這裡假設是從高點跌下來的反彈，所以阻力是上方的Fib位
    resistances = []
    supports = []
    
    # 簡單邏輯：比現價高的叫壓力，比現價低的叫支撐
    for k, v in sorted(fib_levels.items(), key=lambda x: x[1]):
        label = f"{float(k)*100:.1f}%回撤位"
        if v > current_price * 1.01: # 壓力
            resistances.append(f"{label} {v:.2f}")
        elif v < current_price * 0.99: # 支撐
            supports.append(f"{label} {v:.2f}")
            
    # 加上近期高低點
    supports.append(f"近期低點 {recent_low:.2f} ({low_date})")
    
    # --- 3. 操作參考 ---
    action_bull = f"價格穩站{recent_low:.2f}支撐之上，伴隨MACD出現黃金交叉、RSI站穩60上方，可偏多布局，第一目標看{resistances[0] if resistances else '前高'}，突破後再看下一檔。"
    action_wait = f"價格在{recent_low:.2f}-{sma20:.2f}區間震盪、MACD未出現明確翻多訊號、也未有效跌破{recent_low:.2f}支撐時，建議觀望為主，等待方向明朗。"
    action_defend = f"價格有效跌破{recent_low:.2f}支撐（連續2個交易日收盤在該價之下，或單日大跌3%以上跌破）、且RSI跌破50進入偏空區間時，建議止損防守，避免後續大幅下行風險。"

    # --- 4. 風險評分 (0-100) ---
    risk_score = 50
    risk_reason = []
    if macd < 0: 
        risk_score += 15
        risk_reason.append("MACD處於空頭結構")
    if current_price < sma200:
        risk_score += 15
        risk_reason.append("股價在年線之下")
    if rsi > 70:
        risk_score += 10
        risk_reason.append("RSI超買")
    elif rsi < 30:
        risk_score -= 10 # 超賣反而風險低（反彈機率大）
        
    risk_score = max(0, min(100, risk_score))
    risk_text = f"評分：{risk_score}分。理由：{'；'.join(risk_reason) if risk_reason else '指標中性'}。若跌破關鍵支撐，後續下行空間將打開；但當前價格貼近強支撐位，若守住則有反彈機會，多空不確定性較高。"

    # === 組裝報告 ===
    report = {}
    
    report['header'] = f"""
### 📊 {info.get('longName', ticker)} ({ticker})
**最新價格**: ${current_price:.2f} ({change_pct:+.2f}%) | **數據截止**: {df.index[-1].strftime('%Y-%m-%d')}
"""
    
    report['tech_structure'] = f"""
### 📈 技術結構
*   **趨勢**：{trend_text}但RSI落在{rsi:.1f}的性偏多區間，未進入超買區，顯示當前下殺動能尚未極化，整體處於多空爭奪的關鍵節點。
*   **波浪**：{wave_text}
*   **均線**：{ma_text}
"""

    report['key_levels'] = f"""
### 📐 關鍵位

**壓力位（由近至遠）**
1. {resistances[0] if resistances else '無明顯壓力'}
2. {resistances[1] if len(resistances) > 1 else ''}
3. {resistances[2] if len(resistances) > 2 else ''}
4. {resistances[3] if len(resistances) > 3 else ''}
5. {resistances[4] if len(resistances) > 4 else ''}

**支撐位（由近至遠）**
1. {supports[0] if supports else '無明顯支撐'} (當前價格緊鄰該位置)
2. {supports[1] if len(supports) > 1 else ''}
"""

    report['action_plan'] = f"""
### 🎯 操作參考
*   🟢 **偏多**：{action_bull}
*   🟡 **觀望**：{action_wait}
*   🔴 **防守**：{action_defend}
"""

    report['risk'] = f"""
### ⚠️ 風險 (0-100)
**評分**：{risk_score} / 100
**分析**：{risk_text}
"""

    # 圖表
    report['chart'] = generate_clean_chart(df, fib_levels)
    
    # 基本面 (簡化保留)
    report['fundamental'] = f"""
### 💎 基本面速覽
*   **行業**: {info.get('sector', 'N/A')}
*   **市值**: {info.get('marketCap', 0)/1e9:.2f} B
*   **PE**: {info.get('trailingPE', 'N/A')}
"""
    
    return report

# === 主程序 ===
if analyze_btn and ticker_input.strip():
    ticker = ticker_input.strip().upper()
    
    with st.spinner(f"🔍 正在分析 {ticker}..."):
        stock, df, info, news_data, error = fetch_stock_data(ticker)
        
        if error:
            st.error(f"❌ {error}")
        else:
            report = generate_report(ticker, df, info, news_data)
            
            # 1. 標題
            st.markdown(report['header'])
            
            # 2. 即時信號 (用 Alert 框顯示)
            st.info("🔔 **即時信號**：基於最新技術指標生成的綜合判斷。")
            
            # 3. AI 分析報告 (技術結構)
            st.markdown("### 🤖 AI 分析報告")
            st.markdown(report['tech_structure'])
            
            # 4. 關鍵位
            st.markdown(report['key_levels'])
            
            # 5. 圖表 (放在中間)
            if report['chart']:
                st.plotly_chart(report['chart'], use_container_width=True)
            
            # 6. 操作參考
            st.markdown(report['action_plan'])
            
            # 7. 風險
            st.warning(report['risk'])
            
            # 8. 基本面
            st.markdown(report['fundamental'])
            
            st.caption("⚠️ 免責聲明：本分析僅供參考，不構成投資建議。")

elif not ticker_input.strip():
    st.info("👈 請在左側輸入股票代碼開始分析")
