import csv
from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

app = Flask(__name__, static_folder="public", static_url_path="")
DATA_FILE = Path("students.csv")


def load_students():
    if not DATA_FILE.exists():
        return []

    with DATA_FILE.open(newline="", encoding="utf-8") as file:
        return [
            {"name": row["name"], "score": float(row["score"]), "status": row["status"]}
            for row in csv.DictReader(file)
        ]


def save_student(student):
    new_file = not DATA_FILE.exists()

    with DATA_FILE.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["name", "score", "status"])
        if new_file:
            writer.writeheader()
        writer.writerow(student)


students = load_students()


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/tracker", methods=["GET", "POST"])
def tracker():
    result = None
    error = None

    if request.method == "POST":
        name = request.form["name"].strip()

        try:
            score = float(request.form["score"])
            if not name:
                error = "Please enter a student name."
            elif not 0 <= score <= 100:
                error = "Score must be between 0 and 100."
            else:
                status = "Pass" if score >= 50 else "Fail"
                result = {"name": name, "score": score, "status": status}
                students.append(result)
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
    students.clear()
    if DATA_FILE.exists():
        DATA_FILE.unlink()
    return redirect(url_for("tracker"))


if __name__ == "__main__":
    app.run(debug=True)
