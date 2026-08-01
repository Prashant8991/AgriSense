"""
AgriSense Pro — FastAPI Web Application Entry Point
Run with: python app.py
"""
import uvicorn
import webbrowser
import threading
import time
from main import app  # noqa: F401

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://localhost:5000")

if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
