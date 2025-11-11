"""
Check the content of messages in the database.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

import psycopg

def check_messages():
    """Check message content in database."""
    
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        print("✗ DATABASE_URL not found in environment")
        return
    
    if db_url.startswith('postgresql+psycopg://'):
        db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
    
    print("=" * 80)
    print("CHECKING MESSAGE CONTENT IN DATABASE")
    print("=" * 80)
    
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                
                # Get recent messages
                cur.execute("""
                    SELECT 
                        id,
                        patient_id,
                        content,
                        LENGTH(content) as content_length,
                        status,
                        idempotency_key,
                        created_at
                    FROM messages
                    ORDER BY created_at DESC
                    LIMIT 5
                """)
                
                messages = cur.fetchall()
                
                if not messages:
                    print("\n⚠ No messages found in database")
                    return
                
                print(f"\nFound {len(messages)} recent messages:\n")
                
                for msg in messages:
                    msg_id, patient_id, content, content_len, status, idem_key, created_at = msg
                    
                    print("-" * 80)
                    print(f"Message ID: {msg_id}")
                    print(f"Patient ID: {patient_id}")
                    print(f"Status: {status}")
                    print(f"Idempotency Key: {idem_key}")
                    print(f"Created At: {created_at}")
                    print(f"Content Length: {content_len}")
                    print(f"Content is None: {content is None}")
                    print(f"Content is empty string: {content == ''}")
                    
                    if content:
                        print(f"\nContent preview (first 200 chars):")
                        print(f"{content[:200]}...")
                    else:
                        print(f"\n✗ ERROR: Content is NULL or empty!")
                        print(f"Content repr: {repr(content)}")
                    
                    print()
                
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_messages()
