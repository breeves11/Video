"""Snapshot the app's SQLite database and prune old snapshots.

    python scripts/backup_db.py                      # -> ./backups, keep 14
    python scripts/backup_db.py --dest /mnt/backups --keep 30

Uses SQLite's online backup API, so it's safe to run while the app is
serving traffic (a plain file copy can capture a half-written database).
Schedule it, e.g. nightly via cron:

    15 3 * * * cd /path/to/smallbiz-agents && .venv/bin/python scripts/backup_db.py --dest /mnt/backups

A backup on the same disk as the database only protects against mistakes,
not disk loss -- point --dest at different storage, or sync it off-box.
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import config  # noqa: E402

PREFIX = "app-"


def backup(dest: Path, keep: int) -> Path:
    source_path = config.DATABASE_PATH
    if not source_path.exists():
        raise FileNotFoundError(f"No database at {source_path}")

    dest.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = dest / f"{PREFIX}{stamp}.db"

    source = sqlite3.connect(str(source_path))
    try:
        with sqlite3.connect(str(target)) as out:
            source.backup(out)
    finally:
        source.close()

    snapshots = sorted(dest.glob(f"{PREFIX}*.db"))
    for old in snapshots[:-keep] if keep > 0 else []:
        old.unlink()
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dest", default="backups", help="directory for snapshots (default: ./backups)")
    parser.add_argument("--keep", type=int, default=14, help="snapshots to keep (default: 14)")
    args = parser.parse_args(argv)

    try:
        target = backup(Path(args.dest), args.keep)
    except (FileNotFoundError, sqlite3.Error) as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        return 1
    print(f"Backed up {config.DATABASE_PATH} -> {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
