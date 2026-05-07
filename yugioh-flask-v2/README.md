# YGO Vault — Flask App

## Setup (one time)

1. Make sure Python is installed (python --version)
2. Open this folder in VS Code
3. Open the terminal (Ctrl + ` ) and run:

```
pip install flask requests
```

## Run the app

In the VS Code terminal:

```
python app.py
```

Then open your browser to: http://127.0.0.1:5000

## Demo account (pre-loaded with cards)

- Username: demo
- Password: demo123

This account has 10 cards in the collection and 1 pre-built deck so the dashboard is not empty.

## Files

- app.py         — Flask backend, all routes, SQLite database setup
- templates/     — HTML frontend (index.html)
- yugioh.db      — SQLite database (auto-created when you first run app.py)
- requirements.txt

## How the price graph works

1. You go to Price Trends and search a card
2. The app calls the FREE YGOPRODeck API to get the live TCGPlayer price
3. That price is stored in your local database (price_history table)
4. Over time, as you or other users look up cards, real snapshots accumulate
5. The graph shows those real stored snapshots, with 1W / 1M / 3M range buttons

## Replacing the temp database with MySQL

In app.py, the get_db() function uses sqlite3.
To switch to MySQL later, replace it with a MySQL connector (e.g. mysql-connector-python)
and update the connection string. All the SQL queries are standard and will work as-is.
