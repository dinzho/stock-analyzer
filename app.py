import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import math
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
st.markdown("*專業技術面 + 基本面 + 情緒面 + 策略面 四維分析*")

# === 側邊欄 ===
with st.sidebar:
    st.header("🔍 查詢設置")
    ticker_input = st.text_input("股票代碼", value="NOW", placeholder="例如：NOW, NVDA, TSLA")
    exchange = st.selectbox("交易所", ["NYSE", "NASDAQ", "HKEX"], index=0)
    analyze_btn = st.button("🚀 開始深度分析", type="primary", use_container_width=True)
    st.markdown("---")
    st.info("💡 **提示**：如果出現請求限制錯誤，請等待 15-30 分鐘後再試。")

# === 輔助函數：行業與產業鏈分析 ===
def analyze_industry_structure(sector, industry, gross_margin, roe):
    sector = str(sector).lower() if sector else ""
    industry = str(industry).lower() if industry else ""
    
    position = "中游"
    upstream_power = "中等"
    downstream_power = "中等"
    industry_nature = "一般製造/服務業"
    
    if any(x in sector for x in ['technology', 'communication']) or any(x in industry for x in ['software', 'internet', 'semiconductor']):
        industry_nature = "科技成長型 (高壁壘、高研發)"
        position = "中上游 (核心技術/平台)"
        upstream_power = "中等偏弱 (依賴高端人才/芯片/雲設施)" if gross_margin and gross_margin < 0.6 else "中等 (規模效應)"
        downstream_power = "強勢 (高轉換成本/訂閱制)" if gross_margin and gross_margin > 0.5 else "中等 (競爭激烈)"
    elif any(x in sector for x in ['consumer cyclical', 'consumer defensive']):
        industry_nature = "消費驅動型 (品牌/渠道为王)"
        position = "下游 (品牌/零售終端)"
        upstream_power = "強勢 (規模壓價權)" if gross_margin and gross_margin > 0.3 else "弱勢 (成本敏感)"
        downstream_power = "弱勢 (價格敏感)" if gross_margin and gross_margin < 0.3 else "強勢 (品牌忠誠)"
    elif any(x in sector for x in ['industrials', 'basic materials', 'energy']):
        industry_nature = "週期/製造型 (成本/產能驱动)"
        position = "中上游 (原材料/設備)"
        upstream_power = "弱勢 (受制大宗商品)"
        downstream_power = "中等 (取決產能)"
    elif 'financial' in sector:
        industry_nature = "資金密集型 (槓桿/利率驱动)"
        position = "服務中介"
        upstream_power = "弱勢 (資金成本敏感)"
        downstream_power = "中等 (同質化競爭)"

    return {
        "nature": industry_nature,
        "position": position,
        "upstream": upstream_power,
        "downstream": downstream_power
    }

# === 極簡圖表生成 ===
def generate_clean_chart(df, fib_levels):
    """生成簡潔版 K 線圖 + FIB 水平線"""
    plot_df = df.tail(252) 
    if plot_df.empty: return None
    
    x = plot_df.index
    open_ = plot_df['Open']
    high = plot_df['High']
    low = plot_df['Low']
    close = plot_df['Close']
    
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=x, open=open_, high=high, low=low, close=close,
        name="K線", increasing_line_color='#26a69a', decreasing_line_color='#ef5350',
        increasing_fillcolor='#26a69a', decreasing_fillcolor='#ef5350'
    ))

    fib_ratios = ['0.000', '0.236', '0.382', '0.500', '0.618', '0.786', '1.000']
    
    for ratio in fib_ratios:
        if ratio in fib_levels:
            y_val = fib_levels[ratio]
            fig.add_hline(y=y_val, line_dash="dot", line_color="orange", line_width=1, opacity=0.6)
            fig.add_annotation(
                y=y_val, x=1.02,
                text=f"{float(ratio)*100:.1f}%",
                showarrow=False,
                font=dict(size=10, color="orange"),
                xref="paper", yref="y",
                xanchor="left", yanchor="middle"
            )

    fig.update_layout(
        title="K线与FIB",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        height=500,
        margin=dict(l=0, r=50, t=30, b=0),
        plot_bgcolor='white',
        paper_bgcolor='white',
        hovermode='x unified'
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor='lightgray', gridwidth=0.5)
    
    return fig

# === 數據獲取函數 ===
@retry_on_rate_limit(max_retries=3, delay=3)
def fetch_stock_data(ticker):
    stock = yf.Ticker(ticker)
    df = None
    info = {}
    news_data = []
    recommendations = None
    
    try:
        df = stock.history(period="2y", interval="1d")
        if df.empty: return None, None, None, None, None, "無法獲取歷史數據"
    except Exception as e: return None, None, None, None, None, f"歷史數據獲取失敗：{e}"
    
    for _ in range(3):
        try:
            info = stock.info
            if info and 'sector' in info: break
            time.sleep(1)
        except: time.sleep(1)
    
    try:
        time.sleep(0.5)
        news_data = stock.news if hasattr(stock, 'news') and stock.news else []
    except: pass
    
    try:
        time.sleep(0.5)
        recommendations = stock.recommendations if hasattr(stock, 'recommendations') else None
    except: pass
    
    return stock, df, info, news_data, recommendations, None

# === 催化劑數據驗證函數 ===
def fetch_and_verify_catalysts(ticker, news_data, recommendations, info, df):
    verified_catalysts = {
        'upcoming_events': [], 'recent_news': [], 'analyst_actions': [],
        'product_launches': [], 'financial_events': [], 'risks': [], 'target_price': {}
    }
    current_date = datetime.datetime.now()
    
    if news_data and isinstance(news_data, list):
        for news in news_data[:10]:
            try:
                pub_date = news.get('providerPublishTime')
                if pub_date:
                    news_date = datetime.datetime.fromtimestamp(pub_date)
                    days_ago = (current_date - news_date).days
                    if days_ago <= 30:
                        title = news.get('title', '')
                        publisher = news.get('publisher', '')
                        catalyst_type = "一般"
                        k_pos = ['beat', 'surge', 'growth', 'launch', 'partnership', 'upgrade', 'AI']
                        k_neg = ['miss', 'decline', 'layoff', 'lawsuit', 'downgrade', 'risk']
                        k_earn = ['earnings', 'quarter', 'revenue', 'profit']
                        tl = title.lower()
                        if any(k in tl for k in k_earn): catalyst_type = "財報相關"
                        elif any(k in tl for k in k_pos): catalyst_type = "正面催化"
                        elif any(k in tl for k in k_neg): catalyst_type = "負面風險"
                        
                        verified_catalysts['recent_news'].append({
                            'date': news_date.strftime('%Y-%m-%d'), 'title': title,
                            'publisher': publisher, 'type': catalyst_type, 'days_ago': days_ago
                        })
            except: continue
            
    if recommendations is not None and not recommendations.empty:
        try:
            for idx, rec in recommendations.head(5).iterrows():
                firm = rec.get('Firm', 'Unknown')
                action = rec.get('Action', '')
                to_grade = rec.get('To Grade', '')
                if action or to_grade:
                    verified_catalysts['analyst_actions'].append({
                        'firm': firm, 'action': action, 'rating': to_grade,
                        'date': idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)
                    })
        except: pass

    if info:
        next_earnings = info.get('earningsDate')
        if next_earnings:
            try:
                d = next_earnings[0] if isinstance(next_earnings, list) else next_earnings
                if hasattr(d, 'strftime'):
                    verified_catalysts['upcoming_events'].append({'type': '財報發布', 'date': d.strftime('%Y-%m-%d'), 'importance': '高'})
            except: pass

    prod_k = ['launch', 'release', 'new product']
    part_k = ['partnership', 'collaboration', 'deal']
    for item in verified_catalysts['recent_news']:
        tl = item['title'].lower()
        if any(k in tl for k in prod_k): verified_catalysts['product_launches'].append(item)
        if any(k in tl for k in part_k): verified_catalysts['financial_events'].append(item)

    if info:
        if info.get('profitMargins', 0) < 0.1: verified_catalysts['risks'].append('利潤率偏低 (<10%)')
        if info.get('debtToEquity', 0) > 100: verified_catalysts['risks'].append('負債比率較高')
        if info.get('revenueGrowth', 0) < 0.05: verified_catalysts['risks'].append('營收增長放緩')
    
    if info:
        target_mean = info.get('targetMeanPrice')
        current_price = df['Close'].iloc[-1]
        if target_mean and current_price:
            up = ((target_mean - current_price)/current_price)*100
            verified_catalysts['target_price'] = {
                'mean': target_mean, 'high': info.get('targetHighPrice'), 'low': info.get('targetLowPrice'),
                'current': current_price, 'upside': up, 'verified': abs(up) < 100
            }
        
    return verified_catalysts

# === 市場情緒分析函數 ===
def get_market_sentiment(ticker, df, current_price, sma20, recent_low):
    stock_technical = "🟢 多頭" if current_price > sma20.iloc[-1] else "🔴 空頭"
    technical_detail = f"現價 ${current_price:.2f} vs SMA20 ${sma20.iloc[-1]:.2f}"
    
    current_vol = df['Volume'].iloc[-1]
    avg_vol_10 = df['Volume'].rolling(10).mean().iloc[-1]
    vol_change_pct = ((current_vol / avg_vol_10 - 1) * 100) if avg_vol_10 > 0 else 0
    
    if vol_change_pct > 20:
        stock_volume = f"📈 放量 (+{vol_change_pct:.1f}%)"
    elif vol_change_pct < -20:
        stock_volume = f"📉 縮量 ({vol_change_pct:.1f}%)"
    else:
        stock_volume = f"➡️ 平量 ({vol_change_pct:+.1f}%)"
    
    if current_price > recent_low * 1.1:
        stock_position = "🔄 反彈初期"
    elif current_price > recent_low * 1.05:
        stock_position = " 築底階段"
    else:
        stock_position = "⚠️ 接近低點"
    
    try:
        vix = yf.Ticker("^VIX").history(period="1d", interval="1d")
        vix_value = vix['Close'].iloc[-1] if not vix.empty else 20
        
        spy = yf.Ticker("^GSPC").history(period="5d", interval="1d")
        if len(spy) >= 2:
            spy_change = ((spy['Close'].iloc[-1] - spy['Close'].iloc[-2]) / spy['Close'].iloc[-2]) * 100
        else:
            spy_change = 0
            
        qqq = yf.Ticker("^IXIC").history(period="5d", interval="1d")
        if len(qqq) >= 2:
            nasdaq_change = ((qqq['Close'].iloc[-1] - qqq['Close'].iloc[-2]) / qqq['Close'].iloc[-2]) * 100
        else:
            nasdaq_change = 0
    except:
        vix_value = 20
        spy_change = 0
        nasdaq_change = 0
    
    if vix_value > 30:
        vix_mood = "😰 恐慌（高波動）"
        vix_icon = "🔴"
    elif vix_value > 25:
        vix_mood = "😟 謹慎（中高波動）"
        vix_icon = "🟠"
    elif vix_value < 18:
        vix_mood = "😌 樂觀（低波動）"
        vix_icon = "🟢"
    else:
        vix_mood = "😐 中性"
        vix_icon = "🟡"
    
    spy_icon = "🟢" if spy_change > 0 else "🔴"
    nasdaq_icon = "🟢" if nasdaq_change > 0 else "🔴"
    
    stock_change = ((current_price - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100 if len(df) > 1 else 0
    relative_vs_spy = stock_change - spy_change
    relative_vs_nasdaq = stock_change - nasdaq_change
    
    if relative_vs_spy > 2:
        relative_strength = "🟢 強於大盤"
        relative_detail = f"個股 {stock_change:+.2f}% vs 標普 {spy_change:+.2f}% (+{relative_vs_spy:.2f}%)"
    elif relative_vs_spy < -2:
        relative_strength = "🔴 弱於大盤"
        relative_detail = f"個股 {stock_change:+.2f}% vs 標普 {spy_change:+.2f}% ({relative_vs_spy:.2f}%)"
    else:
        relative_strength = "🟡 同步大盤"
        relative_detail = f"個股 {stock_change:+.2f}% vs 標普 {spy_change:+.2f}%"
    
    score = 50
    if current_price > sma20.iloc[-1]: score += 15
    else: score -= 15
    if vol_change_pct > 0: score += 10
    else: score -= 10
    if relative_vs_spy > 0: score += 15
    else: score -= 15
    if vix_value < 20: score += 10
    elif vix_value > 30: score -= 10
    score = max(0, min(100, score))
    
    if score >= 70:
        overall_recommendation = "✅ 多頭環境：個股強勁 + 大盤穩定，適合積極操作"
    elif score >= 55:
        overall_recommendation = "⚖️ 中性偏多：環境尚可，建議精選個股、控制倉位"
    elif score >= 40:
        overall_recommendation = "⚠️ 中性偏空：大盤波動或個股弱勢，建議謹慎觀望"
    else:
        overall_recommendation = "❌ 空頭環境：風險較高，建議防守為主"
    
    prev_close = df['Close'].iloc[-2] if len(df) > 1 else current_price
    price_change_pct = ((current_price - prev_close) / prev_close) * 100
    
    return {
        'stock_technical': stock_technical,
        'technical_detail': technical_detail,
        'stock_volume': stock_volume,
        'stock_position': stock_position,
        'vix_value': vix_value,
        'vix_mood': vix_mood,
        'vix_icon': vix_icon,
        'spy_change': spy_change,
        'spy_icon': spy_icon,
        'nasdaq_change': nasdaq_change,
        'nasdaq_icon': nasdaq_icon,
        'relative_strength': relative_strength,
        'relative_detail': relative_detail,
        'score': score,
        'overall_recommendation': overall_recommendation,
        'price_change_pct': price_change_pct
    }

# === 核心報告生成函數 ===
def generate_deep_report(ticker, exchange):
    stock, df, info, news_data, recommendations, error = fetch_stock_data(ticker)
    if error: return None, None, error
    
    if not info:
        st.warning("⚠️ 基本面數據 (Info) 獲取受限，部分報表數據將顯示為 N/A")

    # === 計算指標 ===
    current_price = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2] if len(df) > 1 else current_price
    price_change_pct = ((current_price - prev_close) / prev_close) * 100
    
    recent_high = df['High'].max()
    recent_low = df['Low'].min()
    high_date = df['High'].idxmax().strftime('%Y-%m')
    low_date = df['Low'].idxmin().strftime('%Y-%m-%d')
    
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=9, adjust=False).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    current_macd = macd.iloc[-1]
    current_signal = signal_line.iloc[-1]
    current_rsi = rsi.iloc[-1]
    
    sma20 = df['Close'].rolling(20).mean()
    sma50 = df['Close'].rolling(50).mean()
    sma200 = df['Close'].rolling(200).mean()
    
    drop_range = recent_high - recent_low
    fib_levels = {
        'high_price': recent_high, 'low_price': recent_low,
        '1.000': recent_high, '0.786': recent_low + drop_range * 0.214,
        '0.618': recent_low + drop_range * 0.618, '0.500': recent_low + drop_range * 0.5,
        '0.382': recent_low + drop_range * 0.382, '0.236': recent_low + drop_range * 0.236, '0.000': recent_low
    }
    
    with st.spinner(" 正在生成圖表..."):
        fig = generate_clean_chart(df, fib_levels)

    with st.spinner("🔍 正在抓取並驗證催化劑數據..."):
        verified_catalysts = fetch_and_verify_catalysts(ticker, news_data, recommendations, info, df)

    with st.spinner("📊 正在分析市場情緒..."):
        sentiment_data = get_market_sentiment(ticker, df, current_price, sma20, recent_low)

    high_52w = df['High'].rolling(252).max().iloc[-1]
    low_52w = df['Low'].rolling(252).min().iloc[-1]
    
    def safe_get(key, default=None):
        try:
            if not info: return default
            val = info.get(key)
            return val if val is not None and not pd.isna(val) else default
        except: return default

    sector = safe_get('sector')
    industry = safe_get('industry')
    gross_margin = safe_get('grossMargins')
    roe = safe_get('returnOnEquity')
    pe_ratio = safe_get('trailingPE')
    revenue_growth = safe_get('revenueGrowth')
    market_cap = safe_get('marketCap')
    beta = safe_get('beta', 1)
    
    industry_analysis = analyze_industry_structure(sector, industry, gross_margin, roe)
    
    today_str = datetime.datetime.now().strftime('%Y-%m-%d')
    last_trade_date = df.index[-1].strftime('%Y-%m-%d')
    
    report = {}
    
    # === 1. 標題與核心數據 ===
    report['header'] = f"""
### 📊 {safe_get('longName', ticker.upper())} ({ticker}:{exchange})
> **📅 數據基準**：{last_trade_date} | **💰 現價**：${current_price:.2f} ({price_change_pct:+.2f}%)  
> **52周**：${low_52w:.1f} - ${high_52w:.1f} | **市值**：${market_cap/1e9:.2f}B (若數據可用)
"""

    # === 2. 技術結構 ===
    if current_macd > current_signal and current_macd > 0:
        trend_text = "MACD多頭排列，短線動能偏強"
    elif current_macd < current_signal and current_macd < 0:
        trend_text = "MACD空頭排列，短線動能偏弱"
    else:
        trend_text = "MACD糾結，方向不明"
        
    if 40 < current_rsi < 60:
        rsi_text = f"RSI {current_rsi:.1f}（中性偏多）"
    elif current_rsi > 70:
        rsi_text = f"RSI {current_rsi:.1f}（超買警示）"
    else:
        rsi_text = f"RSI {current_rsi:.1f}（超賣反彈）"
    
    fib_position = ((current_price - recent_low)/drop_range)*100 if drop_range > 0 else 0
    wave_text = f"位於波段 {fib_position:.1f}% 回撤位"
    
    report['tech_structure'] = f"""
### 📈 技術結構
*   **趨勢**：{trend_text}
*   **動能**：{rsi_text}
*   **位置**：{wave_text}
*   **均線**：{"✅ 站上SMA20" if current_price > sma20.iloc[-1] else "⚠️ 低於SMA20"} | {"✅ 站上SMA200" if current_price > sma200.iloc[-1] else "🔴 低於SMA200"}
"""

    # === 3. 關鍵位 ===
    fib_names = {
        '0.236': '23.6%回撤位',
        '0.382': '38.2%回撤位',
        '0.500': '50.0%回撤位',
        '0.618': '61.8%回撤位',
        '0.786': '78.6%回撤位'
    }
    
    all_levels = []
    for key, name in fib_names.items():
        if key in fib_levels:
            all_levels.append({'name': name, 'price': fib_levels[key]})
    
    all_levels.append({'name': '近期低點', 'price': recent_low})
    all_levels.append({'name': '近期高點', 'price': recent_high})
    
    resistances_raw = [lvl for lvl in all_levels if lvl['price'] > current_price * 1.005]
    supports_raw = [lvl for lvl in all_levels if lvl['price'] < current_price * 0.995]
    
    resistances_raw.sort(key=lambda x: x['price'])
    supports_raw.sort(key=lambda x: x['price'], reverse=True)
    
    resistance_lines = [f"{i}. {lvl['name']} ${lvl['price']:.2f}" for i, lvl in enumerate(resistances_raw[:5], 1)]
    support_lines = [f"{i}. {lvl['name']} ${lvl['price']:.2f}{' (緊鄰)' if i == 1 and abs(supports_raw[0]['price'] - current_price) / current_price < 0.05 else ''}" for i, lvl in enumerate(supports_raw[:5], 1)]
    
    report['key_levels'] = f"""
### 📐 關鍵位

**壓力位（由近至遠）**
{chr(10).join(resistance_lines) if resistance_lines else "暫無明顯壓力"}

**支撐位（由近至遠）**
{chr(10).join(support_lines) if support_lines else "暫無明顯支撐"}
"""

    # === 4. 圖表 ===
    # (在 main 中顯示)

    # === 5. 市場情緒 ===
    report['sentiment'] = f"""
### 🧠 市場情緒

**個股情緒**
*   技術：{sentiment_data['stock_technical']}
*   資金：{sentiment_data['stock_volume']}
*   位置：{sentiment_data['stock_position']}

**大盤環境**
*   標普 500：{sentiment_data['spy_icon']} {sentiment_data['spy_change']:+.2f}%
*   納指：{sentiment_data['nasdaq_icon']} {sentiment_data['nasdaq_change']:+.2f}%
*   VIX：{sentiment_data['vix_icon']} {sentiment_data['vix_value']:.1f} ({sentiment_data['vix_mood']})
*   相對強弱：{sentiment_data['relative_strength']}

**綜合評分**：{sentiment_data['score']}/100  
{sentiment_data['overall_recommendation']}
"""

    # === 6. 基本面分析 ===
    report['fundamental'] = f"""
### 💎 基本面分析

**行業定位**
*   所屬：{sector or 'N/A'} / {industry or 'N/A'}
*   性質：{industry_analysis['nature']}
*   位置：{industry_analysis['position']}

**議價能力**
*   對上游：{industry_analysis['upstream']}
*   對下游：{industry_analysis['downstream']}
*   總結：{"✅ 雙向強勢" if industry_analysis['downstream'] == "強勢" and industry_analysis['upstream'] == "強勢" else "⚖️ 競爭激烈"}
"""

    # === 7. 財報分析 ===
    report['financial'] = f"""
### 💰 財報分析

| 指標 | 數值 | 評估 |
| :--- | :--- | :--- |
| **ROE** | {f"{roe*100:.1f}%" if roe else "N/A"} | {"✅ 優秀 (>15%)" if roe and roe > 0.15 else "⚠️ 一般" if roe else "N/A"} |
| **營收增長** | {f"{revenue_growth*100:.1f}%" if revenue_growth else "N/A"} | {"🚀 高速 (>20%)" if revenue_growth and revenue_growth > 0.2 else "📈 穩健" if revenue_growth and revenue_growth > 0.1 else "🐢 放緩" if revenue_growth else "N/A"} |
| **毛利率** | {f"{gross_margin*100:.1f}%" if gross_margin else "N/A"} | {"💰 高毛利 (>50%)" if gross_margin and gross_margin > 0.5 else "🏭 標準" if gross_margin else "N/A"} |
| **PE (TTM)** | {f"{pe_ratio:.1f}x" if pe_ratio else "N/A"} | {"💸 高估值" if pe_ratio and pe_ratio > 40 else "⚖️ 合理" if pe_ratio and 15 < pe_ratio < 40 else "💰 低估值" if pe_ratio and pe_ratio < 15 else "N/A"} |
"""

    # === 8. 投資評級 ===
    # 計算投資評級
    rating_score = 0
    rating_reasons = []
    
    if roe and roe > 0.15:
        rating_score += 2
        rating_reasons.append("ROE優秀")
    if revenue_growth and revenue_growth > 0.15:
        rating_score += 2
        rating_reasons.append("增長強勁")
    if pe_ratio and pe_ratio < 30:
        rating_score += 1
        rating_reasons.append("估值合理")
    if current_price > sma200.iloc[-1]:
        rating_score += 1
        rating_reasons.append("趨勢向上")
    if sentiment_data['score'] >= 60:
        rating_score += 1
        rating_reasons.append("情緒偏多")
    
    if rating_score >= 6:
        rating = "🟢 強烈買入"
        rating_detail = f"評分：{rating_score}/7 - {'、'.join(rating_reasons)}"
    elif rating_score >= 4:
        rating = "🟡 買入/增持"
        rating_detail = f"評分：{rating_score}/7 - {'、'.join(rating_reasons)}"
    elif rating_score >= 2:
        rating = "🟠 持有/觀望"
        rating_detail = f"評分：{rating_score}/7 - {'、'.join(rating_reasons)}"
    else:
        rating = "🔴 減持/賣出"
        rating_detail = f"評分：{rating_score}/7 - {'、'.join(rating_reasons) if rating_reasons else '多項指標偏弱'}"
    
    report['rating'] = f"""
### 🏆 投資評級

**{rating}**  
{rating_detail}

**分析師目標價**：${verified_catalysts['target_price'].get('mean', 'N/A'):.2f} (upside {verified_catalysts['target_price'].get('upside', 0):+.1f}%) (若數據可用)
"""

    # === 9. 操作策略（入場點 + 止盈止損）===
    first_support = supports_raw[0]['price'] if supports_raw else recent_low
    second_support = supports_raw[1]['price'] if len(supports_raw) > 1 else first_support * 0.95
    third_support = supports_raw[2]['price'] if len(supports_raw) > 2 else first_support * 0.85
    
    first_resistance = resistances_raw[0]['price'] if resistances_raw else recent_high
    second_resistance = resistances_raw[1]['price'] if len(resistances_raw) > 1 else first_resistance * 1.1
    third_resistance = resistances_raw[2]['price'] if len(resistances_raw) > 2 else first_resistance * 1.2
    
    short_entry = first_support * 1.02  # 短線在支撐位附近2%內入場
    long_entry = second_support * 1.03  # 長線在第二支撐位附近3%內入場
    
    stop_loss_short = first_support * 0.97  # 短線止損在支撐下3%
    stop_loss_long = third_support * 0.95   # 長線止損在第三支撐下5%
    
    take_profit_1 = first_resistance * 0.98  # 第一止盈在阻力下2%
    take_profit_2 = second_resistance * 0.97 # 第二止盈在第二阻力下3%
    take_profit_3 = third_resistance * 0.95  # 第三止盈
    
    report['strategy'] = f"""
### 🎯 操作策略

**入場位置**
*   🟢 **短線回調入場**：${short_entry:.2f} (靠近第一支撐 ${first_support:.2f})
*   🔵 **長線回調入場**：${long_entry:.2f} (靠近第二支撐 ${second_support:.2f})

**止盈目標**
*   🎯 **第一目標**：${take_profit_1:.2f} (阻力 ${first_resistance:.2f})
*   🎯 **第二目標**：${take_profit_2:.2f} (阻力 ${second_resistance:.2f})
*   🎯 **第三目標**：${take_profit_3:.2f} (阻力 ${third_resistance:.2f})

**止損策略**
*   🔴 **短線止損**：${stop_loss_short:.2f} (跌破第一支撐 3%)
*   🔴 **長線止損**：${stop_loss_long:.2f} (跌破第三支撐 5%)

**風險回報比**
*   短線：1:{((take_profit_1 - short_entry) / (short_entry - stop_loss_short)):.1f}
*   長線：1:{((take_profit_2 - long_entry) / (long_entry - stop_loss_long)):.1f}
"""

    # === 10. 催化劑 ===
    catalysts_text = "### 🔮 催化劑與風險\n\n"
    
    if verified_catalysts['upcoming_events']:
        catalysts_text += "**即將發生事件**\n"
        for event in verified_catalysts['upcoming_events'][:2]:
            catalysts_text += f"*   📅 {event['date']} | {event['type']}\n"
        catalysts_text += "\n"
    
    if verified_catalysts['analyst_actions']:
        catalysts_text += "**分析師評級**\n"
        for action in verified_catalysts['analyst_actions'][:2]:
            catalysts_text += f"*   {action['firm']}: {action['action']} → {action['rating']}\n"
        catalysts_text += "\n"
    
    if verified_catalysts['risks']:
        catalysts_text += "**風險因素**\n"
        for risk in verified_catalysts['risks'][:3]:
            if isinstance(risk, dict):
                catalysts_text += f"*   ⚠️ {risk['title'][:60]}...\n"
            else:
                catalysts_text += f"*   ⚠️ {risk}\n"
    
    report['catalysts'] = catalysts_text

    # === 11. 免責聲明 ===
    report['disclaimer'] = f"""
---
### ⚠️ 免責聲明
本報告僅供參考，不構成投資建議。數據來源：Yahoo Finance | 生成時間：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    return report, fig, None

# === 主程序 ===
if analyze_btn and ticker_input.strip():
    ticker = ticker_input.strip().upper()
    
    with st.spinner(f"🔍 正在深度分析 {ticker}..."):
        try:
            report, fig, error = generate_deep_report(ticker, exchange)
            
            if error:
                st.error(f"❌ {error}")
            else:
                # 專業排版順序
                st.markdown(report['header'])
                st.markdown("---")
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.markdown(report['tech_structure'])
                with col2:
                    st.markdown(report['key_levels'])
                
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                
                st.markdown(report['sentiment'])
                st.markdown("---")
                
                col3, col4 = st.columns(2)
                with col3:
                    st.markdown(report['fundamental'])
                with col4:
                    st.markdown(report['financial'])
                
                st.markdown(report['rating'])
                st.markdown(report['strategy'])
                st.markdown(report['catalysts'])
                st.markdown(report['disclaimer'])
                
        except Exception as e:
            st.error(f"❌ 系統錯誤：{e}")
            st.exception(e)

elif not ticker_input.strip():
    st.info("👈 請在左側輸入股票代碼開始分析")
