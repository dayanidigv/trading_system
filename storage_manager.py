"""
Storage Manager with Google Drive as Primary Storage
Complete implementation with local fallback

Design: Cloud-first with local caching
Philosophy: Persistent, accessible, auditable
"""

import pandas as pd
import os
import json
from typing import Optional, Dict
from pathlib import Path
from datetime import datetime
import io
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
# GOOGLE DRIVE INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════

try:
    from google.oauth2.credentials import Credentials
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload, MediaIoBaseUpload
    from googleapiclient.errors import HttpError
    DRIVE_AVAILABLE = True
except ImportError:
    DRIVE_AVAILABLE = False
    print("⚠️  Google Drive libraries not installed. Install with:")
    print("   pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")


# ═══════════════════════════════════════════════════════════════════════════
# STORAGE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

class StorageConfig:
    """Storage configuration for Drive and local fallback"""
    
    # Local storage (for caching/fallback)
    LOCAL_STORAGE_DIR = Path("./data")
    LOCAL_CACHE_DIR = Path("./data/cache")
    
    # Credentials
    CREDENTIALS_FILE = "credentials.json"  # Service account or OAuth credentials
    TOKEN_FILE = "token.json"  # OAuth token (if using OAuth)
    
    # Google Drive folder name (will be created if doesn't exist)
    DRIVE_FOLDER_NAME = "TradingSystem_Data"
    
    # File names
    PAPER_TRADES_FILE = "paper_trades.csv"
    ANALYSIS_LOG_FILE = "analysis_log.csv"
    METADATA_FILE = "metadata.json"
    
    @classmethod
    def ensure_local_dirs(cls):
        """Create local storage directories"""
        cls.LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOCAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════
# GOOGLE DRIVE CLIENT
# ═══════════════════════════════════════════════════════════════════════════

class DriveClient:
    """Google Drive API client wrapper"""
    
    def __init__(self, credentials_path: str = None):
        """
        Initialize Drive client
        
        Args:
            credentials_path: Path to credentials JSON file
        """
        if not DRIVE_AVAILABLE:
            raise ImportError("Google Drive libraries not installed")
        
        self.credentials_path = credentials_path or StorageConfig.CREDENTIALS_FILE
        self.service = None
        self.folder_id = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google Drive"""
        creds = None
        
        # Check if credentials file exists
        if not Path(self.credentials_path).exists():
            raise FileNotFoundError(
                f"Credentials file not found: {self.credentials_path}\n"
                "Please follow setup instructions in README"
            )
        
        # Load credentials
        try:
            # Try service account first
            creds = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/drive.file']
            )
        except Exception:
            # Fall back to OAuth (for user accounts)
            from google.auth.transport.requests import Request
            from google_auth_oauthlib.flow import InstalledAppFlow
            
            token_path = Path(StorageConfig.TOKEN_FILE)
            
            if token_path.exists():
                creds = Credentials.from_authorized_user_file(
                    str(token_path),
                    ['https://www.googleapis.com/auth/drive.file']
                )
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path,
                        ['https://www.googleapis.com/auth/drive.file']
                    )
                    creds = flow.run_local_server(port=0)
                
                # Save token
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
        
        # Build service
        self.service = build('drive', 'v3', credentials=creds)
    
    def get_or_create_folder(self, folder_name: str) -> str:
        """
        Get or create folder in Drive
        
        Args:
            folder_name: Folder name
        
        Returns:
            Folder ID
        """
        # Search for existing folder
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        
        try:
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                return folders[0]['id']
            
            # Create new folder
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            
            return folder.get('id')
            
        except HttpError as e:
            raise Exception(f"Failed to get/create folder: {e}")
    
    def upload_file(self, local_path: Path, remote_name: str, folder_id: str) -> str:
        """
        Upload file to Drive (create or update)
        
        Args:
            local_path: Local file path
            remote_name: Remote file name
            folder_id: Parent folder ID
        
        Returns:
            File ID
        """
        # Check if file exists
        query = f"name='{remote_name}' and '{folder_id}' in parents and trashed=false"
        
        try:
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            files = results.get('files', [])
            
            # Read file content
            with open(local_path, 'rb') as f:
                content = f.read()
            
            media = MediaIoBaseUpload(
                io.BytesIO(content),
                mimetype='text/csv',
                resumable=True
            )
            
            if files:
                # Update existing file
                file_id = files[0]['id']
                self.service.files().update(
                    fileId=file_id,
                    media_body=media
                ).execute()
                return file_id
            else:
                # Create new file
                file_metadata = {
                    'name': remote_name,
                    'parents': [folder_id]
                }
                
                file = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
                
                return file.get('id')
                
        except HttpError as e:
            raise Exception(f"Failed to upload file: {e}")
    
    def download_file(self, file_name: str, folder_id: str, local_path: Path) -> bool:
        """
        Download file from Drive
        
        Args:
            file_name: Remote file name
            folder_id: Parent folder ID
            local_path: Local destination path
        
        Returns:
            True if successful
        """
        query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
        
        try:
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            files = results.get('files', [])
            
            if not files:
                return False
            
            file_id = files[0]['id']
            
            request = self.service.files().get_media(fileId=file_id)
            
            with open(local_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
            
            return True
            
        except HttpError as e:
            print(f"Failed to download file: {e}")
            return False
    
    def list_files(self, folder_id: str) -> list:
        """List files in folder"""
        query = f"'{folder_id}' in parents and trashed=false"
        
        try:
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, modifiedTime, size)'
            ).execute()
            
            return results.get('files', [])
            
        except HttpError as e:
            print(f"Failed to list files: {e}")
            return []


# ═══════════════════════════════════════════════════════════════════════════
# STORAGE MANAGER (Drive-First)
# ═══════════════════════════════════════════════════════════════════════════

class StorageManager:
    """
    Drive-first storage manager with local caching
    
    Strategy:
    1. Primary: Google Drive (cloud persistence)
    2. Cache: Local files (faster access, offline fallback)
    3. Sync: Bidirectional (Drive → Local on load, Local → Drive on save)
    """
    
    def __init__(self, use_drive: bool = True, credentials_path: str = None):
        """
        Initialize storage manager
        
        Args:
            use_drive: Use Google Drive (default: True)
            credentials_path: Path to credentials file
        """
        self.config = StorageConfig()
        self.config.ensure_local_dirs()
        
        self.use_drive = use_drive and DRIVE_AVAILABLE
        self.drive_client = None
        self.folder_id = None
        self.drive_available = False  # Track actual Drive availability
        self.drive_error = None  # Store initialization error
        
        # Initialize Drive
        if self.use_drive:
            try:
                self.drive_client = DriveClient(credentials_path)
                self.folder_id = self.drive_client.get_or_create_folder(
                    self.config.DRIVE_FOLDER_NAME
                )
                self.drive_available = True
                print(f"✅ Connected to Google Drive folder: {self.config.DRIVE_FOLDER_NAME}")
            except Exception as e:
                self.drive_error = str(e)
                print(f"⚠️  Drive initialization failed: {e}")
                print("   Falling back to local storage only")
                self.use_drive = False
                self.drive_available = False
        
        # Local paths
        self.trades_path = self.config.LOCAL_CACHE_DIR / self.config.PAPER_TRADES_FILE
        self.analysis_path = self.config.LOCAL_CACHE_DIR / self.config.ANALYSIS_LOG_FILE
        self.metadata_path = self.config.LOCAL_CACHE_DIR / self.config.METADATA_FILE
    
    # ═══════════════════════════════════════════════════════════════════════
    # PAPER TRADES STORAGE
    # ═══════════════════════════════════════════════════════════════════════
    
    def save_trades(self, trades_df: pd.DataFrame) -> bool:
        """
        Save paper trades (Drive-first)
        
        Args:
            trades_df: DataFrame with trade data
        
        Returns:
            True if successful
        """
        try:
            if trades_df.empty:
                return True
            
            # Load existing trades (from cache or Drive)
            existing_df = self.load_trades()
            
            if existing_df.empty:
                combined_df = trades_df
            else:
                # Upsert strategy
                existing_ids = set(existing_df['trade_id'].values)
                new_ids = set(trades_df['trade_id'].values)
                
                kept_df = existing_df[~existing_df['trade_id'].isin(new_ids)]
                combined_df = pd.concat([kept_df, trades_df], ignore_index=True)
            
            # Sort by entry date
            combined_df = combined_df.sort_values('entry_date')
            
            # Save to local cache first
            combined_df.to_csv(self.trades_path, index=False)
            
            # Upload to Drive
            if self.use_drive:
                self.drive_client.upload_file(
                    self.trades_path,
                    self.config.PAPER_TRADES_FILE,
                    self.folder_id
                )
                print(f"✅ Trades synced to Drive ({len(combined_df)} total)")
            
            # Update metadata
            self._update_metadata('trades', len(combined_df))
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving trades: {e}")
            return False
    
    def load_trades(self) -> pd.DataFrame:
        """
        Load paper trades (Drive-first with local cache)
        
        Returns:
            DataFrame with trade data
        """
        try:
            # Try to download from Drive first
            if self.use_drive:
                success = self.drive_client.download_file(
                    self.config.PAPER_TRADES_FILE,
                    self.folder_id,
                    self.trades_path
                )
                if success:
                    print("📥 Loaded trades from Drive")
            
            # Load from local cache
            if not self.trades_path.exists():
                return pd.DataFrame()
            
            df = pd.read_csv(self.trades_path)
            
            if not df.empty:
                df['entry_date'] = pd.to_datetime(df['entry_date'])
                df['exit_date'] = pd.to_datetime(df['exit_date'])
            
            return df
            
        except Exception as e:
            print(f"⚠️  Error loading trades: {e}")
            return pd.DataFrame()
    
    # ═══════════════════════════════════════════════════════════════════════
    # ANALYSIS LOG STORAGE
    # ═══════════════════════════════════════════════════════════════════════
    
    def save_analysis_log(self, log_df: pd.DataFrame) -> bool:
        """
        Save analysis log (Drive-first)
        
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
                # Append and deduplicate
                combined_df = pd.concat([existing_df, log_df], ignore_index=True)
                combined_df = combined_df.drop_duplicates(
                    subset=['symbol', 'date'],
                    keep='last'
                )
            
            # Sort by date
            combined_df = combined_df.sort_values('date')
            
            # Save to local cache
            combined_df.to_csv(self.analysis_path, index=False)
            
            # Upload to Drive
            if self.use_drive:
                self.drive_client.upload_file(
                    self.analysis_path,
                    self.config.ANALYSIS_LOG_FILE,
                    self.folder_id
                )
                print(f"✅ Analysis log synced to Drive ({len(combined_df)} entries)")
            
            # Update metadata
            self._update_metadata('analyses', len(combined_df))
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving analysis log: {e}")
            return False
    
    def load_analysis_log(self) -> pd.DataFrame:
        """
        Load analysis log (Drive-first with local cache)
        
        Returns:
            DataFrame with analysis log
        """
        try:
            # Try to download from Drive first
            if self.use_drive:
                success = self.drive_client.download_file(
                    self.config.ANALYSIS_LOG_FILE,
                    self.folder_id,
                    self.analysis_path
                )
                if success:
                    print("📥 Loaded analysis log from Drive")
            
            # Load from local cache
            if not self.analysis_path.exists():
                return pd.DataFrame()
            
            df = pd.read_csv(self.analysis_path)
            
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
            
            return df
            
        except Exception as e:
            print(f"⚠️  Error loading analysis log: {e}")
            return pd.DataFrame()
    
    # ═══════════════════════════════════════════════════════════════════════
    # METADATA MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════
    
    def _update_metadata(self, key: str, value):
        """Update metadata file"""
        metadata = self._load_metadata()
        metadata[key] = value
        metadata['last_updated'] = ist_now().isoformat()
        
        with open(self.metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def _load_metadata(self) -> Dict:
        """Load metadata file"""
        if not self.metadata_path.exists():
            return {}
        
        try:
            with open(self.metadata_path, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    
    # ═══════════════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════════════════════════════
    
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
    
    def get_storage_info(self) -> dict:
        """Get storage status information"""
        trades_df = self.load_trades()
        log_df = self.load_analysis_log()
        metadata = self._load_metadata()
        
        info = {
            "storage_mode": "Google Drive + Local Cache" if self.use_drive else "Local Only",
            "drive_connected": self.use_drive,
            "drive_folder": self.config.DRIVE_FOLDER_NAME if self.use_drive else "N/A",
            "local_cache_dir": str(self.config.LOCAL_CACHE_DIR),
            "trades_file": str(self.trades_path),
            "total_trades": len(trades_df),
            "open_trades": len(trades_df[trades_df['status'] == 'OPEN']) if not trades_df.empty else 0,
            "closed_trades": len(trades_df[trades_df['status'] == 'CLOSED']) if not trades_df.empty else 0,
            "analysis_log_file": str(self.analysis_path),
            "total_analyses": len(log_df),
            "last_updated": metadata.get('last_updated', 'Never'),
        }
        
        # Add Drive file info if available
        if self.use_drive and self.drive_client:
            try:
                files = self.drive_client.list_files(self.folder_id)
                info['drive_files'] = [f['name'] for f in files]
            except Exception:
                info['drive_files'] = []
        
        return info
    
    def force_sync_from_drive(self) -> bool:
        """Force download all files from Drive"""
        if not self.use_drive:
            print("⚠️  Drive not enabled")
            return False
        
        try:
            # Download trades
            self.drive_client.download_file(
                self.config.PAPER_TRADES_FILE,
                self.folder_id,
                self.trades_path
            )
            
            # Download analysis log
            self.drive_client.download_file(
                self.config.ANALYSIS_LOG_FILE,
                self.folder_id,
                self.analysis_path
            )
            
            print("✅ Synced all files from Drive")
            return True
            
        except Exception as e:
            print(f"❌ Sync failed: {e}")
            return False


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def analysis_result_to_log_entry(analysis_result) -> dict:
    """Convert AnalysisResult to log entry dictionary with proper None handling"""
    
    # Helper to convert None/bool to string for CSV storage
    def format_bool_check(value):
        """
        Convert boolean check results to CSV-safe strings
        None -> 'None' (explicit no data)
        True -> 'True' 
        False -> 'False'
        """
        if value is None:
            return 'None'  # Changed from 'N/A' to 'None' for clarity
        return str(value)  # 'True' or 'False'
    
    # Extract fundamental checks safely
    fund_reasons = analysis_result.fundamental_reasons or {}
    
    return {
        'date': analysis_result.date,
        'symbol': analysis_result.symbol,
        'market_state': analysis_result.market_state.value,
        
        # Fundamental details (with explicit None handling)
        'fundamental_state': analysis_result.fundamental_state.value,
        'fundamental_score': analysis_result.fundamental_score,
        
        # Individual fundamental checks (converted to strings for CSV)
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
