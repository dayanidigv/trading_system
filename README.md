# Complete Trade Analysis & Paper Trading System
## Installation & Usage Guide

**🎉 NEW: Google Drive Cloud Storage Enabled**

---

## 📋 **System Overview**

This is a **production-grade, end-to-end trade analysis and paper trading system** with **cloud persistence** designed for weekly/positional trading with Indian stocks (NSE).

### **Core Philosophy:**
- **Fundamentals decide eligibility** (quality filter)
- **Technicals decide timing** (structure + entry)
- **Paper trades decide truth** (forward-only testing)
- **Data decides improvement** (no opinions until 30+ trades)
- **Cloud storage ensures persistence** (access from anywhere)

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
# Install all dependencies including Google Drive support
pip install -r requirements.txt
```

Or manually:
```bash
pip install streamlit pandas numpy yfinance plotly google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### **Step 3: Google Drive Setup (Required)**

**📖 See [DRIVE_SETUP.md](DRIVE_SETUP.md) for complete setup guide**

Quick overview:
1. Create Google Cloud Project
2. Enable Google Drive API
3. Create service account
4. Download `credentials.json`
5. Run test: `python test_drive.py`

✅ **Cloud storage ensures your data is:**
- Accessible from any device
- Automatically backed up
- Safe from local failures
- Synced in real-time

### **Step 4: Project Structure**

```
trading_system/
├── credentials.json        # Google credentials (DO NOT COMMIT)
├── analysis_engine.py      # Core analysis logic
├── paper_trade_engine.py   # Trade simulation
├── storage_manager.py      # Drive integration
├── main_app.py            # Streamlit application
├── test_drive.py          # Drive connection test
├── requirements.txt       # Dependencies
├── data/
│   └── cache/            # Local cache (auto-synced)
│       ├── paper_trades.csv
│       ├── analysis_log.csv
│       └── metadata.json
├── DRIVE_SETUP.md        # Setup guide
└── README.md
```

### **Step 5: Verify Setup**

```bash
# Test Google Drive connection
python test_drive.py

# Expected output:
# ✅ Connected to Google Drive
# ✅ All tests passed!
```

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
1. Connect to Google Drive (cloud storage)
2. Load existing trades from cloud
3. Allow you to analyze stocks
4. Create new paper trades if rules met
5. Update open trades with current prices
6. Auto-sync all data to Google Drive

**💾 Your data is automatically saved to the cloud on every action!**

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
- Storage information (Drive + Local)
- Total trades logged
- Cloud sync status
- File locations
- Locked system rules

**Cloud Storage Status:**
- Connection state
- Last sync time
- Drive folder location
- Files in cloud

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

### **3. Storage Configuration**

Edit `storage_manager.py` (advanced):

```python
class StorageConfig:
    DRIVE_FOLDER_NAME = "TradingSystem_Data"  # Your folder name
    # ... other settings
```

### **4. Fundamental Data Integration**

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

---

## 💾 **Data Storage Architecture**

### **Cloud-First Design**

```
Your App
   ↓
Local Cache (Fast access)
   ↓
Google Drive (Cloud persistence)
   ↓
Accessible from any device
```

**Benefits:**
- ✅ **Never lose data** - Cloud backup
- ✅ **Access anywhere** - Any device with credentials
- ✅ **Automatic sync** - No manual saves
- ✅ **Offline capable** - Works with cached data
- ✅ **Version safe** - Always latest state

### **File Structure in Drive**

Your Google Drive folder `TradingSystem_Data` contains:
```
TradingSystem_Data/
├── paper_trades.csv     # All trades (open + closed)
├── analysis_log.csv     # Daily analysis log
└── metadata.json        # System metadata
```

### **Local Cache**

Local cache in `./data/cache/` mirrors Drive for:
- Fast access during session
- Offline capability
- Reduced API calls

**Cache is auto-synced on every save/load**

---

## 📈 **Expected Usage Pattern**

### **Daily Routine (5-10 minutes)**

**Before Market Close (3:00-3:30 PM):**
1. Run `streamlit run main_app.py`
2. System connects to Drive automatically
3. Navigate to "Daily Analysis"
4. Click "Analyze All" on your watchlist
5. Review eligible setups
6. Create paper trades if rules met
7. Update open trades
8. **Data auto-saved to cloud ✅**
9. Review Analytics (if ≥5 trades)

**Weekly Review (Saturday):**
1. Access from any device (Drive credentials)
2. Review closed trades
3. Note patterns in exits
4. Update watchlist if needed

**Monthly Review:**
1. Calculate statistics (if ≥30 trades)
2. Identify improvement areas
3. Document learnings
4. NO RULE CHANGES (observation only)

---

## 🚨 **Common Issues & Solutions**

### **Issue: "Drive initialization failed"**
**Solution:** 
```bash
# Verify credentials
python test_drive.py

# Check credentials.json exists
# Ensure Drive API enabled
# For service account: Share folder with service account email
```

### **Issue: "Failed to load index data"**
**Solution:** Check internet connection, try different index symbol

### **Issue: "Insufficient data for [symbol]"**
**Solution:** Stock too new or delisted, remove from universe

### **Issue: "Trade not updating"**
**Solution:** Manually click "Update [Symbol]" button daily

### **Issue: "No trades eligible"**
**Solution:** Normal! Entry rules are strict. Expect 1-3 trades/week max.

### **Issue: "Import error: google.oauth2"**
**Solution:** 
```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

---

## 🔒 **Security & Privacy**

### **Protect Your Credentials**

Add to `.gitignore`:
```
credentials.json
token.json
data/cache/
*.pyc
__pycache__/
```

### **What's Stored in Drive**

- Trade data (CSV format)
- Analysis logs (CSV format)
- System metadata (JSON)

**NOT stored:**
- Credentials
- Code files
- Personal information beyond what you input

### **Access Control**

- Service account: Only you can access (via credentials.json)
- OAuth: Only your Google account
- Data encrypted in transit and at rest by Google

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

## ✅ **Final Checklist**

Before going live:

- [ ] All code files created
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Google Drive setup complete
- [ ] Test script passes (`python test_drive.py`)
- [ ] See "Connected to Google Drive" message
- [ ] System runs without errors
- [ ] Can analyze stocks
- [ ] Can create paper trades
- [ ] Can update trades
- [ ] Data syncs to Drive
- [ ] Can see files in Drive folder
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
- **Never lose data** (cloud persistence)

**Success = Process adherence, not immediate profits**

The edge comes from consistency, not complexity.

---

## 📞 **Support & Documentation**

**Setup Guides:**
- `README.md` - This file (main guide)
- `DRIVE_SETUP.md` - Detailed Drive setup
- `test_drive.py` - Connection verification

**Key Files:**
- `analysis_engine.py` - Analysis logic
- `paper_trade_engine.py` - Trade management
- `storage_manager.py` - Cloud storage
- `main_app.py` - User interface

**Data Location:**
- Cloud: Google Drive folder `TradingSystem_Data`
- Local: `./data/cache/` (auto-synced)

---

## 🚀 **Quick Start Summary**

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Setup Google Drive (see DRIVE_SETUP.md)
# - Create Cloud project
# - Enable Drive API
# - Download credentials.json

# 3. Test connection
python test_drive.py

# 4. Run system
streamlit run main_app.py

# 5. Start analyzing!
```

---

**System Version:** 2.0 (Cloud Edition)  
**Last Updated:** January 2026  
**Status:** Production-Ready with Cloud Storage  
**Discipline Lock:** ACTIVE
**Storage:** Google Drive Primary
