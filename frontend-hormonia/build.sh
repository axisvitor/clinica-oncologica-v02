#!/bin/bash

# Build script for Railway deployment with forced environment variables
set -e  # Exit on any error

echo "🚀 Railway Frontend Build Script Starting..."
echo "============================================"

echo "📝 Setting up environment variables for build..."

# Railway injects these variables - do not hardcode
# Required: VITE_API_URL, VITE_API_BASE_URL, VITE_WS_BASE_URL, Firebase client keys

# Additional environment variables
export NODE_ENV="production"
export VITE_NODE_ENV="production"
export GENERATE_SOURCEMAP="false"
export CI="true"

echo "✅ Environment variables configured:"
echo "   VITE_API_URL=$VITE_API_URL"
echo "   VITE_API_BASE_URL=$VITE_API_BASE_URL"
echo "   VITE_WS_BASE_URL=$VITE_WS_BASE_URL"
echo "   VITE_FIREBASE_PROJECT_ID=$VITE_FIREBASE_PROJECT_ID"
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
