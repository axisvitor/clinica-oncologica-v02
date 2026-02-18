-- Check messages table for recent entries
SELECT id, content, direction, status, created_at FROM messages 
WHERE created_at > NOW() - INTERVAL '10 minutes'
ORDER BY created_at DESC LIMIT 10;
