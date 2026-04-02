import uvicorn
from app.Kernel import app
from config.middleware import setup_middleware
from config.exception import setup_exception

setup_middleware(app)
setup_exception(app)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="localhost",
        port=8002,
        reload=True,
        log_level="info",
    )
