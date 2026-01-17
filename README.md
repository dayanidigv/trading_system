# Complete Trade Analysis & Paper Trading System
## Installation & Usage Guide

---

## 📋 **System Overview**

This is a **production-grade, end-to-end trade analysis and paper trading system** designed for weekly/positional trading with Indian stocks (NSE).

### **Core Philosophy:**
- **Fundamentals decide eligibility** (quality filter)
- **Technicals decide timing** (structure + entry)
- **Paper trades decide truth** (forward-only testing)
- **Data decides improvement** (no opinions until 30+ trades)

---

## 🛠️ **Installation**

### **Step 1: Prerequisites**

```bash
# Python 3.8+ required
python --version

# Create virtual environment
python -m venv trading_env

# Activate environment
# Windows:
trading_env\Scripts\activate
# Mac/Linux:
source trading_env/bin/activate
```

### **Step 2: Install Dependencies**

```bash
pip install streamlit pandas numpy yfinance plotly
```

### **Step 3: Project Structure**

Create this folder structure:

```
trading_system/
├── analysis_engine.py       # Core analysis logic
├── paper_trade_engine.py    # Trade simulation
├── storage_manager.py       # Data persistence
├── main_app.py             # Streamlit application
├── data/                   # Local storage (auto-created)
│   ├── paper_trades.csv
│   └── analysis_log.csv
└── README.md
```

### **Step 4: Copy Code Files**

Copy each artifact code into its corresponding file:
- `analysis_engine.py` → Core Analysis Engine artifact
- `paper_trade_engine.py` → Paper Trade Engine artifact
- `storage_manager.py` → Storage Manager artifact
- `main_app.py` → Main Application artifact

---

## 🚀 **Running the System**

### **Daily Workflow**

```bash
# Activate environment
source trading_env/bin/activate  # or trading_env\Scripts\activate on Windows

# Run Streamlit app
streamlit run main_app.py
```

The system will:
1. Load existing trades from storage
2. Allow you to analyze stocks
3. Create new paper trades if rules met
4. Update open trades with current prices
5. Save all data to local CSV files

---

## 📊 **Using the System**

### **Page 1: Daily Analysis**

**Purpose:** Analyze stocks and create paper trades

**Workflow:**
1. Check **Market State** (RISK-ON / RISK-OFF)
2. Select stocks from universe
3. Click **"Analyze All"** to run batch analysis
4. Review results in summary table
5. For detailed view, select stock and click **"Analyze Stock"**
6. If trade eligible, click **"Create Paper Trade"**

**Entry Rules (All Must Be True):**
- ✅ Fundamentals: PASS or NEUTRAL
- ✅ Trend: STRONG
- ✅ Entry: OK
- ✅ RS: STRONG  
- ✅ Behavior: CONTINUATION

---

### **Page 2: Paper Trades**

**Purpose:** Monitor and update open positions

**Open Trades Tab:**
- View all open positions
- See entry context (trend, RS, behavior)
- Track MFE/MAE (max favorable/adverse excursion)
- Click **"Update [Symbol]"** to check for exits

**Closed Trades Tab:**
- Review all closed trades
- See outcomes: WIN / LOSS / NO-MOVE
- Analyze exit reasons

**Exit Rules (Priority Order):**
1. 🛑 **Stop Loss** (-5%)
2. 🎯 **Target Hit** (+10%)
3. ⚠️ **Behavior FAILURE** (distribution detected)
4. ⏰ **Max Holding Days** (10 days)

---

### **Page 3: Analytics Dashboard**

**Purpose:** Understand system performance (≥5 trades needed)

**Available Analytics:**
- Win/Loss/No-Move distribution
- Exit reason breakdown
- MFE vs MAE scatter plot
- Holding period distribution
- Win rate and average P&L

**⚠️ CRITICAL:** Do NOT interpret results until ≥30 trades

---

### **Page 4: Settings**

**Purpose:** System configuration and rules

**View:**
- Storage information
- Total trades logged
- File locations
- Locked system rules

**Discipline Lock:**
- No rule changes until ≥30 closed trades
- No optimization for 6-8 weeks minimum
- Only bug fixes allowed

---

## 🔧 **Customization**

### **1. Stock Universe**

Edit `main_app.py`:

```python
DEFAULT_UNIVERSE = [
    "RELIANCE.NS",   # Your stocks here
    "TCS.NS",
    # Add more...
]
```

### **2. Position Sizing**

Edit `paper_trade_engine.py`:

```python
class TradeConfig:
    DEFAULT_POSITION_VALUE = 100000  # Change amount here
    STOP_LOSS_PCT = 0.05  # 5% stop
    TARGET_PCT = 0.10     # 10% target
    MAX_HOLDING_DAYS = 10
```

### **3. Fundamental Data Integration**

The system currently uses a **stub** for fundamental analysis. To integrate real data:

**Option A: Manual Whitelist**

```python
# In analysis_engine.py, analyze_fundamentals()
FUNDAMENTAL_WHITELIST = {
    "RELIANCE.NS": {"score": 80, "state": "PASS"},
    "TCS.NS": {"score": 85, "state": "PASS"},
}
```

**Option B: API Integration**

Integrate with:
- Screener.in API
- Angel One fundamental endpoints
- NSE corporate announcements
- Yahoo Finance statistics

```python
def get_fundamental_data(symbol):
    # Implement API call here
    # Return dict with:
    # - eps_growth_3y
    # - pe, roe, debt_equity
    # - operating_cashflow
    pass
```

---

## 💾 **Data Storage**

### **Local Storage (Default)**

All data saved to:
```
trading_system/data/
├── paper_trades.csv     # All trades (open + closed)
└── analysis_log.csv     # Daily analysis log
```

**Format:** Human-readable CSV  
**Strategy:** Append-only with upsert by trade_id  
**Backup:** Manual (copy files to backup location)

### **Google Drive Sync (Optional)**

To enable cloud backup:

1. **Set up Google Cloud Project:**
   - Create project at console.cloud.google.com
   - Enable Google Drive API
   - Create service account
   - Download credentials JSON

2. **Install PyDrive2:**
   ```bash
   pip install PyDrive2
   ```

3. **Implement sync in `storage_manager.py`:**
   ```python
   # Uncomment and implement _sync_to_drive() method
   # See code comments for example
   ```

---

## 📈 **Expected Usage Pattern**

### **Daily Routine (5-10 minutes)**

**Before Market Close (3:00-3:30 PM):**
1. Run `streamlit run main_app.py`
2. Navigate to "Daily Analysis"
3. Click "Analyze All" on your watchlist (10-20 stocks)
4. Review eligible setups
5. Create paper trades if rules met
6. Update open trades
7. Review Analytics (if ≥5 trades)

**Weekly Review (Saturday):**
1. Export trades for analysis
2. Review closed trades
3. Note patterns in exits
4. Update watchlist if needed

**Monthly Review:**
1. Calculate statistics (if ≥30 trades)
2. Identify improvement areas
3. Document learnings
4. NO RULE CHANGES (observation only)

---

## 🎯 **Success Metrics**

### **Short-Term (Weeks 1-4)**
- ✅ System runs without errors
- ✅ Trades logged correctly
- ✅ Entry/exit logic executes properly
- ✅ Data persists between sessions

### **Medium-Term (Weeks 5-8)**
- ✅ ≥20-30 closed trades
- ✅ Consistent usage (no missed days)
- ✅ Analysis log shows filter evolution
- ✅ Understand behavior patterns

### **Long-Term (3+ Months)**
- ✅ ≥50-100 trades for statistical significance
- ✅ Identify which behaviors work
- ✅ Refine one rule at a time
- ✅ Build intuition about setups

---

## 🚨 **Common Issues & Solutions**

### **Issue: "Failed to load index data"**
**Solution:** Check internet connection, try different index symbol

### **Issue: "Insufficient data for [symbol]"**
**Solution:** Stock too new or delisted, remove from universe

### **Issue: "Trade not updating"**
**Solution:** Manually click "Update [Symbol]" button daily

### **Issue: "No trades eligible"**
**Solution:** Normal! Entry rules are strict. Expect 1-3 trades/week max.

### **Issue: "Analysis log growing too large"**
**Solution:** Archive old data (before implementing, keep full history)

---

## 📚 **Understanding the Layers**

### **Layer-0: Market State**
- **Question:** Is market RISK-ON or RISK-OFF?
- **Use:** Context only (doesn't block trades initially)
- **Future:** May gate entries during RISK-OFF

### **Layer-0.5: Fundamentals**
- **Question:** Is this a quality business?
- **Use:** Hard filter (FAIL = no trade)
- **Refresh:** Quarterly only

### **Layer-1: Technical Analysis**
- **TREND:** Structure exists?
- **ENTRY:** Timing favorable?
- **Use:** Both must align

### **Relative Strength (RS)**
- **Question:** Institutions prefer this vs index?
- **Use:** Ranking + filtering
- **Threshold:** >2% = STRONG, <-2% = WEAK

### **Phase-2.5: Behavior**
- **CONTINUATION:** Normal accumulation
- **EXPANSION:** Preparation phase
- **FAILURE:** Distribution warning
- **Use:** Descriptive + exit trigger

---

## 🔒 **Discipline Protocol**

### **Locked Rules (Until 30+ Trades)**

**Cannot Change:**
- Entry criteria
- Stop loss %
- Target %
- Max holding days
- Behavior detection thresholds

**Can Change:**
- Stock universe (add/remove stocks)
- Position size (with documentation)
- Analysis frequency

**Only Allowed:**
- Bug fixes
- Data source updates
- UI improvements

---

## 🎓 **Learning Approach**

### **Phase 1: Operation (Weeks 1-4)**
- Focus: Run system correctly
- Goal: Build habit
- Success: Consistent daily execution

### **Phase 2: Observation (Weeks 5-8)**
- Focus: Watch patterns emerge
- Goal: Understand behavior → outcome
- Success: ≥30 trades logged

### **Phase 3: Refinement (Month 3+)**
- Focus: Data-driven improvements
- Goal: Optimize one rule at a time
- Success: Higher win rate or better R:R

---

## 📞 **Support & Next Steps**

### **If System Works Well:**
- Continue for 6-8 weeks
- Build trade sample (30-50 minimum)
- Document learnings
- Refine ONE rule at a time

### **If System Needs Enhancement:**

**High-Priority Additions:**
1. Real fundamental data integration
2. Multi-timeframe confirmation
3. Sector rotation analysis
4. Google Drive auto-sync

**Medium-Priority:**
1. Email/Telegram alerts
2. Automated daily runs (GitHub Actions)
3. Advanced analytics (drawdown, Sharpe)
4. Volatility regime detection

**Low-Priority:**
1. Backtest module (forward-only is better)
2. ML-based filters (premature)
3. Real-money integration (stay paper for months)

---

## ✅ **Final Checklist**

Before going live:

- [ ] All 4 code files created
- [ ] Dependencies installed
- [ ] System runs without errors
- [ ] Can analyze stocks
- [ ] Can create paper trades
- [ ] Can update trades
- [ ] Data persists between sessions
- [ ] Understand all entry rules
- [ ] Understand all exit rules
- [ ] Committed to 6-8 week discipline lock

---

## 🎯 **Philosophy Reminder**

This system is designed to:
- **Trade less** (quality over quantity)
- **Learn more** (data over opinions)
- **Improve slowly** (one rule at a time)
- **Stay disciplined** (no emotional overrides)

**Success = Process adherence, not immediate profits**

The edge comes from consistency, not complexity.

---

**System Version:** 1.0  
**Last Updated:** January 2026  
**Status:** Production-Ready  
**Discipline Lock:** ACTIVE
