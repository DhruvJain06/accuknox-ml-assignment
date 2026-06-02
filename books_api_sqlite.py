import argparse
import json
import socket
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from urllib.request import urlopen, Request
    from urllib.error import URLError, HTTPError
except ImportError:
    urlopen = None

DB_PATH = Path("books.db")

SAMPLE_BOOKS = [
    {"title": "The Lean Startup", "author": "Eric Ries", "publication_year": 2011},
    {"title": "Clean Code", "author": "Robert C. Martin", "publication_year": 2008},
    {"title": "The Pragmatic Programmer", "author": "Andrew Hunt", "publication_year": 1999},
]


def create_books_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            publication_year INTEGER NOT NULL,
            UNIQUE(title, author, publication_year)
        )
        """
    )
    connection.commit()


def fetch_books(api_url: str) -> List[Dict[str, Any]]:
    if not api_url:
        return SAMPLE_BOOKS

    request = Request(api_url, headers={"User-Agent": "Python SQLite Client"})
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8")
            data = json.loads(payload)
            if isinstance(data, dict):
                if "books" in data:
                    return data["books"]
                if "results" in data:
                    return data["results"]
                if "docs" in data:
                    return data["docs"]
            if isinstance(data, list):
                return data
            raise ValueError("Unexpected JSON format: expected a list or {'books': [...]}" )
    except (URLError, HTTPError, TimeoutError, socket.timeout, ValueError, json.JSONDecodeError) as exc:
        print(f"Warning: failed to fetch API data ({exc}). Using sample data.")
        return SAMPLE_BOOKS


def insert_books(connection: sqlite3.Connection, books: List[Dict[str, Any]]) -> None:
    db_rows = [
        (
            book.get("title", ""),
            book.get("author", ""),
            int(book.get("publication_year", 0) or 0),
        )
        for book in books
    ]
    connection.executemany(
        "INSERT OR IGNORE INTO books (title, author, publication_year) VALUES (?, ?, ?)",
        db_rows,
    )
    connection.commit()


def display_books(connection: sqlite3.Connection) -> None:
    cursor = connection.execute("SELECT title, author, publication_year FROM books ORDER BY publication_year, title")
    rows = cursor.fetchall()
    if not rows:
        print("No books available in the database.")
        return

    print("Books stored in SQLite database:")
    for title, author, year in rows:
        print(f"- {title} by {author} ({year})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch book data from an API and store it in SQLite.")
    parser.add_argument("--api-url", dest="api_url", default="", help="URL of the books JSON API")
    parser.add_argument("--db", dest="db_path", default=str(DB_PATH), help="SQLite database path")
    args = parser.parse_args()

    with sqlite3.connect(args.db_path) as connection:
        create_books_table(connection)
        books = fetch_books(args.api_url)
        insert_books(connection, books)
        display_books(connection)


if __name__ == "__main__":
    main()
