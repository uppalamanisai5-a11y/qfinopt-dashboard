
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

# ── TAB 1: Withdrawal Timing ──
with tab1:
    st.subheader("🎯 When Should You Withdraw?")
    st.markdown(
        f"Using **real data** from {len(fund_df):,} days of "
        f"{selected_fund[:35]} + **live market sentiment: "
        f"{sentiment['sentiment']}**")

    hold_days = 504
    np.random.seed(42)
    daily_ret = np.random.normal(
        mu_adjusted/100, sigma_real/100,
        (hold_days, n_sim))
    paths = np.zeros((hold_days+1, n_sim))
    paths[0] = investment
    for d in range(1, hold_days+1):
        paths[d] = paths[d-1]*(1+daily_ret[d-1])

    exp_v    = paths.mean(axis=1)
    prob_g   = (paths > investment).mean(axis=1)
    vol      = paths.std(axis=1)
    risk_adj = (exp_v - investment)/(vol+1)
    opt_day  = int(np.argmax(risk_adj))
    opt_val  = exp_v[opt_day]
    gain     = opt_val - investment
    ret_pct  = (gain/investment)*100

    # Exact withdrawal date (skip weekends)
    current = datetime.combine(invest_date,
                               datetime.min.time())
    count = 0
    while count < opt_day:
        current += timedelta(days=1)
        if current.weekday() < 5:
            count += 1
    withdraw_date = current.date()

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0d1b2a,#1b263b);
                border:2px solid #4CAF50;
                padding:24px;border-radius:16px;margin:12px 0">
        <h2 style="color:#4CAF50;margin:0 0 6px 0">
            🎯 Personalised Recommendation
        </h2>
        <p style="color:#aaa;margin:0 0 16px 0;font-size:13px">
            Market-adjusted using live {sentiment["sentiment"]} signal
            · Beta {beta_val:.2f} · {n_sim:,} simulations
        </p>
        <div style="display:grid;
                    grid-template-columns:1fr 1fr 1fr 1fr;
                    gap:12px">
            <div style="background:rgba(76,175,80,0.15);
                        border:1px solid #4CAF50;
                        padding:14px;border-radius:10px;
                        text-align:center">
                <div style="color:#81C784;font-size:12px">
                    📅 Invest On</div>
                <div style="color:white;font-size:17px;
                            font-weight:bold">
                    {invest_date.strftime("%d %b %Y")}</div>
            </div>
            <div style="background:rgba(255,215,0,0.15);
                        border:1px solid #FFD700;
                        padding:14px;border-radius:10px;
                        text-align:center">
                <div style="color:#FFD700;font-size:12px">
                    💰 Withdraw On</div>
                <div style="color:#FFD700;font-size:17px;
                            font-weight:bold">
                    {withdraw_date.strftime("%d %b %Y")}</div>
                <div style="color:#aaa;font-size:11px">
                    Day {opt_day} (~{opt_day//21} months)</div>
            </div>
            <div style="background:rgba(33,150,243,0.15);
                        border:1px solid #2196F3;
                        padding:14px;border-radius:10px;
                        text-align:center">
                <div style="color:#64B5F6;font-size:12px">
                    💼 Expected Value</div>
                <div style="color:white;font-size:17px;
                            font-weight:bold">
                    ₹{opt_val:,.0f}</div>
            </div>
            <div style="background:rgba(156,39,176,0.15);
                        border:1px solid #9C27B0;
                        padding:14px;border-radius:10px;
                        text-align:center">
                <div style="color:#CE93D8;font-size:12px">
                    📈 Expected Gain</div>
                <div style="color:#CE93D8;font-size:17px;
                            font-weight:bold">
                    +₹{gain:,.0f}</div>
                <div style="color:#aaa;font-size:11px">
                    {ret_pct:.1f}% return</div>
            </div>
        </div>
        <div style="margin-top:14px;
                    background:rgba(255,255,255,0.05);
                    padding:10px;border-radius:8px;
                    font-size:13px">
            ✅ Profit probability:
            <strong style="color:#81C784">
                {prob_g[opt_day]*100:.1f}%</strong>
            &nbsp;&nbsp;
            📊 Risk level:
            <strong style="color:#64B5F6">{risk_level}</strong>
            &nbsp;&nbsp;
            🌐 NAV source:
            <strong style="color:#FFD54F">{nav_source}</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Period returns
    st.subheader("Returns by Holding Period")
    p_cols = st.columns(4)
    for col,(label,days) in zip(p_cols,[
        ("3 months",63),("6 months",126),
        ("1 year",252),("2 years",504)]):
        v = exp_v[min(days,hold_days)]
        col.metric(label,
            f"₹{v:,.0f}",
            f"+{((v-investment)/investment)*100:.1f}% | "
            f"{prob_g[min(days,hold_days)]*100:.0f}% prob")

    col1,col2 = st.columns(2)
    with col1:
        fig1,ax1 = plt.subplots(figsize=(8,4))
        ax1.plot(paths[:,:min(300,n_sim)],
                 alpha=0.02, color="steelblue",
                 linewidth=0.5)
        ax1.plot(exp_v, color="orange",
                 linewidth=2.5, label="Expected")
        ax1.plot([np.percentile(paths[d],5)
                  for d in range(hold_days+1)],
                 color="red", linewidth=1.5,
                 linestyle="--", label="Worst 5%")
        ax1.plot([np.percentile(paths[d],95)
                  for d in range(hold_days+1)],
                 color="green", linewidth=1.5,
                 linestyle="--", label="Best 95%")
        ax1.axhline(investment, color="white",
                    linewidth=1, linestyle=":")
        ax1.axvline(opt_day, color="yellow",
                    linewidth=2, linestyle="--",
                    label=f"Withdraw Day {opt_day}")
        ax1.set_title(f"Monte Carlo: {n_sim:,} Scenarios")
        ax1.set_xlabel("Trading Days")
        ax1.set_ylabel("Value (₹)")
        ax1.legend(fontsize=7)
        ax1.grid(True, alpha=0.2)
        st.pyplot(fig1); plt.close()

    with col2:
        fig2,ax2 = plt.subplots(figsize=(8,4))
        ax2.plot(range(hold_days+1),
                 prob_g*100, color="green",
                 linewidth=2.5)
        ax2.fill_between(range(hold_days+1),
            prob_g*100, 50,
            where=[p>50 for p in prob_g],
            alpha=0.3, color="green",
            label="Profit zone")
        ax2.fill_between(range(hold_days+1),
            prob_g*100, 50,
            where=[p<=50 for p in prob_g],
            alpha=0.3, color="red",
            label="Loss zone")
        ax2.axvline(opt_day, color="yellow",
                    linewidth=2.5, linestyle="--",
                    label=f"Optimal: Day {opt_day}")
        ax2.axhline(50, color="white",
                    linewidth=1, linestyle=":")
        ax2.set_title("Probability of Profit Over Time")
        ax2.set_xlabel("Trading Days")
        ax2.set_ylabel("Probability (%)")
        ax2.legend(fontsize=8)
        ax2.set_ylim(0,100)
        ax2.grid(True, alpha=0.2)
        st.pyplot(fig2); plt.close()

    # Scenarios
    st.subheader("Scenario Breakdown at Optimal Exit")
    s1,s2,s3,s4 = st.columns(4)
    for col,(label,pct) in zip([s1,s2,s3,s4],[
        ("Worst 5%",5),("Conservative 25%",25),
        ("Optimistic 75%",75),("Best 95%",95)]):
        v = np.percentile(paths[opt_day], pct)
        col.metric(label, f"₹{v:,.0f}",
            f"{((v-investment)/investment)*100:.1f}%")

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
        fig_s, ax_s = plt.subplots(figsize=(8, 4))
        ax_s.plot(sip_paths[:, :min(150, n_sip)], alpha=0.025,
                  color="steelblue", linewidth=0.5)
        ax_s.plot(sip_paths.mean(axis=1), color="orange", linewidth=2.5,
                  label="Expected corpus")
        ax_s.plot(invested_line, color="red", linewidth=2, linestyle="--",
                  label="Amount invested")
        ax_s.set_title(f"SIP Growth — {sip_years} Years")
        ax_s.set_xlabel("Trading Days")
        ax_s.set_ylabel("Value (₹)")
        ax_s.legend(fontsize=8)
        ax_s.grid(True, alpha=0.3)
        st.pyplot(fig_s)
        plt.close(fig_s)

    with col2:
        fig_s2, ax_s2 = plt.subplots(figsize=(8, 4))
        ax_s2.hist(final_sip, bins=60, color="steelblue",
                   edgecolor="white", alpha=0.8)
        ax_s2.axvline(total_invested, color="red", linewidth=2,
                      linestyle="--", label=f"Invested ₹{total_invested:,.0f}")
        ax_s2.axvline(expected_sip, color="green", linewidth=2.5,
                      label=f"Expected ₹{expected_sip:,.0f}")
        ax_s2.set_title("Final Corpus Distribution")
        ax_s2.set_xlabel("Final Value (₹)")
        ax_s2.legend(fontsize=8)
        ax_s2.grid(True, alpha=0.3)
        st.pyplot(fig_s2)
        plt.close(fig_s2)

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


# ── TAB 3: Fund Analysis ──
with tab3:
    st.subheader(f"📈 {selected_fund[:55]}")
    st.caption(
        "Historical NAV analysis. This page does not predict future NAV or investment returns."
    )

    @st.cache_data(ttl=86400)
    def resolve_mfapi_code(fund_name):
        """Find the mfapi.in scheme code using the actual fund name."""
        try:
            response = requests.get(
                "https://api.mfapi.in/mf/search",
                params={"q": fund_name},
                timeout=15
            )
            matches = response.json()
            if not matches:
                return None

            wanted = set(
                word for word in fund_name.lower().split()
                if word not in {"fund", "plan", "option", "growth"}
            )

            def score(match):
                candidate = match.get("schemeName", "").lower()
                candidate_words = set(candidate.split())
                return len(wanted.intersection(candidate_words))

            best = max(matches, key=score)
            return str(best.get("schemeCode")) if best.get("schemeCode") else None
        except Exception:
            return None

    @st.cache_data(ttl=3600)
    def get_live_nav_history(scheme_code):
        """Get NAV history only when a valid mfapi scheme code is found."""
        if not scheme_code:
            return None
        try:
            response = requests.get(
                f"https://api.mfapi.in/mf/{scheme_code}",
                timeout=15
            )
            payload = response.json()
            history = payload.get("data", [])

            if not history:
                return None

            nav_data = pd.DataFrame(history)
            nav_data["date"] = pd.to_datetime(
                nav_data["date"], dayfirst=True, errors="coerce"
            )
            nav_data["nav"] = pd.to_numeric(nav_data["nav"], errors="coerce")
            nav_data = nav_data.dropna().sort_values("date").reset_index(drop=True)

            return nav_data if len(nav_data) > 5 else None
        except Exception:
            return None

    scheme_code = resolve_mfapi_code(selected_fund)
    live_hist = get_live_nav_history(scheme_code)

    period_map = {
        "1M": 21, "3M": 63, "6M": 126, "1Y": 252,
        "2Y": 504, "3Y": 756, "5Y": 1260, "ALL": 100000
    }
    period = st.radio(
        "Period:", list(period_map.keys()),
        index=3, horizontal=True, key="tab3_period"
    )
    n_days = period_map[period]

    # Prefer live history. Use CSV only when live history is unavailable.
    if live_hist is not None:
        full_df = live_hist.rename(columns={"date": "Date", "nav": "NAV"})
        source_label = "📡 Live NAV history from AMFI / mfapi.in"
    else:
        full_df = fund_df[["Date", "NAV_Value"]].copy()
        full_df = full_df.rename(columns={"NAV_Value": "NAV"})
        source_label = "📁 Historical CSV — live NAV is currently unavailable"

    full_df = full_df.dropna().sort_values("Date").reset_index(drop=True)
    plot_df = full_df.tail(n_days) if n_days < len(full_df) else full_df.copy()

    latest_date = pd.Timestamp(full_df["Date"].iloc[-1])
    latest_nav = float(full_df["NAV"].iloc[-1])
    data_age_days = (pd.Timestamp.now().normalize() - latest_date.normalize()).days

    base_nav = float(plot_df["NAV"].iloc[0])
    percent_change = (plot_df["NAV"] / base_nav - 1) * 100
    daily_returns = full_df["NAV"].pct_change().dropna() * 100

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Latest NAV", f"₹{latest_nav:.2f}")
    m2.metric(f"{period} return", f"{percent_change.iloc[-1]:+.2f}%")
    m3.metric("NAV date", latest_date.strftime("%d %b %Y"))
    m4.metric("Data source", "Live" if live_hist is not None else "Historical CSV")

    if data_age_days > 7:
        st.warning(
            f"⚠️ The newest available NAV is {latest_date.strftime('%d %b %Y')} "
            f"({data_age_days} days old). The app is not showing today's NAV."
        )
    else:
        st.success(
            f"Latest available NAV date: {latest_date.strftime('%d %b %Y')}."
        )

    col1, col2 = st.columns([2, 1])

    with col1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=plot_df["Date"],
            y=percent_change,
            mode="lines",
            name="Historical NAV change",
            line=dict(color="#3f7cb8", width=2.5),
            hovertemplate=(
                "%{x|%d %b %Y}<br>"
                "<b>%{y:.2f}%</b><extra>Historical</extra>"
            )
        ))
        fig.add_hline(y=0, line_width=1, line_color="gray", opacity=0.5)
        fig.update_layout(
            title=f"Historical NAV Change — {period}",
            xaxis_title="Date",
            yaxis_title="% Change",
            height=430,
            hovermode="x unified",
            margin=dict(l=10, r=10, t=55, b=10),
        )
        fig.update_xaxes(
            tickformat="%d %b %Y",
            showgrid=True,
            gridcolor="rgba(128,128,128,0.15)",
            rangeslider_visible=True,
        )
        fig.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.15)")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.caption(source_label)

    with col2:
        fig_hist = go.Figure()
        fig_hist.add_trace(go.Histogram(
            x=daily_returns,
            nbinsx=60,
            marker_color="coral",
            opacity=0.85,
            name="Daily returns"
        ))
        if len(daily_returns):
            fig_hist.add_vline(
                x=float(daily_returns.mean()),
                line_width=2,
                line_color="green",
                annotation_text=f"Mean: {daily_returns.mean():.3f}%"
            )
        fig_hist.update_layout(
            title="Historical Daily Returns",
            xaxis_title="Daily return %",
            yaxis_title="Count",
            height=430,
            margin=dict(l=10, r=10, t=55, b=10),
        )
        st.plotly_chart(
            fig_hist, use_container_width=True,
            config={"displayModeBar": False}
        )

    st.info(
        "The chart shows historical NAV movement only. "
        "Future-return predictions are disabled because the model did not "
        "show reliable out-of-sample accuracy."
    )


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

# ── TAB 5: Compare Funds — Live % Change + Forecast ──
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

    if 1 <= len(compare_list) <= 15:
        cdata = []
        fig6, ax6 = plt.subplots(figsize=(13,5))
        cmap = plt.cm.tab10(np.linspace(0,1,10))

        for idx, fund in enumerate(compare_list):
            full_fdf = df[df["Scheme_Name"]==fund].sort_values("Date")
            fdf = full_fdf.tail(n_days) if n_days < len(full_fdf) else full_fdf
            if len(fdf) < 5:
                continue

            base_nav = fdf["NAV_Value"].iloc[0]
            dates  = list(fdf["Date"])
            values = list((fdf["NAV_Value"]/base_nav - 1)*100)

            # attach LIVE AMFI NAV so the line reaches today
            fund_words = set(str(fund).lower().split()) if pd.notna(fund) else set()
            best_match, best_score = None, 0
            for amfi_name in nav_today:
                score = len(fund_words & set(amfi_name.lower().split()))
                if score > best_score:
                    best_score, best_match = score, amfi_name
            if best_match and best_score >= 2:
                live_val = (nav_today[best_match]["nav"]/base_nav - 1)*100
                dates.append(pd.Timestamp(datetime.now(IST).date()))
                values.append(live_val)

            color = cmap[idx % 10]
            ax6.plot(dates, values, label=f"{fund[:28]}",
                     linewidth=1.8, color=color)

            if show_forecast:
                rets = fdf["Daily_Return_%"].dropna().tail(90)
                mu   = rets.mean() if len(rets) > 0 else 0
                last_val, last_date = values[-1], dates[-1]
                fut_dates = pd.bdate_range(
                    last_date + pd.Timedelta(days=1), periods=forecast_days)
                fut_vals = [last_val + mu*(i+1) for i in range(forecast_days)]
                ax6.plot([last_date]+list(fut_dates), [last_val]+fut_vals,
                         linestyle="--", linewidth=1.8, color=color, alpha=0.55)

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

        ax6.axhline(0, color="black", linewidth=0.8, alpha=0.4)
        title = f"% Change — {period}"
        if show_forecast:
            title += "  (solid = actual · dashed = forecast)"
        ax6.set_title(title)
        ax6.set_xlabel("Date")
        ax6.set_ylabel("% Change")
        ax6.legend(fontsize=8, ncol=2)
        ax6.grid(True, alpha=0.3)
        plt.tight_layout()
        st.pyplot(fig6); plt.close()

        st.dataframe(pd.DataFrame(cdata),
                     use_container_width=True,
                     hide_index=True)
        if show_forecast:
            st.caption(
                "Forecast = straight-line trend using each fund's average "
                "daily return over its last 90 trading days. Not a "
                "guarantee of future performance.")
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
