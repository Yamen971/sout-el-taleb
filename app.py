from flask import (
    Flask, request, redirect, url_for,
    render_template_string, session, flash
)
import sqlite3
import secrets
from pathlib import Path

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

DB_PATH = Path(__file__).with_name("database.db")


# ---------------- DATABASE ----------------

def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect_db() as db:

        # Existing suggestions table
        db.execute("""
            CREATE TABLE IF NOT EXISTS suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Preserve compatibility with your existing database
        columns = {
            row["name"]
            for row in db.execute(
                "PRAGMA table_info(suggestions)"
            ).fetchall()
        }

        additions = {
            "student_name": "TEXT",
            "school_name": "TEXT",
            "grade": "TEXT",
            "representation": "TEXT"
        }

        for column, data_type in additions.items():
            if column not in columns:
                db.execute(
                    f"ALTER TABLE suggestions ADD COLUMN "
                    f"{column} {data_type}"
                )

        # Votes for suggestions
        db.execute("""
            CREATE TABLE IF NOT EXISTS suggestion_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                suggestion_id INTEGER NOT NULL,
                voter_id TEXT NOT NULL,
                UNIQUE(suggestion_id, voter_id),
                FOREIGN KEY(suggestion_id)
                    REFERENCES suggestions(id)
            )
        """)

        # Activity and trip proposals
        db.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name TEXT NOT NULL,
                school_name TEXT NOT NULL,
                grade TEXT NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Activity ratings
        db.execute("""
            CREATE TABLE IF NOT EXISTS activity_ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER NOT NULL,
                voter_id TEXT NOT NULL,
                rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                UNIQUE(activity_id, voter_id),
                FOREIGN KEY(activity_id)
                    REFERENCES activities(id)
            )
        """)

        # Polls
        db.execute("""
            CREATE TABLE IF NOT EXISTS polls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS poll_options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id INTEGER NOT NULL,
                option_text TEXT NOT NULL,
                FOREIGN KEY(poll_id) REFERENCES polls(id)
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS poll_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id INTEGER NOT NULL,
                option_id INTEGER NOT NULL,
                voter_id TEXT NOT NULL,
                UNIQUE(poll_id, voter_id),
                FOREIGN KEY(poll_id) REFERENCES polls(id),
                FOREIGN KEY(option_id) REFERENCES poll_options(id)
            )
        """)

        # Add example polls only when the database has none
        count = db.execute(
            "SELECT COUNT(*) FROM polls"
        ).fetchone()[0]

        if count == 0:
            examples = [
                (
                    "ما النشاط الذي تفضله في المدرسة؟",
                    ["مسابقات رياضية", "مسابقات ثقافية",
                     "رحلات تعليمية", "أعمال تطوعية"]
                ),
                (
                    "ما المجال الذي يحتاج إلى اهتمام أكبر؟",
                    ["الأنشطة الطلابية", "الرياضة",
                     "النظافة", "المشاركة الطلابية"]
                )
            ]

            for question, options in examples:
                cursor = db.execute(
                    "INSERT INTO polls (question) VALUES (?)",
                    (question,)
                )
                poll_id = cursor.lastrowid

                for option in options:
                    db.execute("""
                        INSERT INTO poll_options
                        (poll_id, option_text)
                        VALUES (?, ?)
                    """, (poll_id, option))


# ---------------- DESIGN ----------------

BASE_STYLE = """
<style>
* { box-sizing: border-box; }

body {
    margin: 0;
    font-family: Tahoma, Arial, sans-serif;
    background: #f1f5fb;
    color: #192b49;
    line-height: 1.8;
}

header {
    background: #11264b;
    color: white;
    padding: 20px;
    text-align: center;
}

header h1 { margin: 0; }

nav {
    background: #1c3765;
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 8px;
    padding: 12px;
}

nav a {
    color: white;
    text-decoration: none;
    padding: 8px 13px;
    border-radius: 7px;
}

nav a:hover { background: #34588e; }

.hero {
    max-width: 1000px;
    margin: 25px auto;
    padding: 35px 20px;
    border-radius: 18px;
    background: linear-gradient(135deg, #17366b, #3976d2);
    color: white;
    text-align: center;
}

.hero h2 { font-size: 28px; }

.container {
    max-width: 1000px;
    padding: 15px;
    margin: auto;
}

.grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 18px;
}

.card {
    background: white;
    padding: 22px;
    border-radius: 14px;
    margin-bottom: 18px;
    box-shadow: 0 4px 15px #0000000c;
    overflow-wrap: anywhere;
}

h2, h3 { color: #285db0; }

input, select, textarea {
    width: 100%;
    padding: 12px;
    margin: 7px 0 15px;
    border: 1px solid #ccd5e5;
    border-radius: 8px;
    font: inherit;
}

textarea { min-height: 110px; }

button, .button {
    display: inline-block;
    background: #245db5;
    color: white;
    border: none;
    padding: 10px 17px;
    border-radius: 8px;
    cursor: pointer;
    font: inherit;
    text-decoration: none;
}

button:hover, .button:hover { background: #173d7c; }

.item {
    background: #f7f9fe;
    border-right: 4px solid #3976d2;
    padding: 15px;
    margin: 12px 0;
    border-radius: 8px;
}

.muted { color: #65738a; font-size: 13px; }

.notice {
    background: #e3f5e9;
    padding: 12px;
    border-radius: 8px;
    margin: 12px 0;
}

footer {
    text-align: center;
    padding: 25px;
    color: #65738a;
}

@media(max-width:600px) {
    .hero h2 { font-size: 23px; }
    nav { gap: 3px; }
    nav a { padding: 7px; font-size: 13px; }
}
</style>
"""

NAV = """
<header>
    <h1>🎓 صوت الطالب</h1>
    <p>Student Voice | Your Ideas Matter</p>
</header>
<nav>
    <a href="/">الرئيسية</a>
    <a href="/suggestions">الاقتراحات</a>
    <a href="/activities">الرحلات والأنشطة</a>
    <a href="/polls">استطلاعات الرأي</a>
</nav>
"""


def page(title, content, **context):
    template = """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport"
              content="width=device-width, initial-scale=1.0">
        <title>{{ title }} | صوت الطالب</title>
        """ + BASE_STYLE + """
    </head>
    <body>
        """ + NAV + """
        <main class="container">
            {% with messages = get_flashed_messages() %}
                {% for message in messages %}
                    <div class="notice">{{ message }}</div>
                {% endfor %}
            {% endwith %}
            """ + content + """
        </main>
        <footer>صوت الطالب © 2026</footer>
    </body>
    </html>
    """
    return render_template_string(
        template, title=title, **context
    )


# ---------------- HOME ----------------

@app.route("/")
def home():
    with connect_db() as db:
        suggestion_count = db.execute(
            "SELECT COUNT(*) FROM suggestions"
        ).fetchone()[0]

        activity_count = db.execute(
            "SELECT COUNT(*) FROM activities"
        ).fetchone()[0]

        poll_count = db.execute(
            "SELECT COUNT(*) FROM polls"
        ).fetchone()[0]

        popular = db.execute("""
            SELECT s.id, s.title, s.category,
                   COUNT(v.id) AS votes
            FROM suggestions s
            LEFT JOIN suggestion_votes v
                ON s.id = v.suggestion_id
            GROUP BY s.id
            ORDER BY votes DESC, s.id DESC
            LIMIT 5
        """).fetchall()

    content = """
    <section class="hero">
        <h2>صوتك مسموع.. واقتراحك يصنع الفرق</h2>
        <p>
            منصة للمشاركة الطلابية وتطوير الحياة المدرسية.
            شارك فكرتك، اقترح نشاطًا، وصوّت برأيك.
        </p>
        <a class="button" href="/suggestions">شارك الآن</a>
    </section>

    <div class="grid">
        <div class="card">
            <h3>💡 الاقتراحات</h3>
            <h2>{{ suggestion_count }}</h2>
            <p>اقتراح مسجل</p>
            <a class="button" href="/suggestions">عرض الاقتراحات</a>
        </div>

        <div class="card">
            <h3>🚌 الأنشطة والرحلات</h3>
            <h2>{{ activity_count }}</h2>
            <p>طلب نشاط مسجل</p>
            <a class="button" href="/activities">عرض الأنشطة</a>
        </div>

        <div class="card">
            <h3>🗳️ استطلاعات الرأي</h3>
            <h2>{{ poll_count }}</h2>
            <p>استطلاع متاح</p>
            <a class="button" href="/polls">شارك في التصويت</a>
        </div>
    </div>

    <div class="card">
        <h2>🏆 الاقتراحات الأكثر شعبية</h2>
        {% for item in popular %}
            <div class="item">
                <strong>{{ item['title'] }}</strong>
                <p>{{ item['category'] }} | 👍 {{ item['votes'] }} صوت</p>
                <a href="/suggestions#idea{{ item['id'] }}">
                    عرض الاقتراح
                </a>
            </div>
        {% else %}
            <p>كن أول من يقدم اقتراحًا!</p>
        {% endfor %}
    </div>
    """

    return page(
        "الرئيسية", content,
        suggestion_count=suggestion_count,
        activity_count=activity_count,
        poll_count=poll_count,
        popular=popular
    )


# ---------------- SUGGESTIONS ----------------

@app.route("/suggestions")
def suggestions():
    with connect_db() as db:
        items = db.execute("""
            SELECT s.*,
                (SELECT COUNT(*) FROM suggestion_votes v
                 WHERE v.suggestion_id = s.id) AS votes
            FROM suggestions s
            ORDER BY votes DESC, s.id DESC
        """).fetchall()

    content = """
    <div class="card">
        <h2>💡 تقديم اقتراح جديد</h2>

        <form method="POST" action="/suggestions/submit">
            <label>اسم الطالب</label>
            <input name="student_name" maxlength="100" required>

            <label>اسم المدرسة</label>
            <input name="school_name" maxlength="150" required>

            <label>الصف الدراسي</label>
            <input name="grade" maxlength="60" required>

            <label>ماذا تمثل في مدرستك؟</label>
            <input name="representation" maxlength="120" required>

            <label>عنوان الاقتراح</label>
            <input name="title" maxlength="100" required>

            <label>نوع الاقتراح</label>
            <select name="category" required>
                <option>تطوير المدرسة</option>
                <option>رحلات وأنشطة</option>
                <option>مسابقات</option>
                <option>خدمات طلابية</option>
                <option>أخرى</option>
            </select>

            <label>تفاصيل الاقتراح</label>
            <textarea name="details" maxlength="2000"
                      required></textarea>

            <button type="submit">إرسال الاقتراح</button>
        </form>
    </div>

    <div class="card">
        <h2>📋 الاقتراحات الطلابية</h2>

        {% for s in items %}
            <div class="item" id="idea{{ s['id'] }}">
                <h3>{{ s['title'] }}</h3>
                <p>{{ s['details'] }}</p>
                <p><strong>النوع:</strong> {{ s['category'] }}</p>
                <p><strong>الطالب:</strong>
                    {{ s['student_name'] or 'غير مسجل' }}</p>
                <p><strong>المدرسة:</strong>
                    {{ s['school_name'] or 'غير مسجلة' }}</p>
                <p><strong>الصف:</strong>
                    {{ s['grade'] or 'غير مسجل' }}</p>
                <p><strong>الصفة:</strong>
                    {{ s['representation'] or 'غير مسجلة' }}</p>
                <p>👍 الأصوات: {{ s['votes'] }}</p>

                <form method="POST"
                      action="/suggestions/vote/{{ s['id'] }}">
                    <button type="submit">👍 صوّت للاقتراح</button>
                </form>
            </div>
        {% else %}
            <p>لا توجد اقتراحات حتى الآن.</p>
        {% endfor %}
    </div>
    """

    return page("الاقتراحات", content, items=items)


@app.route("/suggestions/submit", methods=["POST"])
def submit_suggestion():
    fields = [
        "student_name", "school_name", "grade",
        "representation", "title", "category", "details"
    ]

    data = {
        field: request.form.get(field, "").strip()
        for field in fields
    }

    if not all(data.values()):
        flash("Please complete all required fields.")
        return redirect(url_for("suggestions"))

    with connect_db() as db:
        db.execute("""
            INSERT INTO suggestions
            (student_name, school_name, grade, representation,
             title, category, details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, tuple(data[field] for field in fields))

    flash("تم حفظ اقتراحك بنجاح!")
    return redirect(url_for("suggestions"))


@app.route("/suggestions/vote/<int:suggestion_id>", methods=["POST"])
def vote_suggestion(suggestion_id):
    voter_id = session.setdefault("voter_id", secrets.token_hex(16))

    with connect_db() as db:
        exists = db.execute(
            "SELECT id FROM suggestions WHERE id = ?",
            (suggestion_id,)
        ).fetchone()

        if not exists:
            flash("الاقتراح غير موجود.")
            return redirect(url_for("suggestions"))

        try:
            db.execute("""
                INSERT INTO suggestion_votes
                (suggestion_id, voter_id)
                VALUES (?, ?)
            """, (suggestion_id, voter_id))
            flash("تم تسجيل صوتك!")
        except sqlite3.IntegrityError:
            flash("لقد صوّت لهذا الاقتراح من هذه الجلسة بالفعل.")

    return redirect(url_for("suggestions"))


# ---------------- ACTIVITIES ----------------

@app.route("/activities")
def activities():
    with connect_db() as db:
        items = db.execute("""
            SELECT a.*,
                ROUND(AVG(r.rating), 1) AS average_rating,
                COUNT(r.id) AS rating_count
            FROM activities a
            LEFT JOIN activity_ratings r ON a.id = r.activity_id
            GROUP BY a.id
            ORDER BY a.id DESC
        """).fetchall()

    content = """
    <div class="card">
        <h2>🚌 اقترح رحلة أو نشاطًا</h2>

        <form method="POST" action="/activities/submit">
            <label>اسم الطالب</label>
            <input name="student_name" maxlength="100" required>

            <label>اسم المدرسة</label>
            <input name="school_name" maxlength="150" required>

            <label>الصف الدراسي</label>
            <input name="grade" maxlength="60" required>

            <label>عنوان النشاط أو الرحلة</label>
            <input name="title" maxlength="120" required>

            <label>نوع النشاط</label>
            <select name="category">
                <option>رحلة</option>
                <option>مسابقة</option>
                <option>نشاط رياضي</option>
                <option>نشاط ثقافي</option>
                <option>عمل تطوعي</option>
                <option>أخرى</option>
            </select>

            <label>التفاصيل والهدف</label>
            <textarea name="details" maxlength="2000"
                      required></textarea>

            <button type="submit">إرسال طلب النشاط</button>
        </form>
    </div>

    <div class="card">
        <h2>📌 الأنشطة المقترحة</h2>
        {% for a in items %}
            <div class="item">
                <h3>{{ a['title'] }}</h3>
                <p>{{ a['details'] }}</p>
                <p>النوع: {{ a['category'] }}</p>
                <p>مقدم الطلب: {{ a['student_name'] }}</p>
                <p>المدرسة: {{ a['school_name'] }}</p>
                <p>⭐ متوسط التقييم:
                   {{ a['average_rating'] if a['average_rating']
                      is not none else 'لا يوجد تقييم بعد' }}
                </p>
                <p>عدد التقييمات: {{ a['rating_count'] }}</p>

                <form method="POST"
                      action="/activities/rate/{{ a['id'] }}">
                    <label>قيّم هذا النشاط من 1 إلى 5</label>
                    <select name="rating" required>
                        <option value="5">⭐⭐⭐⭐⭐ ممتاز</option>
                        <option value="4">⭐⭐⭐⭐ جيد جدًا</option>
                        <option value="3">⭐⭐⭐ جيد</option>
                        <option value="2">⭐⭐ مقبول</option>
                        <option value="1">⭐ يحتاج إلى تحسين</option>
                    </select>
                    <button type="submit">إرسال التقييم</button>
                </form>
            </div>
        {% else %}
            <p>لا توجد أنشطة مقترحة حتى الآن.</p>
        {% endfor %}
    </div>
    """

    return page("الرحلات والأنشطة", content, items=items)


@app.route("/activities/submit", methods=["POST"])
def submit_activity():
    fields = [
        "student_name", "school_name", "grade",
        "title", "category", "details"
    ]

    data = {
        field: request.form.get(field, "").strip()
        for field in fields
    }

    if not all(data.values()):
        flash("من فضلك أكمل جميع البيانات.")
        return redirect(url_for("activities"))

    with connect_db() as db:
        db.execute("""
            INSERT INTO activities
            (student_name, school_name, grade, title, category, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, tuple(data[field] for field in fields))

    flash("تم تسجيل طلب النشاط بنجاح!")
    return redirect(url_for("activities"))


@app.route("/activities/rate/<int:activity_id>", methods=["POST"])
def rate_activity(activity_id):
    voter_id = session.setdefault("voter_id", secrets.token_hex(16))

    try:
        rating = int(request.form.get("rating", "0"))
    except ValueError:
        rating = 0

    if rating < 1 or rating > 5:
        flash("اختَر تقييمًا من 1 إلى 5.")
        return redirect(url_for("activities"))

    with connect_db() as db:
        exists = db.execute(
            "SELECT id FROM activities WHERE id = ?",
            (activity_id,)
        ).fetchone()

        if not exists:
            flash("النشاط غير موجود.")
            return redirect(url_for("activities"))

        old = db.execute("""
            SELECT id FROM activity_ratings
            WHERE activity_id = ? AND voter_id = ?
        """, (activity_id, voter_id)).fetchone()

        if old:
            db.execute("""
                UPDATE activity_ratings SET rating = ?
                WHERE activity_id = ? AND voter_id = ?
            """, (rating, activity_id, voter_id))
            flash("تم تحديث تقييمك.")
        else:
            db.execute("""
                INSERT INTO activity_ratings
                (activity_id, voter_id, rating)
                VALUES (?, ?, ?)
            """, (activity_id, voter_id, rating))
            flash("شكرًا لتقييمك!")

    return redirect(url_for("activities"))


# ---------------- POLLS ----------------

@app.route("/polls")
def polls():
    with connect_db() as db:
        all_polls = db.execute(
            "SELECT * FROM polls ORDER BY id"
        ).fetchall()

        poll_data = []

        for poll in all_polls:
            options = db.execute("""
                SELECT o.id, o.option_text,
                    (SELECT COUNT(*) FROM poll_votes v
                     WHERE v.option_id = o.id) AS votes
                FROM poll_options o
                WHERE o.poll_id = ?
                ORDER BY o.id
            """, (poll["id"],)).fetchall()

            total = sum(option["votes"] for option in options)

            poll_data.append({
                "id": poll["id"],
                "question": poll["question"],
                "options": options,
                "total": total
            })

    content = """
    <div class="card">
        <h2>🗳️ استطلاعات الرأي الطلابية</h2>
        <p>شارك برأيك في الاستطلاعات المتاحة.</p>
    </div>

    {% for poll in poll_data %}
        <div class="card">
            <h3>{{ poll['question'] }}</h3>
            <p>إجمالي الأصوات: {{ poll['total'] }}</p>

            <form method="POST"
                  action="/polls/vote/{{ poll['id'] }}">
                {% for option in poll['options'] %}
                    <label>
                        <input type="radio" name="option_id"
                               value="{{ option['id'] }}"
                               required style="width:auto">
                        {{ option['option_text'] }}
                    </label>
                    <br>
                {% endfor %}
                <br>
                <button type="submit">صوّت الآن</button>
            </form>

            <h4>النتائج الحالية</h4>
            {% for option in poll['options'] %}
                <p>{{ option['option_text'] }} — {{ option['votes'] }} صوت</p>
                <div style="background:#e2e8f2;border-radius:8px;">
                    <div style="background:#3976d2;height:10px;
                        border-radius:8px;width:{{
                            (option['votes'] * 100 / poll['total'])
                            if poll['total'] else 0
                        }}%;"></div>
                </div>
            {% endfor %}
        </div>
    {% else %}
        <div class="card">
            <p>لا توجد استطلاعات متاحة.</p>
        </div>
    {% endfor %}
    """

    return page("استطلاعات الرأي", content, poll_data=poll_data)


@app.route("/polls/vote/<int:poll_id>", methods=["POST"])
def vote_poll(poll_id):
    voter_id = session.setdefault("voter_id", secrets.token_hex(16))

    try:
        option_id = int(request.form.get("option_id", "0"))
    except ValueError:
        option_id = 0

    with connect_db() as db:
        option = db.execute("""
            SELECT id FROM poll_options
            WHERE id = ? AND poll_id = ?
        """, (option_id, poll_id)).fetchone()

        if not option:
            flash("اختيار التصويت غير صحيح.")
            return redirect(url_for("polls"))

        try:
            db.execute("""
                INSERT INTO poll_votes
                (poll_id, option_id, voter_id)
                VALUES (?, ?, ?)
            """, (poll_id, option_id, voter_id))
            flash("تم تسجيل تصويتك بنجاح!")
        except sqlite3.IntegrityError:
            flash("لقد صوّت في هذا الاستطلاع من هذه الجلسة بالفعل.")

    return redirect(url_for("polls"))


# ---------------- START ----------------

if __name__ == "__main__":
    init_db()
    print("Sout El Taleb is running!")
    print("Open http://127.0.0.1:5000")
    app.run(debug=True)
