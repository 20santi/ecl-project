from io import BytesIO
from flask import Flask, render_template, request, redirect
import sqlite3
from flask import send_file
import pandas as pd # type: ignore
from datetime import datetime


app = Flask(__name__)

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
        raw_names = request.form['name']
        name_list = [name.strip() for name in raw_names.split(',') if name.strip()]
        
        placeholders = ','.join(['?'] * len(name_list))
        query = f'SELECT * FROM employees WHERE name IN ({placeholders})'
        conn = sqlite3.connect('employee.db')
        cursor = conn.cursor()
        cursor.execute(query, name_list)
        employees = cursor.fetchall()
        conn.close()
        return render_template('show_employee.html', employees=employees, names=raw_names, searched=True)

    
    # For GET request: just render search form without result
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
@app.route('/download_excel')
def download_excel():
    raw_names = request.args.get('name')  # Might be "Alice, Bob"
    if not raw_names:
        return "No employee name provided.", 400

    name_list = [name.strip() for name in raw_names.split(',') if name.strip()]
    if not name_list:
        return "No valid employee names provided.", 400

    placeholders = ','.join(['?'] * len(name_list))
    query = f"SELECT * FROM employees WHERE name IN ({placeholders})"

    conn = sqlite3.connect('employee.db')
    cursor = conn.cursor()
    cursor.execute(query, name_list)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return "No matching employees found.", 404

    columns = ['ID', 'Name', 'Email', 'Employee ID', 'Phone', 'Address']
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


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
