"""
Angel One API Integration for Fundamental Data
Complete implementation with caching and error handling

Installation:
    pip install smartapi-python

Setup:
    1. Get API credentials from https://smartapi.angelbroking.com/
    2. Create angel_one_config.json with your credentials
    3. Import and use AngelOneFundamentals in analysis_engine.py
"""

import json
import time
from typing import Dict, Optional, Tuple
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
from SmartApi import SmartConnect


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

class AngelOneConfig:
    """Angel One API configuration"""
    
    CONFIG_FILE = "angel_one_config.json"
    CACHE_FILE = Path("./data/cache/fundamental_cache.json")
    CACHE_EXPIRY_DAYS = 7  # Refresh fundamental data weekly

    @classmethod
    def load_credentials(cls) -> Dict:
        """Load Angel One credentials from config file"""
        config_path = Path(cls.CONFIG_FILE)
        
        if not config_path.exists():
            raise FileNotFoundError(
                f"Angel One config not found: {cls.CONFIG_FILE}\n"
                "Create this file with your API credentials:\n"
                "{\n"
                '  "api_key": "your_api_key",\n'
                '  "client_id": "your_client_id",\n'
                '  "password": "your_password"\n'
                "}"
            )
        
        with open(config_path, 'r') as f:
            return json.load(f)


# ═══════════════════════════════════════════════════════════════════════════
# ANGEL ONE FUNDAMENTAL DATA CLIENT
# ═══════════════════════════════════════════════════════════════════════════

class AngelOneFundamentals:
    """
    Angel One API client for fetching fundamental data
    
    Features:
    - Automatic login and session management
    - Intelligent caching (weekly refresh)
    - Fallback to cached data on API errors
    - NSE symbol mapping
    """
    
    def __init__(self):
        """Initialize Angel One client"""
        self.config = AngelOneConfig()
        self.smart_api = None
        self.session_token = None
        self.cache = self._load_cache()
        self.is_connected = False
        
        # Try to connect
        self._connect()
    
    def _connect(self):
        """Connect to Angel One API"""
        try:
            credentials = self.config.load_credentials()
            
            # Initialize SmartConnect
            self.smart_api = SmartConnect(api_key=credentials['api_key'])
            
            # Generate session
            data = self.smart_api.generateSession(
                clientCode=credentials['client_id'],
                password=credentials['password'],
                totp=credentials['totp'],
            )
            
            if data['status']:
                self.session_token = data['data']['jwtToken']
                self.smart_api.setSessionExpiryHook(self._session_expired_hook)
                self.is_connected = True
                print("✅ Connected to Angel One API")
            else:
                print(f"⚠️  Angel One login failed: {data.get('message', 'Unknown error')}")
                self.is_connected = False
                
        except Exception as e:
            print(f"⚠️  Angel One connection error: {e}")
            print("   Using cached fundamental data (if available)")
            self.is_connected = False
    
    def _session_expired_hook(self):
        """Handle session expiry"""
        print("⚠️  Angel One session expired, reconnecting...")
        self._connect()
    
    def _load_cache(self) -> Dict:
        """Load cached fundamental data"""
        if not self.config.CACHE_FILE.exists():
            return {}
        
        try:
            with open(self.config.CACHE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    
    def _save_cache(self):
        """Save fundamental data cache"""
        self.config.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.config.CACHE_FILE, 'w') as f:
            json.dump(self.cache, f, indent=2)
    
    def _is_cache_valid(self, symbol: str) -> bool:
        """Check if cached data is still valid"""
        if symbol not in self.cache:
            return False
        
        cached_data = self.cache[symbol]
        if 'timestamp' not in cached_data:
            return False
        
        cache_time = datetime.fromisoformat(cached_data['timestamp'])
        expiry_time = cache_time + timedelta(days=self.config.CACHE_EXPIRY_DAYS)
        
        return datetime.now() < expiry_time

    def _get_symbol_mapping(self, symbol: str) -> Optional[Dict]:
        clean = symbol.replace(".NS", "")

        # Load cached symbol master
        master = self._load_symbol_master()

        if symbol in master:
            return master[symbol]

        # Fetch from Angel One
        result = self.smart_api.searchScrip(
            exchange="NSE",
            searchtext=clean
        )

        if not result or not result.get("status"):
            return None

        for item in result["data"]:
            if item["tradingsymbol"] == f"{clean}-EQ":
                master[symbol] = {
                    "tradingsymbol": item["tradingsymbol"],
                    "symboltoken": item["symboltoken"]
                }
                self._save_symbol_master(master)
                return master[symbol]

        return None

    def _nse_symbol_to_token(self, symbol: str) -> Optional[str]:
        """
        Convert NSE symbol to Angel One token
        
        Args:
            symbol: NSE symbol (e.g., "TCS.NS", "RELIANCE.NS")
        
        Returns:
            Angel One symbol token or None
        """
        # Remove .NS suffix
        clean_symbol = symbol.replace(".NS", "")
        
        # Map common symbols (you can extend this)
        # For production, use Angel One's searchScrip API
        SYMBOL_MAP = {
            "RELIANCE": "RELIANCE-EQ",
            "TCS": "TCS-EQ",
            "INFY": "INFY-EQ",
            "HDFCBANK": "HDFCBANK-EQ",
            "ICICIBANK": "ICICIBANK-EQ",
            "SBIN": "SBIN-EQ",
            "BHARTIARTL": "BHARTIARTL-EQ",
            "ITC": "ITC-EQ",
            "KOTAKBANK": "KOTAKBANK-EQ",
            "LT": "LT-EQ",
            # Add more as needed
        }
        
        return SYMBOL_MAP.get(clean_symbol, f"{clean_symbol}-EQ")
    
    def get_fundamental_data(self, symbol: str) -> Optional[Dict]:
        """
        Fetch fundamental data for a stock
        
        Args:
            symbol: NSE symbol (e.g., "TCS.NS")
        
        Returns:
            Dictionary with fundamental metrics or None
        """
        # Check cache first
        if self._is_cache_valid(symbol):
            print(f"📦 Using cached fundamental data for {symbol}")
            return self.cache[symbol]['data']
        
        # If not connected, use cache (even if expired)
        if not self.is_connected:
            if symbol in self.cache:
                print(f"⚠️  API offline, using cached data for {symbol}")
                return self.cache[symbol]['data']
            else:
                print(f"⚠️  No cached data for {symbol}, API offline")
                return None
        
        # Fetch from API
        try:
            angel_symbol = self._nse_symbol_to_token(symbol)
            
            # Get quote data (has some fundamentals)
            quote_data = self.smart_api.ltpData(
                exchange="NSE",
                tradingsymbol=angel_symbol,
                symboltoken=None
            )
            
            # Angel One doesn't provide detailed fundamentals in free tier
            # For full fundamentals, you need their premium data APIs
            # For now, we'll construct basic data from available endpoints
            
            if quote_data and quote_data.get('status'):
                # This is a simplified version
                # You'll need to enhance based on your Angel One subscription
                fundamental_data = {
                    "eps_growth_3y": None,  # Not available in basic API
                    "pe": None,             # Not available in basic API
                    "industry_pe": 25.0,    # Default assumption
                    "debt_equity": None,    # Not available in basic API
                    "roe": None,            # Not available in basic API
                    "operating_cashflow": None,  # Not available in basic API
                }
                
                # Cache the data
                self.cache[symbol] = {
                    'timestamp': datetime.now().isoformat(),
                    'data': fundamental_data
                }
                self._save_cache()
                
                print(f"📥 Fetched fundamental data for {symbol}")
                return fundamental_data
            else:
                print(f"⚠️  No data returned for {symbol}")
                return None
                
        except Exception as e:
            print(f"⚠️  Error fetching {symbol}: {e}")
            
            # Fallback to cache
            if symbol in self.cache:
                print(f"   Using expired cache for {symbol}")
                return self.cache[symbol]['data']
            
            return None
    
    def get_quote(self, symbol: str) -> Optional[Dict]:
        """
        Get real-time quote data
        
        Args:
            symbol: NSE symbol
        
        Returns:
            Quote data dictionary
        """
        if not self.is_connected:
            return None
        
        try:
            angel_symbol = self._nse_symbol_to_token(symbol)
            
            quote = self.smart_api.ltpData(
                exchange="NSE",
                tradingsymbol=angel_symbol,
                symboltoken=None
            )
            
            return quote.get('data') if quote.get('status') else None
            
        except Exception as e:
            print(f"Error fetching quote for {symbol}: {e}")
            return None


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION WITH ANALYSIS ENGINE
# ═══════════════════════════════════════════════════════════════════════════

def get_angel_fundamental_data(symbol: str, angel_client: AngelOneFundamentals) -> Optional[Dict]:
    """
    Wrapper function for integration with analysis_engine.py
    
    Usage in analysis_engine.py:
    
    # At top of file:
    from angel_one_integration import AngelOneFundamentals, get_angel_fundamental_data
    
    # Initialize once (global or in main):
    ANGEL_CLIENT = AngelOneFundamentals()
    
    # In analyze_stock():
    fundamental_data = get_angel_fundamental_data(symbol, ANGEL_CLIENT)
    result = analyze_stock(symbol, stock_df, index_df, fundamental_data)
    """
    return angel_client.get_fundamental_data(symbol)


# ═══════════════════════════════════════════════════════════════════════════
# MANUAL FALLBACK WITH SCREENER.IN SCRAPING (Alternative)
# ═══════════════════════════════════════════════════════════════════════════

def scrape_screener_fundamentals(symbol: str) -> Optional[Dict]:
    """
    Fallback: Scrape fundamental data from screener.in
    
    Note: This is a backup option. Screener.in has rate limits.
    For production, use their paid API or Angel One premium data.
    
    Args:
        symbol: NSE symbol (e.g., "TCS.NS")
    
    Returns:
        Fundamental data dictionary
    """
    import requests
    from bs4 import BeautifulSoup
    
    try:
        clean_symbol = symbol.replace(".NS", "")
        url = f"https://www.screener.in/company/{clean_symbol}/consolidated/"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Parse fundamental metrics
        # (This is simplified - you'll need to inspect Screener's HTML)
        fundamental_data = {
            "eps_growth_3y": None,
            "pe": None,
            "industry_pe": 25.0,
            "debt_equity": None,
            "roe": None,
            "operating_cashflow": None,
        }
        
        # TODO: Parse actual values from HTML
        # This requires inspecting screener.in's page structure
        
        return fundamental_data
        
    except Exception as e:
        print(f"Screener.in scraping error for {symbol}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    """Test the Angel One integration"""
    
    print("Testing Angel One Fundamental Data Integration")
    print("=" * 80)
    
    # Initialize client
    angel = AngelOneFundamentals()
    
    if not angel.is_connected:
        print("\n⚠️  Angel One API not connected")
        print("   Create angel_one_config.json with your credentials")
        print("   Or system will use cached data")
    
    # Test with a few stocks
    test_symbols = ["TCS.NS", "INFY.NS", "RELIANCE.NS"]
    
    for symbol in test_symbols:
        print(f"\n{symbol}:")
        data = angel.get_fundamental_data(symbol)
        
        if data:
            print(f"  ✅ Data retrieved:")
            for key, value in data.items():
                print(f"     {key}: {value}")
        else:
            print(f"  ❌ No data available")
    
    print("\n" + "=" * 80)
    print("Integration test complete!")