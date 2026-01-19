"""
Paper Trade Engine
Forward-only simulation with exact entry/exit rules

Design: No hindsight, no optimization, pure forward testing
Philosophy: Data decides truth, not opinions
"""

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
    
    # Entry rules (from design doc)
    @staticmethod
    def entry_allowed(analysis_result) -> bool:
        """
        Entry rules from master design:
        - Fundamentals = PASS or NEUTRAL
        - TREND = STRONG
        - ENTRY = OK
        - RS = STRONG
        - Behavior = CONTINUATION
        """
        from analysis_engine import (
            FundamentalState, TrendState, 
            EntryState, RSState, Behavior
        )
        
        checks = [
            analysis_result.fundamental_state in [FundamentalState.PASS, FundamentalState.NEUTRAL],
            analysis_result.trend_state == TrendState.STRONG,
            analysis_result.entry_state == EntryState.OK,
            analysis_result.rs_state == RSState.STRONG,
            analysis_result.behavior == Behavior.CONTINUATION,
        ]
        
        return all(checks)


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
        print(f"Attempting trade creation for {analysis_result}...")
        # Use the trade_eligible flag from analysis result
        if not analysis_result.trade_eligible:
            print(f"❌ Trade creation rejected for {analysis_result.symbol}: trade_eligible=False")
            return None
        
        try:
            # Calculate position size
            shares = int(self.config.DEFAULT_POSITION_VALUE / analysis_result.close)
            position_value = shares * analysis_result.close
            
            # Calculate stop and target
            stop_loss = analysis_result.close * (1 - self.config.STOP_LOSS_PCT)
            target = analysis_result.close * (1 + self.config.TARGET_PCT)
            
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
            print(f"✅ Trade created for {analysis_result.symbol}: {trade.trade_id}")
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
        
        # Update holding days
        trade.holding_days = (current_date - trade.entry_date).days
        
        # Update MFE/MAE
        unrealized_pnl_pct = (current_price - trade.entry_price) / trade.entry_price
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
        
        def parse_enum_value(enum_class, value):
            """Parse enum value handling both 'VALUE' and 'EnumClass.VALUE' formats"""
            if pd.isna(value) or value == '':
                return None
            
            value_str = str(value)
            
            # Handle 'EnumClass.VALUE' format (strip prefix)
            if '.' in value_str:
                value_str = value_str.split('.')[-1]
            
            try:
                return enum_class[value_str]
            except KeyError:
                # If parsing fails, return None or default
                return None
        
        for _, row in df.iterrows():
            # Parse status enum
            status = parse_enum_value(TradeStatus, row['status'])
            if status is None:
                status = TradeStatus.OPEN  # Default for safety
            
            # Parse exit_reason and outcome enums (handle PENDING for open trades)
            exit_reason = parse_enum_value(ExitReason, row['exit_reason'])
            if exit_reason is None:
                exit_reason = ExitReason.PENDING
            
            outcome = parse_enum_value(TradeOutcome, row['outcome'])
            if outcome is None:
                outcome = TradeOutcome.PENDING
            
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
