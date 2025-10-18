"""
FastAPI application entry point for Hormonia Backend System.

Clean, minimal main.py that delegates all concerns to specialized modules:
- Application factory handles app creation
- Middleware setup manages all middleware configuration
- Router registry handles route registration
- Lifespan manager handles startup/shutdown lifecycle
- Monitoring setup handles observability
"""
from app.core.application_factory import create_application
from app.config import settings

# Create application instance using factory pattern with appropriate mode
deployment_mode = "development" if settings.DEBUG else "production"
app = create_application(deployment_mode=deployment_mode)

# Add a simple test endpoint to verify the server is working (debug mode only)
if settings.DEBUG:
    @app.get("/test", tags=["Debug"])
    async def test_endpoint():
        return {"message": "Server is working", "debug": settings.DEBUG, "mode": deployment_mode}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
