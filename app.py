from io import BytesIO
from flask import Flask, render_template, request, redirect
import sqlite3
from flask import send_file
import pandas as pd # type: ignore
from datetime import datetime
from flask import session # type: ignore


app = Flask(__name__)
app.secret_key = 'my-secret-key-12345'  # type: ignore # Required for session usage

# Create the database and table if not exists
def init_db():
    conn = sqlite3.connect('employee.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            employee_id TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_employee', methods=['GET', 'POST'])
def get_employee_detail():
    if request.method == 'POST':
        raw_input = request.form['name']
        search_terms = [term.strip() for term in raw_input.split(',') if term.strip()]

        if not search_terms:
            return render_template('show_employee.html', employees=[], names=raw_input, searched=True)

        conn = sqlite3.connect('employee.db')
        cursor = conn.cursor()

        result_set = set()
        for term in search_terms:
            like_term = f"%{term}%"
            cursor.execute('''
                SELECT * FROM employees
                WHERE name LIKE ? OR email LIKE ? OR employee_id LIKE ?
                      OR phone LIKE ? OR address LIKE ?
            ''', (like_term, like_term, like_term, like_term, like_term))
            
            for row in cursor.fetchall():
                result_set.add(row)

        conn.close()
        employees = list(result_set)

        # Save result in session
        session['export_data'] = employees

        return render_template('show_employee.html', employees=employees, names=raw_input, searched=True)

    return render_template('show_employee.html', employees=None, names=None, searched=False)



@app.route('/submit', methods=['POST'])
def submit():
    name = request.form['name']
    email = request.form['email']
    employee_id = request.form['employee_id']
    phone = request.form['phone']
    address = request.form['address']

    conn = sqlite3.connect('employee.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO employees (name, email, employee_id, phone, address)
        VALUES (?, ?, ?, ?, ?)
    ''', (name, email, employee_id, phone, address))
    conn.commit()
    conn.close()

    return '<div><a href="/">Data submitted successfully. Go back!</a></div>'

@app.route('/download_excel')
def download_excel():
    if 'export_data' not in session:
        return "No search result to export.", 400

    rows = session['export_data']

    if not rows:
        return "No matching employees found.", 404

    columns = ['ID', 'Name', 'Email', 'Employee ID', 'Phone', 'Leave Reason']
    df = pd.DataFrame(rows, columns=columns)

    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)

    timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    filename = f"{timestamp}.xlsx"

    return send_file(output,
                     download_name=filename,
                     as_attachment=True,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.route('/all_employees', methods=['GET'])
def all_employees():
    conn = sqlite3.connect('employee.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM employees")
    employees = cursor.fetchall()
    conn.close()
    return render_template('show_employee.html', employees=employees, names='All Employees', searched=True)


init_db()  # Always initialize DB

if __name__ == '__main__':
    app.run(debug=True)
