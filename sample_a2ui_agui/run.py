"""
Startup script for OmniCalc A2UI + AG-UI Server.
Automatically detects port conflicts and finds an open port.
"""
import uvicorn
import os
import sys
import socket
import argparse

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure repository root is in Python path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)


def find_available_port(start_port: int = 8080) -> int:
    """Finds the first available port starting from start_port."""
    port = start_port
    while port < start_port + 100:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
        port += 1
    return start_port


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start OmniCalc Server")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8080")), help="Port to run on")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface")
    args = parser.parse_args()

    port = find_available_port(args.port)

    print("=" * 65)
    print("Starting OmniCalc Agent Server (A2UI + AG-UI)")
    print(f"Open your browser at: http://{args.host}:{port}")
    print("=" * 65)

    uvicorn.run("sample_a2ui_agui.backend.server:app", host=args.host, port=port, reload=True)
