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
from pathlib import Path
import pytz
import os
import sys


# ═══════════════════════════════════════════════════════════════════════════
# IST TIMEZONE HANDLING (CRITICAL FOR CLOUD DEPLOYMENT)
# ═══════════════════════════════════════════════════════════════════════════

IST = pytz.timezone("Asia/Kolkata")

def ist_now():
    """Get current datetime in IST (timezone-aware)"""
    return datetime.now(IST)

def ist_today():
    """Get current date in IST"""
    return ist_now().date()

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
    "MARUTI.NS" "M&M.NS",

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
    """Load stock price data with retry logic"""
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            df = yf.download(symbol, period=period, interval="1d", auto_adjust=True, progress=False)
            
            if df.empty:
                if attempt < max_retries - 1:
                    print(f"⚠️ Empty data for {symbol}, retry {attempt + 1}/{max_retries}")
                    import time
                    time.sleep(retry_delay)
                    continue
                return None
            
            # Handle MultiIndex
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            
            df.columns = [col if isinstance(col, str) else col[0] for col in df.columns]
            
            print(f"✅ Loaded {len(df)} rows for {symbol}")
            return df
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️ Error loading {symbol} (attempt {attempt + 1}/{max_retries}): {e}")
                import time
                time.sleep(retry_delay)
            else:
                st.error(f"❌ Failed to load {symbol} after {max_retries} attempts: {e}")
                return None
    
    return None


@st.cache_data(ttl=3600)
def load_index_data(symbol: str = BENCHMARK_INDEX) -> pd.DataFrame:
    """Load benchmark index data with fallback"""
    print(f"📊 Loading index data: {symbol}")
    
    # Try primary symbol
    df = load_stock_data(symbol)
    
    if df is None or df.empty:
        # Fallback: Try alternate symbol format
        alt_symbol = "^NSEI" if symbol != "^NSEI" else "NIFTY50.NS"
        print(f"⚠️ Primary index failed, trying fallback: {alt_symbol}")
        df = load_stock_data(alt_symbol)
    
    if df is None or df.empty:
        st.error(f"""
        ❌ **Failed to load index data from Yahoo Finance**
        
        Possible reasons:
        - Network connectivity issues
        - Yahoo Finance API temporarily unavailable
        - Rate limiting
        
        **Solutions:**
        1. Wait 1-2 minutes and try again
        2. Check your internet connection
        3. Try clearing cache with "Force Reload Modules" button
        """)
    
    return df


# ═══════════════════════════════════════════════════════════════════════════
# STREAMLIT APP
# ═══════════════════════════════════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title="Trade Analysis & Paper Trading System",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS for better UI
    st.markdown("""
    <style>
    .big-metric {
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .status-badge {
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: 600;
        display: inline-block;
        font-size: 0.85rem;
    }
    .status-green { background: #00CC94; color: white; }
    .status-red { background: #FF5252; color: white; }
    .status-orange { background: #FF9800; color: white; }
    .status-blue { background: #4FC3F7; color: white; }
    .status-gray { background: #666; color: white; }
    .card {
        background: #1E1E1E;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #333;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'storage' not in st.session_state:
        # Always try Drive first - will auto-create token.json from env vars if available
        # Falls back to local storage if Drive connection fails
        st.session_state.storage = StorageManager(use_drive=True)
    
    if 'engine' not in st.session_state:
        st.session_state.engine = PaperTradeEngine(TradeConfig())
        # Load existing trades
        trades_df = st.session_state.storage.load_trades()
        if not trades_df.empty:
            st.session_state.engine.load_from_dataframe(trades_df)
        
        # Log engine version
        import paper_trade_engine
        print(f"📦 PaperTradeEngine loaded: v{paper_trade_engine.__version__}")
    
    # Sidebar navigation
    st.sidebar.markdown("""<h1 style='text-align: center; color: #00CC94;'>📊 Trading System</h1>""", unsafe_allow_html=True)
    st.sidebar.markdown("<p style='text-align: center; color: #888; font-size: 0.85rem;'>IST-aligned • Production Ready</p>", unsafe_allow_html=True)
    st.sidebar.markdown("---")
    
    page = st.sidebar.radio(
        "🧭 Navigation",
        ["Daily Analysis", "Paper Trades", "Analytics Dashboard", "Settings"],
        label_visibility="visible"
    )
    
    st.sidebar.markdown("---")
    
    # Quick stats in sidebar
    engine = st.session_state.engine
    stats = engine.get_statistics()
    
    st.sidebar.markdown("### 📈 Quick Stats")
    st.sidebar.metric("Total Trades", stats['total_trades'])
    st.sidebar.metric("Open Positions", stats['open_trades'])
    if stats['total_trades'] > 0:
        st.sidebar.metric("Win Rate", f"{stats.get('win_rate', 0):.1f}%")
    
    st.sidebar.markdown("---")
    
    # Storage status indicator
    storage = st.session_state.storage
    if storage.drive_available:
        st.sidebar.success(f"☁️ **Drive Connected**")
        st.sidebar.caption(f"📁 Folder: {storage.config.DRIVE_FOLDER_NAME}")
    else:
        st.sidebar.warning(f"💾 **Local Storage Only**")
        if storage.drive_error:
            st.sidebar.caption(f"⚠️ {storage.drive_error[:50]}...")
    
    st.sidebar.markdown("---")
    st.sidebar.caption(f"🕐 IST: {ist_now().strftime('%I:%M %p')}")
    st.sidebar.caption(f"📅 {ist_today().strftime('%d %b %Y')}")
    
    # Debug: Show module version
    import paper_trade_engine
    st.sidebar.caption(f"🔧 Engine v{paper_trade_engine.__version__}")
    
    # Force reload button for debugging
    if st.sidebar.button("🔄 Force Reload Modules", help="Clear cache and reload trade engine"):
        st.cache_data.clear()
        # Force reimport
        import importlib
        import sys
        if 'paper_trade_engine' in sys.modules:
            importlib.reload(sys.modules['paper_trade_engine'])
        if 'analysis_engine' in sys.modules:
            importlib.reload(sys.modules['analysis_engine'])
        # Reset engine
        if 'engine' in st.session_state:
            del st.session_state.engine
        st.success("✅ Modules reloaded! App will restart.")
        st.rerun()
    
    if page == "Daily Analysis":
        show_daily_analysis()
    elif page == "Paper Trades":
        show_paper_trades()
    elif page == "Analytics Dashboard":
        show_analytics()
    elif page == "Settings":
        # show_settings()
        show_fundamental_analysis_section()

# ═══════════════════════════════════════════════════════════════════════════
# PAGE: DAILY ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════

def show_daily_analysis():
    # Drive status warning
    if st.session_state.storage.use_drive and not st.session_state.storage.drive_available:
        st.warning("⚠️ **Google Drive not connected** - Data is being saved locally only. Check Settings for details.")
    
    # Header
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("📈 Daily Market Analysis")
        st.caption("End-of-day analysis • Forward-only testing • No hindsight bias")
    with col2:
        st.markdown(f"<div style='text-align: right; padding-top: 10px;'>"
                   f"<div style='color: #888; font-size: 0.8rem;'>IST Time</div>"
                   f"<div style='font-size: 1.2rem; font-weight: 600;'>{ist_now().strftime('%I:%M %p')}</div>"
                   f"<div style='color: #888; font-size: 0.85rem;'>{ist_today().strftime('%d %b %Y')}</div>"
                   f"</div>", unsafe_allow_html=True)
    
    # Load index data
    index_df = load_index_data()
    
    if index_df is None:
        st.error("❌ Failed to load index data. Cannot proceed with analysis.")
        return
    
    # Market State with enhanced visual
    from analysis_engine import analyze_market_state
    market_state = analyze_market_state(index_df)
    
    market_color = "#00CC94" if market_state.value == "RISK-ON" else "#FF5252" if market_state.value == "RISK-OFF" else "#888"
    st.markdown(f"""
    <div style='background: {market_color}22; padding: 15px; border-radius: 10px; border-left: 4px solid {market_color}; margin: 20px 0;'>
        <div style='font-size: 0.85rem; color: #888; text-transform: uppercase; letter-spacing: 1px;'>Market State</div>
        <div style='font-size: 1.8rem; font-weight: 700; color: {market_color}; margin-top: 5px;'>{market_state.value}</div>
        <div style='font-size: 0.85rem; color: #aaa; margin-top: 5px;'>Based on NIFTY 50 vs EMA50</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Stock selection with enhanced UI
    st.markdown("---")
    st.markdown("### 🎯 Stock Universe")
    st.caption(f"Select from {len(DEFAULT_UNIVERSE)} Indian large-cap stocks • Institutionally traded")
    
    # Quick preset selector
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        quick_select = st.selectbox(
            "Quick Presets",
            ["Custom Selection", "Top 5", "Top 10", "IT Sector", "Banking Sector", "All Stocks"]
        )
    
    with col2:
        # Apply preset
        if quick_select == "Top 5":
            default_selection = DEFAULT_UNIVERSE[:5]
        elif quick_select == "Top 10":
            default_selection = DEFAULT_UNIVERSE[:10]
        elif quick_select == "IT Sector":
            default_selection = [s for s in DEFAULT_UNIVERSE if s in ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"]]
        elif quick_select == "Banking Sector":
            default_selection = [s for s in DEFAULT_UNIVERSE if s in ["HDFCBANK.NS", "ICICIBANK.NS", "AXISBANK.NS", "KOTAKBANK.NS", "SBIN.NS"]]
        elif quick_select == "All Stocks":
            default_selection = DEFAULT_UNIVERSE
        else:
            default_selection = DEFAULT_UNIVERSE[:5]
        
        st.metric("Selected", len(default_selection))
    
    with col3:
        st.write("")  # Spacer
        analyze_clicked = st.button("🔍 Analyze", use_container_width=True, type="primary")
    
    # Stock multiselect (full width)
    selected_stocks = st.multiselect(
        "Customize selection (or use preset above)",
        DEFAULT_UNIVERSE,
        default=default_selection
    )
    
    # Execute analysis
    if analyze_clicked and selected_stocks:
        analyze_universe(selected_stocks, index_df, market_state)
    elif analyze_clicked and not selected_stocks:
        st.error("⚠️ Please select at least one stock to analyze")
    
    # Individual stock analysis
    st.markdown("---")
    st.subheader("Detailed Stock Analysis")
    
    stock_to_analyze = st.selectbox("Select stock for detailed view", selected_stocks if selected_stocks else DEFAULT_UNIVERSE)
    
    if st.button("Analyze Stock", key="analyze_single_btn"):
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
            try:
                # Show what we're attempting
                with st.spinner(f"Creating trade for {symbol}..."):
                    trade = st.session_state.engine.create_trade(result)
                
                if trade:
                    st.success(f"✅ New paper trade created: {symbol} (ID: {trade.trade_id})")
                    st.info(f"📊 Entry: ₹{trade.entry_price:.2f} | Stop: ₹{trade.stop_loss:.2f} | Target: ₹{trade.target:.2f}")
                else:
                    st.error(f"⚠️ {symbol} is trade eligible but create_trade returned None")
                    st.error("🔍 **This indicates a bug in create_trade() method**")
                    
                    # Show comprehensive debug info
                    st.markdown("### Debug Information")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Analysis Result:**")
                        st.write(f"- Symbol: {result.symbol}")
                        st.write(f"- Date: {result.date}")
                        st.write(f"- trade_eligible: {result.trade_eligible}")
                        st.write(f"- rejection_reasons: {result.rejection_reasons}")
                        st.write(f"- close: ₹{result.close:.2f}")
                    
                    with col2:
                        st.markdown("**Entry Criteria:**")
                        st.write(f"- Fundamental: {result.fundamental_state.value}")
                        st.write(f"- Trend: {result.trend_state.value}")
                        st.write(f"- Entry: {result.entry_state.value}")
                        st.write(f"- RS: {result.rs_state.value}")
                        st.write(f"- Behavior: {result.behavior.value}")
                    
                    st.markdown("**Engine State:**")
                    st.write(f"- Open trades: {len(st.session_state.engine.open_trades)}")
                    st.write(f"- Closed trades: {len(st.session_state.engine.closed_trades)}")
                    
                    st.warning("⚠️ Check Streamlit logs/terminal for detailed error messages with 🔍 emoji")
                    
            except Exception as e:
                st.error(f"❌ Error creating trade for {symbol}: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
    
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
    
    # Diagnostic: Show rejection reasons
    if results:
        with st.expander("🔧 Diagnostic: Rejection Breakdown"):
            rejection_summary = {}
            for r in results:
                if not r.trade_eligible and r.rejection_reasons:
                    for reason in r.rejection_reasons:
                        rejection_summary[reason] = rejection_summary.get(reason, 0) + 1
            
            if rejection_summary:
                st.markdown("**Most common rejection reasons:**")
                rejection_df = pd.DataFrame([
                    {"Rejection Reason": k, "Count": v, "% of Total": f"{(v/len(results)*100):.1f}%"}
                    for k, v in sorted(rejection_summary.items(), key=lambda x: x[1], reverse=True)
                ])
                st.dataframe(rejection_df, use_container_width=True, hide_index=True)
            else:
                st.success("No rejections - all stocks passed!")


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
    
    # State badges with modern card design
    col1, col2, col3, col4 = st.columns(4)
    
    states_config = [
        ("TREND", result.trend_state.value, {"STRONG": "#00CC94", "DEVELOPING": "#FF9800", "ABSENT": "#FF5252"}),
        ("ENTRY", result.entry_state.value, {"OK": "#00CC94", "WAIT": "#FF9800", "NO": "#FF5252", "N/A": "#666"}),
        ("RS", result.rs_state.value, {"STRONG": "#00CC94", "NEUTRAL": "#FF9800", "WEAK": "#FF5252", "N/A": "#666"}),
        ("BEHAVIOR", result.behavior.value, {"CONTINUATION": "#00CC94", "EXPANSION": "#4FC3F7", "FAILURE": "#FF5252"}),
    ]
    
    for col, (label, value, color_map) in zip([col1, col2, col3, col4], states_config):
        color = color_map.get(value, "#666")
        with col:
            st.markdown(f"""
            <div class='card' style='text-align: center; border-left: 4px solid {color};'>
                <div style='font-size: 0.75rem; color: #888; text-transform: uppercase; letter-spacing: 1px;'>{label}</div>
                <div style='font-size: 1.4rem; font-weight: 700; color: {color}; margin-top: 8px;'>{value}</div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Fundamental and Market context
    fund_color = {"PASS": "#00CC94", "NEUTRAL": "#FF9800", "FAIL": "#FF5252"}.get(result.fundamental_state.value, "#666")
    mkt_color = "#00CC94" if market_state.value == "RISK-ON" else "#FF5252" if market_state.value == "RISK-OFF" else "#666"
    
    st.markdown(f"""
    <div style='text-align: center; padding: 10px;'>
        <span class='status-badge' style='background: {fund_color};'>Fundamental: {result.fundamental_state.value}</span>
        <span class='status-badge' style='background: {mkt_color}; margin-left: 10px;'>Market: {market_state.value}</span>
    </div>
    """, unsafe_allow_html=True)
    
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
    
    # Debug info expander
    with st.expander("🔧 Debug Info"):
        st.caption("Engine Status")
        st.write(f"Open trades in engine: {len(st.session_state.engine.open_trades)}")
        st.write(f"Closed trades in engine: {len(st.session_state.engine.closed_trades)}")
        st.caption("Analysis Result")
        st.write(f"trade_eligible: {result.trade_eligible}")
        st.write(f"rejection_reasons: {result.rejection_reasons}")
        if st.session_state.engine.open_trades:
            st.caption("Current Open Trades:")
            for t in st.session_state.engine.open_trades:
                st.write(f"- {t.symbol}: {t.trade_id} (entered {t.entry_date.date()})")
    
    # Trade eligibility
    if result.trade_eligible:
        st.success("✅ **TRADE ELIGIBLE** - All entry rules met")
        
        # Check if trade was just created (to show persistent success message)
        if f"trade_created_{result.symbol}" in st.session_state:
            st.success(f"✅ Paper trade created: {st.session_state[f'trade_created_{result.symbol}']}")
            if st.button("Clear Message", key=f"clear_{result.symbol}"):
                del st.session_state[f"trade_created_{result.symbol}"]
                st.rerun()
        elif st.button("Create Paper Trade", type="primary"):
            try:
                trade = st.session_state.engine.create_trade(result)
                if trade:
                    # Save immediately
                    trades_df = st.session_state.engine.to_dataframe(include_open=True)
                    save_success = st.session_state.storage.save_trades(trades_df)
                    
                    # Store success in session state
                    st.session_state[f"trade_created_{result.symbol}"] = trade.trade_id
                    
                    if save_success:
                        st.success(f"✅ Paper trade created and saved: {trade.trade_id}")
                    else:
                        st.warning(f"⚠️ Trade created ({trade.trade_id}) but save failed - check storage")
                    
                    # Rerun to show persistent message
                    st.rerun()
                else:
                    st.error("❌ Failed to create trade - trade_eligible is True but create_trade returned None")
                    st.caption("This shouldn't happen. Check logs.")
            except Exception as e:
                st.error(f"❌ Error creating trade: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
    else:
        st.warning("❌ **NOT ELIGIBLE** - Entry rules not met")
        st.caption(f"Reasons: {', '.join(result.rejection_reasons)}")


def display_analysis_summary(results: List[AnalysisResult]):
    """Display summary table of all analyzed stocks"""
    
    st.markdown("### 📋 Analysis Summary")
    
    # Count eligible trades
    eligible_count = sum(1 for r in results if r.trade_eligible)
    total_count = len(results)
    
    # Count by outcome
    continuation_count = sum(1 for r in results if r.behavior.value == "CONTINUATION")
    expansion_count = sum(1 for r in results if r.behavior.value == "EXPANSION")
    failure_count = sum(1 for r in results if r.behavior.value == "FAILURE")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Analyzed", total_count)
    with col2:
        st.metric("Trade Eligible", eligible_count, delta=f"{(eligible_count/total_count*100):.0f}%" if total_count > 0 else "0%")
    with col3:
        st.metric("CONTINUATION", continuation_count, delta="✅ Pass" if continuation_count > 0 else None)
    with col4:
        st.metric("FAILURE", failure_count, delta="❌ Reject" if failure_count > 0 else None, delta_color="inverse")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Build summary table
    summary_data = []
    for r in results:
        # Emoji indicators
        trend_emoji = {"STRONG": "🟢", "DEVELOPING": "🟡", "ABSENT": "🔴"}[r.trend_state.value]
        entry_emoji = {"OK": "🟢", "WAIT": "🟡", "NO": "🔴", "N/A": "⚪"}[r.entry_state.value]
        rs_emoji = {"STRONG": "🟢", "NEUTRAL": "🟡", "WEAK": "🔴", "N/A": "⚪"}[r.rs_state.value]
        behavior_emoji = {"CONTINUATION": "🟢", "EXPANSION": "🔵", "FAILURE": "🔴"}[r.behavior.value]
        
        summary_data.append({
            "✓": "✅" if r.trade_eligible else "❌",
            "Symbol": r.symbol.replace(".NS", ""),
            "Trend": f"{trend_emoji} {r.trend_state.value}",
            "Entry": f"{entry_emoji} {r.entry_state.value}",
            "RS": f"{rs_emoji} {r.rs_state.value}",
            "Behavior": f"{behavior_emoji} {r.behavior.value}",
            "Price": f"₹{r.close:.2f}",
            "RSI": f"{r.rsi:.1f}",
        })
    
    df = pd.DataFrame(summary_data)
    
    # Sort: eligible first, then by symbol
    df['_sort'] = df['✓'].apply(lambda x: 0 if x == '✅' else 1)
    df = df.sort_values(['_sort', 'Symbol']).drop('_sort', axis=1)
    
    # Display toggle between table and card view
    view_mode = st.radio("View Mode", ["📊 Table View", "🗂️ Card View"], horizontal=True, label_visibility="collapsed")
    
    if "Table" in view_mode:
        # Table view
        st.dataframe(
            df, 
            use_container_width=True, 
            hide_index=True, 
            height=min(450, len(df) * 35 + 38)  # Dynamic height based on rows
        )
    else:
        # Card view for better mobile/small screen experience
        for idx, row in df.iterrows():
            status_color = "#00CC94" if row['✓'] == '✅' else "#FF5252"
            
            with st.container():
                st.markdown(f"""
                <div style='background: #1E1E1E; padding: 15px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid {status_color};'>
                    <div style='display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;'>
                        <div style='flex: 1; min-width: 200px;'>
                            <h3 style='margin: 0; color: {status_color};'>{row['✓']} {row['Symbol']}</h3>
                            <p style='margin: 5px 0; color: #888; font-size: 0.9rem;'>{row['Price']} • RSI: {row['RSI']}</p>
                        </div>
                        <div style='display: flex; gap: 10px; flex-wrap: wrap;'>
                            <span class='status-badge' style='background: #333;'>{row['Trend']}</span>
                            <span class='status-badge' style='background: #333;'>{row['Entry']}</span>
                            <span class='status-badge' style='background: #333;'>{row['RS']}</span>
                            <span class='status-badge' style='background: #333;'>{row['Behavior']}</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    
    # Expandable rejection analysis
    if failure_count > 0:
        with st.expander(f"🔍 Why {failure_count} stocks failed (Behavior = FAILURE)"):
            st.markdown("""
            **Behavior FAILURE means:**
            - Stock broke below EMA20 support
            - Or showing weakness in price structure
            - Or momentum deteriorating
            
            **This is NOT an error** - it's the system correctly rejecting weak setups.
            
            **What to do:**
            - ✅ This is normal market filtering
            - ✅ Wait for better setups
            - ✅ FAILURE is a valid decision (logged for learning)
            - ❌ Do NOT force trades when behavior fails
            """)


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
    st.title("📝 Paper Trading Portfolio")
    st.caption("Forward-only simulation • No hindsight • Pure execution tracking")
    
    engine = st.session_state.engine
    
    # Stats with enhanced design
    stats = engine.get_statistics()
    
    st.markdown("### 📊 Performance Metrics")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown(f"""
        <div class='card' style='text-align: center;'>
            <div class='metric-label'>Total Trades</div>
            <div class='big-metric'>{stats['total_trades']}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class='card' style='text-align: center; border-left: 4px solid #4FC3F7;'>
            <div class='metric-label'>Open</div>
            <div class='big-metric' style='color: #4FC3F7;'>{stats['open_trades']}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        wr_color = "#00CC94" if stats.get('win_rate', 0) >= 50 else "#FF9800" if stats.get('win_rate', 0) >= 40 else "#FF5252"
        st.markdown(f"""
        <div class='card' style='text-align: center; border-left: 4px solid {wr_color};'>
            <div class='metric-label'>Win Rate</div>
            <div class='big-metric' style='color: {wr_color};'>{stats.get('win_rate', 0):.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        pnl = stats.get('total_pnl', 0)
        pnl_color = "#00CC94" if pnl >= 0 else "#FF5252"
        pnl_sign = "+" if pnl >= 0 else ""
        st.markdown(f"""
        <div class='card' style='text-align: center; border-left: 4px solid {pnl_color};'>
            <div class='metric-label'>Total P&L</div>
            <div class='big-metric' style='color: {pnl_color};'>{pnl_sign}₹{abs(pnl):.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        avg_pnl = stats.get('avg_pnl_pct', 0)
        avg_color = "#00CC94" if avg_pnl >= 0 else "#FF5252"
        avg_sign = "+" if avg_pnl >= 0 else ""
        st.markdown(f"""
        <div class='card' style='text-align: center; border-left: 4px solid {avg_color};'>
            <div class='metric-label'>Avg P&L %</div>
            <div class='big-metric' style='color: {avg_color};'>{avg_sign}{avg_pnl:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
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
        st.info("📭 No open trades currently. Analyze stocks to create new positions.")
        return
    
    st.markdown(f"### 📈 Open Positions ({len(engine.open_trades)})")
    st.caption("Monitor active trades and update with current market data")
    st.markdown("<br>", unsafe_allow_html=True)
    
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
    
    # Google Drive Status
    st.subheader("☁️ Cloud Storage Status")
    
    storage = st.session_state.storage
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if storage.use_drive and storage.drive_available:
            st.success("✅ Google Drive Connected")
            st.caption("Primary storage: Cloud")
        elif storage.use_drive and not storage.drive_available:
            st.error("❌ Drive Connection Failed")
            st.caption("Using local fallback")
        else:
            st.info("📁 Local Storage Only")
            st.caption("Drive not enabled")
    
    with col2:
        if storage.use_drive and storage.drive_available:
            st.metric("Storage Mode", "Cloud-First")
        else:
            st.metric("Storage Mode", "Local Only")
    
    with col3:
        if storage.use_drive and storage.drive_available:
            st.metric("Sync Status", "Auto")
        else:
            st.metric("Sync Status", "Disabled")
    
    # Show error details if Drive failed
    if storage.use_drive and not storage.drive_available:
        st.error(f"""
        **⚠️ Drive Connection Error:**
        
        ```
        {storage.drive_error}
        ```
        
        **Setup Steps:**
        1. Check if credentials.json exists in project folder
        2. Install: `pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib`
        3. Verify credentials file is valid JSON
        4. See DRIVE_SETUP.md for detailed instructions
        5. Restart Streamlit app after fixing
        """)
    
    st.markdown("---")
    
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
    
    st.subheader("📊 Fundamental Analysis Log")
    
    # Load analysis log
    analysis_df = st.session_state.storage.load_analysis_log()
    
    if not analysis_df.empty and 'fund_eps_growth' in analysis_df.columns:
        st.caption(f"Showing fundamental checks for {len(analysis_df)} analyzed stocks")
        
        # Calculate fundamental statistics
        total_analyzed = len(analysis_df)
        
        # Check columns that exist
        fund_cols = [col for col in ['fund_eps_growth', 'fund_pe_reasonable', 'fund_debt_acceptable', 
                                       'fund_roe_strong', 'fund_cashflow_positive'] if col in analysis_df.columns]
        
        if fund_cols:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                fund_pass = len(analysis_df[analysis_df['fundamental_state'] == 'PASS'])
                st.metric("PASS", fund_pass, delta=f"{(fund_pass/total_analyzed*100):.1f}%")
            
            with col2:
                fund_neutral = len(analysis_df[analysis_df['fundamental_state'] == 'NEUTRAL'])
                st.metric("NEUTRAL", fund_neutral, delta=f"{(fund_neutral/total_analyzed*100):.1f}%")
            
            with col3:
                fund_fail = len(analysis_df[analysis_df['fundamental_state'] == 'FAIL'])
                st.metric("FAIL", fund_fail, delta=f"{(fund_fail/total_analyzed*100):.1f}%")
            
            # Show check-by-check breakdown
            st.markdown("**Fundamental Checks Breakdown:**")
            
            check_stats = []
            check_labels = {
                'fund_eps_growth': 'EPS Growth > 10%',
                'fund_pe_reasonable': 'P/E Reasonable',
                'fund_debt_acceptable': 'Debt/Equity < 0.5',
                'fund_roe_strong': 'ROE > 15%',
                'fund_cashflow_positive': 'Cashflow Positive'
            }
            
            for col in fund_cols:
                if col in analysis_df.columns:
                    # Count string values: 'TRUE', 'FALSE', 'N/A'
                    total = len(analysis_df)
                    
                    # Convert column to string and count
                    col_values = analysis_df[col].astype(str)
                    true_count = (col_values == 'TRUE').sum()
                    false_count = (col_values == 'FALSE').sum()
                    na_count = (col_values == 'N/A').sum()
                    available = true_count + false_count
                    
                    if available > 0:
                        pass_rate = (true_count / available * 100)
                        check_stats.append({
                            'Check': check_labels.get(col, col),
                            'Pass': true_count,
                            'Fail': false_count,
                            'N/A': na_count,
                            'Pass Rate': f"{pass_rate:.1f}%",
                            'Status': '✅' if pass_rate > 60 else '⚠️' if pass_rate > 40 else '❌'
                        })
                    else:
                        check_stats.append({
                            'Check': check_labels.get(col, col),
                            'Pass': 0,
                            'Fail': 0,
                            'N/A': na_count,
                            'Pass Rate': 'No Data',
                            'Status': '⚪'
                        })
            
            if check_stats:
                st.dataframe(pd.DataFrame(check_stats), use_container_width=True, hide_index=True)
            
            # Note about data availability
            st.info("""
            **📝 Note on Fundamental Data:**
            - Currently showing NEUTRAL (60%) as default - no live fundamental data source connected
            - Individual checks show `None` when data is unavailable
            - To enable: Integrate screener.in API or manual stock whitelist
            - See `analyze_fundamentals()` in analysis_engine.py for integration
            """)
        else:
            st.warning("Fundamental check columns not found in analysis log. Run analysis to generate data.")
    else:
        st.info("No analysis log data available. Run stock analysis to generate fundamental logs.")
    
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


def show_fundamental_analysis_section():
    """Display fundamental analysis log with proper None handling"""

    st.subheader("📊 Fundamental Analysis Log")

    # Load analysis log
    analysis_df = st.session_state.storage.load_analysis_log()

    if analysis_df.empty:
        st.info("No analysis log data available. Run stock analysis to generate fundamental logs.")
        return

    # Check if fundamental columns exist
    fund_cols = [
        'fund_eps_growth',
        'fund_pe_reasonable',
        'fund_debt_acceptable',
        'fund_roe_strong',
        'fund_cashflow_positive'
    ]

    has_fund_data = all(col in analysis_df.columns for col in fund_cols)

    if not has_fund_data:
        st.warning("Fundamental check columns not found in analysis log. Run analysis to generate data.")
        return

    st.caption(f"Showing fundamental checks for {len(analysis_df)} analyzed stocks")

    # Calculate statistics
    total_analyzed = len(analysis_df)

    # Convert string values back to booleans for counting
    def parse_bool_string(value):
        """Convert CSV string back to boolean or None"""
        if pd.isna(value) or value in ['None', 'N/A', '']:
            return None
        return value in ['True', 'TRUE', 'true']

    # Overall fundamental state distribution
    col1, col2, col3 = st.columns(3)

    with col1:
        fund_pass = len(analysis_df[analysis_df['fundamental_state'] == 'PASS'])
        st.metric("PASS", fund_pass, delta=f"{(fund_pass / total_analyzed * 100):.1f}%")

    with col2:
        fund_neutral = len(analysis_df[analysis_df['fundamental_state'] == 'NEUTRAL'])
        st.metric("NEUTRAL", fund_neutral, delta=f"{(fund_neutral / total_analyzed * 100):.1f}%")

    with col3:
        fund_fail = len(analysis_df[analysis_df['fundamental_state'] == 'FAIL'])
        st.metric("FAIL", fund_fail, delta=f"{(fund_fail / total_analyzed * 100):.1f}%")

    # Check-by-check breakdown
    st.markdown("**Fundamental Checks Breakdown:**")

    check_stats = []
    check_labels = {
        'fund_eps_growth': 'EPS Growth > 10%',
        'fund_pe_reasonable': 'P/E Reasonable',
        'fund_debt_acceptable': 'Debt/Equity < 0.5',
        'fund_roe_strong': 'ROE > 15%',
        'fund_cashflow_positive': 'Cashflow Positive'
    }

    for col in fund_cols:
        # Parse string values
        col_values = analysis_df[col].apply(parse_bool_string)

        # Count outcomes
        true_count = col_values.apply(lambda x: x is True).sum()
        false_count = col_values.apply(lambda x: x is False).sum()
        none_count = col_values.apply(lambda x: x is None).sum()

        available = true_count + false_count

        if available > 0:
            pass_rate = (true_count / available * 100)
            status = '✅' if pass_rate > 60 else '⚠️' if pass_rate > 40 else '❌'
        else:
            pass_rate = 0
            status = '⚪'

        check_stats.append({
            'Check': check_labels.get(col, col),
            'Pass (✓)': true_count,
            'Fail (✗)': false_count,
            'No Data': none_count,
            'Pass Rate': f"{pass_rate:.1f}%" if available > 0 else 'N/A',
            'Status': status
        })

    if check_stats:
        check_df = pd.DataFrame(check_stats)
        st.dataframe(check_df, use_container_width=True, hide_index=True)

        # Show interpretation
        none_total = sum(stat['No Data'] for stat in check_stats)
        if none_total > 0:
            st.info(f"""
            **📝 Data Availability:**
            - **{none_total} "No Data" entries** across all checks indicates fundamental data source not connected
            - Currently using NEUTRAL default (60% score) when no data available
            - This is WORKING AS DESIGNED - system correctly logs missing data

            **To enable real fundamental analysis:**
            1. Integrate screener.in API, or
            2. Create manual stock whitelist, or  
            3. Connect to broker fundamental endpoints

            See `analyze_fundamentals()` in `analysis_engine.py` for integration details.
            """)
    else:
        st.warning("Could not parse fundamental check data")
# ═══════════════════════════════════════════════════════════════════════════
# RUN APP
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()
