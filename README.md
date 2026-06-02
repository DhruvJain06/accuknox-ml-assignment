# Interview Task Scripts

This repository contains three Python scripts for data ingestion, processing, and storage.

## Tasks

1. **API Data Retrieval and Storage**
   - `books_api_sqlite.py`
   - Fetches book data from an external REST API or uses built-in sample data
   - Stores results in a SQLite database at `books.db`
   - Prints stored book records to the console

2. **Data Processing and Visualization**
   - `student_scores_visualization.py`
   - Fetches student score data from an external API or uses built-in sample data
   - Computes the average score
   - Renders a bar chart and saves it as `student_scores.png`

3. **CSV Data Import to a Database**
   - `csv_to_sqlite.py`
   - Reads a CSV file containing user data
   - Imports the rows into a SQLite database at `users.db`

## Usage

Open a terminal in the `d:\Interview` folder and run the desired script.

### 1. Books API to SQLite

```powershell
python books_api_sqlite.py --api-url "https://gutendex.com/books/?page=2"
```

Use this link for client testing:
- `https://gutendex.com/books/?page=2`

If `--api-url` is omitted, the script falls back to built-in sample book data.

### 2. Student Scores Visualization

```powershell
python student_scores_visualization.py --api-url "https://mocki.io/v1/3b63189a-3d08-4e59-b069-7cd15bedc946"
```

Use this link for client testing:
- `https://mocki.io/v1/3b63189a-3d08-4e59-b069-7cd15bedc946`

If `--api-url` is omitted, the script falls back to built-in sample score data.

### 3. CSV to SQLite Import

```powershell
python csv_to_sqlite.py --csv users.csv --db users.db
```

If `--csv` is omitted, the script defaults to `users.csv` in the current folder.

## Notes

- The `books_api_sqlite.py` and `student_scores_visualization.py` scripts accept any JSON endpoint matching the expected response format.
- `csv_to_sqlite.py` expects a local CSV file and does not download remote CSV files automatically.

## Dependencies

- Python 3.8 or newer
- `matplotlib` for chart rendering in `student_scores_visualization.py`

Install required dependencies with:

```powershell
pip install matplotlib
```

## Files Included

- `books_api_sqlite.py`
- `student_scores_visualization.py`
- `csv_to_sqlite.py`
- `users.csv`
- `README.md`
