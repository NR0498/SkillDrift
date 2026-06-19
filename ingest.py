from skilldrift.config import get_settings
from skilldrift.db import initialize_databases
from skilldrift.ingestion import fetch_jobs, save_snapshot
from skilldrift.logging import configure_logging


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    initialize_databases(settings)
    jobs = fetch_jobs(settings)
    saved = save_snapshot(jobs)
    print(f"[Ingest] fetched={len(jobs)} inserted={saved}")


if __name__ == "__main__":
    main()
