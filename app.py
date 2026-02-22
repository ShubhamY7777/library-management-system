from flask import Flask, render_template, request, redirect, session, url_for
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
import config
import pandas as pd
app = Flask(__name__)
app.secret_key = "library_secret_key"

# MySQL Configuration
app.config['MYSQL_HOST'] = config.MYSQL_HOST
app.config['MYSQL_USER'] = config.MYSQL_USER
app.config['MYSQL_PASSWORD'] = config.MYSQL_PASSWORD
app.config['MYSQL_DB'] = config.MYSQL_DB

mysql = MySQL(app)


@app.route('/')
def home():
    return render_template("login.html")


@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    cur.close()

    if user:
        if check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['role'] = user[4]

            if user[4] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user[4] == 'student':
                return redirect(url_for('student_dashboard'))
            elif user[4] == 'teacher':
                return redirect(url_for('teacher_dashboard'))

    return "Invalid Credentials"


@app.route('/admin')
def admin_dashboard():
    if 'role' in session and session['role'] == 'admin':
        cur = mysql.connection.cursor()

        # Total Books
        cur.execute("SELECT COUNT(*) FROM books")
        total_books = cur.fetchone()[0]

        # Total Students
        cur.execute("SELECT COUNT(*) FROM users WHERE role='student'")
        total_students = cur.fetchone()[0]

        # Total Teachers
        cur.execute("SELECT COUNT(*) FROM users WHERE role='teacher'")
        total_teachers = cur.fetchone()[0]

        # Issued Books
        cur.execute("SELECT COUNT(*) FROM issued_books WHERE status='issued'")
        issued_books = cur.fetchone()[0]

        # Overdue Books
        cur.execute("""
            SELECT COUNT(*) FROM issued_books 
            WHERE status='issued' AND return_date < CURDATE()
        """)
        overdue_books = cur.fetchone()[0]

        # Total Fine Collected
        cur.execute("SELECT SUM(fine_amount) FROM issued_books")
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

    return redirect(url_for('home'))


@app.route('/student')
def student_dashboard():
    if 'role' in session and session['role'] == 'student':
        cur = mysql.connection.cursor()

        cur.execute("""
            SELECT books.title, issued_books.issue_date,
                   issued_books.return_date,
                   issued_books.fine_amount,
                   issued_books.status
            FROM issued_books
            JOIN books ON issued_books.book_id = books.id
            WHERE issued_books.user_id = %s
        """, (session['user_id'],))

        records = cur.fetchall()
        cur.close()

        return render_template("student_dashboard.html", records=records)

    return redirect(url_for('home'))


@app.route('/teacher')
def teacher_dashboard():
    return render_template("teacher_dashboard.html")

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

            cur = mysql.connection.cursor()
            cur.execute("""
                INSERT INTO books (title, author, publisher, total_copies, available_copies)
                VALUES (%s, %s, %s, %s, %s)
            """, (title, author, publisher, 1, 1))
            mysql.connection.commit()
            cur.close()

            return "Book Added Successfully!"

        return render_template("add_book.html")

    return redirect(url_for('home'))
if __name__ == '__main__':
    app.run(debug=True)