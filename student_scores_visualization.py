import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

try:
    from urllib.request import urlopen, Request
    from urllib.error import URLError, HTTPError
except ImportError:
    urlopen = None

OUTPUT_IMAGE = Path("student_scores.png")

SAMPLE_SCORES = [
    {"name": "Alice", "score": 92},
    {"name": "Bob", "score": 78},
    {"name": "Charlie", "score": 85},
    {"name": "Diana", "score": 90},
]


def fetch_scores(api_url: str) -> List[Dict[str, Any]]:
    if not api_url:
        return SAMPLE_SCORES

    request = Request(api_url, headers={"User-Agent": "Python Student Scores Client"})
    try:
        with urlopen(request, timeout=15) as response:
            payload = response.read().decode("utf-8")
            data = json.loads(payload)
            if isinstance(data, dict) and "students" in data:
                return data["students"]
            if isinstance(data, list):
                return data
            raise ValueError("Unexpected JSON format: expected a list or {'students': [...]}.")
    except (URLError, HTTPError, ValueError, json.JSONDecodeError) as exc:
        print(f"Warning: failed to fetch API data ({exc}). Using sample score data.")
        return SAMPLE_SCORES


def calculate_average(scores: List[Dict[str, Any]]) -> float:
    score_values = [float(item.get("score", 0)) for item in scores]
    if not score_values:
        return 0.0
    return sum(score_values) / len(score_values)


def draw_bar_chart(scores: List[Dict[str, Any]], output_path: Path) -> None:
    if plt is None:
        raise RuntimeError("matplotlib is required to render the bar chart. Install it with 'pip install matplotlib'.")

    names = [item.get("name", "Unknown") for item in scores]
    values = [float(item.get("score", 0)) for item in scores]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(names, values, color="#4c72b0")
    ax.set_title("Student Test Scores")
    ax.set_xlabel("Student")
    ax.set_ylabel("Score")
    ax.set_ylim(0, max(values + [100]))
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    plt.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch student scores, compute the average, and visualize them.")
    parser.add_argument("--api-url", dest="api_url", default="", help="URL of the student scores JSON API")
    parser.add_argument("--output", dest="output_path", default=str(OUTPUT_IMAGE), help="Output image path for the bar chart")
    args = parser.parse_args()

    scores = fetch_scores(args.api_url)
    average = calculate_average(scores)

    print(f"Loaded {len(scores)} student score records.")
    print(f"Average score: {average:.2f}")

    try:
        draw_bar_chart(scores, Path(args.output_path))
        print(f"Saved score chart to {args.output_path}")
    except RuntimeError as exc:
        print(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
