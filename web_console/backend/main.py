"""Web Console API Server entry point"""
import sys
import argparse
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Ensure project root in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from web_console.backend.config import BASE_DIR
from web_console.backend.agent_service import AgentService
from web_console.backend.process_manager import AgentProcessManager
from web_console.backend.registry_service import RegistryService
from web_console.backend.routes import agents_router, sessions_router, registry_router, chat_router


def setup_logging(debug: bool = False):
    """Configure logging"""
    level = logging.DEBUG if debug else logging.INFO
    format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    handlers = [logging.StreamHandler()]
    if debug:
        handlers.append(logging.FileHandler('api_debug.log'))
    logging.basicConfig(level=level, format=format_str, handlers=handlers)
    return logging.getLogger(__name__)


def create_app(debug: bool = False):
    """Create FastAPI application"""
    logger = setup_logging(debug)
    logger.info(f"Creating app with debug={debug}")

    # Initialize services
    process_manager = AgentProcessManager(logger)
    agent_service = AgentService(process_manager, logger)
    registry_service = RegistryService(logger)

    # Create FastAPI app
    app = FastAPI(title="Novel Agent API")

    # Add CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files
    frontend_dir = BASE_DIR / "web_console" / "frontend"
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

    # Store services in app state
    app.state.agent_service = agent_service
    app.state.registry_service = registry_service

    # Include routers
    app.include_router(agents_router)
    app.include_router(sessions_router)
    app.include_router(registry_router)
    app.include_router(chat_router)

    # Root and health endpoints
    @app.get("/")
    async def root():
        return FileResponse(str(frontend_dir / "index.html"))

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    return app, logger


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Novel Agent API Server")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    import uvicorn
    app, logger = create_app(debug=args.debug)
    logger.info(f"Starting server on port 8000, debug={args.debug}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
