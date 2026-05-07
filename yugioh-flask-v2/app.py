from flask import Flask, render_template, request, jsonify, session
import sqlite3, hashlib, requests, threading, webbrowser
from datetime import datetime, timedelta
import random

app = Flask(__name__)
app.secret_key = "ygo-vault-secret-key-change-in-production"
DB_PATH = "yugioh.db"


# ── Database connection ──
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Create tables and seed demo data on first run ──
def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT UNIQUE NOT NULL,
            email      TEXT UNIQUE NOT NULL,
            name       TEXT NOT NULL,
            password   TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS card_information (
            card_name         TEXT PRIMARY KEY,
            supertype         TEXT,
            card_text         TEXT,
            monster_attribute TEXT,
            monster_type      TEXT,
            monster_supertype TEXT,
            monster_level     INTEGER,
            attack            INTEGER,
            defense           INTEGER,
            price             REAL DEFAULT 0.0,
            image_url         TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS user_collection (
            collection_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL,
            card_name      TEXT NOT NULL,
            quantity       INTEGER DEFAULT 1,
            card_condition TEXT DEFAULT 'Near Mint',
            acquired_date  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)   REFERENCES users(user_id),
            FOREIGN KEY (card_name) REFERENCES card_information(card_name)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS decks (
            deck_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            deck_name  TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS deck_cards (
            deck_id   INTEGER NOT NULL,
            card_name TEXT NOT NULL,
            quantity  INTEGER DEFAULT 1,
            section   TEXT DEFAULT 'Main',
            PRIMARY KEY (deck_id, card_name),
            FOREIGN KEY (deck_id)   REFERENCES decks(deck_id),
            FOREIGN KEY (card_name) REFERENCES card_information(card_name)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            history_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            card_name   TEXT NOT NULL,
            price       REAL NOT NULL,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    seed_demo_data(conn)
    conn.close()


def seed_demo_data(conn):
    c = conn.cursor()

    # Skip seeding if the demo account already exists
    c.execute("SELECT COUNT(*) FROM users WHERE username = 'demo'")
    if c.fetchone()[0] > 0:
        return

    # Cards: (name, supertype, text, attribute, type, supertype, level, atk, def, price, image)
    cards = [
        ("Dark Magician",             "Monster", "The ultimate wizard in terms of attack and defense.",                                                                        "DARK",  "Spellcaster", "Normal", 7, 2500, 2100,  4.50, "https://images.ygoprodeck.com/images/cards_small/46986414.jpg"),
        ("Blue-Eyes White Dragon",    "Monster", "This legendary dragon is a powerful engine of destruction.",                                                                 "LIGHT", "Dragon",      "Normal", 8, 3000, 2500, 12.00, "https://images.ygoprodeck.com/images/cards_small/89631139.jpg"),
        ("Exodia the Forbidden One",  "Monster", "If you have all 5 pieces, you win the Duel.",                                                                                "DARK",  "Spellcaster", "Normal", 3, 1000, 1000,  8.75, "https://images.ygoprodeck.com/images/cards_small/33396948.jpg"),
        ("Mirror Force",              "Trap",    "When an opponent's monster declares an attack, destroy all Attack Position monsters they control.",                           None,    None,          None,    None, None, None,  1.20, "https://images.ygoprodeck.com/images/cards_small/44095762.jpg"),
        ("Pot of Greed",              "Spell",   "Draw 2 cards.",                                                                                                              None,    None,          None,    None, None, None,  6.00, "https://images.ygoprodeck.com/images/cards_small/55144522.jpg"),
        ("Raigeki",                   "Spell",   "Destroy all monsters your opponent controls.",                                                                               None,    None,          None,    None, None, None,  3.40, "https://images.ygoprodeck.com/images/cards_small/12580477.jpg"),
        ("Red-Eyes Black Dragon",     "Monster", "A ferocious dragon with a deadly attack.",                                                                                   "DARK",  "Dragon",      "Normal", 7, 2400, 2000,  2.80, "https://images.ygoprodeck.com/images/cards_small/74677422.jpg"),
        ("Jinzo",                     "Monster", "As long as this card remains face-up, Trap Cards cannot be activated.",                                                      "DARK",  "Machine",     "Effect", 6, 2400, 1500,  5.50, "https://images.ygoprodeck.com/images/cards_small/77585513.jpg"),
        ("Monster Reborn",            "Spell",   "Target 1 monster in either GY; Special Summon it.",                                                                         None,    None,          None,    None, None, None,  2.10, "https://images.ygoprodeck.com/images/cards_small/83764718.jpg"),
        ("Solemn Judgment",           "Trap",    "When a monster would be Summoned, or a Spell/Trap is activated: Pay half your LP; negate it and destroy that card.",        None,    None,          None,    None, None, None,  7.25, "https://images.ygoprodeck.com/images/cards_small/41420027.jpg"),
        ("Swords of Revealing Light", "Spell",   "Flip all opponent monsters face-up; for the next 3 of your opponent's turns, their monsters cannot attack.",                None,    None,          None,    None, None, None,  0.75, "https://images.ygoprodeck.com/images/cards_small/72302403.jpg"),
        ("Summoned Skull",            "Monster", "A fiend with dark powers for confusing the enemy.",                                                                          "DARK",  "Fiend",       "Normal", 6, 2500, 1200,  1.50, "https://images.ygoprodeck.com/images/cards_small/70781052.jpg"),
    ]

    c.executemany("""
        INSERT OR IGNORE INTO card_information
        (card_name, supertype, card_text, monster_attribute, monster_type,
         monster_supertype, monster_level, attack, defense, price, image_url)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, cards)

    # Create the demo user (password: demo123)
    pw_hash = hashlib.sha256("demo123".encode()).hexdigest()
    c.execute("""
        INSERT OR IGNORE INTO users (username, email, name, password)
        VALUES ('demo', 'demo@ygoprodeck.com', 'Demo Duelist', ?)
    """, (pw_hash,))
    conn.commit()

    user_id = conn.execute("SELECT user_id FROM users WHERE username = 'demo'").fetchone()[0]

    # Add cards to the demo collection
    collection = [
        ("Dark Magician",            3, "Near Mint"),
        ("Blue-Eyes White Dragon",   2, "Near Mint"),
        ("Exodia the Forbidden One", 1, "Lightly Played"),
        ("Mirror Force",             2, "Near Mint"),
        ("Pot of Greed",             1, "Near Mint"),
        ("Raigeki",                  1, "Near Mint"),
        ("Red-Eyes Black Dragon",    2, "Moderately Played"),
        ("Jinzo",                    1, "Near Mint"),
        ("Monster Reborn",           3, "Near Mint"),
        ("Solemn Judgment",          2, "Near Mint"),
    ]
    for card_name, qty, condition in collection:
        c.execute("""
            INSERT INTO user_collection (user_id, card_name, quantity, card_condition)
            VALUES (?, ?, ?, ?)
        """, (user_id, card_name, qty, condition))

    # Create a demo deck
    c.execute("INSERT INTO decks (user_id, deck_name) VALUES (?, 'Classic Beatdown')", (user_id,))
    conn.commit()
    deck_id = conn.execute(
        "SELECT deck_id FROM decks WHERE user_id=? AND deck_name='Classic Beatdown'", (user_id,)
    ).fetchone()[0]

    deck_cards = [
        ("Dark Magician", 3), ("Blue-Eyes White Dragon", 2), ("Red-Eyes Black Dragon", 2),
        ("Jinzo", 1), ("Summoned Skull", 2), ("Monster Reborn", 3),
        ("Raigeki", 1), ("Mirror Force", 2), ("Solemn Judgment", 2),
    ]
    for card_name, qty in deck_cards:
        c.execute("""
            INSERT OR IGNORE INTO deck_cards (deck_id, card_name, quantity)
            VALUES (?, ?, ?)
        """, (deck_id, card_name, qty))

    # Seed 90 days of price history so the dashboard graph has real data to show
    for card_name, _, _, _, _, _, _, _, _, base_price, _ in cards:
        price = base_price * 0.75
        for days_ago in range(90, -1, -1):
            day   = datetime.now() - timedelta(days=days_ago)
            price = max(0.01, price + (random.random() - 0.47) * base_price * 0.055)
            c.execute("""
                INSERT INTO price_history (card_name, price, recorded_at)
                VALUES (?, ?, ?)
            """, (card_name, round(price, 2), day.strftime("%Y-%m-%d %H:%M:%S")))

    conn.commit()


# ── Hash a password with SHA-256 ──
def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


# ── Decorator: block requests from users who are not logged in ──
def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Not logged in"}), 401
        return f(*args, **kwargs)
    return wrapper


# ───────────────────────────────
#  PAGE ROUTE
# ───────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ───────────────────────────────
#  AUTH ROUTES
# ───────────────────────────────

@app.route("/api/register", methods=["POST"])
def register():
    data     = request.json
    name     = data.get("name", "").strip()
    username = data.get("username", "").strip()
    email    = data.get("email", "").strip()
    password = data.get("password", "")

    if not all([name, username, email, password]):
        return jsonify({"error": "All fields are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, email, name, password) VALUES (?,?,?,?)",
            (username, email, name, hash_pw(password))
        )
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        session["user_id"]  = user["user_id"]
        session["username"] = user["username"]
        session["name"]     = user["name"]
        return jsonify({"ok": True, "name": user["name"], "username": user["username"]})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username or email already taken"}), 409
    finally:
        conn.close()


@app.route("/api/login", methods=["POST"])
def login():
    data     = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "")

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (username, hash_pw(password))
    ).fetchone()
    conn.close()

    if not user:
        return jsonify({"error": "Invalid username or password"}), 401

    session["user_id"]  = user["user_id"]
    session["username"] = user["username"]
    session["name"]     = user["name"]
    return jsonify({"ok": True, "name": user["name"], "username": user["username"]})


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/me")
def me():
    if "user_id" not in session:
        return jsonify({"logged_in": False})
    return jsonify({"logged_in": True, "name": session["name"], "username": session["username"]})


# ───────────────────────────────
#  COLLECTION ROUTES
# ───────────────────────────────

@app.route("/api/collection")
@login_required
def get_collection():
    conn = get_db()
    rows = conn.execute("""
        SELECT uc.card_name, uc.quantity, uc.card_condition,
               ci.supertype, ci.price, ci.image_url, ci.monster_attribute
        FROM user_collection uc
        JOIN card_information ci ON uc.card_name = ci.card_name
        WHERE uc.user_id = ?
        ORDER BY ci.price DESC
    """, (session["user_id"],)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/collection/add", methods=["POST"])
@login_required
def add_to_collection():
    card_name = request.json.get("card_name")
    condition = request.json.get("condition", "Near Mint")
    conn      = get_db()

    # If the card isn't in our local DB yet, fetch it from YGOPRODeck and save it
    exists = conn.execute(
        "SELECT card_name FROM card_information WHERE card_name=?", (card_name,)
    ).fetchone()

    if not exists:
        try:
            resp      = requests.get(f"https://db.ygoprodeck.com/api/v7/cardinfo.php?name={requests.utils.quote(card_name)}", timeout=5)
            card_data = resp.json()["data"][0]
            price     = float(card_data.get("card_prices", [{}])[0].get("tcgplayer_price", 0) or 0)
            img       = card_data.get("card_images", [{}])[0].get("image_url_small", "")
            ctype     = card_data.get("type", "")
            supertype = "Monster" if "Monster" in ctype else ("Spell" if "Spell" in ctype else "Trap")
            conn.execute("""
                INSERT OR IGNORE INTO card_information
                (card_name, supertype, card_text, monster_attribute, monster_type,
                 monster_level, attack, defense, price, image_url)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                card_name, supertype, card_data.get("desc", ""),
                card_data.get("attribute"), card_data.get("race"),
                card_data.get("level"), card_data.get("atk"), card_data.get("def"),
                price, img
            ))
            conn.commit()
        except Exception:
            conn.close()
            return jsonify({"error": f"Could not find card: {card_name}"}), 404

    # Increment quantity if already owned, otherwise insert a new row
    owned = conn.execute(
        "SELECT collection_id, quantity FROM user_collection WHERE user_id=? AND card_name=?",
        (session["user_id"], card_name)
    ).fetchone()

    if owned:
        conn.execute(
            "UPDATE user_collection SET quantity=? WHERE collection_id=?",
            (owned["quantity"] + 1, owned["collection_id"])
        )
    else:
        conn.execute(
            "INSERT INTO user_collection (user_id, card_name, quantity, card_condition) VALUES (?,?,1,?)",
            (session["user_id"], card_name, condition)
        )

    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/collection/update", methods=["POST"])
@login_required
def update_collection():
    card_name = request.json.get("card_name")
    qty       = int(request.json.get("quantity", 1))
    conn      = get_db()

    if qty <= 0:
        # Remove the card entirely if quantity drops to zero
        conn.execute(
            "DELETE FROM user_collection WHERE user_id=? AND card_name=?",
            (session["user_id"], card_name)
        )
    else:
        conn.execute(
            "UPDATE user_collection SET quantity=? WHERE user_id=? AND card_name=?",
            (qty, session["user_id"], card_name)
        )

    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/collection/remove", methods=["POST"])
@login_required
def remove_from_collection():
    card_name = request.json.get("card_name")
    conn      = get_db()
    conn.execute(
        "DELETE FROM user_collection WHERE user_id=? AND card_name=?",
        (session["user_id"], card_name)
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ───────────────────────────────
#  DECK ROUTES
# ───────────────────────────────

@app.route("/api/decks")
@login_required
def get_decks():
    conn  = get_db()
    decks = conn.execute(
        "SELECT * FROM decks WHERE user_id=? ORDER BY created_at DESC",
        (session["user_id"],)
    ).fetchall()

    result = []
    for deck in decks:
        total = conn.execute(
            "SELECT COALESCE(SUM(quantity), 0) as total FROM deck_cards WHERE deck_id=?",
            (deck["deck_id"],)
        ).fetchone()["total"]
        result.append({**dict(deck), "total_cards": total})

    conn.close()
    return jsonify(result)


@app.route("/api/decks/create", methods=["POST"])
@login_required
def create_deck():
    name = request.json.get("deck_name", "").strip()
    if not name:
        return jsonify({"error": "Deck name required"}), 400

    conn = get_db()
    conn.execute("INSERT INTO decks (user_id, deck_name) VALUES (?,?)", (session["user_id"], name))
    conn.commit()
    deck_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return jsonify({"ok": True, "deck_id": deck_id})


@app.route("/api/decks/<int:deck_id>")
@login_required
def get_deck(deck_id):
    conn = get_db()
    deck = conn.execute(
        "SELECT * FROM decks WHERE deck_id=? AND user_id=?",
        (deck_id, session["user_id"])
    ).fetchone()

    if not deck:
        conn.close()
        return jsonify({"error": "Deck not found"}), 404

    cards = conn.execute("""
        SELECT dc.card_name, dc.quantity, dc.section,
               ci.supertype, ci.price, ci.image_url
        FROM deck_cards dc
        JOIN card_information ci ON dc.card_name = ci.card_name
        WHERE dc.deck_id=?
    """, (deck_id,)).fetchall()

    conn.close()
    return jsonify({"deck": dict(deck), "cards": [dict(c) for c in cards]})


@app.route("/api/decks/<int:deck_id>/add", methods=["POST"])
@login_required
def add_to_deck(deck_id):
    card_name = request.json.get("card_name")
    conn      = get_db()

    # Make sure this deck belongs to the logged-in user
    deck = conn.execute(
        "SELECT * FROM decks WHERE deck_id=? AND user_id=?",
        (deck_id, session["user_id"])
    ).fetchone()
    if not deck:
        conn.close()
        return jsonify({"error": "Deck not found"}), 404

    # Enforce the 40-card limit
    total = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) as t FROM deck_cards WHERE deck_id=?",
        (deck_id,)
    ).fetchone()["t"]
    if total >= 40:
        conn.close()
        return jsonify({"error": "Deck is full (40 card limit)"}), 400

    # Can't add more copies to the deck than the user actually owns
    owned       = conn.execute(
        "SELECT quantity FROM user_collection WHERE user_id=? AND card_name=?",
        (session["user_id"], card_name)
    ).fetchone()
    in_deck     = conn.execute(
        "SELECT quantity FROM deck_cards WHERE deck_id=? AND card_name=?",
        (deck_id, card_name)
    ).fetchone()
    in_deck_qty = in_deck["quantity"] if in_deck else 0

    if not owned or in_deck_qty >= owned["quantity"]:
        conn.close()
        return jsonify({"error": "Not enough copies owned"}), 400

    if in_deck:
        conn.execute(
            "UPDATE deck_cards SET quantity=? WHERE deck_id=? AND card_name=?",
            (in_deck_qty + 1, deck_id, card_name)
        )
    else:
        conn.execute(
            "INSERT INTO deck_cards (deck_id, card_name, quantity) VALUES (?,?,1)",
            (deck_id, card_name)
        )

    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/decks/<int:deck_id>/remove", methods=["POST"])
@login_required
def remove_from_deck(deck_id):
    card_name = request.json.get("card_name")
    conn      = get_db()
    in_deck   = conn.execute(
        "SELECT quantity FROM deck_cards WHERE deck_id=? AND card_name=?",
        (deck_id, card_name)
    ).fetchone()

    if in_deck:
        if in_deck["quantity"] <= 1:
            conn.execute("DELETE FROM deck_cards WHERE deck_id=? AND card_name=?", (deck_id, card_name))
        else:
            conn.execute(
                "UPDATE deck_cards SET quantity=? WHERE deck_id=? AND card_name=?",
                (in_deck["quantity"] - 1, deck_id, card_name)
            )

    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/decks/<int:deck_id>/delete", methods=["POST"])
@login_required
def delete_deck(deck_id):
    conn = get_db()
    conn.execute("DELETE FROM deck_cards WHERE deck_id=?", (deck_id,))
    conn.execute("DELETE FROM decks WHERE deck_id=? AND user_id=?", (deck_id, session["user_id"]))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ───────────────────────────────
#  CARD SEARCH ROUTE
# ───────────────────────────────

@app.route("/api/cards/search")
@login_required
def search_cards():
    # Proxy to YGOPRODeck so we don't expose the external API call to the browser
    q     = request.args.get("q", "")
    ctype = request.args.get("type", "")
    attr  = request.args.get("attribute", "")

    if not q and not ctype and not attr:
        return jsonify([])

    url = "https://db.ygoprodeck.com/api/v7/cardinfo.php?num=24&offset=0"
    if q:     url += f"&fname={requests.utils.quote(q)}"
    if ctype: url += f"&type={requests.utils.quote(ctype + ' Card')}"
    if attr:  url += f"&attribute={attr}"

    try:
        resp = requests.get(url, timeout=8)
        return jsonify(resp.json().get("data", []))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ───────────────────────────────
#  PRICE ROUTES
# ───────────────────────────────

@app.route("/api/price/live/<card_name>")
@login_required
def price_live(card_name):
    # Fetch the current TCGPlayer price and save a snapshot to price_history
    try:
        resp      = requests.get(
            f"https://db.ygoprodeck.com/api/v7/cardinfo.php?name={requests.utils.quote(card_name)}",
            timeout=8
        )
        card_data = resp.json()["data"][0]
        prices    = card_data.get("card_prices", [{}])[0]
        tcg_price = float(prices.get("tcgplayer_price") or 0)

        conn = get_db()
        conn.execute("INSERT INTO price_history (card_name, price) VALUES (?,?)", (card_name, tcg_price))
        conn.commit()
        conn.close()

        return jsonify({
            "card_name":        card_name,
            "tcgplayer_price":  tcg_price,
            "cardmarket_price": float(prices.get("cardmarket_price") or 0),
            "ebay_price":       float(prices.get("ebay_price") or 0),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/price/history/<card_name>")
@login_required
def price_history(card_name):
    # Return daily averaged price snapshots for the last 90 days
    conn = get_db()
    rows = conn.execute("""
        SELECT price, recorded_at FROM price_history
        WHERE card_name=?
        ORDER BY recorded_at ASC
    """, (card_name,)).fetchall()
    conn.close()

    if not rows:
        return jsonify([])

    # Group snapshots by day and average them
    daily = {}
    for row in rows:
        day = row["recorded_at"][:10]
        daily.setdefault(day, []).append(row["price"])

    result = [
        {"date": day, "price": round(sum(prices) / len(prices), 2)}
        for day, prices in sorted(daily.items())
    ]
    return jsonify(result[-90:])


# ───────────────────────────────
#  DASHBOARD ROUTES
# ───────────────────────────────

@app.route("/api/dashboard")
@login_required
def dashboard():
    conn = get_db()
    col  = conn.execute("""
        SELECT uc.card_name, uc.quantity, ci.price, ci.supertype
        FROM user_collection uc
        JOIN card_information ci ON uc.card_name = ci.card_name
        WHERE uc.user_id=?
        ORDER BY ci.price DESC
    """, (session["user_id"],)).fetchall()

    deck_count = conn.execute(
        "SELECT COUNT(*) as c FROM decks WHERE user_id=?",
        (session["user_id"],)
    ).fetchone()["c"]
    conn.close()

    return jsonify({
        "total_cards":  sum(r["quantity"] for r in col),
        "unique_cards": len(col),
        "total_value":  round(sum(r["quantity"] * r["price"] for r in col), 2),
        "deck_count":   deck_count,
        "recent":       [dict(r) for r in col[:5]],
    })


@app.route("/api/collection/trend")
@login_required
def collection_trend():
    # Returns daily total portfolio value for the dashboard graph
    conn  = get_db()
    owned = conn.execute("""
        SELECT uc.card_name, uc.quantity, ci.price as current_price
        FROM user_collection uc
        JOIN card_information ci ON uc.card_name = ci.card_name
        WHERE uc.user_id = ?
    """, (session["user_id"],)).fetchall()

    if not owned:
        conn.close()
        return jsonify([])

    card_names     = [r["card_name"] for r in owned]
    quantities     = {r["card_name"]: r["quantity"]      for r in owned}
    current_prices = {r["card_name"]: r["current_price"] for r in owned}

    # Get daily average price per card for the last 90 days
    cutoff       = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    placeholders = ",".join("?" * len(card_names))
    rows = conn.execute(f"""
        SELECT card_name, DATE(recorded_at) as day, AVG(price) as avg_price
        FROM price_history
        WHERE card_name IN ({placeholders})
          AND DATE(recorded_at) >= ?
        GROUP BY card_name, DATE(recorded_at)
        ORDER BY day ASC
    """, (*card_names, cutoff)).fetchall()
    conn.close()

    # Build a lookup: day -> {card_name -> avg_price}
    daily_prices = {}
    for row in rows:
        daily_prices.setdefault(row["day"], {})[row["card_name"]] = row["avg_price"]

    if not daily_prices:
        return jsonify([])

    # Walk each day and compute total portfolio value,
    # carrying forward the last known price for any card missing that day
    last_known = dict(current_prices)
    result     = []
    for day in sorted(daily_prices.keys()):
        last_known.update(daily_prices[day])
        total = sum(last_known[name] * quantities[name] for name in card_names)
        result.append({"date": day, "value": round(total, 2)})

    return jsonify(result)


# ───────────────────────────────
#  START
# ───────────────────────────────

def open_browser():
    # Wait 1.2s for Flask to finish starting, then open the browser automatically
    threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:5001")).start()

if __name__ == "__main__":
    init_db()
    print("\n  ✅  YGO Vault is running!")
    print("  🌐  Opening http://127.0.0.1:5001 in your browser…\n")
    open_browser()
    app.run(debug=False, port=5001)