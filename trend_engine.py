import argparse
import os
import sys
from pathlib import Path


def _configure_local_spark_runtime() -> None:
    """Use the active Python and an optional workspace-local Java 17 runtime."""
    python_executable = str(Path(sys.executable).resolve())
    os.environ["PYSPARK_PYTHON"] = python_executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = python_executable

    if os.name != "nt":
        return

    java_root = Path(__file__).resolve().parent / ".tools" / "java17"
    java_homes = sorted(
        (path for path in java_root.glob("jdk-*") if (path / "bin" / "java.exe").is_file()),
        reverse=True,
    )
    if not java_homes:
        return

    java_home = str(java_homes[0])
    os.environ["JAVA_HOME"] = java_home
    os.environ["PATH"] = f"{java_home}\\bin;{os.environ.get('PATH', '')}"


_configure_local_spark_runtime()


def main() -> None:
    from skilldrift.config import get_settings
    from skilldrift.db import initialize_databases
    from skilldrift.logging import configure_logging
    from skilldrift.trends import run_trend_engine

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
