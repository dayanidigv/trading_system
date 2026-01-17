"""
Complete End-to-End Trade Analysis & Paper Trading System
Main Streamlit Application

Design: Manual execution, forward-only testing, data-driven learning
Philosophy: Operate, observe, do not touch (until 30+ trades)
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from typing import List, Dict

# Import our engines
from analysis_engine import (
    analyze_stock, AnalysisResult,
    MarketState, FundamentalState, TrendState,
    EntryState, RSState, Behavior
)
from paper_trade_engine import (
    PaperTradeEngine, TradeConfig, PaperTrade,
    TradeStatus, TradeOutcome, ExitReason
)
from storage_manager import (
    StorageManager, analysis_result_to_log_entry
)


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

# Default stock universe (Indian large-cap, institutionally traded)
DEFAULT_UNIVERSE = [
    # Energy / Commodities
    "RELIANCE.NS", "ONGC.NS", "COALINDIA.NS",

    # IT Services
    "TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS",

    # Banking & Financials
    "HDFCBANK.NS", "ICICIBANK.NS", "AXISBANK.NS", "KOTAKBANK.NS",
    "SBIN.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS",

    # FMCG / Consumer
    "ITC.NS", "HINDUNILVR.NS", "NESTLEIND.NS", "DABUR.NS",

    # Infra / Capital Goods
    "LT.NS", "ULTRACEMCO.NS", "GRASIM.NS",

    # Auto
    "MARUTI.NS", "TATAMOTORS.NS", "M&M.NS",

    # Pharma / Healthcare
    "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS",

    # Telecom / Tech-adjacent
    "BHARTIARTL.NS",

    # Consumer discretionary
    "TITAN.NS", "ASIANPAINT.NS"
]


BENCHMARK_INDEX = "^NSEI"  # NIFTY 50


# ═══════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def load_stock_data(symbol: str, period: str = "6mo") -> pd.DataFrame:
    """Load stock price data"""
    try:
        df = yf.download(symbol, period=period, interval="1d", auto_adjust=True, progress=False)
        
        if df.empty:
            return None
        
        # Handle MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        
        df.columns = [col if isinstance(col, str) else col[0] for col in df.columns]
        
        return df
    except Exception as e:
        st.error(f"Error loading {symbol}: {e}")
        return None


@st.cache_data(ttl=3600)
def load_index_data(symbol: str = BENCHMARK_INDEX) -> pd.DataFrame:
    """Load benchmark index data"""
    return load_stock_data(symbol)


# ═══════════════════════════════════════════════════════════════════════════
# STREAMLIT APP
# ═══════════════════════════════════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title="Trade Analysis & Paper Trading System",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    if 'storage' not in st.session_state:
        st.session_state.storage = StorageManager(use_drive=False)
    
    if 'engine' not in st.session_state:
        st.session_state.engine = PaperTradeEngine(TradeConfig())
        # Load existing trades
        trades_df = st.session_state.storage.load_trades()
        if not trades_df.empty:
            st.session_state.engine.load_from_dataframe(trades_df)
    
    # Sidebar navigation
    st.sidebar.title("📊 Trading System")
    page = st.sidebar.radio(
        "Navigation",
        ["Daily Analysis", "Paper Trades", "Analytics Dashboard", "Settings"]
    )
    
    if page == "Daily Analysis":
        show_daily_analysis()
    elif page == "Paper Trades":
        show_paper_trades()
    elif page == "Analytics Dashboard":
        show_analytics()
    elif page == "Settings":
        show_settings()


# ═══════════════════════════════════════════════════════════════════════════
# PAGE: DAILY ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════

def show_daily_analysis():
    st.title("📈 Daily Market Analysis")
    st.caption("Analyze stocks and execute paper trades")
    
    # Load index data
    index_df = load_index_data()
    
    if index_df is None:
        st.error("Failed to load index data. Cannot proceed with analysis.")
        return
    
    # Market State
    from analysis_engine import analyze_market_state
    market_state = analyze_market_state(index_df)
    
    st.markdown(f"### Market State: **{market_state.value}**")
    st.caption(f"Based on NIFTY 50 vs EMA50")
    
    # Stock selection
    st.markdown("---")
    st.subheader("Stock Universe")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        selected_stocks = st.multiselect(
            "Select stocks to analyze",
            DEFAULT_UNIVERSE,
            default=DEFAULT_UNIVERSE[:5]
        )
    
    with col2:
        if st.button("🔍 Analyze All", use_container_width=True):
            analyze_universe(selected_stocks, index_df, market_state)
    
    # Individual stock analysis
    st.markdown("---")
    st.subheader("Detailed Stock Analysis")
    
    stock_to_analyze = st.selectbox("Select stock for detailed view", selected_stocks if selected_stocks else DEFAULT_UNIVERSE)
    
    if st.button("Analyze Stock"):
        analyze_single_stock(stock_to_analyze, index_df, market_state)


def analyze_universe(symbols: List[str], index_df: pd.DataFrame, market_state: MarketState):
    """Analyze multiple stocks and log results"""
    
    st.markdown("### Analysis Results")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    results = []
    analysis_log = []
    
    for i, symbol in enumerate(symbols):
        status_text.text(f"Analyzing {symbol}...")
        progress_bar.progress((i + 1) / len(symbols))
        
        # Load stock data
        stock_df = load_stock_data(symbol)
        
        if stock_df is None or len(stock_df) < 60:
            continue
        
        # Analyze
        result = analyze_stock(symbol, stock_df, index_df, fundamental_data=None)
        results.append(result)
        
        # Log analysis
        log_entry = analysis_result_to_log_entry(result)
        analysis_log.append(log_entry)
        
        # Check for new trade entry
        if result.trade_eligible:
            trade = st.session_state.engine.create_trade(result)
            if trade:
                st.success(f"✅ New paper trade created: {symbol}")
    
    status_text.text("Analysis complete!")
    progress_bar.empty()
    
    # Save analysis log
    if analysis_log:
        log_df = pd.DataFrame(analysis_log)
        st.session_state.storage.save_analysis_log(log_df)
    
    # Save trades
    trades_df = st.session_state.engine.to_dataframe(include_open=True)
    st.session_state.storage.save_trades(trades_df)
    
    # Display summary
    display_analysis_summary(results)


def analyze_single_stock(symbol: str, index_df: pd.DataFrame, market_state: MarketState):
    """Detailed analysis of single stock"""
    
    stock_df = load_stock_data(symbol)
    
    if stock_df is None or len(stock_df) < 60:
        st.error(f"Insufficient data for {symbol}")
        return
    
    # Analyze
    result = analyze_stock(symbol, stock_df, index_df, fundamental_data=None)
    
    # Display results
    st.markdown(f"## {symbol}")
    
    # State badges
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        color = {"STRONG": "green", "DEVELOPING": "orange", "ABSENT": "red"}[result.trend_state.value]
        st.markdown(f"<h3 style='color:{color};'>TREND: {result.trend_state.value}</h3>", unsafe_allow_html=True)
    
    with col2:
        color = {"OK": "green", "WAIT": "orange", "NO": "red", "N/A": "gray"}[result.entry_state.value]
        st.markdown(f"<h3 style='color:{color};'>ENTRY: {result.entry_state.value}</h3>", unsafe_allow_html=True)
    
    with col3:
        color = {"STRONG": "green", "NEUTRAL": "orange", "WEAK": "red", "N/A": "gray"}[result.rs_state.value]
        st.markdown(f"<h3 style='color:{color};'>RS: {result.rs_state.value}</h3>", unsafe_allow_html=True)
    
    with col4:
        color = {"CONTINUATION": "green", "EXPANSION": "#4FC3F7", "FAILURE": "#FF5252"}[result.behavior.value]
        st.markdown(f"<h3 style='color:{color};'>BEHAVIOR: {result.behavior.value}</h3>", unsafe_allow_html=True)
    
    st.caption(f"Fundamental: {result.fundamental_state.value} | Market: {market_state.value}")
    
    # Chart
    display_stock_chart(stock_df, result)
    
    # Conditions table
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Trend Conditions")
        trend_df = pd.DataFrame({
            "Condition": list(result.trend_conditions.keys()),
            "Status": ["✅" if v else "❌" for v in result.trend_conditions.values()]
        })
        st.dataframe(trend_df, hide_index=True, use_container_width=True)
    
    with col2:
        st.subheader("Entry Conditions")
        entry_df = pd.DataFrame({
            "Condition": list(result.entry_conditions.keys()),
            "Status": ["✅" if v else "❌" for v in result.entry_conditions.values()]
        })
        st.dataframe(entry_df, hide_index=True, use_container_width=True)
    
    # Trade eligibility
    if result.trade_eligible:
        st.success("✅ **TRADE ELIGIBLE** - All entry rules met")
        if st.button("Create Paper Trade"):
            trade = st.session_state.engine.create_trade(result)
            if trade:
                st.success(f"Paper trade created: {trade.trade_id}")
                # Save
                trades_df = st.session_state.engine.to_dataframe(include_open=True)
                st.session_state.storage.save_trades(trades_df)
    else:
        st.warning("❌ **NOT ELIGIBLE** - Entry rules not met")
        st.caption(f"Reasons: {', '.join(result.rejection_reasons)}")


def display_analysis_summary(results: List[AnalysisResult]):
    """Display summary table of all analyzed stocks"""
    
    st.markdown("### Summary")
    
    summary_data = []
    for r in results:
        summary_data.append({
            "Symbol": r.symbol,
            "Trend": r.trend_state.value,
            "Entry": r.entry_state.value,
            "RS": r.rs_state.value,
            "Behavior": r.behavior.value,
            "Eligible": "✅" if r.trade_eligible else "❌",
            "Close": f"₹{r.close:.2f}",
            "RSI": f"{r.rsi:.1f}",
        })
    
    df = pd.DataFrame(summary_data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def display_stock_chart(df: pd.DataFrame, result: AnalysisResult):
    """Display stock chart with EMAs"""
    
    fig = go.Figure()
    
    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name="OHLC",
        increasing_line_color='#00CC94',
        decreasing_line_color='#FF5252'
    ))
    
    # EMAs (calculate if not in df)
    if 'EMA20' not in df.columns:
        from analysis_engine import calculate_ema
        df['EMA20'] = calculate_ema(df['Close'], 20)
        df['EMA50'] = calculate_ema(df['Close'], 50)
    
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df['EMA20'],
        name="EMA 20",
        line=dict(color="cyan", width=2)
    ))
    
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df['EMA50'],
        name="EMA 50",
        line=dict(color="orange", width=2)
    ))
    
    fig.update_layout(
        height=500,
        xaxis_rangeslider_visible=False,
        template='plotly_dark'
    )
    
    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════
# PAGE: PAPER TRADES
# ═══════════════════════════════════════════════════════════════════════════

def show_paper_trades():
    st.title("📝 Paper Trades")
    
    engine = st.session_state.engine
    
    # Stats
    stats = engine.get_statistics()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Trades", stats['total_trades'])
    with col2:
        st.metric("Open Trades", stats['open_trades'])
    with col3:
        st.metric("Win Rate", f"{stats.get('win_rate', 0):.1f}%")
    with col4:
        st.metric("Total P&L", f"₹{stats.get('total_pnl', 0):.0f}")
    
    # Tabs
    tab1, tab2 = st.tabs(["Open Trades", "Closed Trades"])
    
    with tab1:
        display_open_trades()
    
    with tab2:
        display_closed_trades()


def display_open_trades():
    """Display and manage open trades"""
    
    engine = st.session_state.engine
    
    if not engine.open_trades:
        st.info("No open trades")
        return
    
    st.subheader("Open Positions")
    
    for trade in engine.open_trades:
        with st.expander(f"{trade.symbol} - Entered {trade.entry_date.date()}"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Entry Price", f"₹{trade.entry_price:.2f}")
                st.metric("Shares", trade.shares)
            
            with col2:
                st.metric("Stop Loss", f"₹{trade.stop_loss:.2f}")
                st.metric("Target", f"₹{trade.target:.2f}")
            
            with col3:
                st.metric("Holding Days", trade.holding_days)
                st.metric("MFE / MAE", f"{trade.mfe:.1f}% / {trade.mae:.1f}%")
            
            st.caption(f"Entry Context: {trade.trend_state} | {trade.entry_state} | {trade.rs_state} | {trade.behavior}")
            
            # Update trade button
            if st.button(f"Update {trade.symbol}", key=f"update_{trade.trade_id}"):
                update_trade_status(trade)


def update_trade_status(trade: PaperTrade):
    """Update open trade with current market data"""
    
    # Load current data
    stock_df = load_stock_data(trade.symbol, period="1mo")
    
    if stock_df is None or stock_df.empty:
        st.error(f"Failed to load data for {trade.symbol}")
        return
    
    # Get today's data
    latest = stock_df.iloc[-1]
    current_date = stock_df.index[-1]
    
    # Analyze current state
    index_df = load_index_data()
    result = analyze_stock(trade.symbol, stock_df, index_df)
    
    # Update trade
    closed_trade = st.session_state.engine.update_trade(
        trade,
        current_date,
        latest['Close'],
        latest['Low'],
        latest['High'],
        result.behavior.value
    )
    
    if closed_trade:
        st.success(f"Trade closed: {closed_trade.outcome.value} via {closed_trade.exit_reason.value}")
        
        # Save
        trades_df = st.session_state.engine.to_dataframe(include_open=True)
        st.session_state.storage.save_trades(trades_df)
    else:
        st.info("Trade still open")


def display_closed_trades():
    """Display closed trades"""
    
    engine = st.session_state.engine
    
    if not engine.closed_trades:
        st.info("No closed trades yet")
        return
    
    df = engine.to_dataframe(include_open=False)
    
    # Add visual indicators
    df['Outcome_Icon'] = df['outcome'].map({
        'WIN': '🟢',
        'LOSS': '🔴',
        'NO-MOVE': '⚪'
    })
    
    # Display table
    display_cols = [
        'Outcome_Icon', 'symbol', 'entry_date', 'exit_date',
        'entry_price', 'exit_price', 'pnl_pct', 'exit_reason',
        'holding_days', 'mfe', 'mae'
    ]
    
    st.dataframe(
        df[display_cols].sort_values('exit_date', ascending=False),
        use_container_width=True,
        hide_index=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# PAGE: ANALYTICS DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════

def show_analytics():
    st.title("📊 Analytics Dashboard")
    
    engine = st.session_state.engine
    
    if len(engine.closed_trades) < 5:
        st.warning("Not enough data for meaningful analytics (need ≥5 closed trades)")
        st.info(f"Current: {len(engine.closed_trades)} closed trades")
        return
    
    df = engine.to_dataframe(include_open=False)
    
    # Key metrics
    stats = engine.get_statistics()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Trades", stats['total_trades'])
    with col2:
        st.metric("Wins", stats['wins'])
    with col3:
        st.metric("Losses", stats['losses'])
    with col4:
        st.metric("No-Moves", stats['no_moves'])
    with col5:
        st.metric("Win Rate", f"{stats['win_rate']:.1f}%")
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        # Outcome distribution
        outcome_counts = df['outcome'].value_counts()
        fig = px.pie(
            values=outcome_counts.values,
            names=outcome_counts.index,
            title="Outcome Distribution"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Exit reason breakdown
        exit_counts = df['exit_reason'].value_counts()
        fig = px.bar(
            x=exit_counts.index,
            y=exit_counts.values,
            title="Exit Reasons"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # MFE vs MAE scatter
    fig = px.scatter(
        df,
        x='mae',
        y='mfe',
        color='outcome',
        title="MFE vs MAE (Max Favorable vs Max Adverse Excursion)",
        labels={'mae': 'MAE (%)', 'mfe': 'MFE (%)'}
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Holding period stats
    fig = px.histogram(
        df,
        x='holding_days',
        color='outcome',
        title="Holding Period Distribution"
    )
    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════
# PAGE: SETTINGS
# ═══════════════════════════════════════════════════════════════════════════

def show_settings():
    st.title("⚙️ Settings")
    
    st.subheader("Storage Information")
    
    info = st.session_state.storage.get_storage_info()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Total Trades Stored", info['total_trades'])
        st.metric("Open Trades", info['open_trades'])
        st.metric("Closed Trades", info['closed_trades'])
    
    with col2:
        st.metric("Analysis Log Entries", info['total_analyses'])
        st.caption(f"Trades file: {info['trades_file']}")
        st.caption(f"Log file: {info['analysis_log_file']}")
    
    st.markdown("---")
    
    st.subheader("System Rules (Locked)")
    
    st.info("""
    **Entry Rules:**
    - Fundamentals: PASS or NEUTRAL
    - Trend: STRONG
    - Entry: OK
    - RS: STRONG
    - Behavior: CONTINUATION
    
    **Exit Rules (Priority):**
    1. Stop Loss (-5%)
    2. Target (+10%)
    3. Behavior FAILURE
    4. Max Holding Days (10)
    
    **Discipline Lock:**
    No rule changes until ≥30 closed trades and ≥6-8 weeks
    """)


# ═══════════════════════════════════════════════════════════════════════════
# RUN APP
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()
