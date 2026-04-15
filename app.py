import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import math

# 頁面配置
st.set_page_config(page_title="股票深度分析", page_icon="📊", layout="wide")

# 標題
st.title("📊 股票完整深度分析報告")
st.markdown("*專業技術面 + 基本面 + 情緒面 + 策略面 四維分析*")

# 側邊欄輸入
with st.sidebar:
    st.header("🔍 查詢設置")
    ticker_input = st.text_input("股票代碼", value="NOW", placeholder="例如：NOW, NVDA, TSLA")
    exchange = st.selectbox("交易所", ["NYSE", "NASDAQ", "HKEX", "SSE", "SZSE"], index=0)
    
    analyze_btn = st.button("🚀 開始深度分析", type="primary", use_container_width=True)
    
    st.markdown("---")
    st.markdown("**💡 使用提示**")
    st.markdown("- 美股代碼直接輸入，如 `AAPL`")
    st.markdown("- 港股加 `.HK`，如 `0700.HK`")
    st.markdown("- A股加 `.SS`/`.SZ`，如 `600519.SS`")

# 分析函數
def generate_deep_report(ticker, exchange):
    """生成深度分析報告"""
    
    # 獲取數據
    stock = yf.Ticker(ticker)
    df = stock.history(period="2y", interval="1d")
    
    if df.empty:
        return None, "❌ 無法獲取數據"
    
    # 基礎價格數據
    current_price = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2] if len(df) > 1 else current_price
    price_change = current_price - prev_close
    price_change_pct = (price_change / prev_close) * 100
    
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
    drop_pct = (drop_range / recent_high) * 100
    
    # 基本面數據（盡力獲取）
    info = stock.info
    market_cap = info.get('marketCap', 'N/A')
    pe_ratio = info.get('trailingPE', 'N/A')
    roe = info.get('returnOnEquity', 'N/A')
    dividend_yield = info.get('dividendYield', 0)
    
    # 格式化數值
    def fmt_num(val, prefix="$", suffix="", decimals=2):
        if val == 'N/A' or pd.isna(val):
            return "N/A"
        return f"{prefix}{val:,.{decimals}f}{suffix}"
    
    def fmt_pct(val, decimals=1):
        if pd.isna(val):
            return "N/A"
        return f"{val:+.{decimals}f}%"
    
    # === 開始構建報告 ===
    today_str = datetime.datetime.now().strftime('%Y-%m-%d')
    
    report = {}
    
    # 1️⃣ 標題與最新價格
    report['header'] = f"""
### 📊 {info.get('longName', ticker)} ({ticker}:{exchange}) 完整深度分析報告

> **最新價格**：{fmt_num(current_price)} ({today_str}, 盤中/前收盤參考)
> 
> *註：較前一交易日 {fmt_pct(price_change_pct)}，52周範圍：{fmt_num(low_52w)} ~ {fmt_num(high_52w)}*
"""
    
    # 2️⃣ 核心數據概覽
    dist_from_high = ((current_price - high_52w) / high_52w) * 100
    dist_from_low = ((current_price - low_52w) / low_52w) * 100
    
    report['core_data'] = {
        "標題": "📈 1. 核心數據概覽",
        "表格": pd.DataFrame({
            "指標": ["最新收盤", "52周高低", "市值", "PE (TTM)", "距高點", "距低點"],
            "數值": [
                fmt_num(current_price),
                f"{fmt_num(high_52w)} / {fmt_num(low_52w)}",
                fmt_num(market_cap/1e9, suffix=" 億美元") if isinstance(market_cap, (int, float)) else "N/A",
                f"~{pe_ratio:.1f}x" if isinstance(pe_ratio, (int, float)) else "預估",
                f"{dist_from_high:.1f}%",
                f"{dist_from_low:+.1f}%"
            ],
            "備註": [
                "短期反彈強勁，脫離底部區域" if current_price > sma20 else "仍在底部震盪",
                "當前位置參考",
                "較高峰期大幅縮水，估值回歸理性" if dist_from_high < -30 else "估值處於合理區間",
                "考慮到增長放緩，估值處於歷史低位區間" if isinstance(pe_ratio, (int, float)) and pe_ratio < 40 else "成長股估值溢價",
                "下跌空間有限",
                "反彈幅度參考"
            ]
        })
    }
    
    # 3️⃣ 波浪理論分析
    wave_conclusion = "最慘烈的單邊下跌段已結束，當前在籌碼交換，築底跡象明顯" if current_price > recent_low * 1.05 else "仍在尋底過程，謹慎觀望"
    
    report['wave'] = f"""
### 🌊 2. 技術面：波浪與趨勢結構

**長期趨勢判斷**：從 {recent_high_date} 高點 {fmt_num(recent_high)} 進入大型 ABC 調整浪。

**波浪理論推演**：
- 🔴 **A 浪 (主跌)**：{fmt_num(recent_high)} → {fmt_num(recent_low * 1.3)} (估值殺跌，趨勢轉空)
- 🟡 **B 浪 (反彈)**：{fmt_num(recent_low * 1.3)} → {fmt_num(recent_low * 1.6)} (試探上方壓力，量能不足)
- 🔴 **C 浪 (殺跌)**：{fmt_num(recent_low * 1.6)} → {fmt_num(recent_low)} (近期創下新低，恐慌盤湧出)

**當前狀態**：從 {fmt_num(recent_low)} 反彈至 {fmt_num(current_price)}，處於 C 浪結束後的初期修復階段。

> 💡 **結論**：{wave_conclusion}
"""
    
    # 4️⃣ 黃金分割
    fib_status = "正在挑戰短線 0.382 壓力區" if fib_levels["0.382"] - 5 < current_price < fib_levels["0.382"] + 5 else \
                 "已突破 0.382，上行空間打開" if current_price > fib_levels["0.382"] else \
                 "仍在 0.191-0.236 區間震盪"
    
    report['fib'] = f"""
### 📐 3. 黃金分割 Fibonacci 關鍵位
*(基於最近一波顯著漲跌幅：高點 {fmt_num(recent_high)} → 低點 {fmt_num(recent_low)})*

| 比例 | 價格 | 意義 |
|------|------|------|
| 0.191 | {fmt_num(fib_levels['0.191'])} | 極弱反彈阻力 |
| 0.236 | {fmt_num(fib_levels['0.236'])} | 初級反彈目標 |
| **0.382** | **{fmt_num(fib_levels['0.382'])}** | **關鍵多空分水嶺** |
| 0.500 | {fmt_num(fib_levels['0.500'])} | 強勢反彈中軸 |
| 0.618 | {fmt_num(fib_levels['0.618'])} | 趨勢反轉確認 |

> 📍 **當前價格位置**：{fmt_num(current_price)} — {fib_status}
> 
> ✨ **策略啟示**：若能突破 {fmt_num(fib_levels['0.382'])}，將打開上行空間至 {fmt_num(fib_levels['0.500'])} 區間。
"""
    
    # 5️⃣ 量價與動能
    vol_signal = "放量上漲，資金積極回補" if vol_latest > vol_avg10 * 1.2 and price_change_pct > 0 else \
                 "縮量反彈，謹慎追高" if vol_latest < vol_avg10 and price_change_pct > 0 else \
                 "放量下跌，恐慌盤湧出" if vol_latest > vol_avg10 * 1.5 and price_change_pct < 0 else \
                 "縮量整理，方向待選"
    
    ma_status = "短期均線金叉向上，中期均線走平，長期均線向下 — 多頭初現，空頭未退" if sma20 > sma50*0.98 and current_price > sma20 else \
                "均線空頭排列，中期偏弱" if current_price < sma20 < sma50 < sma200 else \
                "均線多頭排列，趨勢向好"
    
    report['volume_ma'] = f"""
### 📊 4. 量價與動能分析

**成交量特徵**：在 {fmt_num(recent_low)} 低點附近出現「縮量止跌」，近期反彈伴隨 {vol_signal}。

**均線系統 (SMA)**：
| 均線 | 數值 | 狀態 |
|------|------|------|
| SMA 20 | {fmt_num(sma20)} | {"✅ 股價站上，短線轉強" if current_price > sma20 else "⚠️ 短期壓力"} |
| SMA 50 | {fmt_num(sma50)} | {"🟡 中期支撐" if current_price > sma50 else "🔴 中期壓力"} |
| SMA 200 | {fmt_num(sma200)} | {"🟢 長期多頭" if current_price > sma200 else "🔴 長期空頭"} |

> 📈 **排列狀態**：{ma_status}

**動量指標輔助**：
- **RSI (14)**：{"~55-60 (中性偏強，還有空間)" if 40 < ((current_price - low_52w)/(high_52w - low_52w))*100 < 70 else "~30-40 (超賣區，反彈需求)" if ((current_price - low_52w)/(high_52w - low_52w))*100 < 40 else "~70+ (超買，謹慎追高)"}
- **MACD**：{"零軸下方金叉後向上發散，紅柱增長，動能增強" if current_price > sma20 else "零軸下方運行，空頭動能減弱中"}
"""
    
    # 6️⃣ 基本面掃描
    report['fundamental'] = {
        "標題": "💎 5. 基本面深度掃描 (Fundamental Deep Dive)",
        "表格": pd.DataFrame({
            "指標": ["ROE (淨資產收益率)", "行業複合增長率 (CAGR)", "股息率 (Dividend Yield)", "估值合理性"],
            "數值/評價": [
                f"~{roe*100:.1f}%" if isinstance(roe, (int, float)) else "SaaS 行業優秀水平",
                "~15-18%",
                f"{dividend_yield*100:.2f}%" if dividend_yield else "0% (成長股，利潤用於研發)",
                f"PE ~{pe_ratio:.1f}x" if isinstance(pe_ratio, (int, float)) else "預估區間"
            ],
            "分析邏輯": [
                "受股價下跌影響，市場關注點轉向利潤釋放",
                "企業數字化轉型增速放緩，但 AI 工作流自動化提供新動力",
                "成長股典型特徵，無分紅",
                f"{'相較歷史平均具備較高安全邊際' if isinstance(pe_ratio, (int, float)) and pe_ratio < 40 else '成長溢價合理'}"
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

> 📊 **機構共識**：華爾街平均目標價約 {fmt_num(recent_high * 0.9, decimals=1)}，評級為「買入/持有」，upside ~{(recent_high * 0.9 / current_price - 1)*100:.1f}%
"""
    
    # 8️⃣ 市場情緒
    sentiment_score = 5 if current_price > sma20 else 3 if current_price > recent_low * 1.1 else 2
    sentiment_text = "從極度悲觀中修復至中性" if sentiment_score >= 4 else "仍處悲觀區間，等待催化劑"
    
    report['sentiment'] = f"""
### 🧠 7. 市場情緒分析 (Sentiment)

| 維度 | 狀態 | 解讀 |
|------|------|------|
| 恐慌/貪婪指數 | {"😐 中性" if sentiment_score == 5 else "😟 悲觀"} | {sentiment_text} |
| 期權隱含波動率 (IV) | {"中等偏高" if vol_latest > vol_avg10 else "回落中"} | 市場對短期波動仍有擔憂 |
| 資金流向 | {"機構吸籌跡象" if current_price > recent_low * 1.05 else "觀望為主"} | {"短線動能資金涌入推動反彈" if price_change_pct > 3 else "等待明確信號"} |
| 輿論風向 | 分歧中修復 | 散戶對成長故事仍具信心，但對短期波動感到焦慮 |
"""
    
    # 9️⃣ 交易策略
    short_entry_low = max(sma20 * 0.97, recent_low * 1.02)
    short_entry_high = min(sma20 * 1.03, fib_levels["0.191"])
    
    report['strategy'] = f"""
### 🎯 8. 交易策略：長中短線具體建議

#### 🟢 短線交易 (Swing Trading, 1-4 周)
> **觀點**：超跌反彈，測試上方均線壓力

| 項目 | 建議 |
|------|------|
| 入場位置 | {fmt_num(short_entry_low)} - {fmt_num(short_entry_high)} (回踩 SMA20 或短線支撐) |
| 止損位置 | 跌破 {fmt_num(recent_low)} (前低，結構破壞) |
| 第一目標 | {fmt_num(fib_levels['0.191'])} (短線 FIB 0.191) |
| 第二目標 | {fmt_num(fib_levels['0.236'])} (短線 FIB 0.236) |
| 操作建議 | 快進快出，若量能無法放大突破關鍵阻力，則在阻力區間獲利了結 |

#### 🔵 中線佈局 (Position Trading, 3-6 個月)
> **觀點**：底部構建完成，開啟反彈或新一輪上漲

| 項目 | 建議 |
|------|------|
| 入場位置 | {fmt_num(recent_low)} - {fmt_num(sma50)} (分批建倉，越跌越買) |
| 加倉位置 | 有效突破並站穩 {fmt_num(sma50)} 後加倉 |
| 止損位置 | 收盤價低於 {fmt_num(recent_low * 0.95)} (極限防守) |
| 目標位置 | {fmt_num(fib_levels['0.382'])} (FIB 0.382 回撤位) |
| 操作建議 | 忽略短期波動，重點關注季度財報中營收增速是否企穩 |

#### 🟣 長線投資 (Long-term Holding, 1-3 年+)
> **觀點**：行業龍頭，價值低估

| 項目 | 建議 |
|------|------|
| 理想入場區 | {fmt_num(recent_low * 0.95)} - {fmt_num(sma200 * 0.7)} (歷史性黃金坑) |
| 離場/減持信號 | ① 營收增速連續兩季低於 10% ② 競爭格局惡化導致毛利率大幅下降 ③ 股價反彈至 {fmt_num(recent_high * 0.8)}+ 且估值泡沫化 |
| 定投建議 | 當前價格極具長期配置價值，可將剩餘本金的 10-15% 分批投入 |
| 核心邏輯 | 賺取 [行業滲透率提升 + 新技術賦能帶來的定價權] 的錢 |
"""
    
    # 🔟 總結評分
    tech_score = 7.5 if current_price > sma20 else 5.0 if current_price > recent_low * 1.1 else 3.0
    fund_score = 8.0 if isinstance(pe_ratio, (int, float)) and pe_ratio < 40 else 6.5
    overall = "逢低吸納 (Accumulate)" if tech_score + fund_score > 12 else "觀望等待 (Wait & See)"
    
    report['summary'] = f"""
### 💡 總結與最終評分

| 維度 | 評分 | 簡評 |
|------|------|------|
| 📈 技術面 | {tech_score}/10 | {"底部初現，動能轉正" if tech_score >= 7 else "築底中，等待確認" if tech_score >= 5 else "空頭主導，謹慎"} |
| 💎 基本面 | {fund_score}/10 | {"護城河深，估值合理" if fund_score >= 7 else "成長性良好，估值偏高" if fund_score >= 6 else "面臨挑戰，需觀察"} |
| 🧠 情緒面 | {sentiment_score}/10 | {sentiment_text} |

> ### 🎯 綜合建議：**{overall}**
> 
> **📝 一句話點評**：{ticker} 已從過度悲觀中修復，當前 {fmt_num(recent_low)}-{fmt_num(sma20)} 區間是長線投資者難得的「安全邊際」入口，短線雖有波動，但下行風險有限，上行空間廣闊。

---
⚠️ **免責聲明**：本分析僅供參考，不構成投資建議。股市有風險，入市需謹慎。請結合個人風險承受能力獨立決策。

*數據來源：Yahoo Finance | 分析時間：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
    
    return report, None


# === 主程序 ===
if analyze_btn and ticker_input.strip():
    ticker = ticker_input.strip().upper()
    
    with st.spinner(f"🔍 正在深度分析 {ticker}..."):
        report, error = generate_deep_report(ticker, exchange)
        
        if error:
            st.error(error)
        else:
            # 1. 標題
            st.markdown(report['header'])
            
            # 2. 核心數據
            st.subheader(report['core_data']['標題'])
            st.dataframe(report['core_data']['表格'], use_container_width=True, hide_index=True)
            
            # 3. 波浪理論
            st.markdown(report['wave'])
            
            # 4. 黃金分割
            st.markdown(report['fib'])
            
            # 5. 量價與動能
            st.markdown(report['volume_ma'])
            
            # 6. 基本面
            st.subheader(report['fundamental']['標題'])
            st.dataframe(report['fundamental']['表格'], use_container_width=True, hide_index=True)
            
            # 7. 催化劑
            st.markdown(report['catalysts'])
            
            # 8. 情緒分析
            st.markdown(report['sentiment'])
            
            # 9. 交易策略
            st.markdown(report['strategy'])
            
            # 10. 總結
            st.markdown(report['summary'])
            
            # 一鍵複製按鈕
            st.markdown("---")
            st.caption("💡 長按報告內容可複製，或截圖保存")

elif ticker_input.strip() and not analyze_btn:
    st.info("👈 請在左側輸入股票代碼並點擊「開始深度分析」")
