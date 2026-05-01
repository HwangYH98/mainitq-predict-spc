import argparse
import time

from realtime_ops import INCOMING_DIR, scan_realtime_folder, write_stage15_20_architecture


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 15-lite file-drop streaming simulation.")
    parser.add_argument("--incoming-dir", default=str(INCOMING_DIR))
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    write_stage15_20_architecture()
    print(f"Watching CSV folder: {args.incoming_dir}")

    while True:
        events = scan_realtime_folder(args.incoming_dir)
        if events:
            print(f"Processed {len(events)} prediction event(s).")
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
