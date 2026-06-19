import argparse

from skilldrift.config import get_settings
from skilldrift.db import initialize_databases
from skilldrift.logging import configure_logging
from skilldrift.simulation import simulate_history


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create deterministic demo job history.")
    parser.add_argument("--days", type=int, default=6, help="Historical days to create (1-90)")
    parser.add_argument("--seed", type=int, default=42, help="Reproducible random seed")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete generated date range before inserting it again",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)
    initialize_databases(settings)
    inserted = simulate_history(days=args.days, seed=args.seed, replace=args.replace)
    print(f"[Simulation] inserted={inserted} days={args.days} seed={args.seed}")


if __name__ == "__main__":
    main()
