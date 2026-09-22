import csv
import os
import tempfile
from pathlib import Path

from flask import Flask, redirect, render_template, request, session, url_for

app = Flask(__name__, static_folder="public", static_url_path="")
app.secret_key = os.environ.get("SECRET_KEY", "student-grade-tracker-secret-key-2026")

BASE_DIR = Path(__file__).resolve().parent


def get_data_file() -> Path:
    """Return a writable Path for students.csv.

    On serverless platforms like Vercel, the app root directory is strictly read-only.
    Writing to it triggers OSError: [Errno 30] Read-only file system.
    We use the system temporary directory (/tmp) in that environment.
    """
    if os.environ.get("VERCEL") or not os.access(BASE_DIR, os.W_OK):
        return Path(tempfile.gettempdir()) / "students.csv"
    return BASE_DIR / "students.csv"


def load_students():
    data_file = get_data_file()
    try:
        if not data_file.exists() or data_file.stat().st_size == 0:
            return []

        with data_file.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            loaded = []
            for row in reader:
                if row.get("name") and row.get("score") is not None:
                    try:
                        loaded.append({
                            "name": row["name"],
                            "score": float(row["score"]),
                            "status": row.get("status", "Pass" if float(row["score"]) >= 50 else "Fail"),
                        })
                    except ValueError:
                        continue
            return loaded
    except OSError:
        return []


def save_student(student):
    data_file = get_data_file()
    try:
        new_file = not data_file.exists() or data_file.stat().st_size == 0
        with data_file.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["name", "score", "status"])
            if new_file:
                writer.writeheader()
            writer.writerow(student)
    except OSError as e:
        app.logger.warning(f"Failed to save student to file: {e}")


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/tracker", methods=["GET", "POST"])
def tracker():
    result = None
    error = None

    # Use session storage so data persists across Vercel serverless function invocations
    if "students" not in session:
        session["students"] = load_students()

    students = list(session.get("students", []))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        score_raw = request.form.get("score", "").strip().replace(",", ".")

        try:
            score = float(score_raw)
            if not name:
                error = "Please enter a student name."
            elif not 0 <= score <= 100:
                error = "Score must be between 0 and 100."
            else:
                status = "Pass" if score >= 50 else "Fail"
                result = {"name": name, "score": score, "status": status}
                students.append(result)
                session["students"] = students
                save_student(result)
        except ValueError:
            error = "Please enter a valid number for the score."

    average_score = sum(student["score"] for student in students) / len(students) if students else None
    return render_template("index.html", result=result, error=error, students=students, average_score=average_score)


@app.route("/about")
def about():
    return render_template("about.html")


@app.post("/reset")
def reset():
    session["students"] = []
    data_file = get_data_file()
    try:
        if data_file.exists():
            data_file.unlink()
    except OSError:
        pass
    return redirect(url_for("tracker"))


if __name__ == "__main__":
    app.run(debug=True)

