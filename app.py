from flask import Flask, render_template, request, redirect, session, url_for
from flask_mysqldb import MySQL
from ai_scanner import detect_books
from werkzeug.security import generate_password_hash, check_password_hash
from book_locator import locate_book
from ocr_locator import locate_book_by_text
from rapidfuzz import fuzz
from flask_mail import Mail, Message
from flask_mail import Message
import config
import pandas as pd
import os
import random
import string
import requests
import qrcode
app = Flask(__name__)
app.secret_key = "Shubham_Library_AI_2026_Secure_Key_@123"

# MySQL Configuration
app.config['MYSQL_HOST'] = config.MYSQL_HOST
app.config['MYSQL_USER'] = config.MYSQL_USER
app.config['MYSQL_PASSWORD'] = config.MYSQL_PASSWORD
app.config['MYSQL_DB'] = config.MYSQL_DB

mysql = MySQL(app)

# =========================
# Flask Mail Configuration
# =========================

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'softwaresky0987@gmail.com'
app.config['MAIL_PASSWORD'] = 'cjft ybvd csbw qmtv'

mail = Mail(app)
def generate_qr_card(student_id, name, library_id):

    qr_data = f"""
    Student ID : {student_id}

    Name : {name}

    Library ID : {library_id}
    """

    qr = qrcode.make(qr_data)

    qr.save(
        f"static/cards/{student_id}.png"
    )

# =========================
# Email Function
# =========================
def send_email(receiver, subject, body):

    msg = Message(
        subject,
        sender=app.config['MAIL_USERNAME'],
        recipients=[receiver]
    )

    msg.body = body

    mail.send(msg)
def send_welcome_email(email, name):

    msg = Message(
        "Welcome To Smart Library AI",
        sender=app.config['MAIL_USERNAME'],
        recipients=[email]
    )

    msg.body = f"""
Hello {name},

Your account has been created successfully.

Welcome to Smart Library AI Platform.

You can now login and access the library.

Regards,
Smart Library AI Team
"""

    mail.send(msg)
student_temp_data = {}
teacher_temp_data = {}
library_temp_data = {}



@app.route('/')
def index():
    return render_template('index.html')
def generate_otp():
    return str(random.randint(100000, 999999))


@app.route('/login', methods=['GET','POST'])
def user_login():

    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        print("="*50)
        print("EMAIL:", email)
        print("PASSWORD:", password)
        print("ROLE:", role)

        cur = mysql.connection.cursor()

        if role == "admin":

            cur.execute("""
            SELECT *
            FROM libraries
            WHERE email=%s
            AND password=%s
            """, (email, password))

            user = cur.fetchone()

            print("ADMIN USER:", user)

            if user:
                session['admin'] = email
                print("ADMIN LOGIN SUCCESS")
                return redirect('/admin')

        elif role == "student":

            cur.execute("""
            SELECT *
            FROM students
            WHERE email=%s
            AND password=%s
            """, (email, password))

            user = cur.fetchone()

            print("STUDENT USER:", user)

            if user:
                session['student'] = email
                print("STUDENT LOGIN SUCCESS")
                return redirect('/student_dashboard')

        elif role == "teacher":

            cur.execute("""
            SELECT *
            FROM teachers
            WHERE email=%s
            AND password=%s
            """, (email, password))

            user = cur.fetchone()

            print("TEACHER USER:", user)

            if user:
                session['teacher'] = email
                print("TEACHER LOGIN SUCCESS")
                return redirect('/teacher_dashboard')

        print("LOGIN FAILED")
        return "Invalid Login"

    return render_template("login.html")

@app.route('/admin')
def admin_dashboard():

    if 'admin' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()

    cur.execute("SELECT COUNT(*) FROM books")
    total_books = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM students")
    total_students = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM teachers")
    total_teachers = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM issued_books")
    issued_books = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM issued_books
        WHERE return_date < CURDATE()
    """)
    overdue_books = cur.fetchone()[0]

    cur.execute("""
        SELECT SUM(fine_amount)
        FROM issued_books
    """)
    total_fine = cur.fetchone()[0]

    if total_fine is None:
        total_fine = 0

    cur.close()

    return render_template(
        "admin_dashboard.html",
        total_books=total_books,
        total_students=total_students,
        total_teachers=total_teachers,
        issued_books=issued_books,
        overdue_books=overdue_books,
        total_fine=total_fine
    )
    return redirect('/')
@app.route('/search', methods=['GET', 'POST'])
def search():
    result = None
    borrower = None

    if request.method == 'POST':
        book_name = request.form['book_name']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM books WHERE title LIKE %s", ('%' + book_name + '%',))
        book = cur.fetchone()

        if book:
            if book[5] > 0:
                result = {
                    "status": "Available",
                    "title": book[1],
                    "copies": book[5]
                }
            else:
                cur.execute("""
                    SELECT users.name, issued_books.return_date
                    FROM issued_books
                    JOIN users ON issued_books.user_id = users.id
                    WHERE issued_books.book_id = %s AND issued_books.status='issued'
                """, (book[0],))
                borrower = cur.fetchone()

                result = {
                    "status": "Not Available",
                    "title": book[1]
                }

        else:
            result = {"status": "Not Found"}

        cur.close()

    return render_template("search.html", result=result, borrower=borrower)
@app.route('/import_books')
def import_books():
    file_path = "uploads/books.xlsx"
    df = pd.read_excel(file_path)

    cur = mysql.connection.cursor()

    for index, row in df.iterrows():
        title = str(row['Title/Name of Book'])
        author = str(row['Author'])
        publisher = str(row['Publication/Publisher/Location'])

        cur.execute("""
            INSERT INTO books (title, author, publisher, total_copies, available_copies)
            VALUES (%s, %s, %s, %s, %s)
        """, (title, author, publisher, 1, 1))

    mysql.connection.commit()
    cur.close()

    return "Books Imported Successfully!"
from datetime import datetime, timedelta

@app.route('/issue', methods=['GET', 'POST'])
def issue_book():
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        user_id = request.form['user_id']
        book_id = request.form['book_id']

        issue_date = datetime.today().date()
        return_date = issue_date + timedelta(days=7)

        # Insert into issued_books
        cur.execute("""
            INSERT INTO issued_books 
            (user_id, book_id, issue_date, return_date, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, book_id, issue_date, return_date, 'issued'))

        # Reduce available copies
        cur.execute("""
            UPDATE books 
            SET available_copies = available_copies - 1 
            WHERE id = %s
        """, (book_id,))

        mysql.connection.commit()
        return "Book Issued Successfully!"

    # Fetch users and books for dropdown
    cur.execute("SELECT id, name FROM users WHERE role IN ('student','teacher')")
    users = cur.fetchall()

    cur.execute("SELECT id, title FROM books WHERE available_copies > 0")
    books = cur.fetchall()

    return render_template("issue_book.html", users=users, books=books)
@app.route('/create_student')
def create_student():
    cur = mysql.connection.cursor()
    password = generate_password_hash("student123")

    cur.execute("""
        INSERT INTO users (name, email, password, role)
        VALUES (%s, %s, %s, %s)
    """, ("Rahul", "rahul@gmail.com", password, "student"))

    mysql.connection.commit()
    cur.close()

    return "Student Created!"
@app.route('/return', methods=['GET', 'POST'])
def return_book():
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        issue_id = request.form['issue_id']

        # Get issue details
        cur.execute("SELECT book_id, return_date FROM issued_books WHERE id=%s AND status='issued'", (issue_id,))
        record = cur.fetchone()

        if record:
            book_id = record[0]
            return_date = record[1]

            today = datetime.today().date()

            # Fine calculation (₹5 per day late)
            fine = 0
            if today > return_date:
                days_late = (today - return_date).days
                fine = days_late * 5

            # Update issued_books
            cur.execute("""
                UPDATE issued_books
                SET status='returned',
                    actual_return=%s,
                    fine_amount=%s
                WHERE id=%s
            """, (today, fine, issue_id))

            # Increase available copies
            cur.execute("""
                UPDATE books
                SET available_copies = available_copies + 1
                WHERE id=%s
            """, (book_id,))

            mysql.connection.commit()
            return f"Book Returned Successfully! Fine: ₹{fine}"

    # Show issued books only
    cur.execute("""
        SELECT issued_books.id, users.name, books.title
        FROM issued_books
        JOIN users ON issued_books.user_id = users.id
        JOIN books ON issued_books.book_id = books.id
        WHERE issued_books.status='issued'
    """)
    records = cur.fetchall()

    return render_template("return_book.html", records=records)
@app.route('/view_issued')
def view_issued():
    if 'role' in session and session['role'] == 'admin':
        cur = mysql.connection.cursor()

        cur.execute("""
            SELECT users.name, books.title,
                   issued_books.issue_date,
                   issued_books.return_date,
                   issued_books.fine_amount,
                   issued_books.status
            FROM issued_books
            JOIN users ON issued_books.user_id = users.id
            JOIN books ON issued_books.book_id = books.id
        """)

        records = cur.fetchall()
        cur.close()

        return render_template("view_issued.html", records=records)

    return redirect(url_for('home'))
@app.route('/export_issued')
def export_issued():
    if 'role' in session and session['role'] == 'admin':
        cur = mysql.connection.cursor()

        cur.execute("""
            SELECT users.name, books.title,
                   issued_books.issue_date,
                   issued_books.return_date,
                   issued_books.fine_amount,
                   issued_books.status
            FROM issued_books
            JOIN users ON issued_books.user_id = users.id
            JOIN books ON issued_books.book_id = books.id
        """)

        records = cur.fetchall()
        cur.close()

        import pandas as pd

        df = pd.DataFrame(records, columns=[
            "User Name", "Book Title",
            "Issue Date", "Return Date",
            "Fine", "Status"
        ])

        file_path = "issued_books_report.xlsx"
        df.to_excel(file_path, index=False)

        return "Report Generated! Check project folder."

    return redirect(url_for('home'))
@app.route('/add_book', methods=['GET', 'POST'])
def add_book():

    if 'role' in session and session['role'] == 'admin':

        if request.method == 'POST':

            title = request.form['title']
            author = request.form['author']
            publisher = request.form['publisher']

            rack = request.form['rack']
            shelf = request.form['shelf']

            cover = request.files['cover']

            cover_filename = cover.filename

            cover_path = os.path.join(
                'static/book_covers',
                cover_filename
            )

            cover.save(cover_path)

            cur = mysql.connection.cursor()

            cur.execute("""
                INSERT INTO books
                (
                    title,
                    author,
                    publisher,
                    total_copies,
                    available_copies,
                    cover_image,
                    rack_no,
                    shelf_no
                )
                VALUES
                (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                title,
                author,
                publisher,
                1,
                1,
                cover_filename,
                rack,
                shelf
            ))

            mysql.connection.commit()

            cur.close()

            return "Book Added Successfully!"

        return render_template("add_book.html")

    return redirect(url_for('home'))
@app.route('/scan_shelf', methods=['GET', 'POST'])
def scan_shelf():

    if request.method == 'POST':

        image = request.files['image']

        upload_folder = 'uploads/shelf_images'

        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)

        image_path = os.path.join(
            upload_folder,
            image.filename
        )

        image.save(image_path)

        detected_texts = detect_books(image_path)

        found_books = []

        cur = mysql.connection.cursor()

        for text in detected_texts:

            cur.execute(
                """
                SELECT *
                FROM books
                WHERE title LIKE %s
                """,
                ('%' + text + '%',)
            )

            books = cur.fetchall()

            for book in books:
                found_books.append(book)

        cur.close()

        return render_template(
            'scan_result.html',
            books=found_books,
            texts=detected_texts
        )

    return render_template('scan_shelf.html')
@app.route('/find_book', methods=['GET', 'POST'])
def find_book():

    if request.method == 'POST':

        book_name = request.form['book_name']

        shelf_image = request.files['shelf_image']

        shelf_path = os.path.join(
            'uploads/shelf_images',
            shelf_image.filename
        )

        shelf_image.save(shelf_path)

        cur = mysql.connection.cursor()

        cur.execute("""
SELECT
    cover_image,
    rack_no,
    shelf_no,
    title
FROM books
WHERE title=%s
AND cover_image IS NOT NULL
ORDER BY id DESC
LIMIT 1
""", (book_name,))

        book = cur.fetchone()

        cur.close()

        if not book:
            return "Book not found in database"

        cover_path = os.path.join(
            'static/book_covers',
            book[0]
        )

        result = locate_book(
          cover_path,
          shelf_path
        )

        if result is None:

            print("ORB Failed - Trying OCR")

            result = locate_book_by_text(
               book_name,
               shelf_path
    )

        if result is None:
            return """
            <h2>Book could not be located in the shelf image.</h2>
            <a href='/find_book'>Try Again</a>
            """
        _, confidence = result
        return render_template(
            'book_found.html',
            title=book[3],
            rack=book[1],
            shelf=book[2],
            confidence = confidence
        )

    return render_template('find_book.html')
@app.route('/manage_books')
def manage_books():

    if 'role' not in session:
        return redirect(url_for('home'))

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT
            id,
            title,
            author,
            publisher,
            rack_no,
            shelf_no,
            available_copies
        FROM books
        ORDER BY id DESC
    """)

    books = cur.fetchall()

    cur.close()

    return render_template(
        'manage_books.html',
        books=books
    )
@app.route('/delete_book/<int:id>')
def delete_book(id):

    cur = mysql.connection.cursor()

    cur.execute(
        "DELETE FROM books WHERE id=%s",
        (id,)
    )

    mysql.connection.commit()

    cur.close()

    return redirect('/manage_books')
@app.route('/edit_book/<int:id>', methods=['GET', 'POST'])
def edit_book(id):

    cur = mysql.connection.cursor()

    if request.method == 'POST':

        title = request.form['title']
        author = request.form['author']
        publisher = request.form['publisher']
        rack_no = request.form['rack_no']
        shelf_no = request.form['shelf_no']

        cur.execute("""
            UPDATE books
            SET title=%s,
                author=%s,
                publisher=%s,
                rack_no=%s,
                shelf_no=%s
            WHERE id=%s
        """,
        (
            title,
            author,
            publisher,
            rack_no,
            shelf_no,
            id
        ))

        mysql.connection.commit()

        return redirect('/manage_books')

    cur.execute(
        "SELECT * FROM books WHERE id=%s",
        (id,)
    )

    book = cur.fetchone()

    cur.close()

    return render_template(
        'edit_book.html',
        book=book
    )

@app.route('/register_library', methods=['GET','POST'])
def register_library():

    if request.method == 'POST':

        library_name = request.form['library_name']
        college_name = request.form['college_name']
        incharge_name = request.form['incharge_name']
        email = request.form['email']
        phone = request.form['phone']
        state = request.form['state']
        city = request.form['city']
        password = request.form['password']

        otp = generate_otp()

        library_temp_data[email] = {

            "library_name": library_name,
            "college_name": college_name,
            "incharge_name": incharge_name,
            "email": email,
            "phone": phone,
            "state": state,
            "city": city,
            "password": password,
            "otp": otp
        }

        send_email(
            email,
            "Library Registration OTP",
            f"Your OTP is: {otp}"
        )

        session['library_email'] = email

        return redirect('/verify_library_otp')

    return render_template('register_library.html')
@app.route('/verify_library_otp', methods=['GET','POST'])
def verify_library_otp():

    email = session.get('library_email')

    if not email:
        return redirect('/register_library')

    if request.method == 'POST':

        entered_otp = request.form['otp']

        if entered_otp == library_temp_data[email]['otp']:

            data = library_temp_data[email]

            library_id = "LIB-" + ''.join(
                random.choices(
                    string.ascii_uppercase + string.digits,
                    k=6
                )
            )

            cur = mysql.connection.cursor()

            cur.execute("""
            INSERT INTO libraries(
                library_id,
                library_name,
                college_name,
                incharge_name,
                email,
                phone,
                state,
                city,
                password
            )
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,(
                library_id,
                data['library_name'],
                data['college_name'],
                data['incharge_name'],
                data['email'],
                data['phone'],
                data['state'],
                data['city'],
                data['password']
            ))

            mysql.connection.commit()

            cur.close()

            send_email(
                data['email'],
                "Library Created Successfully",
                f"""
Hello {data['incharge_name']},

Library Name: {data['library_name']}
College Name: {data['college_name']}

Library ID: {library_id}

Share this Library ID with students and teachers.

Smart Library AI
"""
            )

            del library_temp_data[email]

            return f"""
            <h2>Library Created Successfully</h2>

            <h3>Library ID: {library_id}</h3>

            <a href='/login'>Login Now</a>
            """

        return "<h2>Invalid OTP</h2>"

    return render_template('verify_library_otp.html')
@app.route('/register_student', methods=['GET','POST'])
def register_student():

    if request.method == 'POST':

        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        library_id = request.form['library_id']
        password = request.form['password']

        otp = str(random.randint(100000,999999))

        student_temp_data[email] = {
            "name": name,
            "email": email,
            "phone": phone,
            "library_id": library_id,
            "password": password,
            "otp": otp
        }

        send_email(
            email,
            "Smart Library OTP",
            f"Your OTP is {otp}"
        )

        session['student_email'] = email

        return redirect('/verify_student_otp')

    return render_template('register_student.html')
@app.route('/verify_student_otp', methods=['GET', 'POST'])
def verify_student_otp():

    email = session.get('student_email')

    if not email:
        return redirect('/register_student')

    if request.method == 'POST':

        entered_otp = request.form['otp']

        if entered_otp == student_temp_data[email]['otp']:

            data = student_temp_data[email]

            cur = mysql.connection.cursor()

            # Insert Student
            cur.execute("""
                INSERT INTO students
                (name, email, phone, library_id, password)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                data['name'],
                data['email'],
                data['phone'],
                data['library_id'],
                data['password']
            ))

            mysql.connection.commit()

            # Get Student ID
            cur.execute("""
                SELECT id
                FROM students
                WHERE email=%s
            """, (data['email'],))

            student = cur.fetchone()

            student_id = student[0]

            # Generate QR Card
            generate_qr_card(
                student_id,
                data['name'],
                data['library_id']
            )

            cur.close()

            # Welcome Email
            send_email(
                data['email'],
                "Welcome To Smart Library AI",
                f"""
Hello {data['name']},

Your account has been created successfully.

Student ID:
{student_id}

Library ID:
{data['library_id']}

Enjoy using Smart Library AI.

Regards,
Smart Library AI Team
"""
            )

            del student_temp_data[email]

            return redirect(
                f'/student_card/{student_id}'
            )

        return """
        <h2>Invalid OTP</h2>
        <a href="/verify_student_otp">Try Again</a>
        """

    return '''
    <form method="POST">
        <h2>Verify Student OTP</h2>

        <input
            type="text"
            name="otp"
            placeholder="Enter OTP"
            required>

        <button type="submit">
            Verify OTP
        </button>

    </form>
    '''
@app.route('/register_teacher', methods=['GET','POST'])
def register_teacher():

    if request.method == 'POST':

        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        employee_id = request.form['employee_id']
        library_id = request.form['library_id']
        password = request.form['password']

        cur = mysql.connection.cursor()

        cur.execute("""
        SELECT *
        FROM libraries
        WHERE library_id=%s
        """, (library_id,))

        library = cur.fetchone()

        if not library:
            return "<h2>Invalid Library ID</h2>"

        otp = generate_otp()

        teacher_temp_data[email] = {
            "name": name,
            "email": email,
            "phone": phone,
            "employee_id": employee_id,
            "library_id": library_id,
            "password": password,
            "otp": otp
        }

        send_email(
            email,
            "Teacher Registration OTP",
            f"Your OTP is: {otp}"
        )

        session['teacher_email'] = email

        return redirect('/verify_teacher_otp')

    return render_template('register_teacher.html')
@app.route('/verify_teacher_otp', methods=['GET','POST'])
def verify_teacher_otp():

    email = session.get('teacher_email')

    if not email:
        return redirect('/register_teacher')

    if request.method == 'POST':

        entered_otp = request.form['otp']

        if entered_otp == teacher_temp_data[email]['otp']:

            data = teacher_temp_data[email]

            cur = mysql.connection.cursor()

            cur.execute("""
            INSERT INTO teachers(
                library_id,
                name,
                email,
                phone,
                employee_id,
                password
            )
            VALUES(%s,%s,%s,%s,%s,%s)
            """,(
                data['library_id'],
                data['name'],
                data['email'],
                data['phone'],
                data['employee_id'],
                data['password']
            ))

            mysql.connection.commit()

            cur.close()

            send_email(
                data['email'],
                "Teacher Account Created",
                f"""
Hello {data['name']},

Your Teacher Account has been created successfully.

Library ID: {data['library_id']}

Welcome to Smart Library AI.
"""
            )

            del teacher_temp_data[email]

            return """
            <h2>Teacher Account Created Successfully</h2>
            <a href='/login'>Login Now</a>
            """

        return "<h2>Invalid OTP</h2>"

    return render_template('verify_teacher_otp.html')

@app.route('/student_dashboard')
def student_dashboard():

    if 'student' not in session:
        return redirect('/login')

    return render_template(
        'student_dashboard.html'
    )


@app.route('/teacher_dashboard')
def teacher_dashboard():

    if 'teacher' not in session:
        return redirect('/login')

    return render_template(
        'teacher_dashboard.html'
    )
@app.route('/send_otp', methods=['POST'])
def send_otp():

    phone = request.form['phone']

    otp = generate_otp()

    cur = mysql.connection.cursor()

    cur.execute("""
    INSERT INTO otp_verification(phone, otp)
    VALUES(%s,%s)
    """, (phone, otp))

    mysql.connection.commit()

    print("OTP =", otp)

    return "OTP Sent"
@app.route('/test_email')
def test_email():

    msg = Message(
        'Smart Library AI Test',
        sender=app.config['MAIL_USERNAME'],
        recipients=['softwaresky0987@gmail.com']
    )

    msg.body = '''
Hello Shubham,

This is a test email from Smart Library AI.

Email service is working successfully.

Regards,
Smart Library AI
'''

    mail.send(msg)

    return "Email Sent Successfully!"

@app.route('/test_otp')
def test_otp():

    otp = generate_otp()

    session['otp'] = otp

    msg = Message(
        'Smart Library AI OTP',
        sender=app.config['MAIL_USERNAME'],
        recipients=['softwaresky0987@gmail.com']
    )

    msg.body = f"""
Hello Shubham,

Your OTP is:

{otp}

Valid for 5 minutes.

Smart Library AI
"""

    mail.send(msg)

    return f"OTP Sent Successfully: {otp}"

@app.route('/verify_otp', methods=['GET','POST'])
def verify_otp():

    if request.method == 'POST':

        user_otp = request.form['otp']

        if user_otp == session.get('otp'):
            return "<h2>OTP Verified Successfully</h2>"

        return "<h2>Invalid OTP</h2>"

    return '''
    <form method="POST">
        <input type="text" name="otp" placeholder="Enter OTP">
        <button type="submit">Verify OTP</button>
    </form>
    '''
@app.route('/my_card')
def my_card():

    if 'student' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT id,name,library_id
    FROM students
    WHERE email=%s
    """,(session['student'],))

    student = cur.fetchone()

    cur.close()

    return render_template(
        'student_card.html',
        student_id=student[0],
        name=student[1],
        library_id=student[2]
    )  
if __name__ == '__main__':
    app.run(debug=True)