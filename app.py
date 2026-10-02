"""Student Management System - Flask + SQLite backend."""
import sqlite3
from typing import Any, cast

from flask import Flask, g, jsonify, request

app = Flask(__name__, static_folder="static", static_url_path="")
DB = "sms.db"
SUBJECTS = ["Python", "SQL", "Excel", "Power BI", "Statistics"]
PASS_MARK = 50

SCHEMA = """
CREATE TABLE IF NOT EXISTS students(id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS faculty(id TEXT PRIMARY KEY, name TEXT NOT NULL, department TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS exams(id TEXT PRIMARY KEY, subject TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS marks(
  student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  subject TEXT NOT NULL, marks REAL NOT NULL,
  PRIMARY KEY(student_id, subject));
"""


def db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_: Any) -> None:
    conn = g.pop("db", None)
    if conn:
        conn.close()


def init_db() -> None:
    with sqlite3.connect(DB) as conn:
        conn.executescript(SCHEMA)


def grade(percentage: float) -> str:
    for cutoff, letter in ((90, "A+"), (80, "A"), (70, "B"), (60, "C"), (50, "D")):
        if percentage >= cutoff:
            return letter
    return "F"


def err(msg: str, code: int = 400) -> tuple[Any, int]:
    return jsonify(error=msg), code


def json_body() -> dict[str, Any]:
    """Return the request JSON as a dict (empty dict if missing or not an object)."""
    payload: Any = request.get_json(silent=True)
    if isinstance(payload, dict):
        return cast(dict[str, Any], payload)
    return {}


def clean(data: dict[str, Any], *keys: str) -> list[str]:
    return [str(data.get(k, "")).strip() for k in keys]


# ---- generic CRUD for students / faculty / exams ---------------------------
TABLES: dict[str, tuple[str, ...]] = {
    "students": ("id", "name"),
    "faculty": ("id", "name", "department"),
    "exams": ("id", "subject"),
}


def register(table: str, cols: tuple[str, ...]) -> None:
    def listing() -> Any:
        rows = db().execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
        return jsonify([dict(r) for r in rows])

    def add() -> Any:
        vals = clean(json_body(), *cols)
        if not all(vals[:2]):
            return err(f"{cols[0]} and {cols[1]} are required.")
        if table == "exams" and vals[1] not in SUBJECTS:
            return err("Subject must be one of: " + ", ".join(SUBJECTS))
        try:
            db().execute(
                f"INSERT INTO {table}({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
                vals,
            )
            db().commit()
        except sqlite3.IntegrityError:
            return err(f"ID '{vals[0]}' already exists.", 409)
        return jsonify(dict(zip(cols, vals))), 201

    def remove(item_id: str) -> Any:
        cur = db().execute(f"DELETE FROM {table} WHERE id=?", (item_id,))
        db().commit()
        return ("", 204) if cur.rowcount else err("ID not found.", 404)

    app.add_url_rule(f"/api/{table}", f"list_{table}", listing)
    app.add_url_rule(f"/api/{table}", f"add_{table}", add, methods=["POST"])
    app.add_url_rule(f"/api/{table}/<item_id>", f"del_{table}", remove, methods=["DELETE"])


for _table, _cols in TABLES.items():
    register(_table, _cols)


# ---- results ----------------------------------------------------------------
@app.get("/api/subjects")
def subjects() -> Any:
    return jsonify(SUBJECTS)


@app.post("/api/marks")
def save_marks() -> Any:
    body = json_body()
    sid, subject = clean(body, "student_id", "subject")
    try:
        marks = float(body["marks"])
    except (KeyError, TypeError, ValueError):
        return err("Marks must be a number.")
    if subject not in SUBJECTS:
        return err("Unknown subject.")
    if not 0 <= marks <= 100:
        return err("Marks must be between 0 and 100.")
    if not db().execute("SELECT 1 FROM students WHERE id=?", (sid,)).fetchone():
        return err("Student ID not found. Add the student first.", 404)
    db().execute(
        "INSERT INTO marks VALUES(?,?,?) "
        "ON CONFLICT(student_id,subject) DO UPDATE SET marks=excluded.marks",
        (sid, subject, marks),
    )
    db().commit()
    return jsonify(ok=True)


@app.get("/api/results")
def results() -> Any:
    """Every student with marks, percentage, grade and pass/fail, plus overall stats."""
    out: list[dict[str, Any]] = []
    all_marks: list[float] = []
    for s in db().execute("SELECT * FROM students ORDER BY id").fetchall():
        rows = db().execute(
            "SELECT subject, marks FROM marks WHERE student_id=?", (s["id"],)
        ).fetchall()
        marks = {r["subject"]: float(r["marks"]) for r in rows}
        all_marks.extend(marks.values())
        pct = sum(marks.values()) / len(marks) if marks else None
        out.append(
            dict(
                id=s["id"],
                name=s["name"],
                marks=marks,
                percentage=None if pct is None else round(pct, 2),
                grade=None if pct is None else grade(pct),
                passed=None if pct is None else pct >= PASS_MARK,
            )
        )
    scored = [r for r in out if r["percentage"] is not None]
    distribution: dict[str, int] = {}
    for r in scored:
        distribution[r["grade"]] = distribution.get(r["grade"], 0) + 1
    return jsonify(
        students=out,
        overall_average=round(sum(all_marks) / len(all_marks), 2) if all_marks else None,
        pass_count=sum(bool(r["passed"]) for r in scored),
        fail_count=sum(not r["passed"] for r in scored),
        grade_distribution=distribution,
    )


@app.get("/api/analysis/<subject>")
def analysis(subject: str) -> Any:
    if subject not in SUBJECTS:
        return err("Unknown subject.", 404)
    rows = db().execute(
        "SELECT s.id, s.name, m.marks FROM marks m JOIN students s ON s.id=m.student_id "
        "WHERE m.subject=? ORDER BY m.marks DESC",
        (subject,),
    ).fetchall()
    marks = [r["marks"] for r in rows]
    return jsonify(
        subject=subject,
        entries=[dict(r) for r in rows],
        average=round(sum(marks) / len(marks), 2) if marks else None,
        highest=max(marks) if marks else None,
        lowest=min(marks) if marks else None,
    )


@app.get("/")
def index() -> Any:
    return app.send_static_file("index.html")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
