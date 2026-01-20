"""
Core Analysis Engine
Complete implementation of Layer-0 through Phase-2.5

Design: Deterministic, explainable, production-grade
Philosophy: Fundamentals filter, Technicals time, Behavior describes
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Dict, Tuple, Optional
from enum import Enum
from datetime import datetime
import pytz


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


# ═══════════════════════════════════════════════════════════════════════════
# TYPE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════

class MarketState(Enum):
    RISK_ON = "RISK-ON"
    RISK_OFF = "RISK-OFF"
    UNKNOWN = "UNKNOWN"


class FundamentalState(Enum):
    PASS = "PASS"
    NEUTRAL = "NEUTRAL"
    FAIL = "FAIL"


class TrendState(Enum):
    STRONG = "STRONG"
    DEVELOPING = "DEVELOPING"
    ABSENT = "ABSENT"


class EntryState(Enum):
    OK = "OK"
    WAIT = "WAIT"
    NO = "NO"
    NA = "N/A"


class RSState(Enum):
    STRONG = "STRONG"
    NEUTRAL = "NEUTRAL"
    WEAK = "WEAK"
    NA = "N/A"


class Behavior(Enum):
    CONTINUATION = "CONTINUATION"
    EXPANSION = "EXPANSION"
    FAILURE = "FAILURE"


@dataclass
class AnalysisResult:
    """Complete analysis output for a stock"""
    symbol: str
    date: pd.Timestamp
    
    # Layer-0: Market Context
    market_state: MarketState
    
    # Layer-0.5: Fundamental Gate
    fundamental_state: FundamentalState
    fundamental_score: float
    fundamental_reasons: Dict[str, bool]
    
    # Layer-1: Technical Analysis
    trend_state: TrendState
    entry_state: EntryState
    trend_conditions: Dict[str, bool]
    entry_conditions: Dict[str, bool]
    
    # Relative Strength
    rs_state: RSState
    rs_value: float
    
    # Phase-2.5: Behavior
    behavior: Behavior
    behavior_signals: Dict[str, bool]
    
    # Trend Maturity
    consecutive_bars_above_emas: int
    
    # Price Data
    close: float
    ema20: float
    ema50: float
    rsi: float
    volume: float
    volume_avg: float
    
    # Trade Eligibility
    trade_eligible: bool
    rejection_reasons: list


# ═══════════════════════════════════════════════════════════════════════════
# INDICATOR CALCULATIONS
# ═══════════════════════════════════════════════════════════════════════════

def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average"""
    if len(series) < period:
        return pd.Series(index=series.index, dtype=float)
    return series.ewm(span=period, adjust=False).mean()


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index"""
    if len(series) < period + 1:
        return pd.Series(index=series.index, dtype=float)
    
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = -delta.clip(upper=0).rolling(window=period).mean()
    rs = gain / (loss.replace(0, 1e-10))
    
    return 100 - (100 / (1 + rs))


def consecutive_bars_above_emas(df: pd.DataFrame) -> int:
    """Count consecutive bars where price > both EMAs"""
    if 'EMA20' not in df.columns or 'EMA50' not in df.columns:
        return 0
    
    mask = df["Close"] > df[["EMA20", "EMA50"]].max(axis=1)
    count = 0
    
    for v in reversed(mask.values):
        if v:
            count += 1
        else:
            break
    
    return count


# ═══════════════════════════════════════════════════════════════════════════
# LAYER-0: MARKET STATE (GLOBAL CONTEXT)
# ═══════════════════════════════════════════════════════════════════════════

def analyze_market_state(index_df: pd.DataFrame) -> MarketState:
    """
    Detect broad risk-on / risk-off environment
    
    Simple initial implementation:
    - Index above EMA50 = RISK-ON
    - Index below EMA50 = RISK-OFF
    """
    if index_df is None or len(index_df) < 50:
        return MarketState.UNKNOWN
    
    try:
        index_df = index_df.copy()
        index_df['EMA50'] = calculate_ema(index_df['Close'], 50)
        
        latest = index_df.iloc[-1]
        
        if latest['Close'] > latest['EMA50']:
            return MarketState.RISK_ON
        else:
            return MarketState.RISK_OFF
            
    except Exception:
        return MarketState.UNKNOWN


# ═══════════════════════════════════════════════════════════════════════════
# LAYER-0.5: FUNDAMENTAL ANALYSIS (QUALITY GATE)
# ═══════════════════════════════════════════════════════════════════════════

def analyze_fundamentals(fundamental_data: Dict) -> Tuple[FundamentalState, float, Dict[str, bool]]:
    """
    Fundamental quality filter
    
    Returns: (state, score, reasons_dict)
    
    Implementation Status:
    - Current: NEUTRAL default (no fundamental data source)
    - Phase 2: Manual whitelist of quality stocks
    - Phase 3: API integration (screener.in, Angel One, etc.)
    
    Fundamental Criteria (5 checks):
    1. EPS Growth: 3-year EPS growth > 10%
    2. PE Reasonable: P/E < Industry average or < 25
    3. Debt Acceptable: Debt/Equity < 0.5
    4. ROE Strong: Return on Equity > 15%
    5. Cashflow Positive: Operating cashflow > 0
    
    Scoring:
    - PASS: 4-5 checks pass (70-100%)
    - NEUTRAL: 2-3 checks pass (40-70%) 
    - FAIL: 0-1 checks pass (0-40%)
    """
    
    # DEFAULT IMPLEMENTATION - No fundamental data source yet
    if fundamental_data is None or not fundamental_data:
        # Return NEUTRAL as default - allows trading but flags as incomplete
        return FundamentalState.NEUTRAL, 60.0, {
            "eps_growth": None,           # Not available
            "pe_reasonable": None,        # Not available
            "debt_acceptable": None,      # Not available
            "roe_strong": None,           # Not available
            "cashflow_positive": None,    # Not available
        }
    
    # REAL IMPLEMENTATION - When fundamental data is available
    # Expected data format:
    # {
    #   "eps_growth_3y": 15.5,     # 3-year EPS growth %
    #   "pe": 22.5,                # Current P/E ratio
    #   "industry_pe": 25.0,       # Industry average P/E
    #   "debt_equity": 0.3,        # Debt to Equity ratio
    #   "roe": 18.5,               # Return on Equity %
    #   "operating_cashflow": 5000 # Operating cashflow (millions)
    # }
    
    checks = {
        "eps_growth": fundamental_data.get("eps_growth_3y", 0) > 10,
        "pe_reasonable": fundamental_data.get("pe", 100) < min(
            fundamental_data.get("industry_pe", 25), 25
        ),
        "debt_acceptable": fundamental_data.get("debt_equity", 1.0) < 0.5,
        "roe_strong": fundamental_data.get("roe", 0) > 15,
        "cashflow_positive": fundamental_data.get("operating_cashflow", 0) > 0,
    }
    
    # Calculate score
    passed = sum(1 for v in checks.values() if v)
    total = len(checks)
    score = (passed / total) * 100
    
    # Determine state
    if score >= 70:  # 4-5 checks passed
        state = FundamentalState.PASS
    elif score >= 40:  # 2-3 checks passed
        state = FundamentalState.NEUTRAL
    else:  # 0-1 checks passed
        state = FundamentalState.FAIL
    
    return state, score, checks


# ═══════════════════════════════════════════════════════════════════════════
# LAYER-1: TECHNICAL ANALYSIS (TREND + ENTRY)
# ═══════════════════════════════════════════════════════════════════════════

def analyze_technical(df: pd.DataFrame) -> Tuple[Dict, Dict, TrendState, EntryState]:
    """
    Technical strength analysis
    
    Returns: (trend_conditions, entry_conditions, trend_state, entry_state)
    """
    
    if df is None or len(df) < 50:
        return {}, {}, TrendState.ABSENT, EntryState.NA
    
    # Enrich with indicators
    df = df.copy()
    df['EMA20'] = calculate_ema(df['Close'], 20)
    df['EMA50'] = calculate_ema(df['Close'], 50)
    df['RSI'] = calculate_rsi(df['Close'])
    df['VOL_AVG_20'] = df['Volume'].rolling(20).mean()
    
    df = df.dropna(subset=['EMA20', 'EMA50', 'RSI', 'VOL_AVG_20'])
    
    if len(df) < 50:
        return {}, {}, TrendState.ABSENT, EntryState.NA
    
    latest = df.iloc[-1]
    close = latest['Close']
    ema20 = latest['EMA20']
    ema50 = latest['EMA50']
    rsi_val = latest['RSI']
    vol = latest['Volume']
    vol_avg = latest['VOL_AVG_20']
    
    # Swing-low protection
    no_swing_break = False
    if len(df) >= 10:
        last_5_low = df['Low'].iloc[-5:].min()
        prev_5_low = df['Low'].iloc[-10:-5].min()
        no_swing_break = last_5_low > prev_5_low
    
    # Pullback depth
    pullback_shallow = False
    if len(df) >= 20:
        recent_slice = df.iloc[-20:]
        high_idx = recent_slice['High'].idxmax()
        high_pos = df.index.get_loc(high_idx)
        recent_high = df.loc[high_idx, 'High']
        
        bars_after_high = df.iloc[high_pos:]
        if len(bars_after_high) > 0:
            recent_low_after_high = bars_after_high['Low'].min()
            prior_start = max(0, high_pos - 30)
            prior_slice = df.iloc[prior_start:high_pos]
            
            if len(prior_slice) > 0:
                prior_low_approx = prior_slice['Low'].min()
                impulse_size = recent_high - prior_low_approx
                
                if impulse_size > 1e-6 and recent_low_after_high < recent_high:
                    pullback_depth = (recent_high - recent_low_after_high) / impulse_size
                    pullback_shallow = pullback_depth <= 0.50
    
    # RSI regime-aware
    rsi_trend_ok = rsi_val >= 40
    rsi_entry_ok = 40 <= rsi_val <= 60
    
    # TREND CONDITIONS
    trend_conditions = {
        "price_above_ema20": close > ema20,
        "ema20_above_ema50": ema20 > ema50,
        "ema20_rising": ema20 > df['EMA20'].iloc[-5] if len(df) >= 5 else False,
        "rsi_momentum_exists": rsi_trend_ok,
        "no_swing_low_break": no_swing_break,
    }
    
    # ENTRY CONDITIONS
    entry_conditions = {
        "pullback_shallow": pullback_shallow,
        "rsi_pullback_zone": rsi_entry_ok,
        "volume_normal": vol < vol_avg * 1.75,
    }
    
    # Scoring
    trend_score = sum(trend_conditions.values())
    entry_score = sum(entry_conditions.values())
    
    # Trend State
    if trend_score >= 4:
        trend_state = TrendState.STRONG
    elif trend_score >= 3:
        trend_state = TrendState.DEVELOPING
    else:
        trend_state = TrendState.ABSENT
    
    # Entry State (only meaningful if trend exists)
    if trend_score < 3:
        entry_state = EntryState.NA
    else:
        if entry_score >= 3:
            entry_state = EntryState.OK
        elif entry_score >= 2:
            entry_state = EntryState.WAIT
        else:
            entry_state = EntryState.NO
    
    return trend_conditions, entry_conditions, trend_state, entry_state


# ═══════════════════════════════════════════════════════════════════════════
# RELATIVE STRENGTH ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════

def analyze_relative_strength(stock_df: pd.DataFrame, index_df: pd.DataFrame) -> Tuple[RSState, float]:
    """
    Calculate relative strength vs index
    
    Returns: (rs_state, rs_value)
    """
    if stock_df is None or index_df is None or len(stock_df) < 21 or len(index_df) < 21:
        return RSState.NA, 0.0
    
    try:
        stock_close = stock_df['Close'].iloc[-1]
        stock_close_20d = stock_df['Close'].iloc[-21]
        stock_ret = (stock_close - stock_close_20d) / stock_close_20d
        
        index_close = index_df['Close'].iloc[-1]
        index_close_20d = index_df['Close'].iloc[-21]
        index_ret = (index_close - index_close_20d) / index_close_20d
        
        rs_value = stock_ret - index_ret
        
        if rs_value > 0.02:
            rs_state = RSState.STRONG
        elif rs_value > -0.02:
            rs_state = RSState.NEUTRAL
        else:
            rs_state = RSState.WEAK
        
        return rs_state, rs_value
        
    except Exception:
        return RSState.NA, 0.0


# ═══════════════════════════════════════════════════════════════════════════
# PHASE-2.5: BEHAVIOR CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════

def classify_behavior(df: pd.DataFrame, rs_state: RSState) -> Tuple[Behavior, Dict[str, bool]]:
    """
    Institutional behavior detection
    
    Returns: (behavior, signals_dict)
    """
    if df is None or len(df) < 20:
        return Behavior.CONTINUATION, {}
    
    try:
        latest = df.iloc[-1]
        close = latest['Close']
        rsi_val = latest['RSI']
        vol = latest['Volume']
        vol_avg = latest['VOL_AVG_20']
        
        # ═══ FAILURE DETECTION (Any 2 of 5) ═══
        
        # RSI Divergence
        rsi_divergence = False
        if len(df) >= 10:
            price_higher = close > df['Close'].iloc[-10]
            rsi_lower = rsi_val < df['RSI'].iloc[-10]
            rsi_divergence = price_higher and rsi_lower
        
        # EMA20 flattening
        ema_flat_or_down = False
        if len(df) >= 3:
            ema_flat_or_down = df['EMA20'].iloc[-1] <= df['EMA20'].iloc[-3]
        
        # Swing-low break
        swing_low_break = False
        if len(df) >= 10:
            last_5_low = df['Low'].iloc[-5:].min()
            prev_5_low = df['Low'].iloc[-10:-5].min()
            swing_low_break = last_5_low <= prev_5_low
        
        # Effort without result
        effort_no_result = False
        if len(df) >= 2:
            effort_no_result = (vol > vol_avg * 1.5) and (close <= df['Close'].iloc[-2])
        
        # RS deterioration
        rs_weakening = rs_state == RSState.WEAK
        
        failure_signals = {
            "rsi_divergence": rsi_divergence,
            "ema_flattening": ema_flat_or_down,
            "swing_low_break": swing_low_break,
            "effort_no_result": effort_no_result,
            "rs_weakening": rs_weakening,
        }
        
        if sum(failure_signals.values()) >= 2:
            return Behavior.FAILURE, failure_signals
        
        # ═══ EXPANSION DETECTION (3 of 4) ═══
        
        # Volatility compression
        volatility_compressed = False
        if len(df) >= 34:
            atr = (df['High'] - df['Low']).rolling(14).mean()
            atr_pct = atr / df['Close']
            if len(atr_pct) >= 20:
                current_atr = atr_pct.iloc[-1]
                avg_atr = atr_pct.rolling(20).mean().iloc[-1]
                volatility_compressed = current_atr < avg_atr
        
        # Tight range
        range_tight = False
        if len(df) >= 15:
            recent_high = df['High'].iloc[-15:].max()
            recent_low = df['Low'].iloc[-15:].min()
            if recent_high > 0:
                range_tight = (recent_high - recent_low) / recent_high < 0.08
        
        # Higher lows
        higher_lows = False
        if len(df) >= 6:
            higher_lows = df['Low'].iloc[-3] > df['Low'].iloc[-6]
        
        # Quiet volume
        volume_quiet = vol < vol_avg
        
        expansion_signals = {
            "volatility_compressed": volatility_compressed,
            "range_tight": range_tight,
            "higher_lows": higher_lows,
            "volume_quiet": volume_quiet,
        }
        
        if sum(expansion_signals.values()) >= 3:
            return Behavior.EXPANSION, {**failure_signals, **expansion_signals}
        
        # Default: CONTINUATION
        return Behavior.CONTINUATION, {**failure_signals, **expansion_signals}
        
    except Exception:
        return Behavior.CONTINUATION, {}


# ═══════════════════════════════════════════════════════════════════════════
# MAIN ANALYSIS ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════

def analyze_stock(
    symbol: str,
    stock_df: pd.DataFrame,
    index_df: pd.DataFrame,
    fundamental_data: Optional[Dict] = None,
) -> AnalysisResult:
    """
    Complete end-to-end analysis of a stock
    
    Args:
        symbol: Stock symbol
        stock_df: Price data (OHLCV)
        index_df: Index data for market state and RS
        fundamental_data: Fundamental metrics (optional)
    
    Returns:
        AnalysisResult with complete analysis
    """
    
    # Define minimum required data
    MIN_REQUIRED_ROWS = 50
    
    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 1: Initial Data Validation
    # ═══════════════════════════════════════════════════════════════════════
    
    if stock_df.empty or len(stock_df) < MIN_REQUIRED_ROWS:
        raise ValueError(
            f"Insufficient data for {symbol}: {len(stock_df)} rows "
            f"(need at least {MIN_REQUIRED_ROWS})"
        )
    
    if index_df.empty or len(index_df) < MIN_REQUIRED_ROWS:
        raise ValueError(
            f"Insufficient index data: {len(index_df)} rows "
            f"(need at least {MIN_REQUIRED_ROWS})"
        )
    
    # Layer-0: Market State
    market_state = analyze_market_state(index_df)
    
    # Layer-0.5: Fundamentals
    fund_state, fund_score, fund_reasons = analyze_fundamentals(fundamental_data)
    
    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 2: Data Enrichment (Add Indicators)
    # ═══════════════════════════════════════════════════════════════════════
    
    stock_df = stock_df.copy()
    stock_df['EMA20'] = calculate_ema(stock_df['Close'], 20)
    stock_df['EMA50'] = calculate_ema(stock_df['Close'], 50)
    stock_df['RSI'] = calculate_rsi(stock_df['Close'])
    stock_df['VOL_AVG_20'] = stock_df['Volume'].rolling(20).mean()
    stock_df = stock_df.dropna(subset=['EMA20', 'EMA50', 'RSI', 'VOL_AVG_20'])
    
    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 3: Post-Enrichment Validation (CRITICAL)
    # ═══════════════════════════════════════════════════════════════════════
    # After dropna(), we might have lost rows due to:
    # - Rolling windows (EMA20 needs 20 rows, EMA50 needs 50 rows)
    # - RSI calculation (needs 14+ rows)
    # - Volume average (needs 20 rows)
    # 
    # We must re-validate to ensure sufficient data remains for analysis.
    # ═══════════════════════════════════════════════════════════════════════
    
    if stock_df.empty:
        raise ValueError(
            f"No data remaining for {symbol} after indicator calculation. "
            f"Original data likely had too many NaN values."
        )
    
    if len(stock_df) < MIN_REQUIRED_ROWS:
        raise ValueError(
            f"Insufficient data for {symbol} after cleaning: {len(stock_df)} rows "
            f"(need at least {MIN_REQUIRED_ROWS}). "
            f"Indicators consumed too many rows from the dataset."
        )
    
    # Layer-1: Technical Analysis
    trend_conds, entry_conds, trend_state, entry_state = analyze_technical(stock_df)
    
    # Relative Strength
    rs_state, rs_value = analyze_relative_strength(stock_df, index_df)
    
    # Phase-2.5: Behavior
    behavior, behavior_signals = classify_behavior(stock_df, rs_state)
    
    # Trend Maturity
    consecutive_bars = consecutive_bars_above_emas(stock_df)
    
    # Extract latest values
    latest = stock_df.iloc[-1]
    
    # Convert timestamp to IST for consistency
    latest_date = stock_df.index[-1]
    if latest_date.tz is None:
        # If timezone-naive, assume UTC and convert to IST
        latest_date = latest_date.tz_localize('UTC').tz_convert(IST)
    elif latest_date.tz != IST:
        # If different timezone, convert to IST
        latest_date = latest_date.tz_convert(IST)
    
    # Determine trade eligibility
    rejection_reasons = []
    
    if fund_state == FundamentalState.FAIL:
        rejection_reasons.append("Fundamental: FAIL")
    
    if trend_state == TrendState.ABSENT:
        rejection_reasons.append("Trend: ABSENT")
    
    if entry_state not in [EntryState.OK]:
        rejection_reasons.append(f"Entry: {entry_state.value}")
    
    if rs_state == RSState.WEAK:
        rejection_reasons.append("RS: WEAK")
    
    if behavior == Behavior.FAILURE:
        rejection_reasons.append("Behavior: FAILURE")
    
    trade_eligible = len(rejection_reasons) == 0
    
    return AnalysisResult(
        symbol=symbol,
        date=latest_date,
        market_state=market_state,
        fundamental_state=fund_state,
        fundamental_score=fund_score,
        fundamental_reasons=fund_reasons,
        trend_state=trend_state,
        entry_state=entry_state,
        trend_conditions=trend_conds,
        entry_conditions=entry_conds,
        rs_state=rs_state,
        rs_value=rs_value,
        behavior=behavior,
        behavior_signals=behavior_signals,
        consecutive_bars_above_emas=consecutive_bars,
        close=float(latest['Close']),
        ema20=float(latest['EMA20']),
        ema50=float(latest['EMA50']),
        rsi=float(latest['RSI']),
        volume=float(latest['Volume']),
        volume_avg=float(latest['VOL_AVG_20']),
        trade_eligible=trade_eligible,
        rejection_reasons=rejection_reasons,
    )
