"""Student Management System - Flask + SQLite backend."""
import csv
import io
import os
import sqlite3
from functools import wraps
from typing import Any, Callable, cast

from flask import Flask, Response, g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__, static_folder="static", static_url_path="")
DB = "sms.db"
SUBJECTS = ["Python", "SQL", "Excel", "Power BI", "Statistics"]
PASS_MARK = 50
ROLES = ("admin", "faculty", "student")
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

SCHEMA = """
CREATE TABLE IF NOT EXISTS students(id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS faculty(id TEXT PRIMARY KEY, name TEXT NOT NULL, department TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS exams(id TEXT PRIMARY KEY, subject TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users(
  username TEXT PRIMARY KEY, password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('admin','faculty','student')));
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
        if not conn.execute("SELECT 1 FROM users").fetchone():
            conn.execute("INSERT INTO users VALUES(?,?,?)",
                         ("admin", generate_password_hash("admin123"), "admin"))
            print("Default login created -> username: admin  password: admin123 (change it after signing in)")


def grade(percentage: float) -> str:
    for cutoff, letter in ((90, "A+"), (80, "A"), (70, "B"), (60, "C"), (50, "D")):
        if percentage >= cutoff:
            return letter
    return "F"


def err(msg: str, code: int = 400) -> tuple[Any, int]:
    return jsonify(error=msg), code


def require(*roles: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Allow a route only for logged-in users (and only for the given roles, if any)."""
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if "user" not in session:
                return err("Please sign in.", 401)
            if roles and session.get("role") not in roles:
                return err("You don't have permission to do that.", 403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


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


READ_ROLES: dict[str, tuple[str, ...]] = {
    "students": ("admin", "faculty"),
    "faculty": ("admin",),
    "exams": ("admin", "faculty"),
}


def register(table: str, cols: tuple[str, ...]) -> None:
    @require(*READ_ROLES[table])
    def listing() -> Any:
        rows = db().execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
        return jsonify([dict(r) for r in rows])

    @require("admin")
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

    @require("admin")
    def remove(item_id: str) -> Any:
        cur = db().execute(f"DELETE FROM {table} WHERE id=?", (item_id,))
        if table == "students":
            db().execute("DELETE FROM users WHERE username=? AND role='student'", (item_id,))
        db().commit()
        return ("", 204) if cur.rowcount else err("ID not found.", 404)

    app.add_url_rule(f"/api/{table}", f"list_{table}", listing)
    app.add_url_rule(f"/api/{table}", f"add_{table}", add, methods=["POST"])
    app.add_url_rule(f"/api/{table}/<item_id>", f"del_{table}", remove, methods=["DELETE"])


for _table, _cols in TABLES.items():
    register(_table, _cols)


# ---- results ----------------------------------------------------------------
@app.get("/api/subjects")
@require()
def subjects() -> Any:
    return jsonify(SUBJECTS)


@app.post("/api/marks")
@require("admin", "faculty")
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


def compute_results() -> dict[str, Any]:
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
    return dict(
        students=out,
        overall_average=round(sum(all_marks) / len(all_marks), 2) if all_marks else None,
        pass_count=sum(bool(r["passed"]) for r in scored),
        fail_count=sum(not r["passed"] for r in scored),
        grade_distribution=distribution,
    )


@app.get("/api/results")
@require("admin", "faculty")
def results() -> Any:
    return jsonify(compute_results())


def safe(value: Any) -> Any:
    """Stop spreadsheet apps from running text such as =SUM() as a formula."""
    return "'" + value if isinstance(value, str) and value[:1] in "=+-@" else value


@app.get("/api/results.csv")
@require("admin", "faculty")
def results_csv() -> Any:
    buf = io.StringIO()
    out = csv.writer(buf)
    out.writerow(["ID", "Name", *SUBJECTS, "Percentage", "Grade", "Status"])
    for r in compute_results()["students"]:
        status = "" if r["passed"] is None else ("Pass" if r["passed"] else "Fail")
        out.writerow([safe(r["id"]), safe(r["name"]), *[r["marks"].get(x, "") for x in SUBJECTS],
                      "" if r["percentage"] is None else r["percentage"], r["grade"] or "", status])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=class_results.csv"})


@app.get("/api/report/<sid>")
@require("admin", "faculty", "student")
def report(sid: str) -> Any:
    """Report card for one student: marks, class averages, grade, result and rank."""
    if session["role"] == "student" and sid != session["user"]:
        return err("You can only view your own report.", 403)
    student = db().execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
    if not student:
        return err("Student ID not found.", 404)
    mine = {r["subject"]: float(r["marks"]) for r in
            db().execute("SELECT subject, marks FROM marks WHERE student_id=?", (sid,))}
    avgs = {r["subject"]: round(r["a"], 2) for r in
            db().execute("SELECT subject, AVG(marks) a FROM marks GROUP BY subject")}
    pcts = [r["p"] for r in db().execute("SELECT AVG(marks) p FROM marks GROUP BY student_id")]
    pct = sum(mine.values()) / len(mine) if mine else None
    return jsonify(
        id=student["id"], name=student["name"],
        subjects=[dict(subject=x, marks=mine.get(x), class_average=avgs.get(x),
                       grade=grade(mine[x]) if x in mine else None) for x in SUBJECTS],
        percentage=None if pct is None else round(pct, 2),
        grade=None if pct is None else grade(pct),
        passed=None if pct is None else pct >= PASS_MARK,
        rank=None if pct is None else 1 + sum(p > pct for p in pcts),
        class_size=len(pcts),
    )


@app.get("/api/analysis/<subject>")
@require("admin", "faculty")
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


# ---- accounts ---------------------------------------------------------------
@app.post("/api/login")
def login() -> Any:
    body = json_body()
    username = str(body.get("username", "")).strip()
    row = db().execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not row or not check_password_hash(row["password_hash"], str(body.get("password", ""))):
        return err("Wrong username or password.", 401)
    session.clear()
    session["user"], session["role"] = row["username"], row["role"]
    return jsonify(username=row["username"], role=row["role"])


@app.post("/api/logout")
def logout() -> Any:
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
@require()
def me() -> Any:
    return jsonify(username=session["user"], role=session["role"])


@app.post("/api/password")
@require()
def change_password() -> Any:
    body = json_body()
    new = str(body.get("new", ""))
    row = db().execute("SELECT * FROM users WHERE username=?", (session["user"],)).fetchone()
    if not row or not check_password_hash(row["password_hash"], str(body.get("old", ""))):
        return err("Current password is wrong.", 403)
    if len(new) < 6:
        return err("New password must be at least 6 characters.")
    db().execute("UPDATE users SET password_hash=? WHERE username=?",
                 (generate_password_hash(new), session["user"]))
    db().commit()
    return jsonify(ok=True)


@app.get("/api/users")
@require("admin")
def list_users() -> Any:
    rows = db().execute("SELECT username, role FROM users ORDER BY role, username").fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/users")
@require("admin")
def add_user() -> Any:
    body = json_body()
    username, role = clean(body, "username", "role")
    password = str(body.get("password", ""))
    if not username or role not in ROLES:
        return err("Username and a valid role are required.")
    if len(password) < 6:
        return err("Password must be at least 6 characters.")
    if role == "student" and not db().execute("SELECT 1 FROM students WHERE id=?", (username,)).fetchone():
        return err("For a student login, the username must be an existing student ID.", 404)
    try:
        db().execute("INSERT INTO users VALUES(?,?,?)", (username, generate_password_hash(password), role))
        db().commit()
    except sqlite3.IntegrityError:
        return err(f"Username '{username}' already exists.", 409)
    return jsonify(username=username, role=role), 201


@app.delete("/api/users/<username>")
@require("admin")
def delete_user(username: str) -> Any:
    if username == session["user"]:
        return err("You can't delete the account you're signed in with.")
    cur = db().execute("DELETE FROM users WHERE username=?", (username,))
    db().commit()
    return ("", 204) if cur.rowcount else err("Username not found.", 404)


@app.get("/")
def index() -> Any:
    return app.send_static_file("index.html")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
