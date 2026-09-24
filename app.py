import csv
import json
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from flask import Flask, redirect, render_template, request, session, url_for

app = Flask(__name__, static_folder="public", static_url_path="")
app.secret_key = os.environ.get("SECRET_KEY", "student-grade-tracker-secret-key-2026")

BASE_DIR = Path(__file__).resolve().parent

# Supabase Configuration
SUPABASE_URL = os.environ.get(
    "SUPABASE_URL",
    os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "https://wevbiwegtuplsizzlimc.supabase.co"),
).rstrip("/")

SUPABASE_KEY = (
    os.environ.get("SUPABASE_ANON_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndldmJpd2VndHVwbHNpenpsaW1jIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTAyMTI1NzAsImV4cCI6MjEwNTc4ODU3MH0.i61TgsxCtB8AlQr-XkL5-VstXuXT9U7Mvjgf7pJHABc"
)


def _supabase_request(endpoint: str, method: str = "GET", data=None):
    """Make an HTTP request to Supabase PostgREST API with timeout and error handling."""
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    encoded_data = None
    if data is not None:
        encoded_data = json.dumps(data).encode("utf-8")
        headers["Prefer"] = "return=representation"

    req = urllib.request.Request(url, data=encoded_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            status = response.status
            body = response.read().decode("utf-8")
            return status, json.loads(body) if body else None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        app.logger.warning(f"Supabase request failed ({method} {endpoint}): {e}")
        return 0, None


def get_data_file() -> Path:
    """Return a writable Path for local CSV backup."""
    if os.environ.get("VERCEL") or not os.access(BASE_DIR, os.W_OK):
        return Path(tempfile.gettempdir()) / "students.csv"
    return BASE_DIR / "students.csv"


def calculate_grade(score: float) -> str:
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C"
    if score >= 50:
        return "D"
    return "F"


def load_students_csv():
    """Fallback reader from local CSV."""
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
                        score_val = float(row["score"])
                        loaded.append({
                            "name": row["name"],
                            "score": score_val,
                            "status": row.get("status", "Pass" if score_val >= 50 else "Fail"),
                            "grade": row.get("grade", calculate_grade(score_val)),
                        })
                    except ValueError:
                        continue
            return loaded
    except OSError:
        return []


def save_student_csv(student):
    """Save student to local CSV as fallback."""
    data_file = get_data_file()
    try:
        new_file = not data_file.exists() or data_file.stat().st_size == 0
        with data_file.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["name", "score", "status", "grade"])
            if new_file:
                writer.writeheader()
            writer.writerow({
                "name": student.get("name"),
                "score": student.get("score"),
                "status": student.get("status"),
                "grade": student.get("grade"),
            })
    except OSError as e:
        app.logger.warning(f"Failed to save student to file: {e}")


def load_students():
    """Fetch students from Supabase database, falling back to local CSV if offline."""
    status, data = _supabase_request("students?select=*&order=id.asc")
    if status == 200 and isinstance(data, list):
        students = []
        for row in data:
            try:
                score_val = float(row.get("score", 0))
                students.append({
                    "id": row.get("id"),
                    "name": str(row.get("name", "")),
                    "score": score_val,
                    "status": str(row.get("status", "Pass" if score_val >= 50 else "Fail")),
                    "grade": str(row.get("grade", calculate_grade(score_val))),
                })
            except (ValueError, TypeError):
                continue
        return students

    return load_students_csv()


def save_student(student):
    """Insert a student into Supabase and save local backup."""
    status, res = _supabase_request(
        "students",
        method="POST",
        data={
            "name": student["name"],
            "score": student["score"],
            "status": student["status"],
            "grade": student["grade"],
        },
    )
    if status in (200, 201) and res and isinstance(res, list) and len(res) > 0:
        student["id"] = res[0].get("id")

    save_student_csv(student)
    return student


def delete_student_record(student_id: int):
    """Delete a single student from Supabase."""
    status, _ = _supabase_request(f"students?id=eq.{student_id}", method="DELETE")
    return status in (200, 204)


def reset_all_students():
    """Delete all student records from Supabase and local cache."""
    _supabase_request("students?id=gt.0", method="DELETE")
    data_file = get_data_file()
    try:
        if data_file.exists():
            data_file.unlink()
    except OSError:
        pass


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/tracker", methods=["GET", "POST"], strict_slashes=False)
def tracker():
    result = None
    error = None

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
                grade = calculate_grade(score)
                new_record = {"name": name, "score": score, "status": status, "grade": grade}
                saved_record = save_student(new_record)
                result = saved_record
        except ValueError:
            error = "Please enter a valid number for the score."

    students = load_students()

    if students:
        scores = [s["score"] for s in students]
        average_score = sum(scores) / len(scores)
        highest_score = max(scores)
        passed_count = sum(1 for s in students if s["score"] >= 50)
        pass_rate = (passed_count / len(students)) * 100
    else:
        average_score = None
        highest_score = None
        pass_rate = 0

    return render_template(
        "tracker.html",
        result=result,
        error=error,
        students=students,
        average_score=average_score,
        highest_score=highest_score,
        pass_rate=pass_rate,
        supabase_connected=True,
    )


@app.route("/delete/<int:student_id>", methods=["POST"], strict_slashes=False)
def delete_student(student_id):
    delete_student_record(student_id)
    return redirect(url_for("tracker"))


@app.route("/about", strict_slashes=False)
def about():
    return render_template("about.html")


@app.route("/reset", methods=["POST"], strict_slashes=False)
def reset():
    reset_all_students()
    session.pop("students", None)
    return redirect(url_for("tracker"))


if __name__ == "__main__":
    app.run(debug=True)
