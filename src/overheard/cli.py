"""The `overheard` command: serve, seed, record, batch-label."""

import argparse
import sys

from overheard import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="overheard", description="An AI voicemail console demo.")
    parser.add_argument("--version", action="version", version=f"overheard {__version__}")
    sub = parser.add_subparsers(dest="command")
    serve = sub.add_parser("serve", help="run the console (API and front end) in one process")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    sub.add_parser("seed", help="generate the synthetic day and archive into the database")
    sub.add_parser("record", help="run the live LLM over the day and save its responses for replay")
    sub.add_parser("batch-label", help="label a sample of the archive with the live LLM")
    args = parser.parse_args(argv)

    if args.command == "serve":
        import uvicorn

        from overheard.app import create_app
        from overheard.config import Settings

        settings = Settings()
        host, port = args.host or settings.host, args.port or settings.port
        print(f"Overheard {__version__} on http://{host}:{port}  (LLM mode: {settings.llm_mode})")
        uvicorn.run(create_app(settings), host=host, port=port, log_level="warning")
        return 0
    if args.command in ("seed", "record", "batch-label"):
        print(f"overheard {args.command}: not built yet (this is an early release)", file=sys.stderr)
        return 2
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
