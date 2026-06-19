import argparse

from skilldrift.config import get_settings
from skilldrift.db import initialize_databases
from skilldrift.logging import configure_logging
from skilldrift.trends import run_trend_engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute skill drift with PySpark.")
    parser.add_argument("--threshold", type=float, default=0.3)
    parser.add_argument("--skip-s3", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    initialize_databases(settings)
    results = run_trend_engine(
        threshold=args.threshold,
        upload_summary=not args.skip_s3,
    )
    print(f"[Trends] computed={len(results)}")


if __name__ == "__main__":
    main()
