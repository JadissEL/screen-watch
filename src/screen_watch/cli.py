"""CLI entry: MCP server by default, plus once / advise / status helpers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from screen_watch import __version__
from screen_watch.advisor.cost_estimate import estimate_session_cost
from screen_watch.advisor.llm_catalog import list_models
from screen_watch.advisor.profiler import profile_machine, recommend_settings
from screen_watch.advisor.store import load_advisor_state, save_advisor_state
from screen_watch.config import load_settings
from screen_watch.logging_setup import configure_logging
from screen_watch.privacy import privacy_blurb
from screen_watch.service import get_service, reset_service


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="screen-watch",
        description="Passive desktop observation for AI agents (MCP). Observation only.",
    )
    parser.add_argument("--version", action="version", version=f"screen-watch {__version__}")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("serve", help="Run MCP stdio server (default)")
    once = sub.add_parser("once", help="Capture one JPEG and save to disk")
    once.add_argument("-o", "--output", type=Path, default=Path("screen-watch-once.jpg"))
    once.add_argument("--blur", action="store_true", help="Pixelate the frame")
    sub.add_parser("status", help="Print backend / config status")
    advise = sub.add_parser("advise", help="PC capacity + LLM cost summary")
    advise.add_argument("--model", help="Preferred LLM id (persisted)")
    sub.add_parser("models", help="List built-in vision LLM catalog")
    focus = sub.add_parser(
        "focus",
        help="Guided region focus: drag a loose box, save crop (+ gesture JSON)",
    )
    focus.add_argument("-o", "--output", type=Path, default=Path("screen-watch-region.jpg"))
    focus.add_argument("--gesture", type=Path, default=Path("screen-watch-gesture.json"))
    focus.add_argument("--blur", action="store_true")
    hotkey = sub.add_parser(
        "hotkey",
        help="Register global hotkey (default Ctrl+Shift+F) to open focus overlay",
    )
    hotkey.add_argument(
        "--bind",
        default=None,
        help="Hotkey spec, e.g. ctrl+shift+f (default from SCREEN_WATCH_FOCUS_HOTKEY)",
    )
    sub.add_parser("doctor", help="Print install / backend / optional-tool status")

    args = parser.parse_args(argv)
    settings = load_settings()
    configure_logging(settings.log_level)

    if args.cmd is None or args.cmd == "serve":
        from screen_watch.mcp.server import run_server

        run_server()
        return 0

    if args.cmd == "once":
        reset_service()
        svc = get_service()
        frame = svc.capture_once(blur=True if args.blur else None)
        args.output.write_bytes(frame.jpeg)
        print(f"Wrote {args.output} ({frame.width}x{frame.height}, {len(frame.jpeg)} bytes)", file=sys.stderr)
        return 0

    if args.cmd == "status":
        print(json.dumps(get_service().status(), indent=2))
        print(privacy_blurb(), file=sys.stderr)
        return 0

    if args.cmd == "advise":
        state = load_advisor_state()
        if args.model:
            state["preferred_llm"] = args.model
        rec = recommend_settings(profile_machine())
        state["profile"] = rec
        save_advisor_state(state)
        model_id = state.get("preferred_llm") or "gpt-4o"
        out = {
            "capacity": rec,
            "preferred_llm": model_id,
            "costs": estimate_session_cost(model_id),
            "privacy": privacy_blurb(),
        }
        print(json.dumps(out, indent=2))
        return 0

    if args.cmd == "models":
        print(json.dumps(list_models(), indent=2))
        return 0

    if args.cmd == "focus":
        from screen_watch.focus.runner import run_guided_focus

        reset_service()
        result = run_guided_focus(blur=True if args.blur else None)
        if not result.get("ok"):
            print("Cancelled", file=sys.stderr)
            return 2
        # Also copy to cwd paths for convenience
        from screen_watch.focus.hotkey import latest_focus_dir

        region = (latest_focus_dir() / "region.jpg").read_bytes()
        gesture = json.loads((latest_focus_dir() / "gesture.json").read_text(encoding="utf-8"))
        args.output.write_bytes(region)
        args.gesture.write_text(json.dumps(gesture, indent=2), encoding="utf-8")
        print(
            f"Wrote {args.output}, {args.gesture}, and {result['dir']} "
            f"({result['region_width']}x{result['region_height']})",
            file=sys.stderr,
        )
        return 0

    if args.cmd == "doctor":
        from screen_watch.doctor import run_doctor

        print(json.dumps(run_doctor(), indent=2))
        return 0

    if args.cmd == "hotkey":
        from screen_watch.focus.hotkey import HotkeyDaemon, parse_hotkey
        from screen_watch.focus.runner import run_guided_focus

        bind = args.bind or settings.focus_hotkey
        try:
            spec = parse_hotkey(bind)
        except ValueError as exc:
            print(f"Invalid hotkey: {exc}", file=sys.stderr)
            return 2

        def _on_hotkey() -> None:
            print("Hotkey → opening focus overlay…", file=sys.stderr)
            run_guided_focus()

        daemon = HotkeyDaemon(spec, _on_hotkey)
        daemon.start()
        print(f"Listening for {spec.label}. Ctrl+C to stop.", file=sys.stderr)
        try:
            import time

            # Give the worker a moment to register / report missing pynput
            time.sleep(0.3)
            if daemon.last_error:
                print(daemon.last_error, file=sys.stderr)
                daemon.stop()
                return 1
            while daemon.running:
                time.sleep(0.5)
                if daemon.last_error:
                    print(daemon.last_error, file=sys.stderr)
                    return 1
        except KeyboardInterrupt:
            print("Stopping hotkey daemon…", file=sys.stderr)
        finally:
            daemon.stop()
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
