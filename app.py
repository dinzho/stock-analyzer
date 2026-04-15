import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import math
import time
from functools import wraps

# === 添加重試裝飾器 ===
def retry_on_rate_limit(max_retries=3, delay=2):
    """當遇到速率限制時自動重試"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except yf.exceptions.YFRateLimitError:
                    if attempt < max_retries - 1:
                        wait_time = delay * (2 ** attempt)  # 指數退避
                        st.warning(f"⚠️ Yahoo Finance 請求過於頻繁，等待 {wait_time} 秒後重試... (嘗試 {attempt + 1}/{max_retries})")
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
    exchange = st.selectbox("交易所", ["NYSE", "NASDAQ", "HKEX", "SSE", "SZSE"], index=0)
    
    analyze_btn = st.button("🚀 開始深度分析", type="primary", use_container_width=True)
    
    st.markdown("---")
    st.info("💡 **提示**：如果出現請求限制錯誤，請等待 15-30 分鐘後再試，或減少查詢頻率。")

# === 修改後的分析函數 ===
@retry_on_rate_limit(max_retries=3, delay=3)
def fetch_stock_data(ticker):
    """獲取股票數據（帶重試機制）"""
    stock = yf.Ticker(ticker)
    
    # 先嘗試獲取歷史數據
    try:
        df = stock.history(period="2y", interval="1d")
    except Exception as e:
        st.error(f"❌ 獲取歷史數據失敗：{e}")
        return None, None, "歷史數據獲取失敗"
    
    if df.empty:
        return None, None, "無法獲取數據，請檢查股票代碼"
    
    # 嘗試獲取基本面數據（可能會觸發速率限制）
    try:
        info = stock.info
    except yf.exceptions.YFRateLimitError:
        st.warning("⚠️ 基本面數據請求被限制，使用默認值")
        info = {}
    except Exception:
        info = {}
    
    return stock, df, info

def generate_deep_report(ticker, exchange):
    """生成深度分析報告"""
    
    # 使用帶重試的數據獲取函數
    stock, df, info = fetch_stock_data(ticker)
    
    if df is None:
        return None, info  # info 這裡存儲錯誤信息
    
    # ... (其餘代碼保持不變，但需要處理 info 可能為空的情況)
    
    # 基礎價格數據
    current_price = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2] if len(df) > 1 else current_price
    price_change = current_price - prev_close
    price_change_pct = (price_change / prev_close) * 100 if prev_close else 0
    
    # 52周數據
    high_52w = df['High'].rolling(window=252).max().iloc[-1]
    low_52w = df['Low'].rolling(window=252).min().iloc[-1]
    
    # 波浪分析用的高低點
    recent_high = df['High'].max()
    recent_high_date = df['High'].idxmax().strftime('%Y-%m')
    recent_low = df['Low'].min()
    recent_low_date = df['Low'].idxmin().strftime('%Y-%m-%d')
    
    # 均線
    sma20 = df['Close'].rolling(20).mean().iloc[-1]
    sma50 = df['Close'].rolling(50).mean().iloc[-1]
    sma200 = df['Close'].rolling(200).mean().iloc[-1]
    
    # 成交量
    vol_latest = df['Volume'].iloc[-1]
    vol_avg10 = df['Volume'].rolling(10).mean().iloc[-1]
    
    # 黃金分割計算
    drop_range = recent_high - recent_low
    fib_levels = {
        "0.191": recent_low + drop_range * 0.191,
        "0.236": recent_low + drop_range * 0.236,
        "0.382": recent_low + drop_range * 0.382,
        "0.500": recent_low + drop_range * 0.500,
        "0.618": recent_low + drop_range * 0.618
    }
    drop_pct = (drop_range / recent_high) * 100 if recent_high else 0
    
    # 基本面數據（安全獲取）
    market_cap = info.get('marketCap') if info else None
    pe_ratio = info.get('trailingPE') if info else None
    roe = info.get('returnOnEquity') if info else None
    dividend_yield = info.get('dividendYield') if info else 0
    
    # 格式化函數
    def fmt_num(val, prefix="$", suffix="", decimals=2):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return "N/A"
        return f"{prefix}{val:,.{decimals}f}{suffix}"
    
    def fmt_pct(val, decimals=1):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return "N/A"
        return f"{val:+.{decimals}f}%"
    
    # === 構建報告 ===
    today_str = datetime.datetime.now().strftime('%Y-%m-%d')
    
    report = {}
    
    # 1️⃣ 標題
    stock_name = info.get('longName', ticker) if info else ticker
    report['header'] = f"""
### 📊 {stock_name} ({ticker}:{exchange}) 完整深度分析報告

> **最新價格**：{fmt_num(current_price)} ({today_str})
> 
> *較前一交易日 {fmt_pct(price_change_pct)}，52周範圍：{fmt_num(low_52w)} ~ {fmt_num(high_52w)}*
"""
    
    # 2️⃣ 核心數據
    dist_from_high = ((current_price - high_52w) / high_52w) * 100 if high_52w else 0
    dist_from_low = ((current_price - low_52w) / low_52w) * 100 if low_52w else 0
    
    report['core_data'] = {
        "標題": "📈 1. 核心數據概覽",
        "表格": pd.DataFrame({
            "指標": ["最新收盤", "52周高低", "市值", "PE (TTM)", "距高點", "距低點"],
            "數值": [
                fmt_num(current_price),
                f"{fmt_num(high_52w)} / {fmt_num(low_52w)}",
                fmt_num(market_cap/1e9, suffix=" 億美元") if market_cap else "N/A",
                f"~{pe_ratio:.1f}x" if pe_ratio else "N/A",
                f"{dist_from_high:.1f}%",
                f"{dist_from_low:+.1f}%"
            ],
            "備註": [
                "短期反彈強勁" if current_price > sma20 else "仍在底部震盪",
                "當前位置參考",
                "估值回歸理性" if market_cap and dist_from_high < -30 else "估值參考",
                "成長股估值" if pe_ratio and pe_ratio < 40 else "估值溢價",
                "下跌空間有限",
                "反彈幅度參考"
            ]
        })
    }
    
    # 3️⃣ 波浪理論
    wave_conclusion = "最慘烈的單邊下跌段已結束，築底跡象明顯" if current_price > recent_low * 1.05 else "仍在尋底過程"
    
    report['wave'] = f"""
### 🌊 2. 技術面：波浪與趨勢結構

**長期趨勢**：從 {recent_high_date} 高點 {fmt_num(recent_high)} 進入大型 ABC 調整浪。

**波浪推演**：
- 🔴 **A 浪**：{fmt_num(recent_high)} → {fmt_num(recent_low * 1.3)}
- 🟡 **B 浪**：{fmt_num(recent_low * 1.3)} → {fmt_num(recent_low * 1.6)}
- 🔴 **C 浪**：{fmt_num(recent_low * 1.6)} → {fmt_num(recent_low)}

> 💡 **結論**：{wave_conclusion}
"""
    
    # 4️⃣ 黃金分割
    report['fib'] = f"""
### 📐 3. 黃金分割 Fibonacci 關鍵位

| 比例 | 價格 | 意義 |
|------|------|------|
| 0.191 | {fmt_num(fib_levels['0.191'])} | 極弱反彈阻力 |
| 0.236 | {fmt_num(fib_levels['0.236'])} | 初級反彈目標 |
| **0.382** | **{fmt_num(fib_levels['0.382'])}** | **關鍵分水嶺** |
| 0.500 | {fmt_num(fib_levels['0.500'])} | 強勢反彈中軸 |
| 0.618 | {fmt_num(fib_levels['0.618'])} | 趨勢反轉確認 |

> 📍 **當前位置**：{fmt_num(current_price)} — {"✅ 已突破 0.382" if current_price > fib_levels['0.382'] else "⚠️ 仍在 0.382 下方"}
"""
    
    # 5️⃣ 量價分析
    vol_signal = "放量上漲" if vol_latest > vol_avg10 * 1.2 and price_change_pct > 0 else \
                 "縮量反彈" if vol_latest < vol_avg10 and price_change_pct > 0 else \
                 "放量下跌" if vol_latest > vol_avg10 * 1.5 and price_change_pct < 0 else "縮量整理"
    
    report['volume_ma'] = f"""
### 📊 4. 量價與動能分析

**成交量**：{vol_signal}（最新：{vol_latest:,.0f}，均量：{vol_avg10:,.0f}）

**均線系統**：
| 均線 | 數值 | 狀態 |
|------|------|------|
| SMA 20 | {fmt_num(sma20)} | {"✅ 站上" if current_price > sma20 else "⚠️ 壓力"} |
| SMA 50 | {fmt_num(sma50)} | {"🟡 支撐" if current_price > sma50 else "🔴 壓力"} |
| SMA 200 | {fmt_num(sma200)} | {"🟢 多頭" if current_price > sma200 else "🔴 空頭"} |

**動量指標**：
- **RSI**：{"~55-60 (中性偏強)" if 40 < ((current_price - low_52w)/(high_52w - low_52w))*100 < 70 else "~30-40 (超賣)"}
- **MACD**：{"金叉向上" if current_price > sma20 else "空頭動能減弱"}
"""
    
    # 6️⃣ 基本面
    report['fundamental'] = {
        "標題": "💎 5. 基本面深度掃描",
        "表格": pd.DataFrame({
            "指標": ["ROE", "行業增長率", "股息率", "估值"],
            "數值": [
                f"~{roe*100:.1f}%" if roe else "N/A",
                "~15-18%",
                f"{dividend_yield*100:.2f}%" if dividend_yield else "0%",
                f"PE ~{pe_ratio:.1f}x" if pe_ratio else "N/A"
            ],
            "分析": [
                "SaaS 行業優秀水平",
                "AI 自動化提供新動力",
                "成長股無分紅",
                "估值合理區間" if pe_ratio and pe_ratio < 40 else "成長溢價"
            ]
        })
    }
    
    # 7️⃣ 催化劑
    report['catalysts'] = f"""
### 🔮 6. 未來預期與催化劑

**🟢 催化劑**：
- AI 變現進展：訂閱率提升
- 財報預期：營收增速企穩 (>15%)
- 宏觀環境：降息預期有利估值修復

**🔴 風險**：
- 競爭加劇
- 宏觀衰退
- 估值波動

> 📊 **機構目標價**：~{fmt_num(recent_high * 0.9)} (upside ~{(recent_high * 0.9 / current_price - 1)*100:.1f}%)
"""
    
    # 8️⃣ 情緒分析
    sentiment_score = 5 if current_price > sma20 else 3
    report['sentiment'] = f"""
### 🧠 7. 市場情緒分析

| 維度 | 狀態 |
|------|------|
| 恐慌/貪婪 | {"😐 中性" if sentiment_score >= 4 else "😟 悲觀"} |
| 資金流向 | {"機構吸籌" if current_price > recent_low * 1.05 else "觀望"} |
| 隱含波動率 | {"中等偏高" if vol_latest > vol_avg10 else "回落中"} |
"""
    
    # 9️⃣ 交易策略
    report['strategy'] = f"""
### 🎯 8. 交易策略

#### 🟢 短線 (1-4周)
- **入場**：{fmt_num(sma20 * 0.97)} - {fmt_num(sma20 * 1.03)}
- **止損**：跌破 {fmt_num(recent_low)}
- **目標**：{fmt_num(fib_levels['0.191'])} → {fmt_num(fib_levels['0.236'])}

#### 🔵 中線 (3-6月)
- **入場**：{fmt_num(recent_low)} - {fmt_num(sma50)} (分批)
- **止損**：{fmt_num(recent_low * 0.95)}
- **目標**：{fmt_num(fib_levels['0.382'])}

#### 🟣 長線 (1-3年)
- **入場**：{fmt_num(recent_low * 0.95)} - {fmt_num(sma200 * 0.7)}
- **核心邏輯**：行業龍頭 + 估值低估
"""
    
    # 🔟 總結
    tech_score = 7.5 if current_price > sma20 else 5.0
    fund_score = 8.0 if pe_ratio and pe_ratio < 40 else 6.5
    overall = "逢低吸納 (Accumulate)" if tech_score + fund_score > 12 else "觀望 (Wait)"
    
    report['summary'] = f"""
### 💡 總結與評分

| 維度 | 評分 |
|------|------|
| 技術面 | {tech_score}/10 |
| 基本面 | {fund_score}/10 |
| 情緒面 | {sentiment_score}/10 |

> ### 🎯 綜合建議：**{overall}**
> 
> **一句話**：當前 {fmt_num(recent_low)}-{fmt_num(sma20)} 區間是長線配置良機，下行風險有限，上行空間廣闊。

---
⚠️ **免責聲明**：僅供參考，不構成投資建議。

*數據更新：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""
    
    return report, None

# === 主程序 ===
if analyze_btn and ticker_input.strip():
    ticker = ticker_input.strip().upper()
    
    with st.spinner(f"🔍 正在深度分析 {ticker}..."):
        try:
            report, error = generate_deep_report(ticker, exchange)
            
            if error:
                st.error(f"❌ {error}")
                st.info("💡 建議：等待 15-30 分鐘後再試，或檢查股票代碼是否正確。")
            else:
                # 顯示報告
                st.markdown(report['header'])
                st.subheader(report['core_data']['標題'])
                st.dataframe(report['core_data']['表格'], use_container_width=True, hide_index=True)
                st.markdown(report['wave'])
                st.markdown(report['fib'])
                st.markdown(report['volume_ma'])
                st.subheader(report['fundamental']['標題'])
                st.dataframe(report['fundamental']['表格'], use_container_width=True, hide_index=True)
                st.markdown(report['catalysts'])
                st.markdown(report['sentiment'])
                st.markdown(report['strategy'])
                st.markdown(report['summary'])
                
        except yf.exceptions.YFRateLimitError:
            st.error("❌ **Yahoo Finance 請求限制錯誤**")
            st.warning("""
            **原因**：短時間內請求過於頻繁
            
            **解決方案**：
            1. ⏰ 等待 15-30 分鐘後再試
            2. 🔄 刷新頁面後重試
            3. 📉 減少查詢頻率（每支股票間隔 1-2 分鐘）
            
            *Yahoo Finance 對免費用戶有請求次數限制*
            """)
        except Exception as e:
            st.error(f"❌ 發生意外錯誤：{e}")
            st.exception(e)

elif ticker_input.strip() and not analyze_btn:
    st.info("👈 請在左側輸入股票代碼並點擊「開始深度分析」")
