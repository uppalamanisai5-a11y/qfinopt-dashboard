import pickle

import numpy as np
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Q-FinOpt Dashboard",
    page_icon="📈",
    layout="centered",
)


@st.cache_resource
def load_model_bundle():
    with open("live_nav_fund_model.pkl", "rb") as file:
        return pickle.load(file)


@st.cache_data(ttl=3600)
def get_live_nav_history(scheme_code):
    response = requests.get(
        f"https://api.mfapi.in/mf/{scheme_code}",
        timeout=30,
    )
    response.raise_for_status()

    data = response.json().get("data", [])

    if not data:
        raise ValueError("No NAV history was returned by mfapi.")

    df = pd.DataFrame(data)
    df["Date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df["NAV"] = pd.to_numeric(df["nav"], errors="coerce")

    df = (
        df[["Date", "NAV"]]
        .dropna()
        .query("NAV > 0")
        .sort_values("Date")
        .drop_duplicates("Date")
        .reset_index(drop=True)
    )

    return df


def create_features(df):
    df = df.copy()

    df["Return_1D"] = df["NAV"].pct_change()

    for lag in [1, 2, 3, 5, 10, 21]:
        df[f"Return_Lag_{lag}"] = df["Return_1D"].shift(lag)

    for window in [5, 10, 21, 63]:
        df[f"Momentum_{window}D"] = df["NAV"] / df["NAV"].shift(window) - 1
        df[f"Volatility_{window}D"] = df["Return_1D"].rolling(window).std()

    df["MA_21"] = df["NAV"].rolling(21).mean()
    df["NAV_vs_MA21"] = df["NAV"] / df["MA_21"] - 1

    df["High_63"] = df["NAV"].rolling(63).max()
    df["Drawdown_63"] = df["NAV"] / df["High_63"] - 1

    df["Month_Sin"] = np.sin(2 * np.pi * df["Date"].dt.month / 12)
    df["Month_Cos"] = np.cos(2 * np.pi * df["Date"].dt.month / 12)

    return df.replace([np.inf, -np.inf], np.nan)


try:
    model_data = load_model_bundle()

    fund_name = model_data["fund_name"]
    scheme_code = str(model_data["scheme_code"])
    model = model_data["model"]
    features = model_data["features"]
    horizon = model_data["horizon_days"]

    st.title("📈 Q-FinOpt Dashboard")
    st.caption("Live NAV forecast for a mutual fund")

    st.subheader(fund_name)
    st.write(f"**Scheme code:** {scheme_code}")

    with st.spinner("Getting the latest NAV data..."):
        nav_df = get_live_nav_history(scheme_code)
        featured_df = create_features(nav_df)

    latest_data = featured_df.dropna(subset=features)

    if latest_data.empty:
        st.error("Not enough valid NAV data is available to make a prediction.")
        st.stop()

    latest_row = latest_data.iloc[[-1]]
    latest_nav = float(latest_row["NAV"].iloc[0])
    latest_date = latest_row["Date"].iloc[0]

    predicted_return = float(model.predict(latest_row[features])[0])
    predicted_nav = latest_nav * (1 + predicted_return)

    future_date = pd.bdate_range(
        latest_date + pd.Timedelta(days=1),
        periods=horizon,
    )[-1]

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Current NAV",
        f"₹{latest_nav:.2f}",
        f"As of {latest_date.date()}",
    )

    col2.metric(
        f"Predicted {horizon}-day return",
        f"{predicted_return * 100:+.2f}%",
    )

    col3.metric(
        f"Estimated NAV ({future_date.date()})",
        f"₹{predicted_nav:.2f}",
    )

    st.divider()

    st.subheader("Model validation")

    test_mae = model_data["test_mae_pct"]
    no_change_mae = model_data["zero_baseline_mae_pct"]
    average_mae = model_data["mean_baseline_mae_pct"]
    test_r2 = model_data["test_r2"]

    validation_col1, validation_col2, validation_col3 = st.columns(3)

    validation_col1.metric("Model MAE", f"{test_mae:.2f}%")
    validation_col2.metric("No-change MAE", f"{no_change_mae:.2f}%")
    validation_col3.metric("R² score", f"{test_r2:.4f}")

    if model_data["reliable_vs_baselines"]:
        st.success("The model performed better than its simple validation baselines.")
    else:
        st.warning("The model did not outperform all validation baselines.")

    st.divider()

    st.subheader("NAV history")
    chart_df = nav_df.tail(252).set_index("Date")[["NAV"]]
    st.line_chart(chart_df)

    st.caption(
        "This dashboard is for educational purposes only. "
        "Predictions are estimates and are not investment advice."
    )

except FileNotFoundError:
    st.error(
        "Model file not found. Upload `live_nav_fund_model.pkl` "
        "to the same GitHub folder as `app.py`."
    )

except requests.RequestException:
    st.error("Could not retrieve live NAV data from mfapi. Please try again shortly.")

except Exception as error:
    st.error(f"Dashboard error: {error}")
