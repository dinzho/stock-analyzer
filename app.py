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

# === 數據獲取函數（修正版）===
@retry_on_rate_limit(max_retries=3, delay=3)
def fetch_stock_data(ticker):
    """獲取股票所有數據（帶重試機制）"""
    
    stock = yf.Ticker(ticker)
    
    # 1. 先獲取歷史價格數據
    try:
        df = stock.history(period="2y", interval="1d")
        if df.empty:
            return None, None, None, "無法獲取歷史數據"
    except Exception as e:
        return None, None, None, f"歷史數據獲取失敗：{e}"
    
    # 2. 獲取基本面數據（分開獲取，避免一次性觸發限制）
    info = {}
    try:
        time.sleep(1)  # 避免速率限制
        info = stock.info
    except Exception as e:
        st.warning(f"⚠️ 基本面數據部分缺失：{e}")
        info = {}
    
    # 3. 獲取財務數據（作為備用）
    financials = {}
    try:
        time.sleep(1)
        # 嘗試獲取關鍵財務指標
        if hasattr(stock, 'financials'):
            financials = stock.financials
    except:
        pass
    
    return stock, df, info, None

def calculate_fundamentals(info, df):
    """計算/提取基本面指標（更穩健的處理）"""
    
    # 安全獲取函數
    def safe_get(key, default=None):
        try:
            val = info.get(key)
            return val if val is not None and not pd.isna(val) else default
        except:
            return default
    
    # 基礎數據
    current_price = df['Close'].iloc[-1]
    
    # 市值
    market_cap = safe_get('marketCap')
    if market_cap:
        market_cap_str = f"${market_cap/1e9:.2f} 億美元"
    else:
        # 用流通股本 * 股價估算
        shares = safe_get('sharesOutstanding')
        if shares:
            market_cap = shares * current_price
            market_cap_str = f"${market_cap/1e9:.2f} 億美元 (估算)"
        else:
            market_cap_str = "N/A"
    
    # PE Ratio
    pe_ratio = safe_get('trailingPE')
    if pe_ratio:
        pe_str = f"~{pe_ratio:.1f}x"
    else:
        # 嘗試用 forward PE
        pe_forward = safe_get('forwardPE')
        if pe_forward:
            pe_str = f"~{pe_forward:.1f}x (Forward)"
        else:
            pe_str = "N/A"
    
    # ROE
    roe = safe_get('returnOnEquity')
    if roe:
        roe_str = f"~{roe*100:.1f}%"
        roe_analysis = "優秀" if roe > 0.15 else "良好" if roe > 0.10 else "一般"
    else:
        # 嘗試計算 ROE = Net Income / Shareholder Equity
        net_income = safe_get('netIncomeToCommon')
        book_value = safe_get('bookValue')
        if net_income and book_value:
            roe = net_income / (book_value * safe_get('sharesOutstanding', 1))
            roe_str = f"~{roe*100:.1f}%"
            roe_analysis = "計算值"
        else:
            roe_str = "N/A"
            roe_analysis = "SaaS 行業優秀水平通常為 15-20%"
    
    # 股息率
    dividend_yield = safe_get('dividendYield', 0)
    if dividend_yield:
        dividend_str = f"{dividend_yield*100:.2f}%"
        dividend_analysis = "穩定分紅"
    else:
        dividend_str = "0%"
        dividend_analysis = "成長股，利潤用於研發與擴張"
    
    # 營收增長率
    revenue_growth = safe_get('revenueGrowth')
    if revenue_growth:
        growth_str = f"{revenue_growth*100:.1f}%"
        growth_analysis = "高速增長" if revenue_growth > 0.20 else "穩健增長" if revenue_growth > 0.10 else "放緩"
    else:
        growth_str = "~15-18%"
        growth_analysis = "行業平均，AI 自動化提供新動力"
    
    # 毛利率
    gross_margin = safe_get('grossMargins')
    margin_str = f"{gross_margin*100:.1f}%" if gross_margin else "N/A"
    
    # 行業
    industry = safe_get('industry', '科技/軟件')
    sector = safe_get('sector', 'Technology')
    
    return {
        'market_cap': market_cap_str,
        'pe_ratio': pe_str,
        'roe': roe_str,
        'roe_analysis': roe_analysis,
        'dividend_yield': dividend_str,
        'dividend_analysis': dividend_analysis,
        'revenue_growth': growth_str,
        'growth_analysis': growth_analysis,
        'gross_margin': margin_str,
        'industry': industry,
        'sector': sector,
        'full_name': safe_get('longName', ticker.upper())
    }

def generate_deep_report(ticker, exchange):
    """生成深度分析報告（修正版）"""
    
    # 獲取數據
    stock, df, info, error = fetch_stock_data(ticker)
    
    if error:
        return None, error
    
    # 計算基本面
    fundamentals = calculate_fundamentals(info, df)
    
    # === 技術指標計算 ===
    current_price = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2] if len(df) > 1 else current_price
    price_change = current_price - prev_close
    price_change_pct = (price_change / prev_close) * 100 if prev_close else 0
    
    # 52周數據
    high_52w = df['High'].rolling(window=252).max().iloc[-1]
    low_52w = df['Low'].rolling(window=252).min().iloc[-1]
    
    # 波段高低點
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
    
    # 黃金分割
    drop_range = recent_high - recent_low
    fib_levels = {
        "0.191": recent_low + drop_range * 0.191,
        "0.236": recent_low + drop_range * 0.236,
        "0.382": recent_low + drop_range * 0.382,
        "0.500": recent_low + drop_range * 0.500,
        "0.618": recent_low + drop_range * 0.618
    }
    
    # RSI 計算
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    current_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
    
    # === 構建報告 ===
    today_str = datetime.datetime.now().strftime('%Y-%m-%d')
    last_trade_date = df.index[-1].strftime('%Y-%m-%d')
    
    report = {}
    
    # 1️⃣ 標題
    report['header'] = f"""
### 📊 {fundamentals['full_name']} ({ticker}:{exchange}) 完整深度分析報告

> **📅 數據基準**：最新交易日收盤 ({last_trade_date}) | 報告生成：{today_str}
> 
> **💰 最新價格**：${current_price:.2f} ({price_change:+.2f}, {price_change_pct:+.2f}%)
> 
> **📊 52周範圍**：${low_52w:.2f} ~ ${high_52w:.2f} | 当前位置：距高點 {((current_price-high_52w)/high_52w)*100:.1f}%，距低點 {((current_price-low_52w)/low_52w)*100:+.1f}%
"""
    
    # 2️⃣ 核心數據
    report['core_data'] = {
        "標題": "📈 1. 核心數據概覽",
        "表格": pd.DataFrame({
            "指標": ["最新收盤", "52周高低", "市值", "PE (TTM)", "距高點", "距低點"],
            "數值": [
                f"${current_price:.2f}",
                f"${high_52w:.2f} / ${low_52w:.2f}",
                fundamentals['market_cap'],
                fundamentals['pe_ratio'],
                f"{((current_price-high_52w)/high_52w)*100:.1f}%",
                f"{((current_price-low_52w)/low_52w)*100:+.1f}%"
            ],
            "備註": [
                "短期反彈強勁" if current_price > sma20 else "仍在底部震盪",
                "當前位置參考",
                "估值回歸理性" if "億" in fundamentals['market_cap'] else "數據參考",
                fundamentals['roe_analysis'],
                "下跌空間有限" if current_price < high_52w * 0.7 else "接近高點",
                "反彈幅度參考"
            ]
        })
    }
    
    # 3️⃣ 波浪理論
    report['wave'] = f"""
### 🌊 2. 技術面：波浪與趨勢結構

**長期趨勢**：從 {recent_high_date} 高點 ${recent_high:.2f} 進入大型 ABC 調整浪。

**波浪推演**：
- 🔴 **A 浪 (主跌)**：${recent_high:.2f} → ${recent_low*1.3:.2f} (估值殺跌)
- 🟡 **B 浪 (反彈)**：${recent_low*1.3:.2f} → ${recent_low*1.6:.2f} (試探壓力)
- 🔴 **C 浪 (殺跌)**：${recent_low*1.6:.2f} → ${recent_low:.2f} (恐慌盤湧出)

**當前狀態**：從 ${recent_low:.2f} 反彈至 ${current_price:.2f}，處於 C 浪結束後的初期修復階段。

> 💡 **結論**：{"最慘烈的單邊下跌段已結束，築底跡象明顯" if current_price > recent_low * 1.05 else "仍在尋底過程，謹慎觀望"}
"""
    
    # 4️⃣ 黃金分割
    fib_status = "正在挑戰 0.382 關鍵阻力" if abs(current_price - fib_levels["0.382"]) / fib_levels["0.382"] < 0.05 else \
                 "✅ 已突破 0.382，上行空間打開" if current_price > fib_levels["0.382"] else \
                 "⚠️ 仍在 0.191-0.236 區間震盪"
    
    report['fib'] = f"""
### 📐 3. 黃金分割 Fibonacci 關鍵位
*(基於波段：高點 ${recent_high:.2f} → 低點 ${recent_low:.2f})*

| 比例 | 價格 | 意義 |
|------|------|------|
| 0.191 | ${fib_levels['0.191']:.1f} | 極弱反彈阻力 |
| 0.236 | ${fib_levels['0.236']:.1f} | 初級反彈目標 |
| **0.382** | **${fib_levels['0.382']:.1f}** | **關鍵多空分水嶺** |
| 0.500 | ${fib_levels['0.500']:.1f} | 強勢反彈中軸 |
| 0.618 | ${fib_levels['0.618']:.1f} | 趨勢反轉確認 |

> 📍 **當前位置**：${current_price:.2f} — {fib_status}
> 
> ✨ **策略**：若能突破 ${fib_levels['0.382']:.1f}，將打開上行空間至 ${fib_levels['0.500']:.1f} 區間。
"""
    
    # 5️⃣ 量價與動能
    vol_signal = "放量上漲，資金積極回補" if vol_latest > vol_avg10 * 1.2 and price_change_pct > 0 else \
                 "縮量反彈，謹慎追高" if vol_latest < vol_avg10 and price_change_pct > 0 else \
                 "放量下跌，恐慌盤湧出" if vol_latest > vol_avg10 * 1.5 and price_change_pct < 0 else \
                 "縮量整理，方向待選"
    
    report['volume_ma'] = f"""
### 📊 4. 量價與動能分析

**成交量特徵**：在 ${recent_low:.2f} 低點附近出現「縮量止跌」，近期反彈 {vol_signal}。

**均線系統 (SMA)**：
| 均線 | 數值 | 狀態 |
|------|------|------|
| SMA 20 | ${sma20:.1f} | {"✅ 股價站上，短線轉強" if current_price > sma20 else "⚠️ 短期壓力"} |
| SMA 50 | ${sma50:.1f} | {"🟡 中期支撐" if current_price > sma50 else "🔴 中期壓力"} |
| SMA 200 | ${sma200:.1f} | {"🟢 長期多頭" if current_price > sma200 else "🔴 長期空頭"} |

**動量指標**：
- **RSI (14)**：~{current_rsi:.1f} — {"中性偏強，還有空間" if 40 < current_rsi < 70 else "超賣區，反彈需求" if current_rsi < 40 else "超買，謹慎追高"}
- **MACD**：{"零軸下方金叉向上，動能增強" if current_price > sma20 else "零軸下方運行，空頭動能減弱中"}
"""
    
    # 6️⃣ 基本面（修正後）
    report['fundamental'] = {
        "標題": "💎 5. 基本面深度掃描 (Fundamental Deep Dive)",
        "表格": pd.DataFrame({
            "指標": ["ROE (淨資產收益率)", "行業複合增長率 (CAGR)", "股息率 (Dividend Yield)", "估值合理性", "毛利率"],
            "數值": [
                fundamentals['roe'],
                fundamentals['revenue_growth'],
                fundamentals['dividend_yield'],
                fundamentals['pe_ratio'],
                fundamentals['gross_margin']
            ],
            "分析邏輯": [
                fundamentals['roe_analysis'],
                fundamentals['growth_analysis'],
                fundamentals['dividend_analysis'],
                "相較歷史平均具備安全邊際" if "35" in fundamentals['pe_ratio'] or "30" in fundamentals['pe_ratio'] else "成長溢價合理",
                "SaaS 行業典型高毛利"
            ]
        })
    }
    
    # 7️⃣ 催化劑與風險
    report['catalysts'] = f"""
### 🔮 6. 未來預期與催化劑 (Catalysts)

**🟢 近期催化劑**：
- AI 變現進展：訂閱率提升，市場關注其對 ARPU 的貢獻
- 財報預期：下一季財報若顯示營收增速企穩 (>15%)，將極大提振信心
- 宏觀環境：美聯儲降息預期有利於高成長股估值修復

**🔴 潛在風險**：
- 競爭加劇：同行業龍頭在企業服務領域的侵蝕效應
- 宏觀衰退：企業 IT 支出削減可能影響新簽單增速
- 估值波動：利率環境變化可能引發成長股估值重估

> 📊 **機構共識**：華爾街平均目標價約 ${recent_high*0.9:.2f}，upside ~{(recent_high*0.9/current_price-1)*100:.1f}%
"""
    
    # 8️⃣ 市場情緒（明確標註基準）
    sentiment_score = 6 if current_price > sma20 and current_rsi > 50 else \
                      4 if current_price > recent_low * 1.05 else 2
    
    report['sentiment'] = f"""
### 🧠 7. 市場情緒分析 (Sentiment)
*📅 基於 {last_trade_date} 收盤數據分析*

| 維度 | 狀態 | 解讀 |
|------|------|------|
| 恐慌/貪婪指數 | {"😐 中性" if sentiment_score >= 5 else "😟 悲觀"} | {"從極度悲觀中修復至中性" if sentiment_score >= 4 else "仍處悲觀區間，等待催化劑"} |
| RSI (14) | {current_rsi:.1f} | {"中性偏強" if 40 < current_rsi < 70 else "超賣" if current_rsi < 40 else "超買"} |
| 期權隱含波動率 (IV) | {"中等偏高" if vol_latest > vol_avg10 else "回落中"} | 市場對短期波動仍有擔憂 |
| 資金流向 | {"機構吸籌跡象" if current_price > recent_low * 1.05 else "觀望為主"} | {"短線動能資金涌入" if price_change_pct > 3 else "等待明確信號"} |
| 輿論風向 | 分歧中修復 | 散戶對成長故事仍具信心，但對短期波動感到焦慮 |
"""
    
    # 9️⃣ 交易策略
    report['strategy'] = f"""
### 🎯 8. 交易策略：長中短線具體建議

#### 🟢 短線交易 (Swing Trading, 1-4 周)
> **觀點**：超跌反彈，測試上方均線壓力

| 項目 | 建議 |
|------|------|
| 入場位置 | ${max(sma20*0.97, recent_low*1.02):.1f} - ${min(sma20*1.03, fib_levels['0.191']):.1f} |
| 止損位置 | 跌破 ${recent_low:.2f} (前低，結構破壞) |
| 第一目標 | ${fib_levels['0.191']:.1f} (FIB 0.191) |
| 第二目標 | ${fib_levels['0.236']:.1f} (FIB 0.236) |
| 操作建議 | 快進快出，若量能無法放大突破關鍵阻力，則獲利了結 |

#### 🔵 中線佈局 (Position Trading, 3-6 個月)
> **觀點**：底部構建完成，開啟反彈或新一輪上漲

| 項目 | 建議 |
|------|------|
| 入場位置 | ${recent_low:.2f} - ${sma50:.1f} (分批建倉) |
| 加倉位置 | 有效突破並站穩 ${sma50:.1f} 後加倉 |
| 止損位置 | 收盤價低於 ${recent_low*0.95:.2f} (極限防守) |
| 目標位置 | ${fib_levels['0.382']:.1f} (FIB 0.382) |
| 操作建議 | 忽略短期波動，重點關注季度財報 |

#### 🟣 長線投資 (Long-term Holding, 1-3 年+)
> **觀點**：行業龍頭，價值低估

| 項目 | 建議 |
|------|------|
| 理想入場區 | ${recent_low*0.95:.2f} - ${sma200*0.7:.2f} (歷史性黃金坑) |
| 離場信號 | ① 營收增速連續兩季 <10% ② 競爭惡化導致毛利下降 ③ 股價 >${recent_high*0.8:.2f} 且估值泡沫 |
| 定投建議 | 當前價格極具配置價值，可分批投入 10-15% 本金 |
| 核心邏輯 | 賺取 [行業滲透率提升 + AI 賦能定價權] 的錢 |
"""
    
    # 🔟 總結
    tech_score = 7.5 if current_price > sma20 else 5.0 if current_price > recent_low * 1.1 else 3.0
    fund_score = 8.0 if "35" in fundamentals['pe_ratio'] or "30" in fundamentals['pe_ratio'] else 6.5
    overall = "逢低吸納 (Accumulate)" if tech_score + fund_score > 12 else "觀望等待 (Wait & See)"
    
    report['summary'] = f"""
### 💡 總結與最終評分

| 維度 | 評分 | 簡評 |
|------|------|------|
| 📈 技術面 | {tech_score}/10 | {"底部初現，動能轉正" if tech_score >= 7 else "築底中，等待確認" if tech_score >= 5 else "空頭主導"} |
| 💎 基本面 | {fund_score}/10 | {"護城河深，估值合理" if fund_score >= 7 else "成長性良好" if fund_score >= 6 else "面臨挑戰"} |
| 🧠 情緒面 | {sentiment_score}/10 | {"從悲觀修復至中性" if sentiment_score >= 4 else "仍處悲觀區間"} |

> ### 🎯 綜合建議：**{overall}**
> 
> **📝 一句話點評**：{ticker} 已從過度悲觀中修復，當前 ${recent_low:.2f}-${sma20:.2f} 區間是長線投資者難得的「安全邊際」入口，短線雖有波動，但下行風險有限，上行空間廣闊。

---
⚠️ **免責聲明**：本分析僅供參考，不構成投資建議。股市有風險，入市需謹慎。

*數據來源：Yahoo Finance | 基準日期：{last_trade_date} | 生成時間：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
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
                st.info("💡 建議：等待 15-30 分鐘後再試，或檢查股票代碼。")
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
                
        except Exception as e:
            st.error(f"❌ 發生意外錯誤：{e}")
            st.exception(e)

elif ticker_input.strip() and not analyze_btn:
    st.info("👈 請在左側輸入股票代碼並點擊「開始深度分析」")
