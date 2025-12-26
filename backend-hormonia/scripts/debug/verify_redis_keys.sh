#!/bin/bash
# ============================================================================
# Verify Redis Idempotency Keys
# Sistema Hormonia - Debug Script
# ============================================================================

REDIS_CLI=${REDIS_CLI:-redis-cli}
REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}
REDIS_DB=${REDIS_DB:-0}

echo "=============================================="
echo "Redis Idempotency Keys Verification"
echo "=============================================="
echo ""

# Connect command
REDIS_CMD="$REDIS_CLI -h $REDIS_HOST -p $REDIS_PORT -n $REDIS_DB"

echo "1. Webhook Status Keys (SET NX pattern)"
echo "----------------------------------------"
$REDIS_CMD KEYS "webhook:status:*" | head -20
echo ""
echo "Count: $($REDIS_CMD KEYS 'webhook:status:*' | wc -l)"
echo ""

echo "2. Webhook Message Keys (SET NX pattern)"
echo "----------------------------------------"
$REDIS_CMD KEYS "webhook:message:*" | head -20
echo ""
echo "Count: $($REDIS_CMD KEYS 'webhook:message:*' | wc -l)"
echo ""

echo "3. Quiz Lock Keys"
echo "-----------------"
$REDIS_CMD KEYS "quiz:*" | head -20
echo ""
echo "Count: $($REDIS_CMD KEYS 'quiz:*' | wc -l)"
echo ""

echo "4. Flow Lock Keys"
echo "-----------------"
$REDIS_CMD KEYS "flow:*" | head -20
echo ""
echo "Count: $($REDIS_CMD KEYS 'flow:*' | wc -l)"
echo ""

echo "5. Sample Key TTLs"
echo "------------------"
for key in $($REDIS_CMD KEYS "webhook:*" | head -5); do
    ttl=$($REDIS_CMD TTL "$key")
    value=$($REDIS_CMD GET "$key")
    echo "  $key -> TTL: ${ttl}s, Value: $value"
done
echo ""

echo "6. All Keys by Pattern (Summary)"
echo "---------------------------------"
echo "  webhook:*   : $($REDIS_CMD KEYS 'webhook:*' | wc -l)"
echo "  quiz:*      : $($REDIS_CMD KEYS 'quiz:*' | wc -l)"
echo "  flow:*      : $($REDIS_CMD KEYS 'flow:*' | wc -l)"
echo "  cache:*     : $($REDIS_CMD KEYS 'cache:*' | wc -l)"
echo "  session:*   : $($REDIS_CMD KEYS 'session:*' | wc -l)"
echo ""

echo "=============================================="
echo "Verification Complete"
echo "=============================================="
