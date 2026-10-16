"""To-Do Task Manager - Flask + SQLite REST API with a static HTML/CSS/JS frontend."""
import os
import sqlite3
from datetime import date, datetime

from flask import Flask, g, jsonify, render_template, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRIORITIES = ("Low", "Medium", "High")
STATUSES = ("Pending", "Completed")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    deadline    TEXT,
    created_by  TEXT    NOT NULL DEFAULT 'Me',
    priority    TEXT    NOT NULL DEFAULT 'Medium',
    status      TEXT    NOT NULL DEFAULT 'Pending',
    created_at  TEXT    NOT NULL
);
"""


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path or os.environ.get(
        "DB_PATH", os.path.join(BASE_DIR, "tasks.db")
    )

    # ---------- database helpers ----------
    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DB_PATH"])
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def init_db():
        folder = os.path.dirname(app.config["DB_PATH"])
        if folder:
            os.makedirs(folder, exist_ok=True)
        with sqlite3.connect(app.config["DB_PATH"]) as con:
            con.executescript(SCHEMA)
            cols = [r[1] for r in con.execute("PRAGMA table_info(tasks)")]
            if "created_by" not in cols:  # upgrade older databases
                con.execute("ALTER TABLE tasks ADD COLUMN created_by TEXT NOT NULL DEFAULT 'Me'")

    init_db()

    # ---------- serialisation / validation ----------
    def serialize(row):
        today = date.today().isoformat()
        deadline = row["deadline"]
        return {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "deadline": deadline,
            "created_by": row["created_by"],
            "priority": row["priority"],
            "status": row["status"],
            "created_at": row["created_at"],
            "overdue": bool(deadline and row["status"] == "Pending" and deadline < today),
        }

    def validate(data, existing=None, partial=False):
        """Return (clean_values, errors). With partial=True only supplied keys are checked."""
        errors, clean = {}, {}
        existing = existing or {}

        def pick(key):
            if key in data:
                return True, data[key]
            if partial:
                return False, None
            return True, existing.get(key)

        has, title = pick("title")
        if has:
            title = (title or "").strip() if isinstance(title, str) or title is None else ""
            if not title:
                errors["title"] = "Task title cannot be empty."
            elif len(title) > 120:
                errors["title"] = "Task title must be 120 characters or fewer."
            else:
                clean["title"] = title

        has, desc = pick("description")
        if has:
            desc = (desc or "").strip() if isinstance(desc, (str, type(None))) else ""
            if len(desc) > 1000:
                errors["description"] = "Description must be 1000 characters or fewer."
            else:
                clean["description"] = desc

        has, deadline = pick("deadline")
        if has:
            if deadline in (None, ""):
                clean["deadline"] = None
            else:
                try:
                    datetime.strptime(str(deadline), "%Y-%m-%d")
                    clean["deadline"] = str(deadline)
                except ValueError:
                    errors["deadline"] = "Deadline must be a valid date (YYYY-MM-DD)."

        has, cb = pick("created_by")
        if has:
            cb = (cb or "").strip() if isinstance(cb, (str, type(None))) else ""
            if len(cb) > 60:
                errors["created_by"] = "Created by must be 60 characters or fewer."
            else:
                clean["created_by"] = cb or "Me"

        has, priority = pick("priority")
        if has:
            priority = priority or "Medium"
            if priority not in PRIORITIES:
                errors["priority"] = "Priority must be Low, Medium or High."
            else:
                clean["priority"] = priority

        has, status = pick("status")
        if has:
            status = status or "Pending"
            if status not in STATUSES:
                errors["status"] = "Status must be Pending or Completed."
            else:
                clean["status"] = status

        return clean, errors

    def bad_request(errors):
        return jsonify({"error": "Validation failed.", "errors": errors}), 400

    def not_found():
        return jsonify({"error": "Task not found."}), 404

    def fetch(task_id):
        return get_db().execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

    def json_body():
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else None

    # ---------- pages ----------
    @app.get("/")
    def index():
        return render_template("index.html")

    # ---------- REST API ----------
    @app.get("/api/tasks")
    def list_tasks():
        status = request.args.get("status", "").strip()
        priority = request.args.get("priority", "").strip()
        search = request.args.get("search", "").strip()
        deadline = request.args.get("deadline", "").strip()
        overdue = request.args.get("overdue", "").lower() in ("1", "true", "yes")

        try:
            page = max(int(request.args.get("page", 1)), 1)
            per_page = min(max(int(request.args.get("per_page", 10)), 1), 100)
        except ValueError:
            return bad_request({"page": "page and per_page must be integers."})

        where, params = [], []
        if status in STATUSES:
            where.append("status = ?")
            params.append(status)
        if priority in PRIORITIES:
            where.append("priority = ?")
            params.append(priority)
        if search:
            where.append("(title LIKE ? OR description LIKE ?)")
            params += [f"%{search}%"] * 2
        if deadline:
            where.append("deadline = ?")
            params.append(deadline)
        if overdue:
            where.append("status = 'Pending' AND deadline IS NOT NULL AND deadline < ?")
            params.append(date.today().isoformat())

        clause = ("WHERE " + " AND ".join(where)) if where else ""
        db = get_db()
        total = db.execute(f"SELECT COUNT(*) FROM tasks {clause}", params).fetchone()[0]
        rows = db.execute(
            f"""SELECT * FROM tasks {clause}
                ORDER BY (deadline IS NULL), deadline ASC, id DESC
                LIMIT ? OFFSET ?""",
            params + [per_page, (page - 1) * per_page],
        ).fetchall()

        overdue_count = db.execute(
            "SELECT COUNT(*) FROM tasks WHERE status='Pending' AND deadline IS NOT NULL AND deadline < ?",
            (date.today().isoformat(),),
        ).fetchone()[0]

        return jsonify(
            {
                "items": [serialize(r) for r in rows],
                "total": total,
                "page": page,
                "per_page": per_page,
                "overdue_count": overdue_count,
            }
        )

    @app.get("/api/tasks/<int:task_id>")
    def get_task(task_id):
        row = fetch(task_id)
        return jsonify(serialize(row)) if row else not_found()

    @app.post("/api/tasks")
    def create_task():
        data = json_body()
        if data is None:
            return bad_request({"body": "Request body must be a JSON object."})
        clean, errors = validate(data, existing={})
        if errors:
            return bad_request(errors)
        db = get_db()
        cur = db.execute(
            """INSERT INTO tasks (title, description, deadline, created_by, priority, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                clean["title"],
                clean.get("description", ""),
                clean.get("deadline"),
                clean.get("created_by", "Me"),
                clean.get("priority", "Medium"),
                clean.get("status", "Pending"),
                datetime.now().strftime("%Y-%m-%d"),
            ),
        )
        db.commit()
        return jsonify(serialize(fetch(cur.lastrowid))), 201

    @app.put("/api/tasks/<int:task_id>")
    def replace_task(task_id):
        row = fetch(task_id)
        if not row:
            return not_found()
        data = json_body()
        if data is None:
            return bad_request({"body": "Request body must be a JSON object."})
        clean, errors = validate(data, existing=dict(row))
        if errors:
            return bad_request(errors)
        db = get_db()
        db.execute(
            """UPDATE tasks SET title=?, description=?, deadline=?, created_by=?, priority=?, status=?
               WHERE id=?""",
            (
                clean["title"],
                clean["description"],
                clean["deadline"],
                clean["created_by"],
                clean["priority"],
                clean["status"],
                task_id,
            ),
        )
        db.commit()
        return jsonify(serialize(fetch(task_id)))

    @app.patch("/api/tasks/<int:task_id>")
    def patch_task(task_id):
        row = fetch(task_id)
        if not row:
            return not_found()
        data = json_body()
        if data is None:
            return bad_request({"body": "Request body must be a JSON object."})
        clean, errors = validate(data, existing=dict(row), partial=True)
        if errors:
            return bad_request(errors)
        if not clean:
            return bad_request({"body": "No valid fields supplied."})
        sets = ", ".join(f"{k} = ?" for k in clean)
        db = get_db()
        db.execute(f"UPDATE tasks SET {sets} WHERE id = ?", [*clean.values(), task_id])
        db.commit()
        return jsonify(serialize(fetch(task_id)))

    @app.delete("/api/tasks/<int:task_id>")
    def delete_task(task_id):
        if not fetch(task_id):
            return not_found()
        db = get_db()
        db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        db.commit()
        return jsonify({"message": "Task deleted."})

    @app.errorhandler(404)
    def handle_404(_e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found."}), 404
        return render_template("index.html"), 200

    @app.errorhandler(405)
    def handle_405(_e):
        return jsonify({"error": "Method not allowed."}), 405

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
