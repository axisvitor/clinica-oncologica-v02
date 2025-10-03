#!/bin/bash

# Build script for Railway deployment with forced environment variables
set -e  # Exit on any error

echo "🚀 Railway Frontend Build Script Starting..."
echo "============================================"

echo "📝 Setting up environment variables for build..."

# Export all required environment variables
export VITE_SUPABASE_URL="https://rszpypytdciggybbpnrp.supabase.co"
export VITE_SUPABASE_ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJzenB5cHl0ZGNpZ2d5YmJwbnJwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDkzMDQ0NzksImV4cCI6MjA2NDg4MDQ3OX0.qF_byaebH1q78a6SYhGfCuGSotF523o1ZqTrwOBkPYg"
export VITE_API_URL="https://backend-production-e0bd.up.railway.app/api/v1"
export VITE_API_BASE_URL="https://backend-production-e0bd.up.railway.app"
export VITE_WS_BASE_URL="wss://backend-production-e0bd.up.railway.app/ws"

# Additional environment variables
export NODE_ENV="production"
export VITE_NODE_ENV="production"
export GENERATE_SOURCEMAP="false"
export CI="true"

echo "✅ Environment variables configured:"
echo "   VITE_SUPABASE_URL=$VITE_SUPABASE_URL"
echo "   VITE_API_URL=$VITE_API_URL"
echo "   VITE_API_BASE_URL=$VITE_API_BASE_URL"
echo "   VITE_WS_BASE_URL=$VITE_WS_BASE_URL"
echo "   NODE_ENV=$NODE_ENV"

echo ""
echo "🔨 Starting Vite build process..."
echo "============================================"

# Run the build command with error handling
if npm run build:prod; then
    echo ""
    echo "✅ Build completed successfully!"
    echo "============================================"

    # Check if dist directory exists and has content
    if [ -d "dist" ] && [ "$(ls -A dist)" ]; then
        echo "📦 Build artifacts generated in dist/ directory:"
        ls -la dist/
    else
        echo "❌ ERROR: dist/ directory is empty or missing!"
        exit 1
    fi
else
    echo ""
    echo "❌ BUILD FAILED!"
    echo "============================================"
    exit 1
fi

echo ""
echo "🎉 Frontend build script completed successfully!"