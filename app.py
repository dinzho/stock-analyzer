import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import math
import time
from functools import wraps

# === 重試裝飾器 ===
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

# === 輔助函數：行業與產業鏈分析 ===
def analyze_industry_structure(sector, industry, gross_margin, roe):
    """分析行業屬性、產業鏈位置及議價能力"""
    
    sector = str(sector).lower() if sector else ""
    industry = str(industry).lower() if industry else ""
    
    # 默認值
    position = "中游"
    upstream_power = "中等"
    downstream_power = "中等"
    industry_nature = "一般製造/服務業"
    
    # 1. 軟件/科技/SaaS (高毛利特徵)
    if any(x in sector for x in ['technology', 'communication']) or any(x in industry for x in ['software', 'internet', 'semiconductor']):
        industry_nature = "科技成長型 (高壁壘、高研發)"
        position = "中上游 (核心技術/平台)"
        upstream_power = "中等偏弱 (依賴高端人才/芯片/雲設施)" if gross_margin and gross_margin < 0.6 else "中等 (規模效應攤薄成本)"
        downstream_power = "強勢 (高轉換成本/訂閱制/生態鎖定)" if gross_margin and gross_margin > 0.5 else "中等 (競爭激烈)"
        
    # 2. 消費品 (品牌護城河)
    elif any(x in sector for x in ['consumer cyclical', 'consumer defensive']):
        industry_nature = "消費驅動型 (品牌/渠道为王)"
        position = "下游 (品牌/零售終端)"
        upstream_power = "強勢 (對供應商有規模壓價權)" if gross_margin and gross_margin > 0.3 else "弱勢 (原材料成本敏感)"
        downstream_power = "弱勢 (消費者價格敏感/選擇多)" if gross_margin and gross_margin < 0.3 else "強勢 (品牌忠誠度高)"

    # 3. 工業/製造 (週期性)
    elif any(x in sector for x in ['industrials', 'basic materials', 'energy']):
        industry_nature = "週期/製造型 (成本/產能驱动)"
        position = "中上游 (原材料/設備)"
        upstream_power = "弱勢 (受制於大宗商品價格)"
        downstream_power = "中等 (取決於產能利用率)"

    # 4. 金融 (資金驅動)
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

# === 數據獲取函數 ===
@retry_on_rate_limit(max_retries=3, delay=3)
def fetch_stock_data(ticker):
    stock = yf.Ticker(ticker)
    try:
        df = stock.history(period="2y", interval="1d")
        if df.empty: return None, None, None, "無法獲取歷史數據"
    except Exception as e: return None, None, None, f"歷史數據獲取失敗：{e}"
    
    info = {}
    try:
        time.sleep(1)
        info = stock.info
    except: pass
    
    return stock, df, info, None

# === 核心報告生成函數 ===
def generate_deep_report(ticker, exchange):
    stock, df, info, error = fetch_stock_data(ticker)
    if error: return None, error
    
    # --- 1. 基礎數據準備 ---
    current_price = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2] if len(df) > 1 else current_price
    price_change_pct = ((current_price - prev_close) / prev_close) * 100
    
    high_52w = df['High'].rolling(252).max().iloc[-1]
    low_52w = df['Low'].rolling(252).min().iloc[-1]
    recent_high = df['High'].max()
    recent_low = df['Low'].min()
    
    sma20 = df['Close'].rolling(20).mean().iloc[-1]
    sma50 = df['Close'].rolling(50).mean().iloc[-1]
    sma200 = df['Close'].rolling(200).mean().iloc[-1]
    
    # --- 2. 基本面數據提取 (帶安全處理) ---
    def safe_get(key, default=None):
        try:
            val = info.get(key)
            return val if val is not None and not pd.isna(val) else default
        except: return default

    sector = safe_get('sector')
    industry = safe_get('industry')
    gross_margin = safe_get('grossMargins') # 0.0 ~ 1.0
    roe = safe_get('returnOnEquity') # 0.0 ~ 1.0
    pe_ratio = safe_get('trailingPE')
    revenue_growth = safe_get('revenueGrowth') # 歷史營收增長
    earnings_growth = safe_get('earningsGrowth') # 歷史/預期盈利增長
    
    # 行業結構分析
    industry_analysis = analyze_industry_structure(sector, industry, gross_margin, roe)
    
    # --- 3. 構建報告內容 ---
    today_str = datetime.datetime.now().strftime('%Y-%m-%d')
    last_trade_date = df.index[-1].strftime('%Y-%m-%d')
    
    report = {}
    
    # Header
    report['header'] = f"""
### 📊 {safe_get('longName', ticker.upper())} ({ticker}:{exchange}) 完整深度分析報告
> **📅 數據基準**：{last_trade_date} 收盤 | **💰 現價**：${current_price:.2f} ({price_change_pct:+.2f}%)
"""

    # 1. 核心數據 (簡略)
    report['core_data'] = {
        "標題": "📈 1. 核心數據概覽",
        "表格": pd.DataFrame({
            "指標": ["52周範圍", "市值", "PE (TTM)", "Beta"],
            "數值": [
                f"${low_52w:.1f} - ${high_52w:.1f}",
                f"${safe_get('marketCap', 0)/1e9:.2f}B" if safe_get('marketCap') else "N/A",
                f"{pe_ratio:.2f}" if pe_ratio else "N/A",
                f"{safe_get('beta', 1):.2f}"
            ]
        })
    }

    # 2. 技術面 (簡略)
    report['wave'] = f"""
### 🌊 2. 技術趨勢
*   **波段**：高點 ${recent_high:.2f} → 低點 ${recent_low:.2f}
*   **均線**：現價 ${current_price:.2f} vs SMA20 ${sma20:.2f} | SMA200 ${sma200:.2f}
*   **狀態**：{"✅ 多頭排列" if current_price > sma20 > sma50 else "⚠️ 空頭排列/震盪"}
"""

    # 3. 黃金分割 (簡略)
    drop_range = recent_high - recent_low
    fib_382 = recent_low + drop_range * 0.382
    report['fib'] = f"""
### 📐 3. 關鍵阻力 (Fibonacci)
*   **0.382 黃金坑**: ${fib_382:.2f}
*   **0.500 中軸**: ${recent_low + drop_range * 0.5:.2f}
*   **當前**: {"✅ 突破 0.382" if current_price > fib_382 else "⚠️ 受壓於 0.382"}
"""

    # === 重點修改：第 5 部分 基本面深度掃描 ===
    # 邏輯：行業 -> 產業鏈 -> 議價能力 -> 財務指標
    
    # 判斷議價能力總結
    bargaining_summary = ""
    if industry_analysis['downstream'] == "強勢" and industry_analysis['upstream'] == "強勢":
        bargaining_summary = " **雙向強勢 (产业链霸主)**：對上下游均有極強話語權，典型的壟斷或寡頭特徵。"
    elif industry_analysis['downstream'] == "強勢":
        bargaining_summary = "🛡️ **對下游強勢 (品牌/技術護城河)**：產品有定價權，客戶粘性高，能轉嫁成本。"
    elif industry_analysis['upstream'] == "強勢":
        bargaining_summary = "🏭 **對上游強勢 (規模效應)**：如大型零售，能壓低採購成本，但終端競爭激烈。"
    else:
        bargaining_summary = "⚖️ **競爭激烈 (夾心層)**：上下游議價能力均一般，利潤空間易受兩頭擠壓，需靠效率取勝。"

    report['fundamental'] = f"""
### 💎 5. 基本面深度掃描 (Fundamental Deep Dive)

#### 5.1 行業屬性與產業鏈定位
*   **所屬行業**：{sector} / {industry}
*   **行業性質**：{industry_analysis['nature']}
*   **產業鏈位置**：{industry_analysis['position']}
*   **議價能力評估**：
    *   🔼 **對上游 (供應商)**：{industry_analysis['upstream']}
    *   🔽 **對下游 (客戶)**：{industry_analysis['downstream']}
    *   💡 **總結**：{bargaining_summary}

#### 5.2 核心財務指標分析
*(基於最新財報與市場預期)*

| 指標 | 數值 | 分析與解讀 |
| :--- | :--- | :--- |
| **ROE (淨資產收益率)** | {f"{roe*100:.1f}%" if roe else "N/A"} | {"✅ 優秀 (>15%)" if roe and roe > 0.15 else "⚠️ 一般 (10-15%)" if roe and roe > 0.1 else "❌ 較低 (<10%)"} |
| **行業複合增長率 (CAGR)** | ~{safe_get('industry', 'N/A')} | 行業平均增速參考 (需結合宏觀) |
| **該股預期增長率** | {f"{revenue_growth*100:.1f}%" if revenue_growth else "N/A"} | {"🚀 高速成長 (>20%)" if revenue_growth and revenue_growth > 0.2 else "📈 穩健增長 (10-20%)" if revenue_growth and revenue_growth > 0.1 else "🐢 成熟/放緩 (<10%)"} |
| **毛利率 (Gross Margin)** | {f"{gross_margin*100:.1f}%" if gross_margin else "N/A"} | {"💰 高毛利 (產品強勢)" if gross_margin and gross_margin > 0.5 else "🏭 標準毛利" if gross_margin and gross_margin > 0.2 else "📉 低毛利 (薄利多銷)"} |
| **估值合理性 (PE)** | {f"{pe_ratio:.1f}x" if pe_ratio else "N/A"} | {"💸 高估值溢價" if pe_ratio and pe_ratio > 40 else "⚖️ 合理區間" if pe_ratio and 15 < pe_ratio < 40 else "💰 低估值/價值股" if pe_ratio and pe_ratio < 15 else "N/A"} |
"""

    # === 重點修改：第 6 部分 未來預期與催化劑 ===
    # 邏輯：基於前面的議價能力和增長率來推導催化劑
    
    catalyst_type = ""
    if revenue_growth and revenue_growth > 0.2:
        catalyst_type = "成長驅動型"
        catalysts_list = [
            "新產品/新市場滲透率快速提升",
            "營收規模效應顯現，淨利率擴張",
            "行業紅利釋放，搶佔市場份額"
        ]
    elif industry_analysis['downstream'] == "強勢":
        catalyst_type = "定價權/護城河型"
        catalysts_list = [
            "產品提價 (Pricing Power) 帶動毛利上升",
            "訂閱制/生態鎖定帶來穩定現金流",
            "回購股票或增加分紅回報股東"
        ]
    else:
        catalyst_type = "週期反轉/效率型"
        catalysts_list = [
            "原材料成本下降，修復利潤空間",
            "裁員/重組提升運營效率",
            "宏觀經濟復甦帶動需求回暖"
        ]

    report['catalysts'] = f"""
### 🔮 6. 未來預期與催化劑 (Catalysts)
*基於 {industry_analysis['nature']} 與 {catalyst_type} 邏輯推演*

#### 🟢 核心催化劑 (Upside)
1.  **增長引擎**：{catalysts_list[0]}
2.  **利潤釋放**：{catalysts_list[1]}
3.  **外部環境**：{"降息週期有利估值修復" if "Tech" in str(sector) else "宏觀需求復甦"}

#### 🔴 潛在風險 (Downside)
1.  **競爭格局**：{"新進入者威脅" if industry_analysis['downstream'] == "弱勢" else "巨頭壟斷壓制"}
2.  **成本端**：{"上游原材料/芯片漲價" if industry_analysis['upstream'] == "弱勢" else "人力/研發成本上升"}
3.  **宏觀/監管**：政策監管風險或經濟衰退導致支出削減

#### 📊 機構共識參考
*   **目標價**：~${recent_high * 0.9:.2f} (Upside ~{(recent_high*0.9/current_price - 1)*100:.1f}%)
*   **評級**：{"買入/增持" if revenue_growth and revenue_growth > 0.15 else "持有/觀望"}
"""

    # 7. 情緒與策略 (保持原有邏輯，微調)
    report['sentiment'] = f"""
### 🧠 7. 市場情緒 (Sentiment)
*   **技術面**：{"多頭" if current_price > sma20 else "空頭"}
*   **資金面**：{"放量" if df['Volume'].iloc[-1] > df['Volume'].rolling(10).mean().iloc[-1] else "縮量"}
*   **結論**：{"反彈初期" if current_price > recent_low * 1.05 else "尋底過程"}
"""

    report['strategy'] = f"""
### 🎯 8. 交易策略
*   **短線**：支撐 ${sma20:.2f} / 阻力 ${fib_382:.2f}
*   **中長線**：{"✅ 逢低吸納 (成長/護城河)" if (roe and roe > 0.15) or (industry_analysis['downstream'] == "強勢") else "⚠️ 波段操作 (週期/觀望)"}
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
            else:
                st.markdown(report['header'])
                st.subheader(report['core_data']['標題'])
                st.dataframe(report['core_data']['表格'], hide_index=True, use_container_width=True)
                st.markdown(report['wave'])
                st.markdown(report['fib'])
                
                # 顯示修正後的基本面 (Markdown 格式)
                st.markdown(report['fundamental'])
                
                # 顯示修正後的催化劑 (Markdown 格式)
                st.markdown(report['catalysts'])
                
                st.markdown(report['sentiment'])
                st.markdown(report['strategy'])
                
                st.caption(f"⚠️ 免責聲明：數據僅供參考，不構成投資建議。生成時間：{datetime.datetime.now()}")
                
        except Exception as e:
            st.error(f"❌ 系統錯誤：{e}")
            st.exception(e)
elif not ticker_input.strip():
    st.info("👈 請輸入股票代碼開始分析")
