"""Start the API on a loopback address."""

from __future__ import annotations

import argparse
import sys

from app.config import get_settings
from app.security.loopback import LocalOnlyError, assert_loopback_host


def main(argv: list[str] | None = None) -> None:
    """Bind uvicorn to localhost. A public host is a startup error."""
    parser = argparse.ArgumentParser(description="Run the DevPilot API on localhost.")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args(argv)
    settings = get_settings()
    try:
        host = settings.host if args.host is None else assert_loopback_host(args.host)
    except LocalOnlyError as exc:
        raise SystemExit(str(exc)) from exc
    port = settings.port if args.port is None else args.port
    if port < 1 or port > 65535:
        raise SystemExit("Port must be between 1 and 65535.")
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main(sys.argv[1:])
