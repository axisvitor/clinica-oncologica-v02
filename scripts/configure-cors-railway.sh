#!/bin/bash

# Configure CORS environment variables for Railway deployment
# This script sets up the required CORS_ORIGINS variable for production

echo "🚀 Configuring CORS for Railway Production"
echo "=========================================="

# Get current Railway variables to find frontend and quiz URLs
FRONTEND_URL=$(railway variables --service backend 2>&1 | grep "FRONTEND_URL" | awk -F'│' '{print $2}' | tr -d ' ')
QUIZ_URL=$(railway variables --service backend 2>&1 | grep "QUIZ_URL" | awk -F'│' '{print $2}' | tr -d ' ')

echo "Frontend URL: $FRONTEND_URL"
echo "Quiz URL: $QUIZ_URL"

# Construct CORS_ORIGINS value
CORS_ORIGINS="${FRONTEND_URL},${QUIZ_URL}"

echo ""
echo "Setting CORS_ORIGINS to:"
echo "$CORS_ORIGINS"

# Set the variable in Railway
railway variables --service backend set "CORS_ORIGINS=$CORS_ORIGINS"

echo ""
echo "✅ CORS_ORIGINS configured successfully!"
echo ""
echo "Next steps:"
echo "1. Deploy the updated middleware_setup.py code"
echo "2. The backend will now accept CORS requests from frontend and quiz"
echo "3. Verify with: railway logs --service backend"
