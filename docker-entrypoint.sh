#!/bin/bash
# docker-entrypoint.sh
# Container startup script with optional cache cleanup

set -e

echo "🚀 ChimeraBot Container Starting..."

# Check if FORCE_CLEAN_START is set
if [ "$FORCE_CLEAN_START" = "true" ]; then
    echo "⚠️  FORCE_CLEAN_START enabled - Cleaning all cached data..."
    
    # Remove database
    if [ -f "/app/data/chimerabot.db" ]; then
        echo "   🗑️  Removing old database..."
        rm -f /app/data/chimerabot.db
        echo "   ✅ Database removed"
    fi
    
    # Clean logs (keep directory)
    if [ -d "/app/logs" ]; then
        echo "   🗑️  Cleaning old logs..."
        rm -f /app/logs/*.log
        echo "   ✅ Logs cleaned"
    fi
    
    echo "✅ Clean start complete - Fresh database will be created"
else
    echo "ℹ️  Normal start - Using existing data if available"
fi

# Create directories if they don't exist
mkdir -p /app/data /app/logs

echo "🔄 Initializing database schema..."
# Use SQLAlchemy's create_all() to ensure all tables/columns exist
# This is idempotent - won't drop existing data, just adds missing tables/columns
python3 /app/create_database.py
echo "✅ Database schema ready"

echo "🎯 Starting ChimeraBot..."
# Execute the main command
exec "$@"
