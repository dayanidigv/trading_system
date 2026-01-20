"""
Google Sheets Storage Manager
Replacement for Drive-based storage with Apps Script API

Design: Real-time sync, collaborative, built-in analytics
Philosophy: Let Sheets handle data, Python handles logic
"""

import requests
import pandas as pd
from typing import Optional, Dict, List
from datetime import datetime
import pytz
import os
from dotenv import load_dotenv
import time

load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════
# IST TIMEZONE
# ═══════════════════════════════════════════════════════════════════════════

IST = pytz.timezone("Asia/Kolkata")

def ist_now():
    """Get current datetime in IST"""
    return datetime.now(IST)


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

def get_config(key: str, default=None):
    """Get config from .env or Streamlit secrets"""
    value = os.getenv(key)
    if value:
        return value
    
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except:
        pass
    
    return default


class SheetsConfig:
    """Google Sheets configuration"""
    
    # Apps Script Web App URL (from deployment)
    APPS_SCRIPT_URL = get_config('APPS_SCRIPT_URL')
    
    # API Key for authentication
    API_KEY = get_config('APPS_SCRIPT_API_KEY')
    
    # Timeout for API calls
    TIMEOUT = 30
    
    @classmethod
    def validate(cls):
        """Validate configuration"""
        if not cls.APPS_SCRIPT_URL:
            raise ValueError(
                "APPS_SCRIPT_URL not configured.\n"
                "Set it in .env or Streamlit secrets:\n"
                "APPS_SCRIPT_URL = 'https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec'"
            )
        
        if not cls.API_KEY:
            raise ValueError(
                "APPS_SCRIPT_API_KEY not configured.\n"
                "Set it in .env or Streamlit secrets"
            )


# ═══════════════════════════════════════════════════════════════════════════
# GOOGLE SHEETS CLIENT
# ═══════════════════════════════════════════════════════════════════════════

class SheetsClient:
    """Client for Google Sheets via Apps Script API"""
    
    def __init__(self):
        SheetsConfig.validate()
        self.url = SheetsConfig.APPS_SCRIPT_URL
        self.api_key = SheetsConfig.API_KEY
        self.timeout = SheetsConfig.TIMEOUT
        self.available = True
        self.error = None
    
    def _request(self, method: str, params: Dict = None, data: Dict = None, max_retries: int = 3) -> Dict:
        """Make API request to Apps Script with retry logic"""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                if method == "GET":
                    params = params or {}
                    params['api_key'] = self.api_key
                    
                    response = requests.get(
                        self.url,
                        params=params,
                        timeout=self.timeout
                    )
                
                elif method == "POST":
                    data = data or {}
                    data['api_key'] = self.api_key
                    
                    response = requests.post(
                        self.url,
                        json=data,
                        timeout=self.timeout
                    )
                
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                response.raise_for_status()
                return response.json()
            
            except requests.exceptions.Timeout as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    print(f"⏳ Request timeout, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
            
            except requests.exceptions.RequestException as e:
                last_error = e
                # For DNS errors or connection errors, don't retry immediately
                if attempt < max_retries - 1 and "nodename nor servname" not in str(e):
                    wait_time = 2 ** attempt
                    print(f"⏳ Request failed, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                break  # Don't retry DNS errors
        
        error_msg = f"API request failed after {max_retries} attempts: {last_error}"
        print(f"❌ {error_msg}")
        self.error = error_msg
        return {"success": False, "error": str(last_error)}
    
    # ═══════════════════════════════════════════════════════════════════════
    # TRADE OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_all_trades(self) -> Dict:
        """Get all trades from Sheets"""
        return self._request("GET", params={"action": "get_all_trades"})
    
    def get_open_trades(self) -> Dict:
        """Get open trades"""
        return self._request("GET", params={"action": "get_open_trades"})
    
    def get_closed_trades(self) -> Dict:
        """Get closed trades"""
        return self._request("GET", params={"action": "get_closed_trades"})
    
    def create_trade(self, trade: Dict) -> Dict:
        """Create new trade"""
        return self._request("POST", data={
            "action": "create_trade",
            "trade": trade
        })
    
    def update_trade(self, trade_id: str, updates: Dict) -> Dict:
        """Update existing trade"""
        return self._request("POST", data={
            "action": "update_trade",
            "trade_id": trade_id,
            "updates": updates
        })
    
    # ═══════════════════════════════════════════════════════════════════════
    # ANALYSIS LOG OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════
    
    def log_analysis(self, analysis: Dict) -> Dict:
        """Log single analysis result"""
        return self._request("POST", data={
            "action": "log_analysis",
            "analysis": analysis
        })
    
    def batch_log_analysis(self, analyses: List[Dict]) -> Dict:
        """Log multiple analysis results"""
        return self._request("POST", data={
            "action": "batch_log_analysis",
            "analyses": analyses
        })
    
    def get_analysis_log(self, days: int = 30) -> Dict:
        """Get analysis log for recent days"""
        return self._request("GET", params={
            "action": "get_analysis_log",
            "days": days
        })
    
    # ═══════════════════════════════════════════════════════════════════════
    # STATISTICS
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_statistics(self) -> Dict:
        """Get pre-calculated statistics from Dashboard sheet"""
        return self._request("GET", params={"action": "get_statistics"})


# ═══════════════════════════════════════════════════════════════════════════
# STORAGE MANAGER (Sheets-based)
# ═══════════════════════════════════════════════════════════════════════════

class SheetsStorageManager:
    """
    Google Sheets-based storage manager
    
    Benefits over Drive:
    - Real-time sync across devices
    - Built-in data validation
    - Direct viewing/editing in Sheets
    - Automatic formulas and calculations
    - Version history
    - No file locking issues
    """
    
    def __init__(self):
        """Initialize Sheets storage"""
        try:
            self.client = SheetsClient()
            self.available = True
            self.error = None
            print(f"✅ Connected to Google Sheets via Apps Script")
        
        except Exception as e:
            self.available = False
            self.error = str(e)
            print(f"❌ Sheets initialization failed: {e}")
        
        # Compatibility attributes for old StorageManager interface
        self.use_drive = True  # We're using cloud storage (Sheets)
        self.drive_available = self.available  # Sheets available = "drive" available
        self.storage_type = "sheets"  # Identifier for UI display
        self.drive_error = self.error  # Map error for compatibility
    
    # ═══════════════════════════════════════════════════════════════════════
    # PAPER TRADES
    # ═══════════════════════════════════════════════════════════════════════
    
    def save_trades(self, trades_df: pd.DataFrame) -> bool:
        """
        Save/update trades to Google Sheets
        
        Strategy:
        - For new trades: Create via API
        - For existing trades: Update via API
        """
        if not self.available:
            print("⚠️ Sheets not available, cannot save trades")
            return False
        
        if trades_df.empty:
            return True
        
        try:
            # Get existing trade IDs from Sheets
            result = self.client.get_all_trades()
            
            if not result.get('success'):
                print(f"❌ Failed to fetch existing trades: {result.get('error')}")
                return False
            
            existing_trades = result.get('trades', [])
            existing_ids = {t['trade_id'] for t in existing_trades}
            
            # Separate new vs updated trades
            success_count = 0
            failed_trades = []
            
            for idx, (_, row) in enumerate(trades_df.iterrows()):
                trade_dict = row.to_dict()
                trade_id = trade_dict['trade_id']
                
                # Convert timestamps to ISO strings
                for col in ['entry_date', 'exit_date']:
                    if col in trade_dict and pd.notna(trade_dict[col]):
                        if isinstance(trade_dict[col], pd.Timestamp):
                            trade_dict[col] = trade_dict[col].isoformat()
                
                # Replace NaN with empty string
                trade_dict = {k: (v if pd.notna(v) else "") for k, v in trade_dict.items()}
                
                if trade_id in existing_ids:
                    # Update existing
                    result = self.client.update_trade(trade_id, trade_dict)
                else:
                    # Create new
                    result = self.client.create_trade(trade_dict)
                
                if result.get('success'):
                    success_count += 1
                else:
                    failed_trades.append(trade_id)
                
                # Rate limiting: small delay between requests
                if idx < len(trades_df) - 1:  # Don't sleep after last request
                    time.sleep(0.5)  # 500ms between requests
            
            if failed_trades:
                print(f"⚠️ Saved {success_count}/{len(trades_df)} trades (failed: {', '.join(failed_trades)})")
            else:
                print(f"✅ Saved {success_count}/{len(trades_df)} trades to Sheets")
            
            return success_count > 0  # Partial success is still success
        
        except Exception as e:
            print(f"❌ Error saving trades: {e}")
            return False
    
    def load_trades(self) -> pd.DataFrame:
        """Load all trades from Google Sheets"""
        if not self.available:
            print("⚠️ Sheets not available")
            return pd.DataFrame()
        
        try:
            result = self.client.get_all_trades()
            
            if not result.get('success'):
                print(f"❌ Failed to load trades: {result.get('error')}")
                return pd.DataFrame()
            
            trades = result.get('trades', [])
            
            if not trades:
                return pd.DataFrame()
            
            df = pd.DataFrame(trades)
            
            # Convert date columns
            for col in ['entry_date', 'exit_date', 'created_at', 'updated_at']:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
            
            # Convert numeric columns
            numeric_cols = ['entry_price', 'shares', 'position_value', 'stop_loss', 
                          'target', 'exit_price', 'pnl', 'pnl_pct', 'holding_days', 
                          'mfe', 'mae']
            
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            print(f"📥 Loaded {len(df)} trades from Sheets")
            return df
        
        except Exception as e:
            print(f"❌ Error loading trades: {e}")
            return pd.DataFrame()
    
    # ═══════════════════════════════════════════════════════════════════════
    # ANALYSIS LOG
    # ═══════════════════════════════════════════════════════════════════════
    
    def save_analysis_log(self, log_df: pd.DataFrame) -> bool:
        """Save analysis log to Google Sheets"""
        if not self.available:
            print("⚠️ Sheets not available")
            return False
        
        if log_df.empty:
            return True
        
        try:
            # Convert to list of dicts
            analyses = []
            
            for _, row in log_df.iterrows():
                analysis = row.to_dict()
                
                # Convert timestamps
                if 'date' in analysis and pd.notna(analysis['date']):
                    if isinstance(analysis['date'], pd.Timestamp):
                        analysis['date'] = analysis['date'].isoformat()
                
                # Replace NaN
                analysis = {k: (v if pd.notna(v) else "") for k, v in analysis.items()}
                analyses.append(analysis)
            
            # Batch log
            result = self.client.batch_log_analysis(analyses)
            
            if result.get('success'):
                print(f"✅ Logged {len(analyses)} analyses to Sheets")
                return True
            else:
                print(f"❌ Failed to log analyses: {result.get('error')}")
                return False
        
        except Exception as e:
            print(f"❌ Error saving analysis log: {e}")
            return False
    
    def load_analysis_log(self, days: int = 30) -> pd.DataFrame:
        """Load analysis log from Google Sheets"""
        if not self.available:
            print("⚠️ Sheets not available")
            return pd.DataFrame()
        
        try:
            result = self.client.get_analysis_log(days)
            
            if not result.get('success'):
                print(f"❌ Failed to load analysis log: {result.get('error')}")
                return pd.DataFrame()
            
            analyses = result.get('analyses', [])
            
            if not analyses:
                return pd.DataFrame()
            
            df = pd.DataFrame(analyses)
            
            # Convert timestamps
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
            
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            
            print(f"📥 Loaded {len(df)} analysis entries from Sheets")
            return df
        
        except Exception as e:
            print(f"❌ Error loading analysis log: {e}")
            return pd.DataFrame()
    
    # ═══════════════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_storage_info(self) -> dict:
        """Get storage status"""
        trades_df = self.load_trades()
        
        info = {
            "storage_mode": "Google Sheets",
            "sheets_connected": self.available,
            "sheets_url": SheetsConfig.APPS_SCRIPT_URL if self.available else "N/A",
            "total_trades": len(trades_df),
            "open_trades": len(trades_df[trades_df['status'] == 'OPEN']) if not trades_df.empty else 0,
            "closed_trades": len(trades_df[trades_df['status'] == 'CLOSED']) if not trades_df.empty else 0,
            "last_updated": ist_now().isoformat(),
        }
        
        # Get statistics from Sheets
        if self.available:
            try:
                stats_result = self.client.get_statistics()
                if stats_result.get('success'):
                    info['dashboard_stats'] = stats_result.get('statistics', {})
            except Exception as e:
                print(f"⚠️ Could not fetch dashboard stats: {e}")
        
        return info
    
    def export_trades_for_analysis(self, output_path: Optional[str] = None) -> pd.DataFrame:
        """Export trades for external analysis"""
        df = self.load_trades()
        
        if df.empty:
            return df
        
        # Add derived columns
        df['entry_year'] = pd.to_datetime(df['entry_date']).dt.year
        df['entry_month'] = pd.to_datetime(df['entry_date']).dt.month
        df['entry_weekday'] = pd.to_datetime(df['entry_date']).dt.day_name()
        
        if output_path:
            df.to_csv(output_path, index=False)
            print(f"📁 Exported to: {output_path}")
        
        return df


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS (for compatibility with existing code)
# ═══════════════════════════════════════════════════════════════════════════

def analysis_result_to_log_entry(analysis_result) -> dict:
    """Convert AnalysisResult to log entry dictionary"""
    
    def format_bool_check(value):
        """Convert boolean to string for storage"""
        if value is None:
            return 'None'
        return str(value)
    
    fund_reasons = analysis_result.fundamental_reasons or {}
    
    return {
        'date': analysis_result.date.isoformat() if hasattr(analysis_result.date, 'isoformat') else str(analysis_result.date),
        'symbol': analysis_result.symbol,
        'market_state': analysis_result.market_state.value,
        
        # Fundamental details
        'fundamental_state': analysis_result.fundamental_state.value,
        'fundamental_score': analysis_result.fundamental_score,
        
        # Individual fundamental checks
        'fund_eps_growth': format_bool_check(fund_reasons.get('eps_growth')),
        'fund_pe_reasonable': format_bool_check(fund_reasons.get('pe_reasonable')),
        'fund_debt_acceptable': format_bool_check(fund_reasons.get('debt_acceptable')),
        'fund_roe_strong': format_bool_check(fund_reasons.get('roe_strong')),
        'fund_cashflow_positive': format_bool_check(fund_reasons.get('cashflow_positive')),
        
        # Technical states
        'trend_state': analysis_result.trend_state.value,
        'entry_state': analysis_result.entry_state.value,
        'rs_state': analysis_result.rs_state.value,
        'rs_value': analysis_result.rs_value,
        'behavior': analysis_result.behavior.value,
        
        # Decision
        'trade_eligible': analysis_result.trade_eligible,
        'rejection_reasons': '|'.join(analysis_result.rejection_reasons) if analysis_result.rejection_reasons else '',
        
        # Price data
        'close': analysis_result.close,
        'rsi': analysis_result.rsi,
        'consecutive_bars': analysis_result.consecutive_bars_above_emas,
    }