import csv
import io
import logging
import os
import random
import time
from functools import wraps

import click
from flask import (Flask, Response, abort, flash, jsonify, redirect,
                   render_template, request, url_for)
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                          login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from prometheus_client import (CONTENT_TYPE_LATEST, Counter, Gauge, Histogram,
                               generate_latest)
from werkzeug.security import check_password_hash, generate_password_hash

from grading import at_risk_reasons, grade

# ---------- logging configuration ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("student_portal")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-change-me")

# Normalize database URL to use psycopg2 driver as required
raw_db_url = os.getenv("DATABASE_URL", "sqlite:///portal.db")
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif raw_db_url.startswith("postgresql://") and not raw_db_url.startswith("postgresql+psycopg2://"):
    raw_db_url = raw_db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = raw_db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "warning"


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
            logger.warning(f"Unauthorized staff access attempt by {current_user.username} ({current_user.role})")
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

    # Security headers
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("X-XSS-Protection", "1; mode=block")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return resp


# ---------- error handlers ----------
@app.errorhandler(403)
def forbidden(e):
    return render_template("errors/403.html"), 403


@app.errorhandler(404)
def not_found(e):
    return render_template("errors/404.html"), 404


@app.errorhandler(500)
def server_error(e):
    logger.error(f"Internal server error: {e}", exc_info=True)
    return render_template("errors/500.html"), 500


# ---------- business logic ----------
def summarise(student):
    rows = (db.session.query(Subject.name, db.func.avg(Mark.score))
            .join(Mark, Mark.subject_id == Subject.id)
            .filter(Mark.student_id == student.id).group_by(Subject.name).all())
    subs = {n: float(a) for n, a in rows}
    overall = sum(subs.values()) / len(subs) if subs else 0.0
    reasons = at_risk_reasons(subs, overall)
    return {
        "student": student,
        "subjects": subs,
        "overall": overall,
        "grade": grade(overall) if subs else "-",
        "reasons": reasons,
        "at_risk": bool(reasons)
    }


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
    try:
        db.session.execute(db.text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Healthcheck DB check failed: {e}")
        return {"status": "error", "message": "Database unreachable"}, 503


@app.route("/metrics")
def metrics():
    data = summaries()
    G_STUDENTS.set(len(data))
    G_RISK.clear()
    G_AVG.clear()
    for c in classes():
        cls = [d for d in data if d["student"].class_name == c]
        G_RISK.labels(c).set(sum(d["at_risk"] for d in cls))
        G_AVG.labels(c).set((sum(d["overall"] for d in cls) / len(cls)) if cls else 0.0)
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.route("/api/charts")
@staff_only
def api_charts():
    """JSON API providing chart datasets for the dashboard."""
    cls = request.args.get("class_name") or None
    data = summaries(cls)

    # Grade distribution
    grade_order = ["A+", "A", "B", "C", "D", "F"]
    grade_counts = {g: 0 for g in grade_order}
    for d in data:
        if d["grade"] in grade_counts:
            grade_counts[d["grade"]] += 1

    # Subject averages across the selected cohort
    all_subs = Subject.query.order_by(Subject.name).all()
    sub_avgs = {}
    for s in all_subs:
        scores = [d["subjects"][s.name] for d in data if s.name in d["subjects"]]
        sub_avgs[s.name] = round(sum(scores) / len(scores), 1) if scores else 0.0

    # At-risk breakdown per class
    cls_list = classes() if not cls else [cls]
    class_stats = []
    for c in cls_list:
        c_students = [d for d in summaries(c)]
        at_risk_c = sum(1 for d in c_students if d["at_risk"])
        total_c = len(c_students)
        avg_c = round(sum(d["overall"] for d in c_students) / total_c, 1) if total_c else 0.0
        class_stats.append({
            "class_name": c,
            "total": total_c,
            "at_risk": at_risk_c,
            "safe": total_c - at_risk_c,
            "average": avg_c
        })

    return jsonify({
        "grades": {
            "labels": grade_order,
            "counts": [grade_counts[g] for g in grade_order]
        },
        "subjects": {
            "labels": list(sub_avgs.keys()),
            "averages": list(sub_avgs.values())
        },
        "classes": class_stats
    })


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        uname = request.form.get("username", "").strip()
        pwd = request.form.get("password", "")
        u = User.query.filter_by(username=uname).first()
        if u and check_password_hash(u.password_hash, pwd):
            login_user(u)
            logger.info(f"User '{u.username}' logged in successfully as {u.role}")
            return redirect(url_for("index"))
        flash("Invalid username or password. Please check your credentials.", "danger")
        logger.warning(f"Failed login attempt for username '{uname}'")
    return render_template("login.html")


@app.route("/logout")
def logout():
    if current_user.is_authenticated:
        logger.info(f"User '{current_user.username}' logged out")
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
    total_students = len(data)
    n_risk = sum(d["at_risk"] for d in data)
    avg = (sum(d["overall"] for d in data) / total_students) if total_students else 0.0
    return render_template("dashboard.html",
                           data=data,
                           classes=classes(),
                           cls=cls,
                           n_risk=n_risk,
                           avg=avg,
                           total_students=total_students)


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
            has_error = False
            for s in students:
                raw = request.form.get(f"score_{s.id}", "").strip()
                if raw == "":
                    continue
                try:
                    v = float(raw)
                except ValueError:
                    flash(f"{s.name} ({s.roll}): '{raw}' is not a valid number.", "danger")
                    has_error = True
                    continue
                if not 0 <= v <= 100:
                    flash(f"{s.name} ({s.roll}): score {v} out of range (must be 0 - 100).", "danger")
                    has_error = True
                    continue
                m = Mark.query.filter_by(student_id=s.id, subject_id=sid, exam=exam).first()
                if m:
                    m.score = v
                else:
                    db.session.add(Mark(student_id=s.id, subject_id=sid, exam=exam, score=v))
                saved += 1
            if saved > 0:
                db.session.commit()
                MARKS_ENTRIES.inc(saved)
                flash(f"Successfully recorded marks for {saved} student(s).", "success")
            elif not has_error:
                flash("No marks were entered.", "info")
            return redirect(url_for("marks", class_name=cls, subject_id=sid, exam=exam))
    return render_template("marks.html",
                           classes=classes(),
                           subjects=Subject.query.order_by(Subject.name).all(),
                           cls=cls,
                           sid=sid,
                           exam=exam,
                           students=students,
                           existing=existing)


@app.route("/at-risk")
@staff_only
def at_risk():
    cls = request.args.get("class_name", "")
    all_data = summaries(cls or None)
    data = [d for d in all_data if d["at_risk"]]
    return render_template("at_risk.html",
                           data=data,
                           classes=classes(),
                           cls=cls,
                           total_evaluated=len(all_data))


@app.route("/report/<int:sid>")
@login_required
def report(sid):
    s = db.get_or_404(Student, sid)
    if not can_view(s):
        abort(403)
    return render_template("report.html", d=summarise(s), grade=grade)


@app.route("/report/<int:sid>.pdf")
@login_required
def report_pdf(sid):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    s = db.get_or_404(Student, sid)
    if not can_view(s):
        abort(403)
    d = summarise(s)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=6
    )
    meta_style = ParagraphStyle(
        "DocMeta",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=15
    )

    story = []
    story.append(Paragraph("Student Performance Report Card", title_style))
    story.append(Paragraph(f"Official Academic Record &bull; Generated on {time.strftime('%Y-%m-%d %H:%M')}", meta_style))

    # Student details table
    student_info = [
        [Paragraph("<b>Student Name:</b>", styles["Normal"]), Paragraph(s.name, styles["Normal"]),
         Paragraph("<b>Roll Number:</b>", styles["Normal"]), Paragraph(s.roll, styles["Normal"])],
        [Paragraph("<b>Class / Section:</b>", styles["Normal"]), Paragraph(s.class_name, styles["Normal"]),
         Paragraph("<b>Status:</b>", styles["Normal"]),
         Paragraph(f"<font color='{'#dc2626' if d['at_risk'] else '#16a34a'}'><b>{'Needs Support' if d['at_risk'] else 'Good Standing'}</b></font>", styles["Normal"])]
    ]
    info_table = Table(student_info, colWidths=[90, 160, 90, 160])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 20))

    # Subject marks table
    sub_data = [["Subject", "Average Score", "Subject Grade", "Status"]]
    for n, v in d["subjects"].items():
        sub_grade = grade(v)
        is_low = v < float(os.getenv("AT_RISK_SUBJECT", "40"))
        sub_status = "Attention Needed" if is_low else "Pass"
        sub_data.append([n, f"{v:.1f}%", sub_grade, sub_status])

    # Overall row
    sub_data.append(["Overall Performance", f"{d['overall']:.1f}%", d['grade'], "Overall Grade"])

    marks_table = Table(sub_data, colWidths=[180, 110, 110, 100])
    marks_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f1f5f9")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(marks_table)
    story.append(Spacer(1, 20))

    # At-risk reasons box if applicable
    if d["at_risk"]:
        story.append(Paragraph("<font color='#dc2626'><b>ACADEMIC SUPPORT NOTICE:</b></font>", styles["Heading3"]))
        reasons_text = "<br/>".join([f"&bull; {r}" for r in d["reasons"]])
        story.append(Paragraph(
            f"This student has been flagged as requiring targeted support due to:<br/>{reasons_text}",
            styles["Normal"]
        ))
        story.append(Spacer(1, 15))

    doc.build(story)
    return Response(
        buf.getvalue(),
        mimetype="application/pdf",
        headers={"Content-Disposition": f"inline; filename={s.roll}_report.pdf"}
    )


@app.route("/export.csv")
@staff_only
def export_csv():
    cls = request.args.get("class_name") or None
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Roll", "Name", "Class", "Overall %", "Grade", "Status", "Reasons"])
    for d in summaries(cls):
        s = d["student"]
        w.writerow([
            s.roll,
            s.name,
            s.class_name,
            f"{d['overall']:.1f}",
            d["grade"],
            "Needs Support" if d["at_risk"] else "OK",
            "; ".join(d["reasons"]) if d["reasons"] else "None"
        ])
    return Response(
        out.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=class_summary_{cls or 'all'}.csv"}
    )


# ---------- CLI: flask --app app seed ----------
@app.cli.command("seed")
def seed():
    """Create demo users, subjects, students and marks."""
    random.seed(7)
    # Ensure database schema is created
    db.create_all()

    admin_pw = os.getenv("ADMIN_PASSWORD", "admin123")
    teacher_pw = os.getenv("TEACHER_PASSWORD", "teacher123")
    student_pw = os.getenv("STUDENT_PASSWORD", "student123")

    # Seed Admin user
    if not User.query.filter_by(username="admin").first():
        db.session.add(User(username="admin", role="admin", password_hash=generate_password_hash(admin_pw)))
    # Seed Teacher user
    if not User.query.filter_by(username="teacher").first():
        db.session.add(User(username="teacher", role="teacher", password_hash=generate_password_hash(teacher_pw)))

    # Seed Subjects
    subject_names = ["Maths", "Science", "English", "Social"]
    subjects = []
    for sname in subject_names:
        sub = Subject.query.filter_by(name=sname).first()
        if not sub:
            sub = Subject(name=sname)
            db.session.add(sub)
        subjects.append(sub)
    db.session.flush()

    # Seed Students across Class 10A and 10B
    names = ["Arun", "Divya", "Karthik", "Meena", "Suresh", "Lakshmi", "Vijay", "Priya", "Ravi", "Nithya"]
    for i, n in enumerate(names, 1):
        roll = f"R{i:03d}"
        cname = "10A" if i <= 5 else "10B"
        st = Student.query.filter_by(roll=roll).first()
        if not st:
            st = Student(roll=roll, name=n, class_name=cname)
            db.session.add(st)
            db.session.flush()

        # Seed student login
        if not User.query.filter_by(username=roll).first():
            db.session.add(User(username=roll, role="student", password_hash=generate_password_hash(student_pw)))

        # Seed marks
        base = random.randint(30, 92)
        for sub in subjects:
            existing_mark = Mark.query.filter_by(student_id=st.id, subject_id=sub.id, exam="Midterm").first()
            if not existing_mark:
                score = max(0.0, min(100.0, float(base + random.randint(-15, 15))))
                db.session.add(Mark(student_id=st.id, subject_id=sub.id, exam="Midterm", score=score))

    db.session.commit()
    click.echo(f"Seeded demo users: admin/{admin_pw}, teacher/{teacher_pw}, students R001-R010/{student_pw}")


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
