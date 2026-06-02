import argparse
import csv
import sqlite3
from pathlib import Path
from typing import List

DEFAULT_DB_PATH = Path("users.db")


def create_table(connection: sqlite3.Connection, headers: List[str]) -> None:
    columns = ", ".join([f"\"{header}\" TEXT" for header in headers])
    connection.execute(f"CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, {columns})")
    connection.commit()


def insert_rows(connection: sqlite3.Connection, headers: List[str], rows: List[List[str]]) -> None:
    placeholders = ", ".join(["?" for _ in headers])
    sql = f"INSERT INTO users ({', '.join([f'\"{header}\"' for header in headers])}) VALUES ({placeholders})"
    connection.executemany(sql, rows)
    connection.commit()


def import_csv(csv_path: Path, db_path: Path) -> int:
    with csv_path.open(newline="", encoding="utf-8") as file:
        reader = csv.reader(file)
        headers = next(reader, None)
        if not headers:
            raise ValueError("CSV file must include a header row.")

        rows = [row for row in reader if row]

    with sqlite3.connect(db_path) as connection:
        create_table(connection, headers)
        insert_rows(connection, headers, rows)

    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import CSV user data into a SQLite database.")
    parser.add_argument("--csv", dest="csv_path", default="users.csv", help="Path to the input CSV file")
    parser.add_argument("--db", dest="db_path", default=str(DEFAULT_DB_PATH), help="Path to the SQLite database file")
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    imported_count = import_csv(csv_path, Path(args.db_path))
    print(f"Imported {imported_count} rows into {args.db_path}")


if __name__ == "__main__":
    main()
