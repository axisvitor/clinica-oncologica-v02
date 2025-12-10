#!/bin/bash
# Test login API with CSRF token

cd /tmp
rm -f cookies.txt

echo "Getting CSRF token..."
CSRF_RESPONSE=$(curl -s -c cookies.txt -b cookies.txt "http://localhost:8000/api/v2/auth/csrf-token")
echo "CSRF Response: $CSRF_RESPONSE"

CSRF_TOKEN=$(echo "$CSRF_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['csrf_token'])")
echo "CSRF Token (length): ${#CSRF_TOKEN}"

echo ""
echo "Testing login..."
LOGIN_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v2/auth/login" \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -c cookies.txt \
  -b cookies.txt \
  -d '{"email": "admin@neoplasiaslitoral.com", "password": "Admin@123456!"}')

echo "Login Response: $LOGIN_RESPONSE"
