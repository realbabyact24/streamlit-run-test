import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from openai import OpenAI
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import time
import requests
import json
import hashlib

# ====================== LOAD KEYS ======================
api_key = os.getenv("XAI_API_KEY")
access_key = os.getenv("APP_ACCESS_KEY")
x_bearer = os.getenv("X_BEARER_TOKEN")

if not api_key or not access_key:
    st.error("Missing keys in .env file")
    st.stop()

client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
MODEL = "grok-2-latest"

# ====================== FILES ======================
UNLOCK_FILE = "app_unlocked.flag"
ATTEMPTS_FILE = "login_attempts.json"
USERS_FILE = "users.json"
TRADES_FILE = "trades.json"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_json(file, default):
    if os.path.exists(file):
        try:
            with open(file, "r") as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

# ====================== THEME ======================
st.markdown("""
<style>
    .stApp { background-color: #1a1226; color: #ffffff; }
    section[data-testid="stSidebar"] { background-color: #231833 !important; border-right: 1px solid #ff2d95; }
    h1, h2, h3 { color: #ff4da6 !important; }
    div[data-testid="stMetric"] { background-color: #2b1f3d; border: 1px solid #ff2d95; border-radius: 12px; padding: 10px; }
    .stButton > button { background-color: #ff2d95; color: white; border-radius: 8px; font-weight: 600; }
    .stButton > button:hover { background-color: #ff4da6; color: white; }
</style>
""", unsafe_allow_html=True)

# ====================== APP UNLOCK + SECURITY ======================
def load_attempts():
    return load_json(ATTEMPTS_FILE, {"failed": 0, "lock_until": None})

def save_attempts(data):
    save_json(ATTEMPTS_FILE, data)

def is_temporarily_locked():
    data = load_attempts()
    if data.get("lock_until"):
        lock_until = datetime.fromisoformat(data["lock_until"])
        if datetime.now() < lock_until:
            remaining = lock_until - datetime.now()
            return True, f"{int(remaining.total_seconds()//60)}m {int(remaining.total_seconds()%60)}s"
        else:
            data["failed"] = 0
            data["lock_until"] = None
            save_attempts(data)
    return False, None

if not os.path.exists(UNLOCK_FILE):
    st.title("🔒 AI Trading Terminal")
    locked, remaining = is_temporarily_locked()
    if locked:
        st.error(f"Too many failed attempts. Try again in {remaining}")
        st.stop()

    key = st.text_input("Main Access Key", type="password")
    if st.button("Unlock App"):
        data = load_attempts()
        if key == access_key:
            open(UNLOCK_FILE, "w").write(str(datetime.now()))
            data["failed"] = 0
            data["lock_until"] = None
            save_attempts(data)
            st.success("App unlocked!")
            time.sleep(1)
            st.rerun()
        else:
            data["failed"] = data.get("failed", 0) + 1
            if data["failed"] >= 5:
                data["lock_until"] = (datetime.now() + timedelta(minutes=10)).isoformat()
                st.error("Locked for 10 minutes")
            else:
                st.error(f"Wrong key. Attempts left: {5 - data['failed']}")
            save_attempts(data)
            time.sleep(1.2)
            st.rerun()
    st.stop()

# ====================== USER SYSTEM ======================
users = load_json(USERS_FILE, {})
trades = load_json(TRADES_FILE, {})

if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None

if st.session_state.logged_in_user is None:
    st.title("👤 Account")
    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            if username in users and users[username]["password"] == hash_password(password):
                st.session_state.logged_in_user = username
                st.success(f"Welcome {username}!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Wrong username or password")

    with tab_register:
        new_user = st.text_input("New Username", key="reg_user")
        new_pass = st.text_input("New Password", type="password", key="reg_pass")
        if st.button("Create Account"):
            if new_user in users:
                st.error("Username already taken")
            elif len(new_user) < 3 or len(new_pass) < 4:
                st.error("Username min 3 characters, Password min 4")
            else:
                users[new_user] = {
                    "password": hash_password(new_pass),
                    "email": "",
                    "agreed_to_terms": False,
                    "created": str(datetime.now())
                }
                save_json(USERS_FILE, users)
                trades[new_user] = []
                save_json(TRADES_FILE, trades)
                st.success("Account created! Please login.")
    st.stop()

# ====================== TERMS OF SERVICE ======================
current_user = st.session_state.logged_in_user
if not users.get(current_user, {}).get("agreed_to_terms", False):
    st.title("📜 Terms of Service")
    st.markdown("""
    ### Community Rules

    This app is made for **community fun, learning, and sharing**.

    - There is **no real competition**
    - No arguments or toxic behavior are allowed
    - Everything here is for entertainment and educational purposes only
    - Nothing in this app is financial advice
    - You are fully responsible for your own decisions
    - Be respectful to other users

    By continuing you agree to keep this space positive and friendly.
    """)
    agreed = st.checkbox("I have read and agree to the Terms of Service")
    if st.button("Continue"):
        if agreed:
            users[current_user]["agreed_to_terms"] = True
            save_json(USERS_FILE, users)
            st.success("Thank you!")
            time.sleep(1)
            st.rerun()
        else:
            st.warning("You must agree to continue")
    st.stop()

# ====================== MAIN APP ======================
st.set_page_config(page_title="AI Trading Terminal", page_icon="📈", layout="wide")
st.title(f"📈 AI Trading Terminal — {current_user}")

with st.sidebar:
    st.header(f"👤 {current_user}")
    if st.button("Logout"):
        st.session_state.logged_in_user = None
        st.rerun()
    if st.button("🔒 Lock App"):
        if os.path.exists(UNLOCK_FILE):
            os.remove(UNLOCK_FILE)
        st.session_state.logged_in_user = None
        st.rerun()

    st.markdown("---")
    symbol = st.text_input("Chart Symbol", value="MNQ=F")
    timeframe = st.selectbox("Timeframe", ["1m", "5m", "15m", "30m", "1h", "1d"], index=1)
    refresh_sec = st.slider("Refresh (sec)", 60, 180, 90)

    st.markdown("---")
    st.subheader("Settings")
    new_email = st.text_input("Add/Update Email", value=users[current_user].get("email", ""))
    if st.button("Save Email"):
        users[current_user]["email"] = new_email
        save_json(USERS_FILE, users)
        st.success("Email saved")

# ====================== TABS ======================
tab1, tab2, tab3, tab4 = st.tabs(["📊 Chart + Tweets", "📝 Log Trade", "🏆 Ranking", "🤖 Grok Tips"])

with tab1:
    left, right = st.columns([2.2, 1])
    with left:
        st.subheader(f"{symbol} • {timeframe}")
        try:
            period = "1d" if timeframe in ["1m", "5m"] else "5d"
            df = yf.download(symbol, period=period, interval=timeframe, progress=False, auto_adjust=True)
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df = df.tail(100)
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25], vertical_spacing=0.02)
                fig.add_trace(go.Candlestick(x=df.index, open=df.Open, high=df.High, low=df.Low, close=df.Close,
                                             increasing_line_color="#ff4da6", decreasing_line_color="#c2185b"), row=1, col=1)
                colors = ["#ff4da6" if c >= o else "#c2185b" for o, c in zip(df.Open, df.Close)]
                fig.add_trace(go.Bar(x=df.index, y=df.Volume, marker_color=colors), row=2, col=1)
                fig.update_layout(height=560, template="plotly_dark", paper_bgcolor="#1a1226", plot_bgcolor="#1a1226",
                                  xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=20,b=0), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
        except:
            st.warning("Could not load chart")

    with right:
        st.subheader("🐦 Tweets")
        if x_bearer:
            for acc in ["DeItaone", "unusual_whales", "FirstSquawk"]:
                with st.expander(f"@{acc}", expanded=True):
                    try:
                        r = requests.get("https://api.twitter.com/2/tweets/search/recent",
                            headers={"Authorization": f"Bearer {x_bearer}"},
                            params={"query": f"from:{acc} -is:retweet", "max_results": 3, "tweet.fields": "created_at,text"},
                            timeout=6)
                        for t in r.json().get("data", []):
                            st.caption(t["created_at"][:16].replace("T", " "))
                            st.write(t["text"][:150])
                            st.markdown("---")
                    except:
                        st.write("No tweets")
        else:
            st.info("Add X_BEARER_TOKEN for tweets")

with tab2:
    st.subheader("📝 Log a Trade")
    with st.form("trade_form"):
        t_symbol = st.text_input("Symbol", value="AAPL")
        c1, c2 = st.columns(2)
        entry = c1.number_input("Entry Price", min_value=0.0, format="%.4f")
        exit_p = c2.number_input("Exit Price", min_value=0.0, format="%.4f")
        notes = st.text_area("Notes")
        if st.form_submit_button("Save Trade") and entry > 0 and exit_p > 0:
            profit = round(exit_p - entry, 4)
            trade = {"symbol": t_symbol.upper(), "entry": entry, "exit": exit_p, "profit": profit, "notes": notes, "time": str(datetime.now())}
            if current_user not in trades:
                trades[current_user] = []
            trades[current_user].append(trade)
            save_json(TRADES_FILE, trades)
            st.success(f"Trade saved! Profit: {profit}")

    user_trades = trades.get(current_user, [])
    if user_trades:
        st.dataframe(pd.DataFrame(user_trades), use_container_width=True)
        st.metric("Your Total Profit", f"{sum(t['profit'] for t in user_trades):.4f}")

with tab3:
    st.subheader("🏆 Leaderboard")
    ranking = []
    for user, tlist in trades.items():
        if tlist:
            ranking.append({
                "Username": user,
                "Total Profit": round(sum(t["profit"] for t in tlist), 4),
                "Trades": len(tlist)
            })
    if ranking:
        df_rank = pd.DataFrame(ranking).sort_values("Total Profit", ascending=False).reset_index(drop=True)
        df_rank.index += 1
        st.dataframe(df_rank, use_container_width=True)
    else:
        st.info("No trades yet")

with tab4:
    st.subheader("🤖 Grok Tips")
    if st.button("Get Tips"):
        try:
            res = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": f"Give clear BUY/SELL/HOLD advice for {symbol} on {timeframe}."}],
                temperature=0.3
            )
            st.markdown(res.choices[0].message.content)
        except Exception as e:
            st.error(str(e))

# ====================== FOOTER ======================
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #ff4da6; font-size: 14px; padding: 10px;'>"
    "This is all fun and community sharing • Not financial advice"
    "</div>",
    unsafe_allow_html=True
)

time.sleep(refresh_sec)
st.rerun()
