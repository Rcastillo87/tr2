import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8002,
        reload=False,
        workers=1,  # VPS de 2 cores con otras cargas: 1 worker es óptimo
    )
