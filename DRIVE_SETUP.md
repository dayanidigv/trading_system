# Google Drive Storage Setup Guide

Complete guide to enable Google Drive as primary storage for your trading system.

---

## 📋 Overview

The system now uses **Google Drive as primary storage** with local caching for:
- ✅ **Cloud persistence** - Data accessible from any device
- ✅ **Automatic backup** - No manual file management
- ✅ **Offline capability** - Works with cached data if Drive unavailable
- ✅ **Version safety** - Always syncs latest state

---

## 🚀 Quick Start (Recommended Method)

### **Option A: Service Account (Best for Personal Use)**

**Step 1: Install Dependencies**
```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

**Step 2: Create Google Cloud Project**

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **"Create Project"**
3. Name it: `TradingSystem` (or any name)
4. Click **"Create"**

**Step 3: Enable Google Drive API**

1. In your project, go to **"APIs & Services" → "Library"**
2. Search for **"Google Drive API"**
3. Click on it and press **"Enable"**

**Step 4: Create Service Account**

1. Go to **"APIs & Services" → "Credentials"**
2. Click **"Create Credentials" → "Service Account"**
3. Name: `trading-storage`
4. Click **"Create and Continue"**
5. Skip optional fields, click **"Done"**

**Step 5: Download Credentials**

1. Click on the service account you just created
2. Go to **"Keys"** tab
3. Click **"Add Key" → "Create New Key"**
4. Choose **JSON**
5. Download and save as `credentials.json` in your project folder

**Step 6: Share Drive Folder with Service Account**

1. Open [Google Drive](https://drive.google.com)
2. The system will auto-create a folder named `TradingSystem_Data`
3. Right-click the folder → **"Share"**
4. Copy the service account email from credentials.json:
   - Look for `"client_email": "trading-storage@...iam.gserviceaccount.com"`
5. Paste this email in the share dialog
6. Give it **"Editor"** access
7. Click **"Share"**

**Step 7: Test Connection**

```bash
python test_drive.py
```

✅ **Done!** Your system now saves to Google Drive automatically.

---

## 🔧 Option B: OAuth (For Multiple Users)

If you want to use your personal Google account instead of a service account:

**Step 1-3:** Same as above (Create project, enable API)

**Step 4: Create OAuth Credentials**

1. Go to **"APIs & Services" → "Credentials"**
2. Click **"Create Credentials" → "OAuth Client ID"**
3. If prompted, configure consent screen:
   - User Type: **External**
   - App name: `Trading System`
   - User support email: Your email
   - Developer contact: Your email
   - Click **"Save and Continue"** through all steps
4. Back to credentials, choose:
   - Application type: **Desktop app**
   - Name: `Trading System Desktop`
5. Click **"Create"**
6. Download and save as `credentials.json`

**Step 5: First-Time Authorization**

```bash
python main_app.py
```

- Browser will open automatically
- Sign in with your Google account
- Click **"Allow"**
- Token saved to `token.json` (don't delete this!)

✅ **Done!** Future runs will use saved token.

---

## 📁 Project Structure

After setup, your folder should look like:

```
trading_system/
├── credentials.json          # Google credentials (DO NOT COMMIT)
├── token.json               # OAuth token (DO NOT COMMIT, only if using OAuth)
├── analysis_engine.py
├── paper_trade_engine.py
├── storage_manager.py
├── main_app.py
├── test_drive.py            # Test script (create this)
├── data/
│   └── cache/              # Local cache of Drive files
│       ├── paper_trades.csv
│       ├── analysis_log.csv
│       └── metadata.json
└── .gitignore              # Add credentials.json and token.json here
```

---

## 🧪 Testing Drive Connection

Create `test_drive.py`:

```python
"""Test Google Drive connection"""
from storage_manager import StorageManager
import pandas as pd

def test_drive():
    print("Initializing storage manager...")
    storage = StorageManager(use_drive=True)
    
    print("\nStorage Info:")
    info = storage.get_storage_info()
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    # Test write
    print("\nTesting write...")
    test_df = pd.DataFrame([{
        'test': 'data',
        'timestamp': pd.Timestamp.now()
    }])
    
    success = storage.save_trades(test_df)
    print(f"Write successful: {success}")
    
    # Test read
    print("\nTesting read...")
    loaded_df = storage.load_trades()
    print(f"Loaded {len(loaded_df)} rows")
    
    print("\n✅ All tests passed!")

if __name__ == "__main__":
    test_drive()
```

Run:
```bash
python test_drive.py
```

Expected output:
```
Initializing storage manager...
✅ Connected to Google Drive folder: TradingSystem_Data

Storage Info:
  storage_mode: Google Drive + Local Cache
  drive_connected: True
  drive_folder: TradingSystem_Data
  ...

Testing write...
✅ Trades synced to Drive (1 total)
Write successful: True

Testing read...
📥 Loaded trades from Drive
Loaded 1 rows

✅ All tests passed!
```

---

## 🔒 Security Best Practices

### **1. Protect Your Credentials**

Add to `.gitignore`:
```
credentials.json
token.json
data/cache/
*.pyc
__pycache__/
```

### **2. Service Account Permissions**

- Only share the specific Drive folder
- Use "Editor" access (not "Owner")
- Don't share credentials file

### **3. OAuth Scopes**

The system only requests:
- `https://www.googleapis.com/auth/drive.file`

This limits access to **only files created by the app**.

---

## 🛠️ Troubleshooting

### **Issue: "Credentials file not found"**

**Solution:**
```bash
# Check if file exists
ls -la credentials.json

# Should show the file. If not, re-download from Google Cloud Console
```

### **Issue: "Failed to get/create folder"**

**Solution:**
1. Check Drive API is enabled
2. For service account: Ensure folder is shared with service account email
3. Check credentials have correct permissions

### **Issue: "Import error: google.oauth2"**

**Solution:**
```bash
pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### **Issue: "Drive connected: False"**

**Solution:**
```python
# The system falls back to local storage
# Check console output for specific error
# Common causes:
# - Missing credentials file
# - API not enabled
# - Network connectivity issue
```

### **Issue: "Permission denied"**

**Solution:**
- For service account: Re-share folder with service account email
- For OAuth: Re-authorize by deleting token.json and running again

---

## 📊 How It Works

### **Data Flow**

```
┌─────────────────────────────────────────────┐
│  Your Trading System                        │
│  ┌────────────────────────────────────────┐ │
│  │  Daily Analysis                        │ │
│  │  ↓                                      │ │
│  │  Create/Update Trades                  │ │
│  │  ↓                                      │ │
│  │  storage.save_trades()                 │ │
│  └────────────────────────────────────────┘ │
│           ↓                                  │
│  ┌────────────────────────────────────────┐ │
│  │  Local Cache (./data/cache/)          │ │
│  │  - Instant access                      │ │
│  │  - Offline capability                  │ │
│  └────────────────────────────────────────┘ │
│           ↓                                  │
│  ┌────────────────────────────────────────┐ │
│  │  Google Drive Sync                     │ │
│  │  - Cloud persistence                   │ │
│  │  - Cross-device access                 │ │
│  └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### **Save Process**

1. Load existing data (Drive → Cache)
2. Merge with new data (upsert by ID)
3. Save to local cache (instant)
4. Upload to Drive (background sync)
5. Update metadata

### **Load Process**

1. Try download from Drive (latest version)
2. Fall back to local cache if Drive unavailable
3. Parse and return data

---

## 🎯 Usage in Main App

The main app already uses Drive by default:

```python
# In main_app.py, this happens automatically:

if 'storage' not in st.session_state:
    # This will use Drive if credentials exist
    st.session_state.storage = StorageManager(use_drive=True)
```

**Manual control:**

```python
# Force local-only mode
storage = StorageManager(use_drive=False)

# Custom credentials path
storage = StorageManager(
    use_drive=True,
    credentials_path="/path/to/credentials.json"
)

# Force sync from Drive
storage.force_sync_from_drive()
```

---

## 📈 Advanced Features

### **1. Manual Sync**

```python
# In Streamlit app settings page:
if st.button("Force Sync from Drive"):
    success = st.session_state.storage.force_sync_from_drive()
    if success:
        st.success("Synced successfully!")
```

### **2. Export for Analysis**

```python
# Export with derived columns
df = storage.export_trades_for_analysis("backup_trades.csv")
```

### **3. Multiple Environments**

```python
# Development
dev_storage = StorageManager(use_drive=False)

# Production
prod_storage = StorageManager(use_drive=True)
```

---

## 🔄 Migration from Local Storage

If you have existing local data:

```python
from storage_manager import StorageManager
import pandas as pd

# Load old data
old_trades = pd.read_csv("./data/paper_trades.csv")
old_log = pd.read_csv("./data/analysis_log.csv")

# Initialize new Drive storage
storage = StorageManager(use_drive=True)

# Upload existing data
storage.save_trades(old_trades)
storage.save_analysis_log(old_log)

print("✅ Migration complete!")
```

---

## 💡 Tips

1. **First Run:** System creates `TradingSystem_Data` folder in your Drive root
2. **Folder Location:** You can move this folder anywhere in Drive after creation
3. **Sharing:** You can share the folder with others (they need their own credentials)
4. **Backup:** Drive handles versioning, but you can export manually for extra safety
5. **Offline:** System works offline using cached data

---

## ✅ Checklist

Setup complete when you can check all:

- [ ] Google Cloud Project created
- [ ] Drive API enabled
- [ ] Credentials downloaded to `credentials.json`
- [ ] Dependencies installed
- [ ] Test script runs successfully
- [ ] See "Connected to Google Drive" message
- [ ] Trades save to Drive
- [ ] Can load trades from Drive
- [ ] `TradingSystem_Data` folder visible in Drive

---

## 📞 Next Steps

1. Run the test script to verify setup
2. Start the main app: `streamlit run main_app.py`
3. System will automatically sync to Drive on every save
4. Check your Drive folder to see files appear

**Your data is now safe in the cloud! 🎉**
