import os
import sys
import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app import app, db, User, Student, Subject, Mark


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        db.create_all()
        # Seed test users
        admin = User(username="admin", role="admin", password_hash=generate_password_hash("admin123"))
        teacher = User(username="teacher", role="teacher", password_hash=generate_password_hash("teacher123"))
        student_user1 = User(username="R001", role="student", password_hash=generate_password_hash("student123"))
        student_user2 = User(username="R002", role="student", password_hash=generate_password_hash("student123"))

        # Seed subjects
        sub_math = Subject(name="Maths")
        sub_sci = Subject(name="Science")

        # Seed students
        s1 = Student(roll="R001", name="Alice", class_name="10A")
        s2 = Student(roll="R002", name="Bob", class_name="10A")

        db.session.add_all([admin, teacher, student_user1, student_user2, sub_math, sub_sci, s1, s2])
        db.session.commit()

        # Seed marks: Alice is doing well, Bob is at risk in Maths
        m1 = Mark(student_id=s1.id, subject_id=sub_math.id, exam="Midterm", score=85.0)
        m2 = Mark(student_id=s1.id, subject_id=sub_sci.id, exam="Midterm", score=90.0)
        m3 = Mark(student_id=s2.id, subject_id=sub_math.id, exam="Midterm", score=32.0)  # below 40
        m4 = Mark(student_id=s2.id, subject_id=sub_sci.id, exam="Midterm", score=60.0)

        db.session.add_all([m1, m2, m3, m4])
        db.session.commit()

        with app.test_client() as test_client:
            yield test_client

        db.session.remove()
        db.drop_all()


def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok"}


def test_metrics_endpoint(client):
    res = client.get("/metrics")
    assert res.status_code == 200
    data = res.get_data(as_text=True)
    assert "students_total 2.0" in data
    assert 'students_at_risk{class_name="10A"} 1.0' in data
    assert 'class_average{class_name="10A"}' in data
    assert "http_requests_total" in data


def test_login_and_logout(client):
    # Unauthenticated redirect
    res = client.get("/", follow_redirects=False)
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]

    # Invalid login
    res = client.post("/login", data={"username": "teacher", "password": "wrongpassword"}, follow_redirects=True)
    assert res.status_code == 200
    assert "Invalid username or password" in res.get_data(as_text=True)

    # Valid teacher login
    res = client.post("/login", data={"username": "teacher", "password": "teacher123"}, follow_redirects=True)
    assert res.status_code == 200
    assert "Academic Performance Dashboard" in res.get_data(as_text=True)

    # Logout
    res = client.get("/logout", follow_redirects=True)
    assert res.status_code == 200
    assert "Sign In" in res.get_data(as_text=True)


def test_student_role_access(client):
    # Login as student R001
    client.post("/login", data={"username": "R001", "password": "student123"}, follow_redirects=True)

    # Student accessing root is redirected to their own report
    res = client.get("/", follow_redirects=True)
    assert res.status_code == 200
    assert "Alice" in res.get_data(as_text=True)

    # Student CANNOT access /marks (403 Forbidden)
    res = client.get("/marks")
    assert res.status_code == 403

    # Student CANNOT access /at-risk (403 Forbidden)
    res = client.get("/at-risk")
    assert res.status_code == 403

    # Student CANNOT access /export.csv (403 Forbidden)
    res = client.get("/export.csv")
    assert res.status_code == 403

    # Student CANNOT view Bob's report (R002, id=2)
    res = client.get("/report/2")
    assert res.status_code == 403

    # Student CAN view their own report (R001, id=1)
    res = client.get("/report/1")
    assert res.status_code == 200
    assert "Alice" in res.get_data(as_text=True)


def test_marks_validation_and_upsert(client):
    # Login as teacher
    client.post("/login", data={"username": "teacher", "password": "teacher123"})

    # Submit invalid mark (> 100)
    res = client.post("/marks", data={
        "class_name": "10A",
        "subject_id": 1,
        "exam": "Final",
        "score_1": "105.0"
    }, follow_redirects=True)
    assert "out of range" in res.get_data(as_text=True)

    # Submit invalid non-numeric
    res = client.post("/marks", data={
        "class_name": "10A",
        "subject_id": 1,
        "exam": "Final",
        "score_1": "abc"
    }, follow_redirects=True)
    assert "not a valid number" in res.get_data(as_text=True)

    # Submit valid mark
    res = client.post("/marks", data={
        "class_name": "10A",
        "subject_id": 1,
        "exam": "Final",
        "score_1": "92.5"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert "Successfully recorded marks" in res.get_data(as_text=True)

    # Verify mark was saved
    with app.app_context():
        m = Mark.query.filter_by(student_id=1, subject_id=1, exam="Final").first()
        assert m is not None
        assert m.score == 92.5

    # Upsert mark
    client.post("/marks", data={
        "class_name": "10A",
        "subject_id": 1,
        "exam": "Final",
        "score_1": "95.0"
    }, follow_redirects=True)
    with app.app_context():
        m = Mark.query.filter_by(student_id=1, subject_id=1, exam="Final").first()
        assert m.score == 95.0


def test_pdf_report_download(client):
    # Login as teacher
    client.post("/login", data={"username": "teacher", "password": "teacher123"})

    res = client.get("/report/1.pdf")
    assert res.status_code == 200
    assert res.content_type == "application/pdf"
    # PDF starts with %PDF magic bytes
    assert res.data.startswith(b"%PDF")


def test_csv_export(client):
    # Login as teacher
    client.post("/login", data={"username": "teacher", "password": "teacher123"})

    res = client.get("/export.csv")
    assert res.status_code == 200
    assert "text/csv" in res.content_type
    text = res.get_data(as_text=True)
    assert "Roll,Name,Class,Overall %,Grade,Status,Reasons" in text
    assert "R001,Alice,10A" in text
    assert "R002,Bob,10A" in text
    assert "Needs Support" in text


def test_charts_api(client):
    # Login as teacher
    client.post("/login", data={"username": "teacher", "password": "teacher123"})

    res = client.get("/api/charts")
    assert res.status_code == 200
    data = res.get_json()
    assert "grades" in data
    assert "subjects" in data
    assert "classes" in data
    assert "A" in data["grades"]["labels"]
    assert "Maths" in data["subjects"]["labels"]
