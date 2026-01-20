"""
CSV to Google Sheets Migration Tool
One-time migration script to move existing data to Sheets

Usage:
    python migrate_to_sheets.py

Requirements:
    pip install gspread google-auth pandas python-dotenv
"""

import pandas as pd
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from pathlib import Path
import json
import os
from datetime import datetime
from dotenv import load_dotenv
import pickle

load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

class MigrationConfig:
    """Migration configuration"""
    
    # Google Sheets setup
    SHEET_NAME = "Trading_System_Database"  # Name of the new Google Sheet
    
    # OAuth2 credentials (same as main app)
    CREDENTIALS_FILE = "credentials.json"
    TOKEN_FILE = "token.json"
    
    # CSV file paths
    PAPER_TRADES_CSV = "data/cache/paper_trades.csv"
    ANALYSIS_LOG_CSV = "data/cache/analysis_log.csv"
    
    # Sheet names
    TRADES_SHEET = "Paper_Trades"
    ANALYSIS_SHEET = "Analysis_Log"
    DASHBOARD_SHEET = "Dashboard"
    CONFIG_SHEET = "Config"
    
    # Share with (optional - email addresses to share the sheet with)
    SHARE_WITH = os.getenv('SHARE_SHEET_WITH', '').split(',')


# ═══════════════════════════════════════════════════════════════════════════
# GOOGLE SHEETS CLIENT
# ═══════════════════════════════════════════════════════════════════════════

class SheetsManager:
    """Manager for Google Sheets operations"""
    
    def __init__(self):
        """Initialize Google Sheets client"""
        self.scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        self.client = self._authenticate()
        self.spreadsheet = None
    
    def _authenticate(self):
        """Authenticate with Google Sheets API using OAuth2 (same as main app)"""
        try:
            creds = None
            
            # Load existing token if available
            if Path(MigrationConfig.TOKEN_FILE).exists():
                print(f"🔐 Loading existing token from {MigrationConfig.TOKEN_FILE}")
                with open(MigrationConfig.TOKEN_FILE, 'r') as token:
                    token_data = json.load(token)
                    creds = Credentials(
                        token=token_data.get('token'),
                        refresh_token=token_data.get('refresh_token'),
                        token_uri=token_data.get('token_uri'),
                        client_id=token_data.get('client_id'),
                        client_secret=token_data.get('client_secret'),
                        scopes=self.scopes
                    )
            
            # If no valid credentials, do OAuth flow
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    print("🔄 Refreshing expired token...")
                    creds.refresh(Request())
                else:
                    if not Path(MigrationConfig.CREDENTIALS_FILE).exists():
                        raise ValueError(
                            f"\n❌ {MigrationConfig.CREDENTIALS_FILE} not found!\n\n"
                            "Please ensure credentials.json exists in the project root.\n"
                            "This is the OAuth2 client secrets file from Google Cloud Console."
                        )
                    
                    print(f"🔐 Starting OAuth2 flow with {MigrationConfig.CREDENTIALS_FILE}")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        MigrationConfig.CREDENTIALS_FILE,
                        self.scopes
                    )
                    creds = flow.run_local_server(port=0)
                    
                    # Save token for future use
                    print(f"💾 Saving token to {MigrationConfig.TOKEN_FILE}")
                    with open(MigrationConfig.TOKEN_FILE, 'w') as token:
                        token.write(creds.to_json())
            
            return gspread.authorize(creds)
        
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            raise
    
    def create_spreadsheet(self, name: str):
        """Create new spreadsheet"""
        print(f"📊 Creating spreadsheet: {name}")
        
        try:
            # Check if spreadsheet already exists
            try:
                self.spreadsheet = self.client.open(name)
                print(f"✅ Found existing spreadsheet: {name}")
                
                user_input = input("⚠️  Spreadsheet exists. Overwrite? (yes/no): ")
                if user_input.lower() != 'yes':
                    print("❌ Migration cancelled")
                    return None
                
                # Clear existing sheets except first one
                for sheet in self.spreadsheet.worksheets()[1:]:
                    self.spreadsheet.del_worksheet(sheet)
                
            except gspread.exceptions.SpreadsheetNotFound:
                # Create new spreadsheet
                self.spreadsheet = self.client.create(name)
                print(f"✅ Created new spreadsheet: {name}")
            
            # Share with specified users
            if MigrationConfig.SHARE_WITH:
                for email in MigrationConfig.SHARE_WITH:
                    email = email.strip()
                    if email:
                        self.spreadsheet.share(email, perm_type='user', role='writer')
                        print(f"📧 Shared with: {email}")
            
            return self.spreadsheet
        
        except Exception as e:
            print(f"❌ Error creating spreadsheet: {e}")
            raise
    
    def create_sheet(self, name: str, rows: int = 1000, cols: int = 26):
        """Create worksheet in spreadsheet"""
        print(f"📄 Creating sheet: {name}")
        
        try:
            # Check if sheet exists
            try:
                sheet = self.spreadsheet.worksheet(name)
                self.spreadsheet.del_worksheet(sheet)
            except gspread.exceptions.WorksheetNotFound:
                pass
            
            # Create new sheet
            sheet = self.spreadsheet.add_worksheet(
                title=name,
                rows=rows,
                cols=cols
            )
            
            print(f"✅ Created sheet: {name}")
            return sheet
        
        except Exception as e:
            print(f"❌ Error creating sheet: {e}")
            raise
    
    def setup_paper_trades_sheet(self, df: pd.DataFrame):
        """Setup Paper_Trades sheet with data and formulas"""
        print("\n📊 Setting up Paper_Trades sheet...")
        
        sheet = self.create_sheet(
            MigrationConfig.TRADES_SHEET,
            rows=max(1000, len(df) + 100),
            cols=30
        )
        
        # Define headers with proper order
        headers = [
            'trade_id', 'symbol', 'entry_date', 'entry_price', 'shares', 
            'position_value', 'stop_loss', 'target', 'max_holding_days',
            'trend_state', 'entry_state', 'rs_state', 'behavior', 
            'market_state', 'fundamental_state',
            'status', 'exit_date', 'exit_price', 'exit_reason', 'outcome',
            'pnl', 'pnl_pct', 'holding_days', 'mfe', 'mae', 'notes',
            'created_at', 'updated_at'
        ]
        
        # Add headers
        sheet.update(values=[headers], range_name='A1:AB1')
        
        # Format header row
        sheet.format('A1:AB1', {
            'backgroundColor': {'red': 0.2, 'green': 0.3, 'blue': 0.4},
            'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
            'horizontalAlignment': 'CENTER'
        })
        
        # Freeze header row
        sheet.freeze(rows=1)
        
        # Add data if exists
        if not df.empty:
            print(f"📥 Migrating {len(df)} trades...")
            
            # Prepare data
            data = []
            for _, row in df.iterrows():
                row_data = []
                for col in headers:
                    value = row.get(col, '')
                    
                    # Handle timestamps
                    if col in ['entry_date', 'exit_date', 'created_at', 'updated_at']:
                        if pd.notna(value):
                            if isinstance(value, pd.Timestamp):
                                value = value.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Handle NaN
                    if pd.isna(value):
                        value = ''
                    
                    row_data.append(value)
                
                data.append(row_data)
            
            # Batch update
            if data:
                sheet.update(values=data, range_name=f'A2:AB{len(data)+1}')
                print(f"✅ Migrated {len(data)} rows")
        
        # Add formulas for auto-calculated columns
        print("⚙️ Adding formulas...")
        
        # Note: Using R1C1 notation for formulas
        # Formula for pnl_pct (if not already calculated)
        # =IF(R="""", """", (R-D)/D*100) where R=exit_price, D=entry_price
        
        # Add conditional formatting for status
        sheet.format('P2:P1000', {
            'backgroundColor': {
                'red': 0.8,
                'green': 0.9,
                'blue': 0.8
            }
        })
        
        # Add data validation for status column
        from gspread_formatting import DataValidationRule, BooleanCondition
        
        validation_rule = DataValidationRule(
            BooleanCondition('ONE_OF_LIST', ['OPEN', 'CLOSED']),
            showCustomUi=True
        )
        
        print("✅ Paper_Trades sheet setup complete")
        return sheet
    
    def setup_analysis_log_sheet(self, df: pd.DataFrame):
        """Setup Analysis_Log sheet"""
        print("\n📊 Setting up Analysis_Log sheet...")
        
        sheet = self.create_sheet(
            MigrationConfig.ANALYSIS_SHEET,
            rows=max(2000, len(df) + 100),
            cols=25
        )
        
        # Headers
        headers = [
            'timestamp', 'date', 'symbol', 'market_state', 
            'fundamental_state', 'fundamental_score',
            'fund_eps_growth', 'fund_pe_reasonable', 'fund_debt_acceptable',
            'fund_roe_strong', 'fund_cashflow_positive',
            'trend_state', 'entry_state', 'rs_state', 'rs_value', 'behavior',
            'trade_eligible', 'rejection_reasons', 'close', 'rsi', 'consecutive_bars'
        ]
        
        # Add headers
        sheet.update(values=[headers], range_name='A1:U1')
        
        # Format header
        sheet.format('A1:U1', {
            'backgroundColor': {'red': 0.2, 'green': 0.3, 'blue': 0.4},
            'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
            'horizontalAlignment': 'CENTER'
        })
        
        sheet.freeze(rows=1)
        
        # Add data
        if not df.empty:
            print(f"📥 Migrating {len(df)} analysis logs...")
            
            # Add timestamp column if missing
            if 'timestamp' not in df.columns:
                df['timestamp'] = datetime.now().isoformat()
            
            data = []
            for _, row in df.iterrows():
                row_data = []
                for col in headers:
                    value = row.get(col, '')
                    
                    # Handle timestamps
                    if col in ['timestamp', 'date']:
                        if pd.notna(value):
                            if isinstance(value, pd.Timestamp):
                                value = value.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Handle boolean strings from CSV
                    if col.startswith('fund_'):
                        if value == 'None':
                            value = 'N/A'
                        elif value in ['True', 'TRUE', 'true']:
                            value = 'TRUE'
                        elif value in ['False', 'FALSE', 'false']:
                            value = 'FALSE'
                    
                    # Handle NaN
                    if pd.isna(value):
                        value = ''
                    
                    row_data.append(value)
                
                data.append(row_data)
            
            if data:
                sheet.update(values=data, range_name=f'A2:U{len(data)+1}')
                print(f"✅ Migrated {len(data)} rows")
        
        print("✅ Analysis_Log sheet setup complete")
        return sheet
    
    def setup_dashboard_sheet(self):
        """Setup Dashboard sheet with formulas"""
        print("\n📊 Setting up Dashboard sheet...")
        
        sheet = self.create_sheet(MigrationConfig.DASHBOARD_SHEET, rows=50, cols=10)
        
        # Dashboard structure
        dashboard_data = [
            ['Metric', 'Value', '', 'Formula'],
            ['', '', '', ''],
            ['TRADE STATISTICS', '', '', ''],
            ['Total Trades', '=COUNTA(Paper_Trades!A:A)-1', '', 'Count of all trades'],
            ['Open Trades', '=COUNTIF(Paper_Trades!P:P,"OPEN")', '', 'Currently open positions'],
            ['Closed Trades', '=COUNTIF(Paper_Trades!P:P,"CLOSED")', '', 'Completed trades'],
            ['', '', '', ''],
            ['PERFORMANCE METRICS', '', '', ''],
            ['Win Count', '=COUNTIF(Paper_Trades!T:T,"WIN")', '', 'Number of wins'],
            ['Loss Count', '=COUNTIF(Paper_Trades!T:T,"LOSS")', '', 'Number of losses'],
            ['No-Move Count', '=COUNTIF(Paper_Trades!T:T,"NO-MOVE")', '', 'Breakeven trades'],
            ['Win Rate %', '=IF(B5=0,0,B9/B5*100)', '', 'Win percentage'],
            ['', '', '', ''],
            ['P&L ANALYSIS', '', '', ''],
            ['Total P&L', '=SUM(Paper_Trades!U:U)', '', 'Sum of all P&L'],
            ['Avg P&L %', '=AVERAGE(Paper_Trades!V:V)', '', 'Average P&L percentage'],
            ['Best Trade %', '=MAX(Paper_Trades!V:V)', '', 'Maximum gain'],
            ['Worst Trade %', '=MIN(Paper_Trades!V:V)', '', 'Maximum loss'],
            ['Avg Win %', '=AVERAGEIF(Paper_Trades!T:T,"WIN",Paper_Trades!V:V)', '', 'Average winning trade'],
            ['Avg Loss %', '=AVERAGEIF(Paper_Trades!T:T,"LOSS",Paper_Trades!V:V)', '', 'Average losing trade'],
            ['', '', '', ''],
            ['HOLDING PERIOD', '', '', ''],
            ['Avg Holding Days', '=AVERAGE(Paper_Trades!W:W)', '', 'Average days in trade'],
            ['', '', '', ''],
            ['EXIT ANALYSIS', '', '', ''],
            ['Stop Loss Exits', '=COUNTIF(Paper_Trades!S:S,"STOP_LOSS")', '', ''],
            ['Target Exits', '=COUNTIF(Paper_Trades!S:S,"TARGET_HIT")', '', ''],
            ['Behavior Exits', '=COUNTIF(Paper_Trades!S:S,"BEHAVIOR_FAILURE")', '', ''],
            ['Time Exits', '=COUNTIF(Paper_Trades!S:S,"MAX_HOLDING_DAYS")', '', ''],
            ['', '', '', ''],
            ['RISK METRICS', '', '', ''],
            ['Avg MFE %', '=AVERAGE(Paper_Trades!X:X)', '', 'Avg max favorable excursion'],
            ['Avg MAE %', '=AVERAGE(Paper_Trades!Y:Y)', '', 'Avg max adverse excursion'],
            ['', '', '', ''],
            ['Last Updated', f'=NOW()', '', 'Auto-updated timestamp'],
        ]
        
        # Write dashboard
        sheet.update(values=dashboard_data, range_name=f'A1:D{len(dashboard_data)}')
        
        # Format dashboard
        sheet.format('A1:D1', {
            'backgroundColor': {'red': 0.2, 'green': 0.3, 'blue': 0.4},
            'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
            'horizontalAlignment': 'CENTER'
        })
        
        # Format section headers
        section_rows = [3, 8, 14, 22, 25, 30]
        for row in section_rows:
            sheet.format(f'A{row}:D{row}', {
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9},
                'textFormat': {'bold': True}
            })
        
        # Format metrics column
        sheet.format('A:A', {'textFormat': {'bold': True}})
        
        # Format values column (numbers)
        sheet.format('B:B', {
            'horizontalAlignment': 'RIGHT',
            'numberFormat': {'type': 'NUMBER', 'pattern': '#,##0.00'}
        })
        
        # Freeze header
        sheet.freeze(rows=1)
        
        # Set column widths
        sheet.update_dimensions_request = {
            'updateDimensionProperties': {
                'range': {'dimension': 'COLUMNS', 'startIndex': 0, 'endIndex': 1},
                'properties': {'pixelSize': 200}
            }
        }
        
        print("✅ Dashboard sheet setup complete")
        return sheet
    
    def setup_config_sheet(self):
        """Setup Config sheet with system settings"""
        print("\n📊 Setting up Config sheet...")
        
        sheet = self.create_sheet(MigrationConfig.CONFIG_SHEET, rows=30, cols=5)
        
        config_data = [
            ['Parameter', 'Value', 'Description', 'Editable'],
            ['', '', '', ''],
            ['TRADING RULES', '', '', ''],
            ['Position Size', '100000', 'Default position value (₹)', 'YES'],
            ['Stop Loss %', '5', 'Stop loss percentage', 'NO'],
            ['Target %', '10', 'Profit target percentage', 'NO'],
            ['Max Holding Days', '10', 'Maximum days in trade', 'NO'],
            ['', '', '', ''],
            ['ENTRY CRITERIA', '', '', ''],
            ['Fundamental Required', 'PASS or NEUTRAL', 'Minimum fundamental state', 'NO'],
            ['Trend Required', 'STRONG', 'Required trend state', 'NO'],
            ['Entry Required', 'OK', 'Required entry state', 'NO'],
            ['RS Required', 'STRONG', 'Required relative strength', 'NO'],
            ['Behavior Required', 'CONTINUATION', 'Required behavior state', 'NO'],
            ['', '', '', ''],
            ['EXIT PRIORITY', '', '', ''],
            ['Priority 1', 'STOP_LOSS', '-5%', 'NO'],
            ['Priority 2', 'TARGET_HIT', '+10%', 'NO'],
            ['Priority 3', 'BEHAVIOR_FAILURE', 'Distribution detected', 'NO'],
            ['Priority 4', 'MAX_HOLDING_DAYS', '10 days', 'NO'],
            ['', '', '', ''],
            ['SYSTEM INFO', '', '', ''],
            ['Version', '2.0', 'System version', 'NO'],
            ['Storage', 'Google Sheets', 'Storage backend', 'NO'],
            ['Discipline Lock', 'ACTIVE', 'Rules locked until 30 trades', 'NO'],
            ['', '', '', ''],
            ['API SETTINGS', '', '', ''],
            ['API Key', 'SET_IN_APPS_SCRIPT', 'Authentication key', 'YES'],
            ['Web App URL', 'DEPLOY_APPS_SCRIPT', 'Apps Script endpoint', 'YES'],
        ]
        
        sheet.update(values=config_data, range_name=f'A1:D{len(config_data)}')
        
        # Format
        sheet.format('A1:D1', {
            'backgroundColor': {'red': 0.2, 'green': 0.3, 'blue': 0.4},
            'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
            'horizontalAlignment': 'CENTER'
        })
        
        section_rows = [3, 9, 16, 22, 27]
        for row in section_rows:
            sheet.format(f'A{row}:D{row}', {
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9},
                'textFormat': {'bold': True}
            })
        
        print("✅ Config sheet setup complete")
        return sheet


# ═══════════════════════════════════════════════════════════════════════════
# MAIN MIGRATION FUNCTION
# ═══════════════════════════════════════════════════════════════════════════

def migrate_csv_to_sheets():
    """Main migration function"""
    
    print("="*80)
    print("🚀 CSV TO GOOGLE SHEETS MIGRATION")
    print("="*80)
    print()
    
    # Step 1: Load CSV files
    print("📂 Loading CSV files...")
    
    trades_df = pd.DataFrame()
    analysis_df = pd.DataFrame()
    
    if Path(MigrationConfig.PAPER_TRADES_CSV).exists():
        trades_df = pd.read_csv(MigrationConfig.PAPER_TRADES_CSV)
        print(f"✅ Loaded {len(trades_df)} trades from {MigrationConfig.PAPER_TRADES_CSV}")
    else:
        print(f"⚠️  No trades CSV found at {MigrationConfig.PAPER_TRADES_CSV}")
    
    if Path(MigrationConfig.ANALYSIS_LOG_CSV).exists():
        analysis_df = pd.read_csv(MigrationConfig.ANALYSIS_LOG_CSV)
        print(f"✅ Loaded {len(analysis_df)} analysis logs from {MigrationConfig.ANALYSIS_LOG_CSV}")
    else:
        print(f"⚠️  No analysis log CSV found at {MigrationConfig.ANALYSIS_LOG_CSV}")
    
    print()
    
    # Step 2: Initialize Sheets Manager
    print("🔐 Authenticating with Google Sheets...")
    manager = SheetsManager()
    print()
    
    # Step 3: Create spreadsheet
    spreadsheet = manager.create_spreadsheet(MigrationConfig.SHEET_NAME)
    if not spreadsheet:
        return
    
    print()
    
    # Step 4: Setup sheets
    manager.setup_paper_trades_sheet(trades_df)
    manager.setup_analysis_log_sheet(analysis_df)
    manager.setup_dashboard_sheet()
    manager.setup_config_sheet()
    
    # Step 5: Print success
    print()
    print("="*80)
    print("✅ MIGRATION COMPLETE!")
    print("="*80)
    print()
    print(f"📊 Spreadsheet URL:")
    print(f"   {spreadsheet.url}")
    print()
    print(f"📝 Next Steps:")
    print(f"   1. Open the spreadsheet above")
    print(f"   2. Go to Extensions → Apps Script")
    print(f"   3. Paste the Apps Script code (see setup guide)")
    print(f"   4. Deploy as Web App")
    print(f"   5. Copy deployment URL to .env as APPS_SCRIPT_URL")
    print(f"   6. Update your Python code to use SheetsStorageManager")
    print()
    print(f"💾 Migrated Data:")
    print(f"   - Paper Trades: {len(trades_df)} rows")
    print(f"   - Analysis Log: {len(analysis_df)} rows")
    print()
    print(f"📋 Sheets Created:")
    print(f"   - Paper_Trades (main data)")
    print(f"   - Analysis_Log (history)")
    print(f"   - Dashboard (auto-calculated metrics)")
    print(f"   - Config (system settings)")
    print()


if __name__ == "__main__":
    try:
        migrate_csv_to_sheets()
    except KeyboardInterrupt:
        print("\n\n❌ Migration cancelled by user")
    except Exception as e:
        print(f"\n\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()