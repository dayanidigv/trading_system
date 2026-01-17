"""
Storage Manager
Google Drive integration for persistent data storage

Design: Human-readable CSVs, append-only with upsert by ID
Philosophy: Auditable history, no data loss
"""

import pandas as pd
import os
from typing import Optional
from pathlib import Path
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════════
# STORAGE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

class StorageConfig:
    """Storage configuration for local and Drive"""
    
    # Local storage (for development/backup)
    LOCAL_STORAGE_DIR = Path("./data")
    
    # Google Drive folder ID (set this to your Drive folder)
    # You'll need to share this folder with your service account
    DRIVE_FOLDER_ID = None  # Replace with actual folder ID
    
    # File names
    PAPER_TRADES_FILE = "paper_trades.csv"
    ANALYSIS_LOG_FILE = "analysis_log.csv"
    
    @classmethod
    def ensure_local_dir(cls):
        """Create local storage directory if it doesn't exist"""
        cls.LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════
# STORAGE MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class StorageManager:
    """
    Manages persistent storage of trades and analysis logs
    
    Storage Strategy:
    1. Primary: Local CSV files (always accessible)
    2. Backup: Google Drive (optional, for cloud sync)
    
    For Google Drive integration, you'll need:
    - Google Cloud Project with Drive API enabled
    - Service account credentials JSON
    - PyDrive2 or google-api-python-client
    
    This implementation uses LOCAL storage by default.
    Drive sync can be added as an enhancement.
    """
    
    def __init__(self, use_drive: bool = False):
        """
        Initialize storage manager
        
        Args:
            use_drive: Whether to sync with Google Drive
        """
        self.config = StorageConfig()
        self.config.ensure_local_dir()
        self.use_drive = use_drive
        
        # Paths
        self.trades_path = self.config.LOCAL_STORAGE_DIR / self.config.PAPER_TRADES_FILE
        self.analysis_path = self.config.LOCAL_STORAGE_DIR / self.config.ANALYSIS_LOG_FILE
    
    # ═══════════════════════════════════════════════════════════════════════
    # PAPER TRADES STORAGE
    # ═══════════════════════════════════════════════════════════════════════
    
    def save_trades(self, trades_df: pd.DataFrame) -> bool:
        """
        Save paper trades to storage
        
        Uses upsert strategy: update existing trades by ID, append new ones
        
        Args:
            trades_df: DataFrame with trade data
        
        Returns:
            True if successful
        """
        try:
            if trades_df.empty:
                return True
            
            # Load existing trades
            existing_df = self.load_trades()
            
            if existing_df.empty:
                # No existing data, save directly
                combined_df = trades_df
            else:
                # Upsert: remove existing trades with same ID, then append new
                existing_ids = set(existing_df['trade_id'].values)
                new_ids = set(trades_df['trade_id'].values)
                
                # Keep existing trades not in new batch
                kept_df = existing_df[~existing_df['trade_id'].isin(new_ids)]
                
                # Combine kept + new
                combined_df = pd.concat([kept_df, trades_df], ignore_index=True)
            
            # Sort by entry date
            combined_df = combined_df.sort_values('entry_date')
            
            # Save
            combined_df.to_csv(self.trades_path, index=False)
            
            # Sync to Drive if enabled
            if self.use_drive:
                self._sync_to_drive(self.trades_path, self.config.PAPER_TRADES_FILE)
            
            return True
            
        except Exception as e:
            print(f"Error saving trades: {e}")
            return False
    
    def load_trades(self) -> pd.DataFrame:
        """
        Load paper trades from storage
        
        Returns:
            DataFrame with trade data, empty if file doesn't exist
        """
        try:
            if not self.trades_path.exists():
                return pd.DataFrame()
            
            df = pd.read_csv(self.trades_path)
            
            # Convert date columns
            if not df.empty:
                df['entry_date'] = pd.to_datetime(df['entry_date'])
                df['exit_date'] = pd.to_datetime(df['exit_date'])
            
            return df
            
        except Exception as e:
            print(f"Error loading trades: {e}")
            return pd.DataFrame()
    
    # ═══════════════════════════════════════════════════════════════════════
    # ANALYSIS LOG STORAGE
    # ═══════════════════════════════════════════════════════════════════════
    
    def save_analysis_log(self, log_df: pd.DataFrame) -> bool:
        """
        Save daily analysis log
        
        Logs all analyzed stocks (including rejected ones) to track:
        - Why stocks were rejected
        - Market regime during analysis
        - Filter harshness over time
        
        Args:
            log_df: DataFrame with analysis results
        
        Returns:
            True if successful
        """
        try:
            if log_df.empty:
                return True
            
            # Load existing log
            existing_df = self.load_analysis_log()
            
            if existing_df.empty:
                combined_df = log_df
            else:
                # Append new entries (analysis log is append-only)
                # Remove duplicates based on symbol + date
                combined_df = pd.concat([existing_df, log_df], ignore_index=True)
                combined_df = combined_df.drop_duplicates(subset=['symbol', 'date'], keep='last')
            
            # Sort by date
            combined_df = combined_df.sort_values('date')
            
            # Save
            combined_df.to_csv(self.analysis_path, index=False)
            
            # Sync to Drive if enabled
            if self.use_drive:
                self._sync_to_drive(self.analysis_path, self.config.ANALYSIS_LOG_FILE)
            
            return True
            
        except Exception as e:
            print(f"Error saving analysis log: {e}")
            return False
    
    def load_analysis_log(self) -> pd.DataFrame:
        """
        Load analysis log from storage
        
        Returns:
            DataFrame with analysis log, empty if file doesn't exist
        """
        try:
            if not self.analysis_path.exists():
                return pd.DataFrame()
            
            df = pd.read_csv(self.analysis_path)
            
            # Convert date column
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
            
            return df
            
        except Exception as e:
            print(f"Error loading analysis log: {e}")
            return pd.DataFrame()
    
    # ═══════════════════════════════════════════════════════════════════════
    # GOOGLE DRIVE SYNC (Stub - implement when needed)
    # ═══════════════════════════════════════════════════════════════════════
    
    def _sync_to_drive(self, local_path: Path, remote_name: str) -> bool:
        """
        Sync local file to Google Drive
        
        STUB IMPLEMENTATION - To implement:
        1. Set up Google Cloud Project
        2. Enable Drive API
        3. Create service account
        4. Download credentials JSON
        5. Install: pip install PyDrive2
        6. Implement upload logic
        
        Args:
            local_path: Local file path
            remote_name: Remote file name
        
        Returns:
            True if successful
        """
        # TODO: Implement Google Drive sync
        # Example using PyDrive2:
        #
        # from pydrive2.auth import GoogleAuth
        # from pydrive2.drive import GoogleDrive
        #
        # gauth = GoogleAuth()
        # gauth.LocalWebserverAuth()
        # drive = GoogleDrive(gauth)
        #
        # # Search for existing file
        # file_list = drive.ListFile({
        #     'q': f"title='{remote_name}' and trashed=false"
        # }).GetList()
        #
        # if file_list:
        #     # Update existing file
        #     file = file_list[0]
        #     file.SetContentFile(str(local_path))
        #     file.Upload()
        # else:
        #     # Create new file
        #     file = drive.CreateFile({'title': remote_name})
        #     file.SetContentFile(str(local_path))
        #     file.Upload()
        
        return True
    
    # ═══════════════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════════════════════════════
    
    def export_trades_for_analysis(self, output_path: Optional[str] = None) -> pd.DataFrame:
        """
        Export trades in analysis-friendly format
        
        Args:
            output_path: Optional path to save exported data
        
        Returns:
            DataFrame ready for analysis
        """
        df = self.load_trades()
        
        if df.empty:
            return df
        
        # Add derived columns for analysis
        df['entry_year'] = pd.to_datetime(df['entry_date']).dt.year
        df['entry_month'] = pd.to_datetime(df['entry_date']).dt.month
        df['entry_weekday'] = pd.to_datetime(df['entry_date']).dt.day_name()
        
        if output_path:
            df.to_csv(output_path, index=False)
        
        return df
    
    def get_storage_info(self) -> dict:
        """Get information about stored data"""
        
        trades_df = self.load_trades()
        log_df = self.load_analysis_log()
        
        return {
            "trades_file": str(self.trades_path),
            "trades_exist": self.trades_path.exists(),
            "total_trades": len(trades_df),
            "open_trades": len(trades_df[trades_df['status'] == 'OPEN']) if not trades_df.empty else 0,
            "closed_trades": len(trades_df[trades_df['status'] == 'CLOSED']) if not trades_df.empty else 0,
            "analysis_log_file": str(self.analysis_path),
            "analysis_log_exist": self.analysis_path.exists(),
            "total_analyses": len(log_df),
            "drive_sync_enabled": self.use_drive,
        }


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def analysis_result_to_log_entry(analysis_result) -> dict:
    """
    Convert AnalysisResult to log entry dictionary
    
    Args:
        analysis_result: AnalysisResult from analysis engine
    
    Returns:
        Dictionary suitable for analysis log
    """
    return {
        'date': analysis_result.date,
        'symbol': analysis_result.symbol,
        'market_state': analysis_result.market_state.value,
        'fundamental_state': analysis_result.fundamental_state.value,
        'fundamental_score': analysis_result.fundamental_score,
        'trend_state': analysis_result.trend_state.value,
        'entry_state': analysis_result.entry_state.value,
        'rs_state': analysis_result.rs_state.value,
        'rs_value': analysis_result.rs_value,
        'behavior': analysis_result.behavior.value,
        'trade_eligible': analysis_result.trade_eligible,
        'rejection_reasons': '|'.join(analysis_result.rejection_reasons) if analysis_result.rejection_reasons else '',
        'close': analysis_result.close,
        'rsi': analysis_result.rsi,
        'consecutive_bars': analysis_result.consecutive_bars_above_emas,
    }
