import uvicorn


def main() -> None:
    """Start the local FastAPI development server."""
    uvicorn.run("app.main:app", reload=True)
