#!/usr/bin/env python3
"""
Launcher for RepoPulse: Repository-Aware Coding Assistant.
Starts the FastAPI application with Uvicorn.
"""

import sys
import uvicorn
from app.config import settings

def main():
    print("=" * 60)
    print("  ⚡ Starting RepoPulse - Repository-Aware Coding Assistant")
    print(f"  🌐 UI running at: http://{settings.HOST}:{settings.PORT}")
    print(f"  📚 API Docs at:   http://{settings.HOST}:{settings.PORT}/docs")
    print("=" * 60)
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )

if __name__ == "__main__":
    main()
