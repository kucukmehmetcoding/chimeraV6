#!/bin/bash
# ============================================================================
# ChimeraBot Coolify Deployment Script
# ============================================================================
# Bu script Coolify platformunda ChimeraBot'u deploy etmek için gerekli
# tüm adımları otomatikleştirir.
# ============================================================================

set -e  # Exit on error

echo "============================================================================"
echo "🚀 ChimeraBot Coolify Deployment"
echo "============================================================================"
echo ""

# --- Step 1: Environment Variables Check ---
echo "📋 Step 1: Environment Variables Check"
echo "------------------------------------------------------------"
echo "⚠️  Coolify'da aşağıdaki environment variable'ları tanımlamanız gerekiyor:"
echo ""
echo "REQUIRED (Secrets):"
echo "  - BINANCE_API_KEY"
echo "  - BINANCE_SECRET_KEY"
echo "  - TELEGRAM_BOT_TOKEN"
echo "  - TELEGRAM_CHAT_ID"
echo ""
echo "REQUIRED (Production Mode):"
echo "  - BINANCE_TESTNET=False"
echo "  - ENABLE_REAL_TRADING=true"
echo ""
echo "OPTIONAL (Sentiment Analysis):"
echo "  - REDDIT_CLIENT_ID"
echo "  - REDDIT_CLIENT_SECRET"
echo "  - GEMINI_API_KEY"
echo ""
echo "OPTIONAL (Configuration):"
echo "  - MAX_COINS_TO_SCAN=600"
echo "  - SCAN_INTERVAL_SECONDS=300"
echo "  - LOG_LEVEL=INFO"
echo ""

# --- Step 2: Docker Configuration Check ---
echo "🐳 Step 2: Docker Configuration Check"
echo "------------------------------------------------------------"

if [ ! -f "Dockerfile" ]; then
    echo "❌ ERROR: Dockerfile not found!"
    exit 1
fi
echo "✅ Dockerfile exists"

if [ ! -f "docker-compose.yaml" ]; then
    echo "❌ ERROR: docker-compose.yaml not found!"
    exit 1
fi
echo "✅ docker-compose.yaml exists"

# --- Step 3: Dependencies Check ---
echo ""
echo "📦 Step 3: Dependencies Check"
echo "------------------------------------------------------------"

if [ ! -f "requirements.txt" ]; then
    echo "❌ ERROR: requirements.txt not found!"
    exit 1
fi
echo "✅ requirements.txt exists"

# Count dependencies
dep_count=$(grep -v '^#' requirements.txt | grep -v '^$' | wc -l | xargs)
echo "   📊 Total dependencies: $dep_count"

# --- Step 4: Database Check ---
echo ""
echo "🗄️  Step 4: Database Configuration"
echo "------------------------------------------------------------"

if [ ! -d "data" ]; then
    echo "⚠️  Creating data directory..."
    mkdir -p data
fi
echo "✅ data/ directory exists"

if [ ! -d "logs" ]; then
    echo "⚠️  Creating logs directory..."
    mkdir -p logs
fi
echo "✅ logs/ directory exists"

# --- Step 5: Migration Scripts Check ---
echo ""
echo "🔄 Step 5: Migration Scripts"
echo "------------------------------------------------------------"

if [ -d "migrations" ]; then
    migration_count=$(ls -1 migrations/*.py 2>/dev/null | wc -l | xargs)
    echo "✅ migrations/ directory exists"
    echo "   📊 Total migration scripts: $migration_count"
else
    echo "⚠️  No migrations directory found (optional)"
fi

# --- Step 6: Source Code Check ---
echo ""
echo "💻 Step 6: Source Code Structure"
echo "------------------------------------------------------------"

required_dirs=("src" "src/technical_analyzer" "src/risk_manager" "src/trade_manager" "src/database" "src/notifications")
for dir in "${required_dirs[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "❌ ERROR: Required directory '$dir' not found!"
        exit 1
    fi
    echo "✅ $dir/"
done

# --- Step 7: HTF-LTF Strategy Check ---
echo ""
echo "📈 Step 7: HTF-LTF Strategy (v11.0) Check"
echo "------------------------------------------------------------"

if [ ! -f "src/technical_analyzer/htf_ltf_strategy.py" ]; then
    echo "❌ ERROR: htf_ltf_strategy.py not found!"
    exit 1
fi
echo "✅ HTF-LTF strategy module exists"

# --- Step 8: Configuration Check ---
echo ""
echo "⚙️  Step 8: Configuration File Check"
echo "------------------------------------------------------------"

if [ ! -f "src/config.py" ]; then
    echo "❌ ERROR: src/config.py not found!"
    exit 1
fi
echo "✅ src/config.py exists"

# Check critical config values
if grep -q "MAX_OPEN_POSITIONS = 15" src/config.py; then
    echo "✅ MAX_OPEN_POSITIONS = 15 (v11.1)"
else
    echo "⚠️  MAX_OPEN_POSITIONS might not be 15"
fi

if grep -q "ATR_SL_MULTIPLIER = 1.0" src/config.py; then
    echo "✅ ATR_SL_MULTIPLIER = 1.0 (v11.1)"
else
    echo "⚠️  ATR_SL_MULTIPLIER might not be 1.0"
fi

# --- Step 9: .env.example Check ---
echo ""
echo "📝 Step 9: Environment Template Check"
echo "------------------------------------------------------------"

if [ ! -f ".env.example" ]; then
    echo "❌ ERROR: .env.example not found!"
    exit 1
fi
echo "✅ .env.example exists"

# --- Step 10: Git Safety Check ---
echo ""
echo "🔒 Step 10: Security Check"
echo "------------------------------------------------------------"

if [ -f ".env" ]; then
    echo "⚠️  WARNING: .env file exists (should NOT be in git!)"
    if [ -f ".gitignore" ]; then
        if grep -q "^\.env$" .gitignore; then
            echo "✅ .env is in .gitignore"
        else
            echo "❌ WARNING: .env is NOT in .gitignore!"
        fi
    fi
else
    echo "✅ No .env file found (good for production)"
fi

# --- Summary ---
echo ""
echo "============================================================================"
echo "✅ DEPLOYMENT READINESS CHECK COMPLETE"
echo "============================================================================"
echo ""
echo "📋 Next Steps for Coolify Deployment:"
echo ""
echo "1. Push this code to your Git repository"
echo "2. In Coolify, create a new Docker Compose application"
echo "3. Connect your Git repository"
echo "4. Configure Environment Variables (see Step 1 above)"
echo "5. Set the following as SECRETS in Coolify:"
echo "   - BINANCE_API_KEY"
echo "   - BINANCE_SECRET_KEY"
echo "   - TELEGRAM_BOT_TOKEN"
echo "6. Configure Volume Mounts:"
echo "   - ./data:/app/data"
echo "   - ./logs:/app/logs"
echo "7. Deploy the application"
echo "8. Monitor healthcheck status in Coolify dashboard"
echo ""
echo "⚠️  IMPORTANT: For PRODUCTION mode:"
echo "   - Set BINANCE_TESTNET=False"
echo "   - Set ENABLE_REAL_TRADING=true"
echo "   - Double-check all safety mechanisms are active"
echo ""
echo "============================================================================"
echo "🎉 System is ready for Coolify deployment!"
echo "============================================================================"
