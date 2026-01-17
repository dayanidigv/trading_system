"""
Diagnostic Script - Verify Fundamental Data Flow
Run this to check if fundamental data is flowing correctly through the system

Usage:
    python diagnostic_fundamental_flow.py
"""

import pandas as pd
from pathlib import Path
from storage_manager import StorageManager

def diagnose_fundamental_data():
    """Check fundamental data in analysis log"""
    
    print("=" * 80)
    print("FUNDAMENTAL DATA FLOW DIAGNOSTIC")
    print("=" * 80)
    
    # Initialize storage
    storage = StorageManager(use_drive=False)  # Check local only
    
    # Load analysis log
    print("\n1. Loading analysis log...")
    analysis_df = storage.load_analysis_log()
    
    if analysis_df.empty:
        print("   ❌ Analysis log is empty - no data to check")
        print("   → Run stock analysis first to generate data")
        return
    
    print(f"   ✅ Found {len(analysis_df)} analysis entries")
    
    # Check columns
    print("\n2. Checking for fundamental columns...")
    fund_cols = [
        'fund_eps_growth', 
        'fund_pe_reasonable', 
        'fund_debt_acceptable', 
        'fund_roe_strong', 
        'fund_cashflow_positive'
    ]
    
    existing_cols = [col for col in fund_cols if col in analysis_df.columns]
    missing_cols = [col for col in fund_cols if col not in analysis_df.columns]
    
    if existing_cols:
        print(f"   ✅ Found {len(existing_cols)} fundamental columns:")
        for col in existing_cols:
            print(f"      - {col}")
    
    if missing_cols:
        print(f"   ⚠️  Missing {len(missing_cols)} fundamental columns:")
        for col in missing_cols:
            print(f"      - {col}")
        print("   → This is expected if using old analysis data")
    
    if not existing_cols:
        print("   ❌ No fundamental columns found")
        return
    
    # Check values
    print("\n3. Analyzing fundamental check values...")
    
    for col in existing_cols:
        print(f"\n   {col}:")
        value_counts = analysis_df[col].value_counts()
        
        for value, count in value_counts.items():
            print(f"      '{value}': {count} ({count/len(analysis_df)*100:.1f}%)")
    
    # Check fundamental_state distribution
    print("\n4. Fundamental state distribution:")
    if 'fundamental_state' in analysis_df.columns:
        state_counts = analysis_df['fundamental_state'].value_counts()
        for state, count in state_counts.items():
            print(f"   {state}: {count} ({count/len(analysis_df)*100:.1f}%)")
    else:
        print("   ❌ No 'fundamental_state' column found")
    
    # Check fundamental_score
    print("\n5. Fundamental score statistics:")
    if 'fundamental_score' in analysis_df.columns:
        scores = analysis_df['fundamental_score']
        print(f"   Mean: {scores.mean():.1f}")
        print(f"   Min: {scores.min():.1f}")
        print(f"   Max: {scores.max():.1f}")
        print(f"   Unique values: {scores.nunique()}")
        
        if scores.nunique() == 1:
            print(f"   ⚠️  All scores are identical ({scores.iloc[0]:.1f})")
            print("   → This indicates no real fundamental data is available")
    else:
        print("   ❌ No 'fundamental_score' column found")
    
    # Recommendations
    print("\n" + "=" * 80)
    print("INTERPRETATION:")
    print("=" * 80)
    
    # Count None values
    none_counts = {}
    for col in existing_cols:
        none_count = (analysis_df[col] == 'None').sum()
        none_counts[col] = none_count
    
    total_none = sum(none_counts.values())
    total_checks = len(existing_cols) * len(analysis_df)
    
    if total_none == total_checks:
        print("\n✅ WORKING AS DESIGNED:")
        print("   - All fundamental checks show 'None' (no data available)")
        print("   - System correctly records missing fundamental data")
        print("   - Fundamental state defaulting to NEUTRAL (60%)")
        print("   - This is EXPECTED behavior when no fundamental source is connected")
        print("\nTO ENABLE REAL FUNDAMENTAL DATA:")
        print("   1. Integrate screener.in API")
        print("   2. Create manual whitelist in analyze_fundamentals()")
        print("   3. Connect to broker fundamental endpoints")
        print("   → See analysis_engine.py, analyze_fundamentals() function")
    
    elif total_none > 0:
        print("\n⚠️  PARTIAL DATA:")
        print(f"   - {total_none}/{total_checks} checks have 'None' values")
        print("   - Some fundamental data is available, some is missing")
        print("   → Check your fundamental data source integration")
    
    else:
        print("\n✅ FULL DATA:")
        print("   - All fundamental checks have valid True/False values")
        print("   - Fundamental data source is working correctly")
    
    # Sample data
    print("\n" + "=" * 80)
    print("SAMPLE DATA (first 3 rows):")
    print("=" * 80)
    
    display_cols = ['symbol', 'fundamental_state', 'fundamental_score'] + existing_cols
    display_cols = [col for col in display_cols if col in analysis_df.columns]
    
    print(analysis_df[display_cols].head(3).to_string(index=False))
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    diagnose_fundamental_data()
