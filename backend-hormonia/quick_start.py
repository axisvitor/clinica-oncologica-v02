#!/usr/bin/env python3
"""
Quick start script - tries different ports automatically.
"""
import sys
import socket
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def find_free_port(start_port=8000, max_port=8010):
    """Find a free port starting from start_port."""
    for port in range(start_port, max_port):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return port
        except OSError:
            continue
    return None

def main():
    """Quick start with automatic port detection."""
    print("🚀 Quick Start - Finding available port...")

    # Find free port
    port = find_free_port()
    if not port:
        print("❌ No available ports found between 8000-8010")
        sys.exit(1)

    print(f"✅ Using port {port}")

    # Test basic imports first
    try:
        from app.main import app
        print("✅ Backend imports successful")
    except Exception as e:
        print(f"❌ Import error: {e}")
        sys.exit(1)

    # Start server
    try:
        import uvicorn
        print(f"🌐 Starting server at: http://localhost:{port}")
        print(f"📚 API docs at: http://localhost:{port}/docs")
        print("🛑 Press Ctrl+C to stop")

        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=port,
            reload=False,  # Disable reload for quick start
            log_level="warning"  # Reduce log noise
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()