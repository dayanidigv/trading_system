"""
Test Google Drive Connection
Run this to verify your Drive setup is working correctly
"""

import pandas as pd
from datetime import datetime
from storage_manager import StorageManager, DRIVE_AVAILABLE
import sys


def print_section(title):
    """Print formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_dependencies():
    """Test if required packages are installed"""
    print_section("Step 1: Testing Dependencies")
    
    if not DRIVE_AVAILABLE:
        print("❌ Google Drive libraries not installed!")
        print("\nPlease run:")
        print("  pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
        return False
    
    print("✅ All required packages installed")
    return True


def test_initialization():
    """Test storage manager initialization"""
    print_section("Step 2: Initializing Storage Manager")
    
    try:
        storage = StorageManager(use_drive=True)
        
        if not storage.use_drive:
            print("⚠️  Drive initialization failed - falling back to local storage")
            print("\nPossible issues:")
            print("  - credentials.json file missing or invalid")
            print("  - Google Drive API not enabled")
            print("  - Network connectivity issue")
            return None
        
        print(f"✅ Connected to Google Drive")
        print(f"   Folder: {storage.config.DRIVE_FOLDER_NAME}")
        print(f"   Folder ID: {storage.folder_id}")
        
        return storage
        
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return None


def test_storage_info(storage):
    """Test getting storage information"""
    print_section("Step 3: Checking Storage Status")
    
    try:
        info = storage.get_storage_info()
        
        print(f"Storage Mode: {info['storage_mode']}")
        print(f"Drive Connected: {info['drive_connected']}")
        print(f"Drive Folder: {info['drive_folder']}")
        print(f"Local Cache: {info['local_cache_dir']}")
        print(f"\nCurrent Data:")
        print(f"  Total Trades: {info['total_trades']}")
        print(f"  Open Trades: {info['open_trades']}")
        print(f"  Closed Trades: {info['closed_trades']}")
        print(f"  Analysis Entries: {info['total_analyses']}")
        print(f"  Last Updated: {info['last_updated']}")
        
        if 'drive_files' in info and info['drive_files']:
            print(f"\nFiles in Drive:")
            for file in info['drive_files']:
                print(f"  - {file}")
        
        print("\n✅ Storage info retrieved successfully")
        return True
        
    except Exception as e:
        print(f"❌ Failed to get storage info: {e}")
        return False


def test_write_operation(storage):
    """Test writing data to Drive"""
    print_section("Step 4: Testing Write Operation")
    
    try:
        # Create test trade data
        test_trade = pd.DataFrame([{
            'trade_id': 'TEST_001',
            'symbol': 'TEST.NS',
            'entry_date': pd.Timestamp.now(),
            'entry_price': 100.0,
            'shares': 100,
            'position_value': 10000,
            'stop_loss': 95.0,
            'target': 110.0,
            'max_holding_days': 10,
            'trend_state': 'STRONG',
            'entry_state': 'OK',
            'rs_state': 'STRONG',
            'behavior': 'CONTINUATION',
            'market_state': 'RISK-ON',
            'fundamental_state': 'PASS',
            'status': 'OPEN',
            'exit_date': pd.NaT,
            'exit_price': None,
            'exit_reason': 'PENDING',
            'outcome': 'PENDING',
            'pnl': 0.0,
            'pnl_pct': 0.0,
            'holding_days': 0,
            'mfe': 0.0,
            'mae': 0.0,
            'notes': 'Test trade from setup verification'
        }])
        
        print("Writing test trade to storage...")
        success = storage.save_trades(test_trade)
        
        if success:
            print("✅ Write operation successful")
            print("   Test trade saved to Drive")
            return True
        else:
            print("❌ Write operation failed")
            return False
            
    except Exception as e:
        print(f"❌ Write test failed: {e}")
        return False


def test_read_operation(storage):
    """Test reading data from Drive"""
    print_section("Step 5: Testing Read Operation")
    
    try:
        print("Loading trades from storage...")
        trades_df = storage.load_trades()
        
        print(f"✅ Read operation successful")
        print(f"   Loaded {len(trades_df)} trade(s)")
        
        if not trades_df.empty:
            print("\nRecent trades:")
            display_cols = ['trade_id', 'symbol', 'entry_date', 'status']
            print(trades_df[display_cols].tail(5).to_string(index=False))
        
        return True
        
    except Exception as e:
        print(f"❌ Read test failed: {e}")
        return False


def test_analysis_log(storage):
    """Test analysis log operations"""
    print_section("Step 6: Testing Analysis Log")
    
    try:
        # Create test analysis log entry
        test_log = pd.DataFrame([{
            'date': pd.Timestamp.now(),
            'symbol': 'TEST.NS',
            'market_state': 'RISK-ON',
            'fundamental_state': 'PASS',
            'fundamental_score': 75.0,
            'trend_state': 'STRONG',
            'entry_state': 'OK',
            'rs_state': 'STRONG',
            'rs_value': 0.05,
            'behavior': 'CONTINUATION',
            'trade_eligible': True,
            'rejection_reasons': '',
            'close': 100.0,
            'rsi': 55.0,
            'consecutive_bars': 5
        }])
        
        print("Writing test analysis log...")
        success = storage.save_analysis_log(test_log)
        
        if not success:
            print("❌ Analysis log write failed")
            return False
        
        print("✅ Analysis log write successful")
        
        print("\nLoading analysis log...")
        log_df = storage.load_analysis_log()
        
        print(f"✅ Analysis log read successful")
        print(f"   Total entries: {len(log_df)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Analysis log test failed: {e}")
        return False


def test_cleanup(storage):
    """Optional: Clean up test data"""
    print_section("Step 7: Cleanup (Optional)")
    
    response = input("\nDo you want to remove test data? (y/n): ").strip().lower()
    
    if response == 'y':
        try:
            # Load existing trades
            trades_df = storage.load_trades()
            
            # Remove test trades
            if not trades_df.empty:
                clean_df = trades_df[~trades_df['trade_id'].str.startswith('TEST_')]
                storage.save_trades(clean_df)
                print(f"✅ Removed test trades")
            
            # Load existing log
            log_df = storage.load_analysis_log()
            
            # Remove test log entries
            if not log_df.empty:
                clean_log = log_df[log_df['symbol'] != 'TEST.NS']
                storage.save_analysis_log(clean_log)
                print(f"✅ Removed test log entries")
            
            print("\n✅ Cleanup complete")
            
        except Exception as e:
            print(f"⚠️  Cleanup error: {e}")
    else:
        print("Skipping cleanup - test data retained")


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("  GOOGLE DRIVE CONNECTION TEST")
    print("  Trading System Storage Verification")
    print("=" * 70)
    
    # Test 1: Dependencies
    if not test_dependencies():
        sys.exit(1)
    
    # Test 2: Initialization
    storage = test_initialization()
    if storage is None:
        print("\n" + "=" * 70)
        print("  SETUP INCOMPLETE")
        print("=" * 70)
        print("\nPlease complete these steps:")
        print("1. Place credentials.json in project root")
        print("2. Ensure Google Drive API is enabled")
        print("3. For service account: Share Drive folder with service account email")
        print("\nSee DRIVE_SETUP.md for detailed instructions")
        sys.exit(1)
    
    # Test 3: Storage info
    if not test_storage_info(storage):
        sys.exit(1)
    
    # Test 4: Write
    if not test_write_operation(storage):
        sys.exit(1)
    
    # Test 5: Read
    if not test_read_operation(storage):
        sys.exit(1)
    
    # Test 6: Analysis log
    if not test_analysis_log(storage):
        sys.exit(1)
    
    # Test 7: Cleanup
    test_cleanup(storage)
    
    # Success summary
    print("\n" + "=" * 70)
    print("  ✅ ALL TESTS PASSED!")
    print("=" * 70)
    print("\nYour Google Drive storage is fully configured and working.")
    print("\nNext steps:")
    print("1. Run your trading system: streamlit run main_app.py")
    print("2. All data will automatically sync to Google Drive")
    print("3. Check your Drive folder to see files appear")
    print("\nHappy trading! 🚀")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
