#!/usr/bin/env python3
"""
Create audit_logs table to fix the missing table error.
"""

import os
import sys
from pathlib import Path
import psycopg2

def load_env():
    """Load environment variables from .env file"""
    env_path = Path(__file__).parent.parent / '.env'
    
    if not env_path.exists():
        print("❌ Error: .env file not found")
        return None
    
    env_vars = {}
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip().strip('"\'')
    
    return env_vars.get('DATABASE_URL')

def create_audit_logs_table():
    """Create the audit_logs table."""
    
    database_url = load_env()
    if not database_url:
        return
    
    # Fix DATABASE_URL format for psycopg2
    if database_url.startswith('postgresql+psycopg://'):
        database_url = database_url.replace('postgresql+psycopg://', 'postgresql://')
    
    print("🔧 Creating audit_logs table...")
    
    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        
        with conn.cursor() as cursor:
            # Check if table already exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'audit_logs'
                );
            """)
            
            if cursor.fetchone()[0]:
                print("✅ audit_logs table already exists")
                return
            
            # Create the audit_logs table
            create_table_sql = """
            CREATE TABLE audit_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                
                -- Event information
                event_type VARCHAR(50) NOT NULL,
                event_status VARCHAR(20) NOT NULL DEFAULT 'success',
                
                -- User information
                user_id UUID,
                user_email VARCHAR(255),
                firebase_uid VARCHAR(255),
                
                -- Request context
                ip_address INET,
                user_agent VARCHAR(500),
                
                -- Resource and action
                resource VARCHAR(255),
                action VARCHAR(100),
                
                -- Event details
                event_metadata JSONB DEFAULT '{}',
                message VARCHAR(500),
                error_details VARCHAR(1000),
                
                -- Timestamps
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            );
            """
            
            cursor.execute(create_table_sql)
            print("✅ audit_logs table created")
            
            # Create indexes for performance
            indexes = [
                "CREATE INDEX idx_audit_logs_event_type ON audit_logs(event_type);",
                "CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);",
                "CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);",
                "CREATE INDEX idx_audit_logs_event_status ON audit_logs(event_status);",
                "CREATE INDEX idx_audit_logs_user_email ON audit_logs(user_email);",
                "CREATE INDEX idx_audit_logs_ip_address ON audit_logs(ip_address);",
                "CREATE INDEX idx_audit_logs_resource_action ON audit_logs(resource, action);",
            ]
            
            for index_sql in indexes:
                cursor.execute(index_sql)
            
            print("✅ audit_logs indexes created")
            
            # Add foreign key constraint to users table if it exists
            try:
                cursor.execute("""
                    ALTER TABLE audit_logs 
                    ADD CONSTRAINT fk_audit_logs_user 
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;
                """)
                print("✅ Foreign key constraint added")
            except Exception as e:
                print(f"⚠️ Could not add foreign key constraint: {e}")
            
            # Add comment
            cursor.execute("""
                COMMENT ON TABLE audit_logs IS 'Security audit logs for authentication and authorization events';
            """)
            
            # Create trigger for updated_at
            cursor.execute("""
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """)
            
            cursor.execute("""
                CREATE TRIGGER update_audit_logs_updated_at
                    BEFORE UPDATE ON audit_logs
                    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
            """)
            
            print("✅ audit_logs trigger created")
        
        conn.close()
        print("✅ audit_logs table setup completed successfully")
        
    except Exception as e:
        print(f"❌ Error creating audit_logs table: {e}")

if __name__ == "__main__":
    create_audit_logs_table()