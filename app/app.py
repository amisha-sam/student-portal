import csv, io, os, random, time
from functools import wraps

import click
from flask import (Flask, Response, abort, flash, redirect, render_template,
                   request, url_for)
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from prometheus_client import (CONTENT_TYPE_LATEST, Counter, Gauge, Histogram,
                               generate_latest)
from werkzeug.security import check_password_hash, generate_password_hash

from grading import at_risk_reasons, grade

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///portal.db")
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


# ---------- models ----------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # admin | teacher | student


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roll = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    class_name = db.Column(db.String(20), nullable=False, index=True)


class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)


class Mark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    exam = db.Column(db.String(50), nullable=False)
    score = db.Column(db.Float, nullable=False)  # out of 100
    __table_args__ = (db.UniqueConstraint("student_id", "subject_id", "exam"),)


@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


def staff_only(f):
    @wraps(f)
    @login_required
    def wrapper(*a, **kw):
        if current_user.role not in ("admin", "teacher"):
            abort(403)
        return f(*a, **kw)
    return wrapper


# ---------- metrics ----------
REQS = Counter("http_requests_total", "HTTP requests", ["method", "endpoint", "status"])
LAT = Histogram("http_request_duration_seconds", "Request latency", ["endpoint"])
MARKS_ENTRIES = Counter("marks_entries_total", "Marks saved")
G_STUDENTS = Gauge("students_total", "Total students")
G_RISK = Gauge("students_at_risk", "At-risk students", ["class_name"])
G_AVG = Gauge("class_average", "Class average %", ["class_name"])


@app.before_request
def _start():
    request._t0 = time.time()


@app.after_request
def _record(resp):
    ep = request.endpoint or "unknown"
    if ep != "metrics":
        REQS.labels(request.method, ep, resp.status_code).inc()
        LAT.labels(ep).observe(time.time() - getattr(request, "_t0", time.time()))
    return resp


# ---------- business logic ----------
def summarise(student):
    rows = (db.session.query(Subject.name, db.func.avg(Mark.score))
            .join(Mark, Mark.subject_id == Subject.id)
            .filter(Mark.student_id == student.id).group_by(Subject.name).all())
    subs = {n: float(a) for n, a in rows}
    overall = sum(subs.values()) / len(subs) if subs else 0.0
    reasons = at_risk_reasons(subs, overall)
    return {"student": student, "subjects": subs, "overall": overall,
            "grade": grade(overall) if subs else "-", "reasons": reasons,
            "at_risk": bool(reasons)}


def summaries(class_name=None):
    q = Student.query.order_by(Student.class_name, Student.roll)
    if class_name:
        q = q.filter_by(class_name=class_name)
    return [summarise(s) for s in q.all()]


def classes():
    return [c for (c,) in db.session.query(Student.class_name).distinct().order_by(Student.class_name)]


def can_view(student):
    return current_user.role in ("admin", "teacher") or current_user.username == student.roll


# ---------- routes ----------
@app.route("/health")
def health():
    db.session.execute(db.text("SELECT 1"))
    return {"status": "ok"}


@app.route("/metrics")
def metrics():
    data = summaries()
    G_STUDENTS.set(len(data))
    G_RISK.clear(); G_AVG.clear()
    for c in classes():
        cls = [d for d in data if d["student"].class_name == c]
        G_RISK.labels(c).set(sum(d["at_risk"] for d in cls))
        G_AVG.labels(c).set(sum(d["overall"] for d in cls) / len(cls))
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = User.query.filter_by(username=request.form["username"].strip()).first()
        if u and check_password_hash(u.password_hash, request.form["password"]):
            login_user(u)
            return redirect(url_for("index"))
        flash("Invalid username or password", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    if current_user.role == "student":
        s = Student.query.filter_by(roll=current_user.username).first_or_404()
        return redirect(url_for("report", sid=s.id))
    cls = request.args.get("class_name", "")
    data = summaries(cls or None)
    return render_template("dashboard.html", data=data, classes=classes(), cls=cls,
                           n_risk=sum(d["at_risk"] for d in data),
                           avg=(sum(d["overall"] for d in data) / len(data)) if data else 0)


@app.route("/marks", methods=["GET", "POST"])
@staff_only
def marks():
    cls = request.values.get("class_name", "")
    sid = request.values.get("subject_id", type=int)
    exam = request.values.get("exam", "").strip()
    students = Student.query.filter_by(class_name=cls).order_by(Student.roll).all() if cls else []
    existing = {}
    if students and sid and exam:
        for m in Mark.query.filter_by(subject_id=sid, exam=exam).all():
            existing[m.student_id] = m.score
        if request.method == "POST":
            saved = 0
            for s in students:
                raw = request.form.get(f"score_{s.id}", "").strip()
                if raw == "":
                    continue
                try:
                    v = float(raw)
                except ValueError:
                    flash(f"{s.name}: '{raw}' is not a number", "danger"); continue
                if not 0 <= v <= 100:
                    flash(f"{s.name}: marks must be between 0 and 100", "danger"); continue
                m = Mark.query.filter_by(student_id=s.id, subject_id=sid, exam=exam).first()
                if m: m.score = v
                else: db.session.add(Mark(student_id=s.id, subject_id=sid, exam=exam, score=v))
                saved += 1
            db.session.commit()
            MARKS_ENTRIES.inc(saved)
            flash(f"Saved {saved} entries", "success")
            return redirect(url_for("marks", class_name=cls, subject_id=sid, exam=exam))
    return render_template("marks.html", classes=classes(), subjects=Subject.query.all(),
                           cls=cls, sid=sid, exam=exam, students=students, existing=existing)


@app.route("/at-risk")
@staff_only
def at_risk():
    data = [d for d in summaries(request.args.get("class_name") or None) if d["at_risk"]]
    return render_template("at_risk.html", data=data, classes=classes(),
                           cls=request.args.get("class_name", ""))


@app.route("/report/<int:sid>")
@login_required
def report(sid):
    s = db.get_or_404(Student, sid)
    if not can_view(s): abort(403)
    return render_template("report.html", d=summarise(s), grade=grade)


@app.route("/report/<int:sid>.pdf")
@login_required
def report_pdf(sid):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    s = db.get_or_404(Student, sid)
    if not can_view(s): abort(403)
    d = summarise(s)
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4); y = 800
    c.setFont("Helvetica-Bold", 18); c.drawString(50, y, "Student Report Card"); y -= 30
    c.setFont("Helvetica", 12)
    c.drawString(50, y, f"{s.name}  |  Roll: {s.roll}  |  Class: {s.class_name}"); y -= 30
    for n, v in d["subjects"].items():
        c.drawString(60, y, f"{n}"); c.drawString(300, y, f"{v:.1f}%"); c.drawString(380, y, grade(v)); y -= 20
    y -= 10; c.setFont("Helvetica-Bold", 12)
    c.drawString(60, y, f"Overall: {d['overall']:.1f}%   Grade: {d['grade']}"); y -= 25
    if d["at_risk"]:
        c.setFillColorRGB(0.8, 0, 0); c.drawString(60, y, "NEEDS SUPPORT:"); y -= 18
        c.setFont("Helvetica", 11)
        for r in d["reasons"]:
            c.drawString(75, y, "- " + r); y -= 16
    c.save()
    return Response(buf.getvalue(), mimetype="application/pdf",
                    headers={"Content-Disposition": f"inline; filename={s.roll}_report.pdf"})


@app.route("/export.csv")
@staff_only
def export_csv():
    out = io.StringIO(); w = csv.writer(out)
    w.writerow(["Roll", "Name", "Class", "Overall %", "Grade", "At risk", "Reasons"])
    for d in summaries(request.args.get("class_name") or None):
        s = d["student"]
        w.writerow([s.roll, s.name, s.class_name, f"{d['overall']:.1f}", d["grade"],
                    "YES" if d["at_risk"] else "no", "; ".join(d["reasons"])])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=class_summary.csv"})


# ---------- CLI: flask --app app seed ----------
@app.cli.command("seed")
def seed():
    """Create demo users, subjects, students and marks."""
    if User.query.first():
        click.echo("Already seeded"); return
    random.seed(7)
    db.session.add_all([
        User(username="admin", role="admin", password_hash=generate_password_hash(os.getenv("ADMIN_PASSWORD", "admin123"))),
        User(username="teacher", role="teacher", password_hash=generate_password_hash(os.getenv("TEACHER_PASSWORD", "teacher123"))),
    ])
    subjects = [Subject(name=n) for n in ("Maths", "Science", "English", "Social")]
    db.session.add_all(subjects)
    names = ["Arun", "Divya", "Karthik", "Meena", "Suresh", "Lakshmi", "Vijay", "Priya", "Ravi", "Nithya"]
    for i, n in enumerate(names, 1):
        s = Student(roll=f"R{i:03d}", name=n, class_name="10A" if i <= 5 else "10B")
        db.session.add(s); db.session.flush()
        base = random.randint(30, 92)
        for sub in subjects:
            db.session.add(Mark(student_id=s.id, subject_id=sub.id, exam="Midterm",
                                score=max(0, min(100, base + random.randint(-15, 15)))))
        db.session.add(User(username=s.roll, role="student", password_hash=generate_password_hash("student123")))
    db.session.commit()
    click.echo("Seeded: admin/admin123, teacher/teacher123, students R001.. / student123")


with app.app_context():
    db.create_all()
