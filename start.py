import os
import uvicorn
from app import app  # Import your FastAPI app

if __name__ == "__main__":
    # Use Render's PORT if available, otherwise default to 8000
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        workers=1,         # Use 1 worker to save memory
        reload=True        # Optional for local development
    )
    