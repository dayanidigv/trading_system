"""
Paper Trade Engine
Forward-only simulation with exact entry/exit rules

Design: No hindsight, no optimization, pure forward testing
Philosophy: Data decides truth, not opinions
"""

# Version tracking for cache busting
__version__ = "2.0.0"  # Updated: Fixed create_trade to use trade_eligible flag

import pandas as pd
import numpy as np
from dataclasses import dataclass, asdict
from typing import Optional, List
from datetime import datetime, timedelta
from enum import Enum
import uuid
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

class TradeStatus(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class TradeOutcome(Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    NO_MOVE = "NO-MOVE"
    PENDING = "PENDING"


class ExitReason(Enum):
    TARGET_HIT = "TARGET_HIT"
    STOP_LOSS = "STOP_LOSS"
    BEHAVIOR_FAILURE = "BEHAVIOR_FAILURE"
    MAX_HOLDING_DAYS = "MAX_HOLDING_DAYS"
    PENDING = "PENDING"


@dataclass
class PaperTrade:
    """Single paper trade record"""
    trade_id: str
    symbol: str
    entry_date: pd.Timestamp
    entry_price: float
    
    # Position sizing
    shares: int
    position_value: float
    
    # Risk management
    stop_loss: float
    target: float
    max_holding_days: int
    
    # Entry context
    trend_state: str
    entry_state: str
    rs_state: str
    behavior: str
    market_state: str
    fundamental_state: str
    
    # Exit tracking
    status: TradeStatus
    exit_date: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: ExitReason = ExitReason.PENDING
    outcome: TradeOutcome = TradeOutcome.PENDING
    
    # Performance metrics
    pnl: float = 0.0
    pnl_pct: float = 0.0
    holding_days: int = 0
    
    # Max Favorable/Adverse Excursion
    mfe: float = 0.0  # Max Favorable Excursion (%)
    mae: float = 0.0  # Max Adverse Excursion (%)
    
    # Notes
    notes: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# TRADE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

class TradeConfig:
    """Paper trading configuration"""
    
    # Position sizing
    DEFAULT_POSITION_VALUE = 100000  # ₹1 lakh per trade
    
    # Risk management
    STOP_LOSS_PCT = 0.05  # 5% stop loss
    TARGET_PCT = 0.10     # 10% target (2:1 R:R)
    MAX_HOLDING_DAYS = 10  # Max 10 trading days


# ═══════════════════════════════════════════════════════════════════════════
# PAPER TRADE ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class PaperTradeEngine:
    """
    Forward-only paper trading simulation
    
    Rules:
    1. Entry on same-day EOD if rules met
    2. Exit on priority: Stop → Target → Behavior → Max Days
    3. Track MFE/MAE for post-analysis
    """
    
    def __init__(self, config: TradeConfig = None):
        self.config = config or TradeConfig()
        self.open_trades: List[PaperTrade] = []
        self.closed_trades: List[PaperTrade] = []
    
    def create_trade(self, analysis_result) -> Optional[PaperTrade]:
        """
        Create new paper trade if entry rules met
        
        Args:
            analysis_result: AnalysisResult from analysis engine
        
        Returns:
            PaperTrade if entry allowed, None otherwise
        """
        
        # Debug logging
        print(f"🔍 create_trade called for {analysis_result.symbol}")
        print(f"   trade_eligible: {analysis_result.trade_eligible}")
        
        # Use the trade_eligible flag from analysis result
        if not analysis_result.trade_eligible:
            print(f"❌ Trade creation rejected for {analysis_result.symbol}: trade_eligible=False")
            print(f"   rejection_reasons: {analysis_result.rejection_reasons}")
            return None
        
        print(f"✅ Entry rules passed for {analysis_result.symbol}, creating trade...")
        
        try:
            # Calculate position size
            shares = int(self.config.DEFAULT_POSITION_VALUE / analysis_result.close)
            position_value = shares * analysis_result.close
            
            # Calculate stop and target
            stop_loss = analysis_result.close * (1 - self.config.STOP_LOSS_PCT)
            target = analysis_result.close * (1 + self.config.TARGET_PCT)
            
            print(f"   Entry: ₹{analysis_result.close:.2f}, Stop: ₹{stop_loss:.2f}, Target: ₹{target:.2f}")
            print(f"   Position: {shares} shares = ₹{position_value:.2f}")
            
            trade = PaperTrade(
                trade_id=str(uuid.uuid4())[:8],
                symbol=analysis_result.symbol,
                entry_date=analysis_result.date,
                entry_price=analysis_result.close,
                shares=shares,
                position_value=position_value,
                stop_loss=stop_loss,
                target=target,
                max_holding_days=self.config.MAX_HOLDING_DAYS,
                trend_state=analysis_result.trend_state.value,
                entry_state=analysis_result.entry_state.value,
                rs_state=analysis_result.rs_state.value,
                behavior=analysis_result.behavior.value,
                market_state=analysis_result.market_state.value,
                fundamental_state=analysis_result.fundamental_state.value,
                status=TradeStatus.OPEN,
            )
            
            self.open_trades.append(trade)
            print(f"✅ Trade created successfully: {analysis_result.symbol} [{trade.trade_id}]")
            return trade
            
        except Exception as e:
            print(f"❌ Exception creating trade for {analysis_result.symbol}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def update_trade(
        self, 
        trade: PaperTrade, 
        current_date: pd.Timestamp,
        current_price: float,
        low: float,
        high: float,
        behavior: str
    ) -> Optional[PaperTrade]:
        """
        Update open trade with current market data
        
        Args:
            trade: Open PaperTrade
            current_date: Current date
            current_price: Current close price
            low: Today's low
            high: Today's high
            behavior: Current behavior state
        
        Returns:
            Trade if closed, None if still open
        """
        
        if trade.status == TradeStatus.CLOSED:
            return None
        
        # Ensure dates are timezone-aware for correct calculation
        # Convert to date-only for holding days calculation
        entry_date_only = pd.to_datetime(trade.entry_date).date()
        current_date_only = pd.to_datetime(current_date).date()
        
        # Update holding days (TRADING DAYS, not calendar days)
        # MAX_HOLDING_DAYS = 10 means 10 trading sessions, excluding weekends/holidays
        trade.holding_days = len(pd.bdate_range(entry_date_only, current_date_only)) - 1
        
        # ═══════════════════════════════════════════════════════════════════
        # Update MFE/MAE BEFORE Exit Checks (Critical Design Decision)
        # ═══════════════════════════════════════════════════════════════════
        # 
        # MFE/MAE are updated using the day's high/low BEFORE checking exits.
        # This is intentional and correct because:
        #
        # 1. INTRADAY REALITY: The high/low represent actual price points that
        #    occurred during the trading day, regardless of exit timing.
        #
        # 2. ACCURATE TRACKING: Even if stopped out, we want to know what the
        #    maximum favorable/adverse excursion was during that day. This gives
        #    us "what could have been" data for post-analysis.
        #
        # 3. EXAMPLE: Stock opens at entry, drops to stop loss, then rallies:
        #    - Stop loss hit: Exit at stop price ✓
        #    - BUT day's high was above entry: MFE should reflect this ✓
        #    - This shows opportunity cost and volatility patterns
        #
        # 4. STATISTICAL VALUE: MFE/MAE help analyze:
        #    - Whether stops are too tight (high MAE but wins)
        #    - Whether targets are too ambitious (high MFE but misses)
        #    - Trade efficiency (MFE vs actual gain)
        #
        # DO NOT move these calculations after exit checks.
        # ═══════════════════════════════════════════════════════════════════
        
        # Only update MFE/MAE from day after entry onwards
        # Entry day high/low can include pre-entry price action (EOD entry)
        if current_date_only > entry_date_only:
            high_pnl_pct = (high - trade.entry_price) / trade.entry_price
            low_pnl_pct = (low - trade.entry_price) / trade.entry_price
            
            trade.mfe = max(trade.mfe, high_pnl_pct * 100)
            trade.mae = min(trade.mae, low_pnl_pct * 100)
        
        # EXIT RULES (Priority Order)
        
        # 1. Stop Loss (intraday low check)
        if low <= trade.stop_loss:
            return self._close_trade(
                trade, 
                current_date, 
                trade.stop_loss,
                ExitReason.STOP_LOSS,
                TradeOutcome.LOSS
            )
        
        # 2. Target Hit (intraday high check)
        if high >= trade.target:
            return self._close_trade(
                trade,
                current_date,
                trade.target,
                ExitReason.TARGET_HIT,
                TradeOutcome.WIN
            )
        
        # 3. Behavior FAILURE (EOD check)
        if behavior == "FAILURE":
            return self._close_trade(
                trade,
                current_date,
                current_price,
                ExitReason.BEHAVIOR_FAILURE,
                self._determine_outcome(trade, current_price)
            )
        
        # 4. Max Holding Days
        if trade.holding_days >= trade.max_holding_days:
            return self._close_trade(
                trade,
                current_date,
                current_price,
                ExitReason.MAX_HOLDING_DAYS,
                TradeOutcome.NO_MOVE
            )
        
        return None
    
    def _close_trade(
        self,
        trade: PaperTrade,
        exit_date: pd.Timestamp,
        exit_price: float,
        exit_reason: ExitReason,
        outcome: TradeOutcome
    ) -> PaperTrade:
        """Close trade and calculate final metrics"""
        
        trade.status = TradeStatus.CLOSED
        trade.exit_date = exit_date
        trade.exit_price = exit_price
        trade.exit_reason = exit_reason
        trade.outcome = outcome
        
        # Calculate P&L
        trade.pnl = (exit_price - trade.entry_price) * trade.shares
        trade.pnl_pct = ((exit_price - trade.entry_price) / trade.entry_price) * 100
        
        # Move to closed trades
        self.open_trades.remove(trade)
        self.closed_trades.append(trade)
        
        return trade
    
    def _determine_outcome(self, trade: PaperTrade, exit_price: float) -> TradeOutcome:
        """Determine outcome based on P&L"""
        pnl_pct = ((exit_price - trade.entry_price) / trade.entry_price) * 100
        
        if pnl_pct > 1.0:
            return TradeOutcome.WIN
        elif pnl_pct < -1.0:
            return TradeOutcome.LOSS
        else:
            return TradeOutcome.NO_MOVE
    
    def get_statistics(self) -> dict:
        """Calculate portfolio statistics"""
        
        if not self.closed_trades:
            return {
                "total_trades": 0,
                "open_trades": len(self.open_trades),
            }
        
        outcomes = [t.outcome for t in self.closed_trades]
        pnls = [t.pnl for t in self.closed_trades]
        pnl_pcts = [t.pnl_pct for t in self.closed_trades]
        
        wins = [t for t in self.closed_trades if t.outcome == TradeOutcome.WIN]
        losses = [t for t in self.closed_trades if t.outcome == TradeOutcome.LOSS]
        no_moves = [t for t in self.closed_trades if t.outcome == TradeOutcome.NO_MOVE]
        
        return {
            "total_trades": len(self.closed_trades),
            "open_trades": len(self.open_trades),
            "wins": len(wins),
            "losses": len(losses),
            "no_moves": len(no_moves),
            "win_rate": len(wins) / len(self.closed_trades) * 100 if self.closed_trades else 0,
            "avg_win": np.mean([t.pnl_pct for t in wins]) if wins else 0,
            "avg_loss": np.mean([t.pnl_pct for t in losses]) if losses else 0,
            "total_pnl": sum(pnls),
            "avg_pnl": np.mean(pnls),
            "avg_pnl_pct": np.mean(pnl_pcts),
            "max_win": max(pnl_pcts) if pnl_pcts else 0,
            "max_loss": min(pnl_pcts) if pnl_pcts else 0,
            "avg_holding_days": np.mean([t.holding_days for t in self.closed_trades]),
        }
    
    def to_dataframe(self, include_open: bool = False) -> pd.DataFrame:
        """Convert trades to DataFrame for storage/analysis"""
        
        trades = self.closed_trades.copy()
        if include_open:
            trades.extend(self.open_trades)
        
        if not trades:
            return pd.DataFrame()
        
        # Convert to dict and ensure enums are saved as their value strings
        records = []
        for trade in trades:
            trade_dict = asdict(trade)
            # Convert enum values to just their name (e.g., 'OPEN' instead of 'TradeStatus.OPEN')
            if isinstance(trade.status, TradeStatus):
                trade_dict['status'] = trade.status.value
            if isinstance(trade.exit_reason, ExitReason):
                trade_dict['exit_reason'] = trade.exit_reason.value
            if isinstance(trade.outcome, TradeOutcome):
                trade_dict['outcome'] = trade.outcome.value
            records.append(trade_dict)
        
        return pd.DataFrame(records)
    
    def load_from_dataframe(self, df: pd.DataFrame):
        """Load trades from DataFrame (for persistence)"""
        
        if df.empty:
            return
        
        def parse_enum_value(enum_class, value, default=None):
            """
            Parse enum value with robust error handling and fallback
            
            Handles multiple formats:
            - 'VALUE' → Direct enum lookup
            - 'EnumClass.VALUE' → Strips class prefix
            - 'EnumClass(VALUE)' → Extracts from parens
            
            Args:
                enum_class: The enum class to parse into
                value: The value to parse (can be string, enum, or None)
                default: Default value if parsing fails (None = first enum value)
            
            Returns:
                Parsed enum value or default/first enum value
            """
            if pd.isna(value) or value == '':
                return default if default else list(enum_class)[0]
            
            value_str = str(value).strip()
            
            # Handle 'EnumClass.VALUE' format (strip prefix)
            if '.' in value_str:
                value_str = value_str.split('.')[-1]
            
            # Handle 'EnumClass(VALUE)' format
            if '(' in value_str and ')' in value_str:
                value_str = value_str.split('(')[1].split(')')[0]
            
            try:
                return enum_class[value_str]
            except KeyError:
                fallback = default if default else list(enum_class)[0]
                print(f"⚠️ Invalid {enum_class.__name__}: '{value}' → using {fallback.value}")
                return fallback
        
        try:
            for idx, row in df.iterrows():
                # Parse enums with appropriate defaults
                status = parse_enum_value(TradeStatus, row['status'], default=TradeStatus.OPEN)
                exit_reason = parse_enum_value(ExitReason, row['exit_reason'], default=ExitReason.PENDING)
                outcome = parse_enum_value(TradeOutcome, row['outcome'], default=TradeOutcome.PENDING)
                
                trade = PaperTrade(
                    trade_id=row['trade_id'],
                    symbol=row['symbol'],
                    entry_date=pd.Timestamp(row['entry_date']),
                    entry_price=float(row['entry_price']),
                    shares=int(row['shares']),
                    position_value=float(row['position_value']),
                    stop_loss=float(row['stop_loss']),
                    target=float(row['target']),
                    max_holding_days=int(row['max_holding_days']),
                    trend_state=str(row['trend_state']),
                    entry_state=str(row['entry_state']),
                    rs_state=str(row['rs_state']),
                    behavior=str(row['behavior']),
                    market_state=str(row['market_state']),
                    fundamental_state=str(row['fundamental_state']),
                    status=status,
                    exit_date=pd.Timestamp(row['exit_date']) if pd.notna(row['exit_date']) else None,
                    exit_price=float(row['exit_price']) if pd.notna(row['exit_price']) else None,
                    exit_reason=exit_reason,
                    outcome=outcome,
                    pnl=float(row['pnl']),
                    pnl_pct=float(row['pnl_pct']),
                    holding_days=int(row['holding_days']),
                    mfe=float(row['mfe']),
                    mae=float(row['mae']),
                    notes=str(row['notes']) if pd.notna(row['notes']) else "",
                )
                
                if trade.status == TradeStatus.OPEN:
                    self.open_trades.append(trade)
                else:
                    self.closed_trades.append(trade)
        
        except Exception as e:
            print(f"❌ Error loading trades from dataframe: {e}")
            import traceback
            traceback.print_exc()
            raise
