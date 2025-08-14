#!/bin/bash

# Set bypass environment variables
export SKIP_SUPABASE_AUTH=1
export BYPASS_USER_DB=1

echo "🔧 Environment configured for Supabase bypass:"
echo "   SKIP_SUPABASE_AUTH=$SKIP_SUPABASE_AUTH"
echo "   BYPASS_USER_DB=$BYPASS_USER_DB"

# Run the update and restart script
echo "🚀 Starting update and restart process..."
./update_and_restart.sh
