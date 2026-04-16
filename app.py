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

# === 側邊欄 ===
with st.sidebar:
    st.header("🔍 查詢設置")
    ticker_input = st.text_input("股票代碼", value="NOW", placeholder="例如：NOW, NVDA, TSLA")
    exchange = st.selectbox("交易所", ["NYSE", "NASDAQ", "HKEX"], index=0)
    analyze_btn = st.button("🚀 開始深度分析", type="primary", use_container_width=True)
    st.markdown("---")
    st.info("💡 **提示**：如果出現請求限制，請等待 15-30 分鐘後再試。")

# === 行業分析函數 ===
def analyze_industry_structure(sector, industry, gross_margin, roe):
    sector = str(sector).lower() if sector else ""
    industry = str(industry).lower() if industry else ""
    
    if any(x in sector for x in ['technology', 'communication']) or any(x in industry for x in ['software', 'internet', 'semiconductor']):
        return "科技成長型", "中上游 (核心技術)", "中等", "強勢 (訂閱制)"
    elif any(x in sector for x in ['consumer cyclical', 'consumer defensive']):
        return "消費驅動型", "下游 (品牌終端)", "強勢 (規模)", "弱勢 (價格敏感)"
    elif any(x in sector for x in ['industrials', 'basic materials', 'energy']):
        return "週期製造型", "中上游 (原材料)", "弱勢", "中等"
    elif 'financial' in sector:
        return "資金密集型", "服務中介", "弱勢", "中等"
    else:
        return "一般行業", "中游", "中等", "中等"

# === 圖表生成 ===
def generate_clean_chart(df, fib_levels):
    plot_df = df.tail(252) 
    if plot_df.empty: return None
    
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=plot_df.index, open=plot_df['Open'], high=plot_df['High'],
        low=plot_df['Low'], close=plot_df['Close'], name="K線",
        increasing_line_color='#26a69a', decreasing_line_color='#ef5350',
        increasing_fillcolor='#26a69a', decreasing_fillcolor='#ef5350'
    ))

    for ratio in ['0.000', '0.236', '0.382', '0.500', '0.618', '0.786', '1.000']:
        if ratio in fib_levels:
            y_val = fib_levels[ratio]
            fig.add_hline(y=y_val, line_dash="dot", line_color="orange", line_width=1, opacity=0.6)
            fig.add_annotation(y=y_val, x=1.02, text=f"{float(ratio)*100:.1f}%",
                showarrow=False, font=dict(size=10, color="orange"),
                xref="paper", yref="y", xanchor="left", yanchor="middle")

    fig.update_layout(title="K线与FIB", yaxis_title="Price", xaxis_rangeslider_visible=False,
        height=500, margin=dict(l=0, r=50, t=30, b=0), plot_bgcolor='white',
        paper_bgcolor='white', hovermode='x unified')
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor='lightgray', gridwidth=0.5)
    return fig

# === 數據獲取 ===
@retry_on_rate_limit(max_retries=3, delay=3)
def fetch_stock_data(ticker):
    stock = yf.Ticker(ticker)
    try:
        df = stock.history(period="2y", interval="1d")
        if df.empty: return None, None, None, None, None, "無法獲取歷史數據"
    except Exception as e: return None, None, None, None, None, f"歷史數據失敗：{e}"
    
    info = {}
    for _ in range(3):
        try:
            info = stock.info
            if info and 'sector' in info: break
            time.sleep(1)
        except: time.sleep(1)
    
    try:
        time.sleep(0.5)
        news_data = stock.news if hasattr(stock, 'news') and stock.news else []
    except: news_data = []
    
    try:
        time.sleep(0.5)
        recommendations = stock.recommendations if hasattr(stock, 'recommendations') else None
    except: recommendations = None
    
    return stock, df, info, news_data, recommendations, None

# === 催化劑驗證 ===
def fetch_and_verify_catalysts(ticker, news_data, recommendations, info, df):
    verified = {'upcoming_events': [], 'recent_news': [], 'analyst_actions': [], 'risks': [], 'target_price': {}}
    current_date = datetime.datetime.now()
    
    if news_data and isinstance(news_data, list):
        for news in news_data[:10]:
            try:
                pub_date = news.get('providerPublishTime')
                if pub_date:
                    news_date = datetime.datetime.fromtimestamp(pub_date)
                    if (current_date - news_date).days <= 30:
                        title = news.get('title', '')
                        catalyst_type = "財報" if any(k in title.lower() for k in ['earnings', 'quarter']) else \
                                       "正面" if any(k in title.lower() for k in ['beat', 'surge', 'growth', 'upgrade']) else \
                                       "風險" if any(k in title.lower() for k in ['miss', 'decline', 'downgrade', 'risk']) else "一般"
                        verified['recent_news'].append({'date': news_date.strftime('%Y-%m-%d'), 'title': title, 'type': catalyst_type})
            except: continue
    
    if recommendations is not None and not recommendations.empty:
        for idx, rec in recommendations.head(3).iterrows():
            verified['analyst_actions'].append({
                'firm': rec.get('Firm', 'Unknown'), 'action': rec.get('Action', ''),
                'rating': rec.get('To Grade', ''), 'date': idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)
            })
    
    if info:
        next_earnings = info.get('earningsDate')
        if next_earnings:
            try:
                d = next_earnings[0] if isinstance(next_earnings, list) else next_earnings
                if hasattr(d, 'strftime'):
                    verified['upcoming_events'].append({'type': '財報發布', 'date': d.strftime('%Y-%m-%d')})
            except: pass
        
        target_mean = info.get('targetMeanPrice')
        current_price = df['Close'].iloc[-1]
        if target_mean and current_price:
            up = ((target_mean - current_price)/current_price)*100
            verified['target_price'] = {'mean': target_mean, 'upside': up}
        
        if info.get('profitMargins', 0) < 0.1: verified['risks'].append('利潤率偏低')
        if info.get('debtToEquity', 0) > 100: verified['risks'].append('負債比率高')
        if info.get('revenueGrowth', 0) < 0.05: verified['risks'].append('營收增長放緩')
    
    return verified

# === 市場情緒 ===
def get_market_sentiment(ticker, df, current_price, sma20, recent_low):
    stock_technical = "🟢 多頭" if current_price > sma20.iloc[-1] else "🔴 空頭"
    current_vol = df['Volume'].iloc[-1]
    avg_vol_10 = df['Volume'].rolling(10).mean().iloc[-1]
    vol_change = ((current_vol / avg_vol_10 - 1) * 100) if avg_vol_10 > 0 else 0
    stock_volume = f"📈 放量 (+{vol_change:.0f}%)" if vol_change > 20 else f"📉 縮量 ({vol_change:.0f}%)" if vol_change < -20 else f"➡️ 平量"
    
    try:
        vix = yf.Ticker("^VIX").history(period="1d", interval="1d")
        vix_value = vix['Close'].iloc[-1] if not vix.empty else 20
        spy = yf.Ticker("^GSPC").history(period="5d", interval="1d")
        spy_change = ((spy['Close'].iloc[-1] - spy['Close'].iloc[-2]) / spy['Close'].iloc[-2]) * 100 if len(spy) >= 2 else 0
    except:
        vix_value, spy_change = 20, 0
    
    vix_mood = "😰 恐慌" if vix_value > 30 else "😟 謹慎" if vix_value > 25 else "😌 樂觀" if vix_value < 18 else "😐 中性"
    stock_change = ((current_price - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100 if len(df) > 1 else 0
    relative = "🟢 強於大盤" if stock_change > spy_change + 2 else "🔴 弱於大盤" if stock_change < spy_change - 2 else "🟡 同步大盤"
    
    score = 50
    if current_price > sma20.iloc[-1]: score += 15
    if vol_change > 0: score += 10
    if stock_change > spy_change: score += 15
    if vix_value < 20: score += 10
    score = max(0, min(100, score))
    
    recommendation = "✅ 積極操作" if score >= 70 else "⚖️ 控制倉位" if score >= 55 else "⚠️ 謹慎觀望" if score >= 40 else "❌ 防守為主"
    
    return {'technical': stock_technical, 'volume': stock_volume, 'vix': vix_value, 'vix_mood': vix_mood,
            'spy_change': spy_change, 'relative': relative, 'score': score, 'recommendation': recommendation}

# === 核心報告生成 ===
def generate_deep_report(ticker, exchange):
    stock, df, info, news_data, recommendations, error = fetch_stock_data(ticker)
    if error: return None, None, error
    
    if not info: st.warning("⚠️ 基本面數據獲取受限")

    # === 基礎數據 ===
    current_price = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2] if len(df) > 1 else current_price
    price_change_pct = ((current_price - prev_close) / prev_close) * 100
    
    recent_high = df['High'].max()
    recent_low = df['Low'].min()
    
    # 技術指標
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=9, adjust=False).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi = 100 - (100 / (1 + gain / loss))
    
    sma20 = df['Close'].rolling(20).mean()
    sma50 = df['Close'].rolling(50).mean()
    sma200 = df['Close'].rolling(200).mean()
    
    # FIB
    drop_range = recent_high - recent_low
    fib_levels = {
        '1.000': recent_high, '0.786': recent_low + drop_range * 0.214,
        '0.618': recent_low + drop_range * 0.618, '0.500': recent_low + drop_range * 0.5,
        '0.382': recent_low + drop_range * 0.382, '0.236': recent_low + drop_range * 0.236, '0.000': recent_low
    }
    
    # 生成圖表
    fig = generate_clean_chart(df, fib_levels)
    
    # 獲取數據
    verified_catalysts = fetch_and_verify_catalysts(ticker, news_data, recommendations, info, df)
    sentiment = get_market_sentiment(ticker, df, current_price, sma20, recent_low)
    
    # 安全獲取
    def safe_get(key, default=None):
        try:
            val = info.get(key) if info else None
            return val if val is not None and not pd.isna(val) else default
        except: return default

    sector = safe_get('sector', 'N/A')
    industry = safe_get('industry', 'N/A')
    gross_margin = safe_get('grossMargins')
    roe = safe_get('returnOnEquity')
    pe_ratio = safe_get('trailingPE')
    revenue_growth = safe_get('revenueGrowth')
    market_cap = safe_get('marketCap')
    
    industry_type, position, upstream, downstream = analyze_industry_structure(sector, industry, gross_margin, roe)
    
    # 關鍵位
    fib_names = {'0.236': '23.6%', '0.382': '38.2%', '0.500': '50.0%', '0.618': '61.8%', '0.786': '78.6%'}
    all_levels = [{'name': name, 'price': fib_levels[key]} for key, name in fib_names.items() if key in fib_levels]
    all_levels.extend([{'name': '近期低點', 'price': recent_low}, {'name': '近期高點', 'price': recent_high}])
    
    resistances = sorted([lvl for lvl in all_levels if lvl['price'] > current_price * 1.005], key=lambda x: x['price'])
    supports = sorted([lvl for lvl in all_levels if lvl['price'] < current_price * 0.995], key=lambda x: x['price'], reverse=True)
    
    first_support = supports[0]['price'] if supports else recent_low
    second_support = supports[1]['price'] if len(supports) > 1 else first_support * 0.95
    third_support = supports[2]['price'] if len(supports) > 2 else first_support * 0.85
    
    first_resistance = resistances[0]['price'] if resistances else recent_high
    second_resistance = resistances[1]['price'] if len(resistances) > 1 else first_resistance * 1.1
    third_resistance = resistances[2]['price'] if len(resistances) > 2 else first_resistance * 1.2
    
    # 入場點與止盈止損
    short_entry = first_support * 1.01
    long_entry = second_support * 1.02
    stop_loss_short = first_support * 0.97
    stop_loss_long = third_support * 0.95
    take_profit_1 = first_resistance * 0.99
    take_profit_2 = second_resistance * 0.98
    take_profit_3 = third_resistance * 0.97
    
    # 投資評級評分
    rating_score = 0
    if roe and roe > 0.15: rating_score += 2
    if revenue_growth and revenue_growth > 0.15: rating_score += 2
    if pe_ratio and pe_ratio < 30: rating_score += 1
    if current_price > sma200.iloc[-1]: rating_score += 1
    if sentiment['score'] >= 60: rating_score += 1
    
    rating = "🟢 強烈買入" if rating_score >= 6 else "🟡 買入/增持" if rating_score >= 4 else "🟠 持有/觀望" if rating_score >= 2 else "🔴 減持"
    
    last_trade_date = df.index[-1].strftime('%Y-%m-%d')
    
    # === 組裝報告 ===
    report = {}
    
    report['header'] = f"""
### 📊 {safe_get('longName', ticker.upper())} ({ticker}:{exchange})
**現價**: ${current_price:.2f} ({price_change_pct:+.2f}%) | **52周**: ${df['Low'].rolling(252).min().iloc[-1]:.1f} - ${df['High'].rolling(252).max().iloc[-1]:.1f} | **市值**: ${market_cap/1e9:.2f}B (若可用)  
**數據日期**: {last_trade_date}
"""
    
    report['chart'] = fig
    
    report['tech_summary'] = f"""
**技術指標**
*   MACD: {"🟢 多頭" if macd.iloc[-1] > signal_line.iloc[-1] else "🔴 空頭"}
*   RSI: {rsi.iloc[-1]:.1f} {"(超買)" if rsi.iloc[-1] > 70 else "(超賣)" if rsi.iloc[-1] < 30 else ""}
*   均線: {"✅ SMA20" if current_price > sma20.iloc[-1] else "⚠️ SMA20"} | {"✅ SMA200" if current_price > sma200.iloc[-1] else "🔴 SMA200"}
"""
    
    res_lines = [f"{i}. {lvl['name']} ${lvl['price']:.2f}" for i, lvl in enumerate(resistances[:5], 1)]
    sup_lines = [f"{i}. {lvl['name']} ${lvl['price']:.2f}{' (緊鄰)' if i == 1 else ''}" for i, lvl in enumerate(supports[:5], 1)]
    
    report['key_levels'] = f"""
**關鍵位**
*   **壓力**: {', '.join([f"${lvl['price']:.2f}" for lvl in resistances[:3]]) if resistances else "無"}
*   **支撐**: {', '.join([f"${lvl['price']:.2f}" for lvl in supports[:3]]) if supports else "無"}
"""
    
    report['sentiment'] = f"""
**市場情緒** ({sentiment['score']}/100)
*   技術：{sentiment['technical']} | 資金：{sentiment['volume']}
*   大盤：標普 {sentiment['spy_change']:+.2f}% | VIX {sentiment['vix']:.1f} ({sentiment['vix_mood']})
*   相對：{sentiment['relative']}
*   建議：{sentiment['recommendation']}
"""
    
    report['fundamental'] = f"""
**基本面分析**
*   行業：{sector} / {industry}
*   類型：{industry_type}
*   位置：{position}
*   議價：上游 {upstream} | 下游 {downstream}
"""
    
    report['financial'] = f"""
**財報指標**
| 指標 | 數值 | 評估 |
| :--- | :--- | :--- |
| ROE | {f"{roe*100:.1f}%" if roe else "N/A"} | {"✅ 優秀" if roe and roe > 0.15 else "⚠️ 一般" if roe else "N/A"} |
| 營收增長 | {f"{revenue_growth*100:.1f}%" if revenue_growth else "N/A"} | {"🚀 高速" if revenue_growth and revenue_growth > 0.2 else "📈 穩健" if revenue_growth and revenue_growth > 0.1 else "🐢 放緩" if revenue_growth else "N/A"} |
| 毛利率 | {f"{gross_margin*100:.1f}%" if gross_margin else "N/A"} | {"💰 高" if gross_margin and gross_margin > 0.5 else "🏭 標準" if gross_margin else "N/A"} |
| PE | {f"{pe_ratio:.1f}x" if pe_ratio else "N/A"} | {"💸 高" if pe_ratio and pe_ratio > 40 else "⚖️ 合理" if pe_ratio and 15 < pe_ratio < 40 else "💰 低" if pe_ratio and pe_ratio < 15 else "N/A"} |
"""
    
    report['rating'] = f"""
**投資評級**: {rating}
*   評分：{rating_score}/7
*   目標價：${verified_catalysts['target_price'].get('mean', 'N/A'):.2f} (upside {verified_catalysts['target_price'].get('upside', 0):+.1f}%) (若可用)
"""
    
    report['entry_strategy'] = f"""
**入場策略**
*   🟢 **短線回調入場**: ${short_entry:.2f} (支撐 ${first_support:.2f} 附近)
*   🔵 **長線回調入場**: ${long_entry:.2f} (支撐 ${second_support:.2f} 附近)

**止盈目標**
*   🎯 T1: ${take_profit_1:.2f} | T2: ${take_profit_2:.2f} | T3: ${take_profit_3:.2f}

**止損策略**
*   🔴 **短線止損**: ${stop_loss_short:.2f} (跌破支撐 3%)
*   🔴 **長線止損**: ${stop_loss_long:.2f} (跌破支撐 5%)

**風險回報比**
*   短線: 1:{((take_profit_1 - short_entry) / (short_entry - stop_loss_short)):.1f}
*   長線: 1:{((take_profit_2 - long_entry) / (long_entry - stop_loss_long)):.1f}
"""
    
    catalysts_text = "**催化劑與風險**\n"
    if verified_catalysts['upcoming_events']:
        catalysts_text += "\n**即將事件**\n"
        for event in verified_catalysts['upcoming_events'][:2]:
            catalysts_text += f"*   📅 {event['date']} | {event['type']}\n"
    
    if verified_catalysts['analyst_actions']:
        catalysts_text += "\n**分析師評級**\n"
        for action in verified_catalysts['analyst_actions'][:2]:
            catalysts_text += f"*   {action['firm']}: {action['rating']}\n"
    
    if verified_catalysts['risks']:
        catalysts_text += "\n**風險因素**\n"
        for risk in verified_catalysts['risks'][:3]:
            catalysts_text += f"*   ⚠️ {risk}\n"
    
    report['catalysts'] = catalysts_text
    
    report['disclaimer'] = f"""
---
⚠️ **免責聲明**：本報告僅供參考，不構成投資建議。數據來源：Yahoo Finance | 生成時間：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
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
                # === 專業排版 ===
                st.markdown(report['header'])
                st.markdown("---")
                
                # 1. 圖表 (第一位)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                
                # 2. 技術摘要與關鍵位 (並排)
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown(report['tech_summary'])
                with col2:
                    st.markdown(report['key_levels'])
                with col3:
                    st.markdown(report['sentiment'])
                
                st.markdown("---")
                
                # 3. 基本面與財報 (並排)
                col4, col5 = st.columns(2)
                with col4:
                    st.markdown(report['fundamental'])
                with col5:
                    st.markdown(report['financial'])
                
                # 4. 投資評級
                st.markdown(report['rating'])
                st.markdown("---")
                
                # 5. 操作策略
                st.markdown(report['entry_strategy'])
                
                # 6. 催化劑
                st.markdown(report['catalysts'])
                
                # 7. 免責聲明
                st.markdown(report['disclaimer'])
                
        except Exception as e:
            st.error(f"❌ 系統錯誤：{e}")
            st.exception(e)

elif not ticker_input.strip():
    st.info("👈 請在左側輸入股票代碼開始分析")
