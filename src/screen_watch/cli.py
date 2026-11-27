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
    once.add_argument("--display", type=int, default=None, help="1-based monitor id")
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
    bench = sub.add_parser("bench", help="Measure grab+encode latency")
    bench.add_argument("-n", "--iterations", type=int, default=5)
    bench.add_argument("--display", type=int, default=None, help="1-based monitor id")
    watch = sub.add_parser("watch", help="Run capture daemon in the foreground (stderr logs)")
    watch.add_argument("--display", type=int, default=None, help="1-based monitor id")
    watch.add_argument(
        "--seconds",
        type=float,
        default=0.0,
        help="Stop after N seconds (0 = until Ctrl+C)",
    )
    wait = sub.add_parser("wait", help="Block until the screen changes (JSON on stdout)")
    wait.add_argument("--since-hash", default="", help="Baseline content hash (default: current)")
    wait.add_argument("--min-score", type=float, default=0.0, help="Minimum change_score")
    wait.add_argument("--timeout", type=float, default=30.0, help="Seconds (max 120)")
    wait.add_argument("--poll", type=float, default=0.25, help="Poll interval seconds")
    wait.add_argument(
        "--start-watch",
        action="store_true",
        help="Start the watch daemon for the wait (stops afterward)",
    )
    export = sub.add_parser("export", help="Zip a finished recording session locally")
    export.add_argument("session_id", help="Recording session id")
    export.add_argument("-o", "--output", type=Path, default=None, help="Zip path")
    export.add_argument(
        "--keyframes-only",
        action="store_true",
        help="Include meta/timeline + changed JPEGs only",
    )

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
        frame = svc.capture_once(
            blur=True if args.blur else None,
            display_id=args.display,
        )
        args.output.write_bytes(frame.jpeg)
        print(
            f"Wrote {args.output} ({frame.width}x{frame.height}, {len(frame.jpeg)} bytes"
            f", display={frame.display_id})",
            file=sys.stderr,
        )
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

    if args.cmd == "bench":
        reset_service()
        out = get_service().bench(iterations=args.iterations, display_id=args.display)
        print(json.dumps(out, indent=2))
        return 0

    if args.cmd == "wait":
        reset_service()
        svc = get_service()
        started_watch = False
        if args.start_watch and not svc.daemon.running:
            svc.daemon.start()
            started_watch = True
        try:
            out = svc.wait_for_change(
                since_hash=args.since_hash,
                min_change_score=args.min_score,
                timeout_s=args.timeout,
                poll_s=args.poll,
            )
            print(json.dumps(out, indent=2))
            return 0 if out.get("changed") else 2
        finally:
            if started_watch:
                svc.daemon.stop()
                reset_service()

    if args.cmd == "export":
        from screen_watch.recording.session import RecordingManager

        mgr = RecordingManager(settings)
        out = mgr.export_session(
            args.session_id,
            dest=args.output,
            keyframes_only=args.keyframes_only,
        )
        print(json.dumps(out, indent=2))
        return 0 if out.get("ok") else 1

    if args.cmd == "watch":
        import time

        reset_service()
        svc = get_service()
        if args.display is not None:
            svc.set_display(args.display)
        svc.daemon.start()
        print(
            f"Watching via {svc.backend_name} @ {svc.settings.capped_fps()} FPS "
            f"(display={svc.settings.display}). Ctrl+C to stop.",
            file=sys.stderr,
        )
        started = time.time()
        last_hash = ""
        try:
            while True:
                if args.seconds > 0 and (time.time() - started) >= args.seconds:
                    break
                frame = svc.store.get()
                if frame is not None and frame.content_hash != last_hash:
                    print(
                        f"change hash={frame.content_hash[:12]}… "
                        f"{frame.width}x{frame.height} bytes={len(frame.jpeg)}",
                        file=sys.stderr,
                    )
                    last_hash = frame.content_hash
                time.sleep(0.2)
        except KeyboardInterrupt:
            print("Stopping watch…", file=sys.stderr)
        finally:
            svc.daemon.stop()
            reset_service()
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
