import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Bollinger Stretch Check", page_icon="📈", layout="centered")


def compute(close: pd.Series, length: int, mult: float) -> pd.DataFrame:
    """Bollinger Bands with population std dev (ddof=0), as Bollinger specifies."""
    mid = close.rolling(length).mean()
    sd = close.rolling(length).std(ddof=0)
    df = pd.DataFrame({"close": close, "mid": mid})
    df["upper"] = mid + mult * sd
    df["lower"] = mid - mult * sd
    df["pb"] = (close - df["lower"]) / (df["upper"] - df["lower"])
    df["bw"] = (df["upper"] - df["lower"]) / mid
    return df.dropna()


def status(pb: float, near_hi: float, near_lo: float):
    if pb > 1.0:
        return "Overstretched: above upper band", "red"
    if pb > near_hi:
        return "Extended: near upper band", "orange"
    if pb < 0.0:
        return "Oversold: below lower band", "green"
    if pb < near_lo:
        return "Stretched low: near lower band", "blue"
    return "Normal range", "gray"


@st.cache_data(ttl=900, show_spinner=False)
def load(ticker: str) -> pd.Series:
    hist = yf.Ticker(ticker).history(period="2y", interval="1d", auto_adjust=False)
    return hist["Close"] if not hist.empty else pd.Series(dtype=float)


def chart(df: pd.DataFrame, ticker: str, days: int) -> go.Figure:
    d = df.tail(days)
    fig = go.Figure()
    fig.add_scatter(x=d.index, y=d["upper"], name="Upper", line=dict(width=1, color="#4c78d8"))
    fig.add_scatter(x=d.index, y=d["lower"], name="Lower", line=dict(width=1, color="#4c78d8"),
                    fill="tonexty", fillcolor="rgba(76,120,216,0.12)")
    fig.add_scatter(x=d.index, y=d["mid"], name="Middle (SMA)", line=dict(width=1, dash="dash", color="#888"))
    fig.add_scatter(x=d.index, y=d["close"], name="Close", line=dict(width=2, color="#e8ecf2"))
    fig.update_layout(title=ticker, height=380, margin=dict(l=10, r=10, t=40, b=10),
                      legend=dict(orientation="h", y=-0.15), hovermode="x unified")
    return fig


st.title("Bollinger Stretch Check")
st.caption("Enter tickers to see whether each is stretched, with the band levels. Information only, not financial advice.")

with st.sidebar:
    st.header("Settings")
    length = st.number_input("Period", 2, 200, 20)
    mult = st.number_input("Std deviations", 0.5, 5.0, 2.0, step=0.1)
    near_hi = st.slider("Extended above %B", 0.5, 1.0, 0.8, 0.05)
    near_lo = st.slider("Stretched low below %B", 0.0, 0.5, 0.2, 0.05)
    days = st.slider("Chart days", 30, 250, 90, 10)

raw = st.text_input("Tickers (comma or space separated)", value="DELL")
tickers = [t.strip().upper() for t in raw.replace(",", " ").split() if t.strip()]

for t in tickers:
    with st.spinner(f"Loading {t}..."):
        try:
            close = load(t)
        except Exception as e:
            st.error(f"{t}: could not fetch data ({e})")
            continue
    if len(close) < length + 5:
        st.warning(f"{t}: not enough data. Check the ticker symbol.")
        continue

    df = compute(close, int(length), float(mult))
    last, prev = df.iloc[-1], df.iloc[-2]
    label, color = status(last["pb"], near_hi, near_lo)

    st.subheader(f"{t}  ·  :{color}[{label}]")
    st.caption(f"As of {df.index[-1].date()}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Close", f"{last['close']:.2f}")
    c2.metric("Upper (resistance)", f"{last['upper']:.2f}")
    c3.metric("Middle (mean)", f"{last['mid']:.2f}", f"{(last['mid'] / last['close'] - 1) * 100:+.1f}% from close", delta_color="off")
    c4.metric("Lower (support)", f"{last['lower']:.2f}")

    rank = (df["bw"].tail(120) <= last["bw"]).mean() * 100
    st.write(f"**%B:** {last['pb']:.2f}  |  **Bandwidth:** {last['bw'] * 100:.1f}% (rank {rank:.0f}% of last 120 days)")

    if prev["close"] > prev["upper"] and last["close"] <= last["upper"]:
        st.warning("Closed back inside the upper band after a close above it. This is the usual first exhaustion warning.")
    if prev["close"] < prev["lower"] and last["close"] >= last["lower"]:
        st.info("Closed back inside the lower band after a close below it. This is the usual first bounce sign.")
    if rank <= 20:
        st.info(f"Squeeze: bandwidth is in the lowest {rank:.0f}% of the last 120 days. A large move often follows.")
    elif rank >= 80:
        st.info(f"High volatility: bandwidth is in the top {100 - rank:.0f}% of the last 120 days.")

    st.plotly_chart(chart(df, t, int(days)), use_container_width=True)
    st.divider()