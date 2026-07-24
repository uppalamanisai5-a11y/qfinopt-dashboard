
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import json, requests, time
from datetime import datetime, timedelta, date, timezone
IST = timezone(timedelta(hours=5, minutes=30))

st.set_page_config(
    page_title="Q-FinOpt Live",
    page_icon="📈", layout="wide")

# ══════════════════════════════════════
# REAL-TIME DATA FUNCTIONS
# ══════════════════════════════════════

@st.cache_data(ttl=300)  # refresh every 5 minutes
def get_live_market():
    """Fetch live Nifty + Sensex from Yahoo Finance"""
    import yfinance as yf
    result = {}
    indices = [
        ("Nifty 50",   "^NSEI"),
        ("Sensex",     "^BSESN"),
        ("Bank Nifty", "^NSEBANK"),
        ("Nifty IT",   "^CNXIT")
    ]
    for name, ticker in indices:
        try:
            # Try multiple methods to get data
            tk   = yf.Ticker(ticker)
            # Method 1: fast_info
            try:
                fi   = tk.fast_info
                now  = float(fi.last_price)
                prev = float(fi.previous_close)
                if now > 0 and prev > 0:
                    chg = now - prev
                    pct = (chg/prev)*100
                    result[name] = {
                        "price" : now,
                        "change": chg,
                        "pct"   : pct
                    }
                    continue
            except:
                pass
            # Method 2: history
            try:
                hist = tk.history(period="5d", interval="1d")
                if len(hist) >= 2:
                    now  = float(hist["Close"].iloc[-1])
                    prev = float(hist["Close"].iloc[-2])
                    chg  = now - prev
                    pct  = (chg/prev)*100
                    result[name] = {
                        "price" : now,
                        "change": chg,
                        "pct"   : pct
                    }
            except:
                pass
        except:
            pass
    return result

@st.cache_data(ttl=3600)  # refresh every 1 hour
def get_live_nav_amfi():
    """Fetch TODAY's NAV for all funds from AMFI India official API"""
    try:
        url  = "https://www.amfiindia.com/spages/NAVAll.txt"
        resp = requests.get(url, timeout=15)
        lines = resp.text.strip().split("\n")
        nav_data = {}
        for line in lines:
            parts = line.strip().split(";")
            if len(parts) >= 5:
                try:
                    scheme_code = parts[0].strip()
                    scheme_name = parts[3].strip()
                    nav_val     = parts[4].strip()
                    nav_date    = parts[5].strip() if len(parts)>5 else ""
                    if nav_val not in ["N.A.","","#N/A"]:
                        nav_data[scheme_name] = {
                            "code": scheme_code,
                            "nav" : float(nav_val),
                            "date": nav_date
                        }
                except:
                    pass
        return nav_data
    except:
        return {}

@st.cache_data(ttl=300)
def get_market_news():
    """Get market sentiment from Nifty performance"""
    try:
        import yfinance as yf
        nifty = yf.Ticker("^NSEI")
        hist  = nifty.history(period="1mo")
        if len(hist) > 0:
            month_ret = (float(hist["Close"].iloc[-1]) /
                         float(hist["Close"].iloc[0]) - 1)*100
            week_ret  = (float(hist["Close"].iloc[-1]) /
                         float(hist["Close"].iloc[-5]) - 1)*100 if len(hist)>=5 else 0
            return {
                "month_return": month_ret,
                "week_return" : week_ret,
                "sentiment"   : "Bullish" if month_ret > 2 else
                                "Bearish" if month_ret < -2 else "Neutral"
            }
    except:
        pass
    return {"month_return":0,"week_return":0,"sentiment":"Neutral"}

@st.cache_data
def load_historical():
    """Load historical dataset from Google Drive"""
    file_id = "1EfNv54tjvjcsJdZhxYwa4zPJxl9q9_9X"
    url     = f"https://drive.google.com/uc?id={file_id}"
    df      = pd.read_csv(url)
    df["Date"] = pd.to_datetime(df["Date"])
    return df

# ══════════════════════════════════════
# LOAD ALL DATA
# ══════════════════════════════════════

st.title("📈 Q-FinOpt: Live Mutual Fund Advisor")
st.markdown("*Real-time NAV · Live Market · SIP Calculator · Withdrawal Timing*")

# Loading bar
with st.spinner("Fetching live market data..."):
    market    = get_live_market()
    nav_today = get_live_nav_amfi()
    sentiment = get_market_news()
    df        = load_historical()

# ══════════════════════════════════════
# LIVE MARKET TICKER
# ══════════════════════════════════════

st.subheader("📡 Live Market — Auto refreshes every 5 minutes")
if market:
    cols = st.columns(len(market))
    for col, (name, data) in zip(cols, market.items()):
        arrow = "▲" if data["pct"] > 0 else "▼"
        col.metric(
            name,
            f"{data['price']:,.2f}",
            f"{arrow} {abs(data['change']):.2f} ({data['pct']:+.2f}%)")
else:
    st.warning("Market data loading... refresh in a moment.")

# Market sentiment bar
sent  = sentiment["sentiment"]
m_ret = sentiment["month_return"]
w_ret = sentiment["week_return"]
color = "🟢" if sent=="Bullish" else "🔴" if sent=="Bearish" else "🟡"
st.markdown(
    f"{color} **Market Sentiment: {sent}** &nbsp;|&nbsp; "
    f"1-Month Nifty: **{m_ret:+.2f}%** &nbsp;|&nbsp; "
    f"1-Week: **{w_ret:+.2f}%** &nbsp;|&nbsp; "
    f"Last updated: **{datetime.now(IST).strftime('%d %b %Y %I:%M %p')} IST**")

# Auto refresh button
if st.button("🔄 Refresh Live Data Now"):
    st.cache_data.clear()
    st.rerun()

st.divider()

# ══════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════

st.sidebar.title("🎯 Your Investment")
categories  = sorted(df["Sheet_Category"].unique())
risk_levels = sorted(df["Risk_Level"].unique())

st.sidebar.subheader("Filter Funds")
sel_cat  = st.sidebar.multiselect(
    "Category", categories, default=categories[:3])
sel_risk = st.sidebar.multiselect(
    "Risk Level", risk_levels, default=risk_levels)

filtered = sorted(df[
    (df["Sheet_Category"].isin(sel_cat)) &
    (df["Risk_Level"].isin(sel_risk))
]["Scheme_Name"].unique())

st.sidebar.subheader("Fund & Amount")
selected_fund = st.sidebar.selectbox("Choose Fund:", filtered)
invest_date   = st.sidebar.date_input(
    "Start Date:", value=date.today())
investment    = st.sidebar.number_input(
    "Lump Sum (₹)", min_value=500,
    max_value=10000000, value=100000, step=500)
sip_amount    = st.sidebar.number_input(
    "Monthly SIP (₹)", min_value=500,
    max_value=100000, value=5000, step=500)
sip_years     = st.sidebar.slider(
    "SIP Duration (years)", 1, 30, 10)
n_sim = st.sidebar.selectbox(
    "Simulations", [1000,5000,10000], index=1)

st.sidebar.divider()

# Show live NAV in sidebar
if nav_today:
    # Try to match fund name
    best_match  = None
    best_score  = 0
    fund_words  = set(selected_fund.lower().split())
    for amfi_name in nav_today:
        amfi_words = set(amfi_name.lower().split())
        score = len(fund_words & amfi_words)
        if score > best_score:
            best_score = score
            best_match = amfi_name

    if best_match and best_score >= 2:
        live_nav  = nav_today[best_match]["nav"]
        nav_date  = nav_today[best_match]["date"]
        st.sidebar.success(
            f"📡 **Live NAV Today**\n\n"
            f"₹{live_nav:.4f}\n\n"
            f"As of {nav_date}")
    else:
        st.sidebar.info("Live NAV: Searching AMFI...")

# ══════════════════════════════════════
# FUND STATISTICS (from real data)
# ══════════════════════════════════════

fund_df    = df[df["Scheme_Name"]==selected_fund].sort_values("Date")
mu_real    = fund_df["Daily_Return_%"].mean()
sigma_real = fund_df["Daily_Return_%"].std()
sharpe_val = fund_df["Sharpe"].mean()
alpha_val  = fund_df["Alpha"].mean()
beta_val   = fund_df["Beta"].mean()
expense    = fund_df["Expense_Ratio"].mean()
risk_level = fund_df["Risk_Level"].iloc[-1]
category   = fund_df["Sheet_Category"].iloc[-1]
hist_nav   = fund_df["NAV_Value"].iloc[-1]
nav_1y     = fund_df["NAV_Value"].iloc[-252] if len(fund_df)>252 else fund_df["NAV_Value"].iloc[0]
ret_1y     = ((hist_nav - nav_1y)/nav_1y)*100

# Use live NAV if available
display_nav = hist_nav
if nav_today and best_match and best_score >= 2:
    display_nav = nav_today[best_match]["nav"]
    nav_source  = "📡 LIVE"
else:
    nav_source  = "📁 Historical"

# Market-adjusted mu
try:
    mu_adjusted = mu_real + (
        sentiment["week_return"]/500 * beta_val)
except:
    mu_adjusted = mu_real

# Fund header
st.subheader(f"📊 {selected_fund}")
st.caption(
    f"Category: {category} | Risk: {risk_level} | "
    f"NAV Source: {nav_source} | "
    f"Market: {sentiment['sentiment']}")

c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("NAV Today",
          f"₹{display_nav:.2f}",
          nav_source)
c2.metric("1Y Return",    f"{ret_1y:.2f}%",  f"{ret_1y:.1f}%")
c3.metric("Sharpe Ratio", f"{sharpe_val:.3f}")
c4.metric("Alpha",        f"{alpha_val:.3f}")
c5.metric("Beta",         f"{beta_val:.3f}")
c6.metric("Expense",      f"{expense:.2f}%")
st.divider()

# ══════════════════════════════════════
# TABS
# ══════════════════════════════════════

tab1,tab2,tab3,tab4,tab5,tab6,tab7,tab8 = st.tabs([
    "📅 Withdrawal Timing",
    "📅 SIP Calculator",
    "📈 Fund Analysis",
    "🏦 Platform Guide",
    "⚖️ Compare Funds",
    "📡 Live NAV Search",
    "📄 PDF Report",
    "🔔 Reminders"])

# -- TAB 1: Fund Ranking Signal (replaces withdrawal-timing) --
with tab1:
    st.subheader("📊 Fund Outperformance Ranking")
    st.caption(
        "Based on a ranking model validated with a rank correlation of "
        "approx. 0.05-0.06 against actual 21-day forward returns, confirmed "
        "positive across 5 walk-forward test windows - a real but modest "
        "statistical edge, not a guarantee. This replaces the earlier "
        "'optimal withdraw day' feature: our own backtesting across 64 "
        "parameter combinations found no price/drawdown exit rule beats "
        "simply holding for this fund universe."
    )

    @st.cache_data(ttl=3600)
    def load_ranking_snapshot():
        file_id = "1u6bsaGaAumPnF8DxAS6jmHrlllkzshJu"
        url = f"https://drive.google.com/uc?id={file_id}"
        return pd.read_csv(url)

    try:
        rank_df = load_ranking_snapshot()
    except Exception as e:
        rank_df = None
        st.error(f"Could not load ranking snapshot: {e}")

    cat_col_name = next(
        (c for c in ["Sheet_Category", "Category", "Fund_Category"]
         if rank_df is not None and c in rank_df.columns),
        None
    )

    if rank_df is None or selected_fund not in rank_df["Scheme_Name"].values:
        st.warning("Ranking data not available yet for this fund.")
    else:
        row = rank_df[rank_df["Scheme_Name"] == selected_fund].iloc[0]
        pct = row["Category_Percentile"]
        cat_name = row[cat_col_name] if cat_col_name else None

        if pct >= 75:
            tier, color, icon = "Top Quartile", "#4CAF50", "🟢"
        elif pct >= 50:
            tier, color, icon = "Above Median", "#8BC34A", "🟡"
        elif pct >= 25:
            tier, color, icon = "Below Median", "#FF9800", "🟠"
        else:
            tier, color, icon = "Bottom Quartile", "#F44336", "🔴"

        peer_group = f"{cat_name} funds" if cat_name else "all funds in our dataset"

        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#0d1b2a,#1b263b);
                    border:2px solid {color};
                    padding:24px;border-radius:16px;margin:12px 0">
            <h2 style="color:{color};margin:0 0 6px 0">
                {icon} {tier}
            </h2>
            <p style="color:#aaa;margin:0 0 16px 0;font-size:13px">
                Model-based outperformance rank vs peers, next-21-day horizon
            </p>
            <div style="font-size:15px;color:white">
                This fund ranks in the <strong>{pct:.0f}th percentile</strong>
                of {peer_group} on the model's outperformance score.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.subheader("Top-Ranked Peers" + (f" - {cat_name}" if cat_name else ""))
        peers = rank_df if not cat_name else rank_df[rank_df[cat_col_name] == cat_name]
        top_peers = peers.sort_values("Category_Percentile", ascending=False).head(10)
        st.dataframe(
            top_peers[["Scheme_Name", "Category_Percentile"]].rename(
                columns={"Scheme_Name": "Fund", "Category_Percentile": "Percentile"}
            ),
            use_container_width=True, hide_index=True)

    st.info(
        "This is a relative signal for comparing funds against their "
        "peers - not a buy, sell, or withdrawal-timing recommendation. "
        "Use it alongside your own judgment and the Fund Analysis and "
        "Compare Funds tabs.")


# ── TAB 2: SIP Calculator ──
with tab2:
    st.subheader("📅 SIP Calculator")
    st.caption(
        "Illustrative planning scenario — not a price prediction or guaranteed return."
    )

    c1, c2 = st.columns(2)
    with c1:
        annual_return_pct = st.slider(
            "Annual return assumption (%)",
            min_value=4.0, max_value=15.0, value=10.0, step=0.5,
            help="A planning assumption, not the ML model prediction."
        )
    with c2:
        nav_log_returns = np.log(
            fund_df["NAV_Value"] / fund_df["NAV_Value"].shift(1)
        ).dropna()
        historical_vol = float(nav_log_returns.std() * np.sqrt(252) * 100)
        default_vol = float(np.clip(historical_vol, 8.0, 35.0))
        annual_vol_pct = st.slider(
            "Annual volatility (%)",
            min_value=8.0, max_value=35.0, value=default_vol, step=1.0,
            help="Higher volatility means a wider range of possible outcomes."
        )

    sip_months = sip_years * 12
    sip_days_total = sip_years * 252
    total_invested = sip_amount * sip_months
    n_sip = min(n_sim, 5000)

    # Annual assumptions -> daily lognormal returns.
    # This avoids impossible returns below -100% and does NOT use mu_adjusted.
    rng = np.random.default_rng(42)
    annual_return = annual_return_pct / 100
    annual_vol = annual_vol_pct / 100
    daily_log_mean = (
        np.log1p(annual_return) - 0.5 * annual_vol**2
    ) / 252
    daily_log_vol = annual_vol / np.sqrt(252)

    daily_returns = np.exp(rng.normal(
        daily_log_mean, daily_log_vol,
        size=(sip_days_total, n_sip)
    )) - 1

    sip_paths = np.zeros((sip_days_total + 1, n_sip))
    invested_line = np.zeros(sip_days_total + 1)
    portfolio = np.zeros(n_sip)
    deposited = 0.0

    for day in range(sip_days_total):
        # One deposit every 21 trading days = 12 deposits/year.
        if day % 21 == 0:
            portfolio += sip_amount
            deposited += sip_amount

        portfolio *= (1 + daily_returns[day])
        sip_paths[day + 1] = portfolio
        invested_line[day] = deposited
        invested_line[day + 1] = deposited

    final_sip = sip_paths[-1]
    expected_sip = float(final_sip.mean())
    median_sip = float(np.median(final_sip))
    gain_sip = expected_sip - total_invested
    profit_probability = float((final_sip > total_invested).mean() * 100)

    # Correct money-weighted annual return for monthly deposits.
    def calculate_xirr(amounts, dates):
        days = np.array([(d - dates[0]).days for d in dates], dtype=float)

        def npv(rate):
            return np.sum(np.asarray(amounts) / (1 + rate) ** (days / 365.25))

        low, high = -0.9999, 2.0
        while npv(high) > 0 and high < 100:
            high *= 2
        for _ in range(120):
            mid = (low + high) / 2
            if npv(mid) > 0:
                low = mid
            else:
                high = mid
        return (low + high) / 2

    cashflow_dates = [
        invest_date + timedelta(days=30 * month)
        for month in range(sip_months)
    ]
    expected_xirr = calculate_xirr(
        [-sip_amount] * sip_months + [expected_sip],
        cashflow_dates + [invest_date + timedelta(days=365.25 * sip_years)]
    ) * 100

    r1, r2, r3, r4, r5 = st.columns(5)
    r1.metric("Monthly SIP", f"₹{sip_amount:,}")
    r2.metric("Total Invested", f"₹{total_invested:,.0f}")
    r3.metric("Expected Corpus", f"₹{expected_sip:,.0f}", f"+₹{gain_sip:,.0f}")
    r4.metric("Est. XIRR", f"{expected_xirr:.1f}%/year")
    r5.metric("Profit Probability", f"{profit_probability:.1f}%")

    st.caption(
        f"Median corpus: ₹{median_sip:,.0f} · "
        f"10th–90th percentile: ₹{np.percentile(final_sip, 10):,.0f} – "
        f"₹{np.percentile(final_sip, 90):,.0f}"
    )

    col1, col2 = st.columns(2)

    with col1:
        days_axis_sip = np.arange(sip_days_total + 1)
        sample_idx_sip = np.random.choice(n_sip, size=min(30, n_sip), replace=False)
        fig_s = go.Figure()
        for i in sample_idx_sip:
            fig_s.add_trace(go.Scatter(
                x=days_axis_sip, y=sip_paths[:, i], mode="lines",
                line=dict(color="rgba(70,130,180,0.12)", width=1),
                showlegend=False, hoverinfo="skip"))
        fig_s.add_trace(go.Scatter(
            x=days_axis_sip, y=sip_paths.mean(axis=1), mode="lines",
            name="Expected corpus", line=dict(color="orange", width=2.5),
            hovertemplate="Day %{x}<br>₹%{y:,.0f}<extra>Expected</extra>"))
        fig_s.add_trace(go.Scatter(
            x=days_axis_sip, y=invested_line, mode="lines",
            name="Amount invested", line=dict(color="#F44336", width=2, dash="dash"),
            hovertemplate="Day %{x}<br>₹%{y:,.0f}<extra>Invested</extra>"))
        fig_s.update_layout(
            title=f"SIP Growth — {sip_years} Years",
            xaxis_title="Trading Days", yaxis_title="Value (₹)",
            hovermode="x unified", height=430,
            margin=dict(l=10, r=10, t=55, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1))
        st.plotly_chart(fig_s, use_container_width=True, config={"displayModeBar": False})

    with col2:
        fig_s2 = go.Figure()
        fig_s2.add_trace(go.Histogram(
            x=final_sip, nbinsx=60, marker_color="steelblue", opacity=0.85,
            hovertemplate="Final value: ₹%{x:,.0f}<br>Count: %{y}<extra></extra>"))
        fig_s2.add_vline(x=total_invested, line_width=2, line_dash="dash", line_color="#F44336",
                          annotation_text=f"Invested ₹{total_invested:,.0f}",
                          annotation_position="top")
        fig_s2.add_vline(x=expected_sip, line_width=2.5, line_color="#4CAF50",
                          annotation_text=f"Expected ₹{expected_sip:,.0f}",
                          annotation_position="top")
        fig_s2.update_layout(
            title="Final Corpus Distribution",
            xaxis_title="Final Value (₹)", yaxis_title="Count",
            height=430, margin=dict(l=10, r=10, t=55, b=10))
        st.plotly_chart(fig_s2, use_container_width=True, config={"displayModeBar": False})

    st.subheader("📆 Year-by-Year Projection")
    rows = []
    for yr in range(1, sip_years + 1):
        day_index = yr * 252
        yearly_values = sip_paths[day_index]
        yearly_invested = invested_line[day_index]
        rows.append({
            "Year": f"Year {yr}",
            "Invested": f"₹{yearly_invested:,.0f}",
            "Expected": f"₹{yearly_values.mean():,.0f}",
            "Median": f"₹{np.median(yearly_values):,.0f}",
            "10th–90th Range": (
                f"₹{np.percentile(yearly_values, 10):,.0f} – "
                f"₹{np.percentile(yearly_values, 90):,.0f}"
            ),
            "Profit Probability": f"{(yearly_values > yearly_invested).mean() * 100:.1f}%"
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ── TAB 3: Fund Analysis — Interactive Plotly chart + predicted-value callouts ──
with tab3:
    st.subheader(f"📈 {selected_fund[:55]}")
    @st.cache_data(ttl=86400)
    def resolve_mfapi_code(fund_name, fallback_code):
        """Your dataset's Scheme_Code is an internal ID mfapi.in doesn't
        recognize (this is why live NAV history was always unavailable
        and charts looked frozen). Search mfapi.in by fund name instead."""
        try:
            resp = requests.get(
                "https://api.mfapi.in/mf/search",
                params={"q": fund_name}, timeout=15)
            matches = resp.json()
            if not matches:
                return fallback_code

            fn_lower = fund_name.lower()
            def score(m):
                n = m.get("schemeName", "").lower()
                s = 0
                if "direct" in fn_lower and "direct" in n: s += 3
                elif "direct" not in fn_lower and "direct" not in n: s += 1
                if "growth" in fn_lower and "growth" in n: s += 2
                return s

            best = max(matches, key=score)
            return str(best.get("schemeCode", fallback_code))
        except Exception:
            return fallback_code

    fallback_code = str(fund_df["Scheme_Code"].iloc[-1]).split(".")[0]
    scheme_code = resolve_mfapi_code(selected_fund, fallback_code)
    @st.cache_data(ttl=3600)
    def get_live_nav_history(code):
        """Full daily NAV history for one fund from mfapi.in (free, no key, updates daily)"""
        try:
            resp = requests.get(f"https://api.mfapi.in/mf/{code}", timeout=15)
            debug_info = {"status_code": resp.status_code, "url": resp.url}
            payload = resp.json()
            hist = payload.get("data", [])
            debug_info["rows_returned"] = len(hist)
            debug_info["meta"] = payload.get("meta", {})
            if not hist:
                return None, debug_info
            hdf = pd.DataFrame(hist)
            hdf["date"] = pd.to_datetime(hdf["date"], dayfirst=True, errors="coerce")
            hdf["nav"]  = pd.to_numeric(hdf["nav"], errors="coerce")
            hdf = hdf.dropna().sort_values("date").reset_index(drop=True)
            debug_info["last_date"] = str(hdf["date"].max()) if len(hdf) else None
            return (hdf if len(hdf) > 5 else None), debug_info
        except Exception as e:
            return None, {"error": f"{type(e).__name__}: {e}"}

    live_hist, live_debug = get_live_nav_history(scheme_code)
    with st.expander("🔍 Debug: live NAV fetch status", expanded=False):
        st.write("Scheme code used:", scheme_code)
        st.json(live_debug)

    period_map = {"1M":21,"3M":63,"6M":126,"1Y":252,
                  "2Y":504,"3Y":756,"5Y":1260,"ALL":100000}
    period = st.radio("Period:", list(period_map.keys()),
                       index=3, horizontal=True, key="tab3_period")
    n_days = period_map[period]

    fc_col1, fc_col2 = st.columns([1,2])
    with fc_col1:
        show_forecast3 = st.checkbox("📈 Show predicted trend", value=True, key="tab3_forecast")
    with fc_col2:
        forecast_days3 = st.slider("Forecast days", 5, 90, 30, key="tab3_fc_days") if show_forecast3 else 0

    if live_hist is not None:
        plot_df = live_hist.tail(n_days) if n_days < len(live_hist) else live_hist
        base    = plot_df["nav"].iloc[0]
        dates   = list(plot_df["date"])
        values  = list((plot_df["nav"]/base - 1)*100)
        source_label = "📡 Live daily NAV history — mfapi.in (AMFI data)"
    else:
        plot_df = fund_df.tail(n_days) if n_days < len(fund_df) else fund_df
        base    = plot_df["NAV_Value"].iloc[0]
        dates   = list(plot_df["Date"])
        values  = list((plot_df["NAV_Value"]/base - 1)*100)
        source_label = "📁 Historical CSV (live NAV history unavailable for this fund's code)"

    recent_window = values[-30:] if len(values) > 30 else values
    recent_rets   = np.diff(recent_window) if len(recent_window) > 1 else [0]
    mu_trend      = float(np.mean(recent_rets)) if len(recent_rets) > 0 else 0.0

    if mu_trend > 0.01:
        trend_label, trend_icon = "Trending UP", "📈"
    elif mu_trend < -0.01:
        trend_label, trend_icon = "Trending DOWN", "📉"
    else:
        trend_label, trend_icon = "Flat / Sideways", "➖"

    # ── Predicted trend (computed up front so we can show a metric AND the chart) ──
    fut_dates, fut_vals, predicted_final = [], [], None
    if show_forecast3 and len(values) > 0:
        last_val, last_date = values[-1], dates[-1]
        fut_dates = list(pd.bdate_range(last_date + pd.Timedelta(days=1), periods=forecast_days3))
        fut_vals  = [last_val + mu_trend*(i+1) for i in range(forecast_days3)]
        predicted_final = fut_vals[-1] if fut_vals else last_val

    # ── Headline metrics: current value, predicted value, predicted NAV ──
    m1, m2, m3 = st.columns(3)
    m1.metric("Current % Change", f"{values[-1]:+.2f}%" if values else "—")
    if predicted_final is not None:
        m2.metric(f"Predicted (+{forecast_days3}d)", f"{predicted_final:+.2f}%",
                   delta=f"{predicted_final - values[-1]:+.2f}%")
        predicted_nav = base * (1 + predicted_final/100)
        m3.metric("Predicted NAV", f"₹{predicted_nav:.2f}")
    else:
        m2.metric("Predicted", "—")
        m3.metric("Predicted NAV", "—")

    col1, col2 = st.columns([2,1])

    with col1:
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=dates, y=values, mode="lines", name="Actual (% change)",
            line=dict(color="#3f7cb8", width=2.4),
            hovertemplate="%{x|%d %b %Y}<br><b>%{y:.2f}%</b><extra>Actual</extra>"
        ))

        if show_forecast3 and fut_vals:
            fig3.add_trace(go.Scatter(
                x=[dates[-1]] + fut_dates, y=[values[-1]] + fut_vals,
                mode="lines", name="Predicted",
                line=dict(color="orange", width=2.4, dash="dash"),
                hovertemplate="%{x|%d %b %Y}<br><b>%{y:.2f}%</b><extra>Predicted</extra>"
            ))

        fig3.add_hline(y=0, line_width=1, line_color="gray", opacity=0.5)
        fig3.update_layout(
            title=f"% Change — {period}  ({trend_icon} {trend_label})",
            xaxis_title="Date", yaxis_title="% Change",
            hovermode="x unified",
            height=430,
            margin=dict(l=10, r=10, t=55, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
        )
        fig3.update_xaxes(
            tickformat="%d %b %Y", tickangle=0, nticks=10,
            showgrid=True, gridcolor="rgba(128,128,128,0.15)",
            rangeslider_visible=True,
        )
        fig3.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.15)")
        st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})
        st.caption(source_label)

    with col2:
        rets = fund_df["Daily_Return_%"].dropna()
        fig4 = go.Figure()
        fig4.add_trace(go.Histogram(
            x=rets, nbinsx=60, marker_color="coral", opacity=0.85,
            hovertemplate="Return: %{x:.2f}%<br>Count: %{y}<extra></extra>"
        ))
        fig4.add_vline(x=mu_real, line_width=2, line_color="green",
                        annotation_text=f"Mean: {mu_real:.4f}%",
                        annotation_position="top")
        fig4.update_layout(
            title="Daily Return Distribution",
            xaxis_title="Daily Return %", yaxis_title="Count",
            height=430, margin=dict(l=10, r=10, t=55, b=10),
        )
        st.plotly_chart(fig4, use_container_width=True, config={"displayModeBar": False})

    if mu_trend > 0.01:
        st.success(
            f"📈 **{selected_fund[:50]} is trending UP** — average change "
            f"~{mu_trend:+.3f}%/day over the recent window. If this holds, "
            f"the forecast projects continued growth.")
    elif mu_trend < -0.01:
        st.error(
            f"📉 **{selected_fund[:50]} is trending DOWN** — average change "
            f"~{mu_trend:+.3f}%/day over the recent window. If this holds, "
            f"the forecast projects continued decline.")
    else:
        st.info(
            f"➖ **{selected_fund[:50]} is roughly flat** — no strong "
            f"recent directional trend detected.")

    stats = pd.DataFrame({
        "Metric" : ["Daily Return (avg)",
                    "Annual Return (est)",
                    "Volatility (SD)",
                    "Sharpe Ratio","Alpha","Beta",
                    "Expense Ratio","Risk Level",
                    "Historical NAV","Live NAV Today",
                    "1 Year Return"],
        "Value"  : [f"{mu_real:.4f}%",
                    f"{mu_real*252:.2f}%",
                    f"{sigma_real:.4f}%",
                    f"{sharpe_val:.3f}",
                    f"{alpha_val:.3f}",
                    f"{beta_val:.3f}",
                    f"{expense:.2f}%",
                    risk_level,
                    f"₹{hist_nav:.2f}",
                    f"₹{display_nav:.2f} ({nav_source})",
                    f"{ret_1y:.2f}%"]
    })
    st.dataframe(stats, use_container_width=True,
                 hide_index=True)

# ── TAB 4: Platform Guide ──
with tab4:
    st.subheader("🏦 Best Platform to Invest")
    if investment < 10000:
        top = "Groww"
        reason = "Best for small amounts · zero minimum"
    elif investment < 100000:
        top = "Kuvera"
        reason = "Best free direct fund platform"
    else:
        top = "Zerodha Coin"
        reason = "Best analytics for large investments"

    st.success(f"🥇 **Best for you: {top}** — {reason}")

    for name,url,rating,desc in [
        ("🌱 Groww","groww.in","⭐⭐⭐⭐⭐",
         "Zero commission · ₹100 min · Instant KYC"),
        ("🪙 Zerodha Coin","coin.zerodha.com","⭐⭐⭐⭐⭐",
         "Best analytics · Direct funds · Stocks+MF"),
        ("💎 Kuvera","kuvera.in","⭐⭐⭐⭐⭐",
         "100% free · Tax harvesting · Goal planning"),
        ("💰 Paytm Money","paytmmoney.com","⭐⭐⭐⭐",
         "UPI instant · SIP automation"),
        ("🏛️ MF Central","mfcentral.com","⭐⭐⭐⭐",
         "SEBI official · Most secure · Free"),
    ]:
        with st.expander(f"{name} {rating}"):
            st.markdown(f"**{desc}** · 🌐 {url}")

    st.divider()
    st.subheader("📌 Your Personalised Action Plan")
    st.info(f"""
**Step 1:** Open **{top}** → complete KYC (Aadhaar + PAN, 5 min)

**Step 2:** Search: **{selected_fund[:50]}**

**Step 3:** Invest **₹{investment:,}** as lump sum
           OR **₹{sip_amount:,}/month** as SIP

**Step 4:** Set reminder to withdraw on:
           **{withdraw_date.strftime("%d %B %Y")}**

**Expected outcome:**
- Lump sum: ₹{investment:,} → ₹{opt_val:,.0f} ({ret_pct:.1f}% in {opt_day//21} months)
- SIP: ₹{sip_amount:,}/mo × {sip_years*12} months → ₹{expected_sip:,.0f}
    """)

# ── TAB 5: Compare Funds — Live % Change + Forecast (Plotly) ──
with tab5:
    st.subheader("⚖️ Live Fund Performance & Forecast")

    all_funds = sorted(df["Scheme_Name"].unique())

    period_map = {"1M":21,"3M":63,"6M":126,"1Y":252,
                  "2Y":504,"3Y":756,"ALL":100000}
    period = st.radio("Period:", list(period_map.keys()),
                       index=3, horizontal=True)
    n_days = period_map[period]

    c1, c2 = st.columns([3,1])
    with c1:
        compare_list = st.multiselect(
            "Select funds to compare (up to 15 for a readable chart):",
            all_funds, default=all_funds[:2])
    with c2:
        show_forecast = st.checkbox("📈 Show forecast", value=True)
        forecast_days = st.slider("Forecast days", 5, 90, 30) if show_forecast else 0

    tab10_colors = ["#1f77b4","#ff7f0e","#2ca02c","#d62728","#9467bd",
                     "#8c564b","#e377c2","#7f7f7f","#bcbd22","#17becf"]

    if 1 <= len(compare_list) <= 15:
        cdata = []
        fig6 = go.Figure()

        for idx, fund in enumerate(compare_list):
            full_fdf = df[df["Scheme_Name"]==fund].sort_values("Date")
            fdf = full_fdf.tail(n_days) if n_days < len(full_fdf) else full_fdf
            if len(fdf) < 5:
                continue

            base_nav = fdf["NAV_Value"].iloc[0]
            dates  = list(fdf["Date"])
            values = list((fdf["NAV_Value"]/base_nav - 1)*100)

            # attach LIVE AMFI NAV so the line reaches today — but only if it's
            # a sane continuation of the series (guards against bad fuzzy matches)
            fund_words = set(fund.lower().split())
            best_match, best_score = None, 0
            for amfi_name in nav_today:
                score = len(fund_words & set(amfi_name.lower().split()))
                if score > best_score:
                    best_score, best_match = score, amfi_name
            if best_match and best_score >= 2:
                live_val = (nav_today[best_match]["nav"]/base_nav - 1)*100
                if abs(live_val - values[-1]) <= max(15, abs(values[-1]) * 0.5):
                    dates.append(pd.Timestamp(datetime.now(IST).date()))
                    values.append(live_val)

            color = tab10_colors[idx % 10]
            fig6.add_trace(go.Scatter(
                x=dates, y=values, mode="lines", name=fund[:28],
                line=dict(color=color, width=2),
                hovertemplate="%{x|%d %b %Y}<br><b>%{y:.2f}%</b><extra>" + fund[:28] + "</extra>"))

            if show_forecast:
                rets = fdf["Daily_Return_%"].dropna().tail(90)
                mu   = rets.mean() if len(rets) > 0 else 0
                last_val, last_date = values[-1], dates[-1]
                fut_dates = list(pd.bdate_range(
                    last_date + pd.Timedelta(days=1), periods=forecast_days))
                fut_vals = [last_val + mu*(i+1) for i in range(forecast_days)]
                fig6.add_trace(go.Scatter(
                    x=[last_date]+fut_dates, y=[last_val]+fut_vals,
                    mode="lines", name=f"{fund[:22]} (forecast)",
                    line=dict(color=color, width=2, dash="dash"), opacity=0.6,
                    hovertemplate="%{x|%d %b %Y}<br><b>%{y:.2f}%</b><extra>Forecast</extra>",
                    showlegend=False))

            r1y = ((full_fdf["NAV_Value"].iloc[-1] -
                    full_fdf["NAV_Value"].iloc[-252 if len(full_fdf)>252 else 0]) /
                   full_fdf["NAV_Value"].iloc[-252 if len(full_fdf)>252 else 0])*100
            cdata.append({
                "Fund"    : fund[:35],
                "Sharpe"  : round(full_fdf["Sharpe"].mean(),3),
                "1Y Ret%" : round(r1y,2),
                "Alpha"   : round(full_fdf["Alpha"].mean(),3),
                "Beta"    : round(full_fdf["Beta"].mean(),3),
                "Expense" : round(full_fdf["Expense_Ratio"].mean(),3),
                "Risk"    : full_fdf["Risk_Level"].iloc[-1],
            })

        fig6.add_hline(y=0, line_width=1, line_color="gray", opacity=0.5)
        title = f"% Change — {period}"
        if show_forecast:
            title += "  (solid = actual · dashed = forecast)"
        fig6.update_layout(
            title=title, xaxis_title="Date", yaxis_title="% Change",
            hovermode="x unified", height=480,
            margin=dict(l=10, r=10, t=55, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="left", x=0))
        fig6.update_xaxes(tickformat="%d %b %Y", showgrid=True,
                            gridcolor="rgba(128,128,128,0.15)", rangeslider_visible=True)
        fig6.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.15)")
        st.plotly_chart(fig6, use_container_width=True, config={"displayModeBar": False})

        st.dataframe(pd.DataFrame(cdata),
                     use_container_width=True,
                     hide_index=True)
        if show_forecast:
            st.caption(
                "Forecast = straight-line trend using each fund's average "
                "daily return over its last 90 trading days. Not a "
                "guarantee of future performance. Click a legend entry to "
                "show/hide that fund.")
    elif len(compare_list) > 15:
        st.warning("Please select 15 funds or fewer for a readable chart.")
    else:
        st.warning("Select at least 1 fund to compare.")


# ── TAB 6: Live NAV Search ──
with tab6:
    st.subheader("📡 Live NAV Search — All Funds")
    st.markdown(
        f"Data from **AMFI India Official API** · "
        f"Updated daily at 11 PM · "
        f"{len(nav_today):,} funds loaded")

    search = st.text_input(
        "Search any mutual fund:",
        placeholder="e.g. SBI, HDFC, Quant, Axis...")

    if search and len(nav_today) > 0:
        results = {k:v for k,v in nav_today.items()
                   if search.lower() in k.lower()}
        if results:
            nav_df = pd.DataFrame([
                {"Fund Name": k,
                 "NAV (₹)"  : f"₹{v['nav']:.4f}",
                 "Date"     : v["date"],
                 "Code"     : v["code"]}
                for k,v in list(results.items())[:50]
            ])
            st.dataframe(nav_df,
                         use_container_width=True,
                         hide_index=True)
            st.caption(
                f"Showing {min(50,len(results))} of "
                f"{len(results)} results")
        else:
            st.warning(f"No funds found for: {search}")
    elif len(nav_today) == 0:
        st.error(
            "AMFI API not responding. "
            "Try clicking Refresh Live Data button above.")
    else:
        st.info(
            "Type a fund name above to search "
            "today's live NAV from AMFI India.")

    if nav_today:
        st.subheader("📊 NAV Statistics Today")
        navs = [v["nav"] for v in nav_today.values()]
        n1,n2,n3,n4 = st.columns(4)
        n1.metric("Total Funds", f"{len(nav_today):,}")
        n2.metric("Lowest NAV",  f"₹{min(navs):.2f}")
        n3.metric("Highest NAV", f"₹{max(navs):,.2f}")
        n4.metric("Average NAV", f"₹{sum(navs)/len(navs):.2f}")


# ── TAB 7: PDF Report ──
with tab7:
    st.subheader("📄 Download Your Investment Report")
    st.markdown("Generate a personalised PDF with your complete analysis.")

    report_name = st.text_input("Your Name:", value="MANI SAI")

    if st.button("📄 Generate and Download PDF"):
        try:
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()

            pdf.set_font("Arial", "B", 18)
            pdf.cell(190, 12, "Q-FinOpt Investment Report", 0, 1, "C")
            pdf.set_font("Arial", "", 10)
            pdf.cell(190, 8,
                f"For: {report_name} | Date: {datetime.now(IST).strftime('%d %b %Y %I:%M %p')} IST",
                0, 1, "C")
            pdf.ln(5)

            pdf.set_font("Arial", "B", 13)
            pdf.cell(190, 10, "Fund Details", 0, 1)
            pdf.set_font("Arial", "", 10)
            for label, value in [
                ("Fund Name",        selected_fund[:60]),
                ("Category",         category),
                ("Risk Level",       risk_level),
                ("Latest NAV",       f"Rs {display_nav:.2f}"),
                ("1 Year Return",    f"{ret_1y:.2f}%"),
                ("Sharpe Ratio",     f"{sharpe_val:.3f}"),
                ("Alpha",            f"{alpha_val:.3f}"),
                ("Beta",             f"{beta_val:.3f}"),
                ("Expense Ratio",    f"{expense:.2f}%"),
                ("Market Sentiment", sentiment["sentiment"]),
            ]:
                pdf.set_font("Arial", "B", 10)
                pdf.cell(70, 7, label + ":", 0, 0)
                pdf.set_font("Arial", "", 10)
                pdf.cell(120, 7, str(value), 0, 1)
            pdf.ln(4)

            pdf.set_font("Arial", "B", 13)
            pdf.cell(190, 10, "Withdrawal Recommendation", 0, 1)
            for label, value in [
                ("Investment Amount",  f"Rs {investment:,}"),
                ("Investment Date",    invest_date.strftime("%d %b %Y")),
                ("Withdraw On",        withdraw_date.strftime("%d %b %Y")),
                ("Holding Period",     f"{opt_day} days (~{opt_day//21} months)"),
                ("Expected Value",     f"Rs {opt_val:,.0f}"),
                ("Expected Gain",      f"Rs {gain:,.0f} ({ret_pct:.1f}%)"),
                ("Profit Probability", f"{prob_g[opt_day]*100:.1f}%"),
            ]:
                pdf.set_font("Arial", "B", 10)
                pdf.cell(70, 7, label + ":", 0, 0)
                pdf.set_font("Arial", "", 10)
                pdf.cell(120, 7, str(value), 0, 1)
            pdf.ln(4)

            pdf.set_font("Arial", "B", 13)
            pdf.cell(190, 10, "SIP Projection", 0, 1)
            for label, value in [
                ("Monthly SIP",      f"Rs {sip_amount:,}"),
                ("Duration",         f"{sip_years} years"),
                ("Total Invested",   f"Rs {total_invested:,}"),
                ("Expected Corpus",  f"Rs {expected_sip:,.0f}"),
                ("Wealth Gain",      f"Rs {gain_sip:,.0f}"),
                ("Est. XIRR",        f"{xirr:.1f}% per year"),
            ]:
                pdf.set_font("Arial", "B", 10)
                pdf.cell(70, 7, label + ":", 0, 0)
                pdf.set_font("Arial", "", 10)
                pdf.cell(120, 7, str(value), 0, 1)
            pdf.ln(4)

            pdf.set_font("Arial", "I", 8)
            pdf.set_text_color(100, 100, 100)
            pdf.multi_cell(190, 6,
                "DISCLAIMER: For educational purposes only. "
                "Mutual fund investments are subject to market risks. "
                "Past performance does not guarantee future returns.")

            pdf.set_font("Arial", "B", 8)
            pdf.set_text_color(0, 0, 0)
            pdf.set_xy(10, 285)
            pdf.cell(190, 6,
                f"Q-FinOpt v3.0 | Built by MANI SAI | {datetime.now(IST).strftime('%d %b %Y')}",
                0, 0, "C")

            pdf_bytes = pdf.output(dest="S").encode("latin-1")
            st.download_button(
                label="⬇️ Click Here to Download PDF",
                data=pdf_bytes,
                file_name=f"QFinOpt_{selected_fund[:15].replace(' ','_')}_{date.today()}.pdf",
                mime="application/pdf")
            st.success("✅ PDF ready! Click button above to download.")

        except ImportError:
            st.warning("Installing PDF library...")
            import subprocess
            subprocess.run(["pip","install","fpdf2","-q"])
            st.info("Done! Click Generate again.")
        except Exception as e:
            st.error(f"Error: {e}")

# ── TAB 8: Reminders ──
with tab8:
    st.subheader("🔔 Set Withdrawal Reminder")
    st.markdown(f"Your optimal withdrawal date is **{withdraw_date.strftime('%d %B %Y')}**")

    st.info(f"""
Fund      : {selected_fund[:55]}
Invested  : Rs {investment:,} on {invest_date.strftime('%d %b %Y')}
Withdraw  : {withdraw_date.strftime('%d %B %Y')} (Day {opt_day})
Expected  : Rs {opt_val:,.0f} (+Rs {gain:,.0f} | {ret_pct:.1f}%)
Probability: {prob_g[opt_day]*100:.1f}%
    """)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📱 WhatsApp Reminder")
        msg = (
            f"Q-FinOpt Reminder%0A"
            f"Fund: {selected_fund[:40]}%0A"
            f"WITHDRAW ON: {withdraw_date.strftime('%d %b %Y')}%0A"
            f"Expected: Rs {opt_val:,.0f}%0A"
            f"Gain: Rs {gain:,.0f} ({ret_pct:.1f}%)")
        wa_url = f"https://wa.me/?text={msg}"
        st.markdown(
            f'''<a href="{wa_url}" target="_blank">
            <button style="background:#25D366;color:white;
                           padding:14px 28px;border:none;
                           border-radius:8px;font-size:15px;
                           cursor:pointer;width:100%">
                📱 Send WhatsApp Reminder
            </button></a>''',
            unsafe_allow_html=True)

    with col2:
        st.markdown("### 📧 Email Reminder")
        subject = f"Withdraw {selected_fund[:25]} on {withdraw_date.strftime('%d %b %Y')}"
        body = (
            f"Q-FinOpt Reminder%0A"
            f"Fund: {selected_fund}%0A"
            f"WITHDRAW ON: {withdraw_date.strftime('%d %B %Y')}%0A"
            f"Expected: Rs {opt_val:,.0f}%0A"
            f"Gain: Rs {gain:,.0f} ({ret_pct:.1f}%)")
        mailto = f"mailto:?subject={subject}&body={body}"
        st.markdown(
            f'''<a href="{mailto}">
            <button style="background:#4285F4;color:white;
                           padding:14px 28px;border:none;
                           border-radius:8px;font-size:15px;
                           cursor:pointer;width:100%">
                📧 Send Email Reminder
            </button></a>''',
            unsafe_allow_html=True)

    st.divider()
    st.markdown("### 📅 Add to Google Calendar")
    cal_date = withdraw_date.strftime("%Y%m%d")
    cal_url  = (
        f"https://calendar.google.com/calendar/render"
        f"?action=TEMPLATE"
        f"&text=Withdraw+{selected_fund[:20].replace(' ','+')}+-+QFinOpt"
        f"&dates={cal_date}/{cal_date}"
        f"&details=QFinOpt+Reminder")
    st.markdown(
        f'''<a href="{cal_url}" target="_blank">
        <button style="background:#DB4437;color:white;
                       padding:14px 28px;border:none;
                       border-radius:8px;font-size:15px;
                       cursor:pointer">
            📅 Add to Google Calendar
        </button></a>''',
        unsafe_allow_html=True)
    st.caption(f"Adds reminder on {withdraw_date.strftime('%d %B %Y')} to Google Calendar!")

st.divider()
from datetime import timezone
IST = timezone(timedelta(hours=5, minutes=30))
st.markdown(
    f"*Q-FinOpt v3.0 Live · "
    f"AMFI India + Yahoo Finance + Historical Data · "
    f"Last refresh: {datetime.now(IST).strftime('%d %b %Y %I:%M %p')} IST · "
    f"Built by MANI SAI*")
