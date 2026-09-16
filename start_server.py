"""Starts the Northwind FastAPI target server."""

import uvicorn
from app.northwind.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    print(f"Starting {settings.app_name} on http://{settings.app_host}:{settings.app_port}...")
    print(f"Active Groq Model: {settings.groq_model}")
    print(f"Planted Secret:    {settings.fake_secret}")
    uvicorn.run(
        "app.northwind.api.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
        log_level="info",
    )

