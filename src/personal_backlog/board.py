"""Compatibility adapter for the backlog board."""

from __future__ import annotations

from pathlib import Path
from http.server import ThreadingHTTPServer

from personal_backlog.server import create_server, serve


def create_board_server(backlog_dir: Path, port: int = 8766) -> ThreadingHTTPServer:
    """Create a server in read-only mode for backward compatibility."""
    return create_server(backlog_dir, port=port, read_only=True)


def serve_board(backlog_dir: Path, *, port: int = 8766, open_browser: bool = True) -> None:
    """Serve the backlog in read-only mode for backward compatibility."""
    serve(backlog_dir, port=port, open_browser=open_browser, read_only=True)

