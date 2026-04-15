import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import math

# 頁面配置
st.set_page_config(page_title="股票技術分析", page_icon="📊", layout="centered")
st.title("📊 股票技術分析工具")
st.markdown("**輸入代碼 → 點擊分析 → 隨時切換下一支**")

# 使用 Session State 記住查詢狀態
if 'target_ticker' not in st.session_state:
    st.session_state.target_ticker = None

# 側邊欄
with st.sidebar:
    st.header("🔍 查詢設置")
    input_ticker = st.text_input("股票代碼", value="NOW", placeholder="例如：NOW, NVDA, TSLA")
    
    if st.button("🚀 開始分析", type="primary", use_container_width=True):
        st.session_state.target_ticker = input_ticker.strip().upper()
        st.rerun()

# 主顯示區域
if st.session_state.target_ticker:
    ticker = st.session_state.target_ticker
    st.subheader(f"📈 {ticker} 技術分析報告")

    try:
        with st.spinner(f"正在抓取 {ticker} 數據..."):
            stock = yf.Ticker(ticker)
            df = stock.history(period="2y", interval="1d")

            if df.empty:
                st.error("❌ 無法獲取數據，請確認代碼是否正確。")
                st.stop()

            # 數據計算
            current_price = df['Close'].iloc[-1]
            prev_close = df['Close'].iloc[-2] if len(df) > 1 else current_price
            price_change = current_price - prev_close
            price_change_pct = (price_change / prev_close) * 100

            high_52w = df['High'].rolling(window=252).max().iloc[-1]
            low_52w = df['Low'].rolling(window=252).min().iloc[-1]

            recent_high = df['High'].max()
            recent_high_date = df['High'].idxmax().strftime('%Y-%m')
            recent_low = df['Low'].min()
            recent_low_date = df['Low'].idxmin().strftime('%Y-%m-%d')

            sma20 = df['Close'].rolling(20).mean().iloc[-1]
            sma50 = df['Close'].rolling(50).mean().iloc[-1]
            sma200 = df['Close'].rolling(200).mean().iloc[-1]

            vol_latest = df['Volume'].iloc[-1]
            vol_avg10 = df['Volume'].rolling(10).mean().iloc[-1]

            drop_range = recent_high - recent_low
            fib_191 = recent_low + drop_range * 0.191
            fib_236 = recent_low + drop_range * 0.236
            fib_382 = recent_low + drop_range * 0.382
            drop_pct = (drop_range / recent_high) * 100

            res1 = math.ceil(current_price / 5) * 5 if current_price < 100 else math.ceil(current_price / 10) * 10
            sup2 = math.floor(recent_low / 5) * 5 if recent_low > 10 else recent_low - 2

        # UI 渲染
        st.metric(label=f"{ticker} 最新價", value=f"${current_price:.2f}", delta=f"{price_change:+.2f} ({price_change_pct:+.2f}%)")
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.metric("52週高", f"${high_52w:.2f}")
            st.metric("波段高點", f"${recent_high:.2f}", delta=recent_high_date)
        with col2:
            st.metric("52週低", f"${low_52w:.2f}")
            st.metric("波段低點", f"${recent_low:.2f}", delta=recent_low_date)
        st.divider()

        st.subheader("🌊 波浪與黃金分割")
        st.write(f"**A浪跌幅**：{drop_pct:.1f}%")
        if current_price < fib_191:
            st.error(f"📉 **B浪狀態**：極弱反彈（現價 ${current_price:.2f} < 0.191阻力 ${fib_191:.1f}）")
        else:
            st.success(f"📈 **B浪狀態**：反彈空間打開")

        st.write("**黃金分割阻力位**：")
        st.write(f"• 0.191 → ${fib_191:.1f}")
        st.write(f"• 0.236 → ${fib_236:.1f}")
        st.write(f"• 0.382 → ${fib_382:.1f}")
        st.divider()

        st.subheader("📊 均線與量能")
        c1, c2, c3 = st.columns(3)
        c1.metric("SMA20", f"{sma20:.1f}")
        c2.metric("SMA50", f"{sma50:.1f}")
        c3.metric("SMA200", f"{sma200:.1f}")

        if current_price < sma20:
            st.warning("📉 **均線排列**：空頭排列，中期偏弱")
        else:
            st.success("📈 **均線排列**：多頭或修復中")

        vol_msg = "📉 買盤枯竭（縮量）" if vol_latest < vol_avg10 else "📈 資金介入（放量）"
        st.info(f"**成交量狀態**：{vol_msg}")
        st.divider()

        st.subheader("🎯 關鍵價位與策略")
        st.write(f"**阻力**：${res1:.1f} (心理) | ${sma20:.1f} (SMA20)")
        st.write(f"**支撐**：${recent_low:.2f} (前低) | ${sup2:.1f} (整數)")

        if current_price < sma20:
            st.warning("💡 **建議**：高拋為主，謹慎低吸。跌破前低清倉。")
        else:
            st.info("💡 **建議**：順勢而為，回調確認後可輕倉試多。")

        st.divider()
        st.caption(f"⚠️ 免責聲明：僅供參考，不構成投資建議。數據更新：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

    except Exception as e:
        st.error(f"❌ 分析失敗：{e}")

else:
    st.info("👈 請在左側輸入股票代碼並點擊「開始分析」")
