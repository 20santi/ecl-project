from io import BytesIO
from flask import Flask, render_template, request, redirect
import sqlite3
from flask import send_file
import pandas as pd # type: ignore
import re # type: ignore
from datetime import datetime
from flask import session # type: ignore


app = Flask(__name__)
app.secret_key = 'my-secret-key-12345'  # type: ignore # Required for session usage

# Create the database and table if not exists
def init_db():
    conn = sqlite3.connect('employee.db')
    cursor = conn.cursor()
    # cursor.execute("DROP TABLE IF EXISTS leave_requests")
    # cursor.execute("DROP TABLE IF EXISTS employees")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            employee_id TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT,
            leave_array TEXT DEFAULT ''
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_date TEXT NOT NULL,
            to_date TEXT NOT NULL,
            number_of_days INTEGER NOT NULL,
            leave_type TEXT NOT NULL,
            leave_reason TEXT NOT NULL,
            employee_id INTEGER NOT NULL,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    ''')

    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/get_employee', methods=['GET', 'POST'])
def get_employee_detail():
    result = None
    if request.method == 'POST':
        raw_input = request.form['name']
        search_terms = [term.strip() for term in raw_input.split(',') if term.strip()]

        if not search_terms:
            return render_template('show_employee.html', employees=[], names=raw_input, searched=True)

        conn = sqlite3.connect('employee.db')
        cursor = conn.cursor()

        result_set = {}
        for term in search_terms:
            like_term = f"%{term}%"
            cursor.execute('''
                SELECT * FROM employees
                WHERE name LIKE ? OR email LIKE ? OR employee_id LIKE ?
                      OR phone LIKE ? OR address LIKE ?
            ''', (like_term, like_term, like_term, like_term, like_term))

            for row in cursor.fetchall():
                emp_id = row[0]
                leave_array_csv = row[6]  # leave_array
                latest_reason = ''
                date_from = ''
                date_to = ''
                leaveType = ''
                if leave_array_csv:
                    leave_ids = leave_array_csv.split(',')
                    last_leave_id = leave_ids[-1]
                    cursor.execute('''
                        SELECT leave_reason,leave_type,from_date,to_date
                        FROM leave_requests
                        WHERE id = ?
                    ''', (last_leave_id,))
                    result = cursor.fetchone()
                    latest_reason = ''
                to_date = ''
                if result:
                    reason,leave_type, from_date_str, to_date_str = result
                    to_date = to_date_str
                    current_date = datetime.now().date()
                    try:
                        leave_end_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
                        if current_date <= leave_end_date:
                            latest_reason = reason  # Employee is currently on leave
                            date_from = from_date_str
                            date_to = to_date_str
                            leaveType = leave_type
                        else:
                            latest_reason = ''  # Leave has ended
                    except ValueError:
                        latest_reason = ''  # Invalid date format fallback

                result_set[emp_id] = row + (latest_reason,leaveType, date_from, date_to)

        employees = list(result_set.values())
        print("Employees found:", employees)

        session['export_data'] = employees  # Updated export data includes leave_reason

        conn.close()
        return render_template('show_employee.html', employees=employees, names=raw_input, searched=True)

    return render_template('show_employee.html', employees=None, names=None, searched=False)


@app.route('/submitLeave', methods=['POST'])
def submit_leave():
    emp_emp_id = request.form['employee_id']  # Example: "EMP001"
    from_date = request.form['from_date']
    to_date = request.form['to_date']
    number_of_days = int(request.form['days'])
    reason = request.form['reason']
    leave_type = request.form['leave_type']
    print("leave type: ", leave_type)
    print("leave reason: ", reason)

    conn = sqlite3.connect('employee.db')
    cursor = conn.cursor()

    # Step 1: Get internal employee ID using external employee_id
    cursor.execute("SELECT id, leave_array FROM employees WHERE employee_id = ?", (emp_emp_id,))
    emp_data = cursor.fetchone()

    if not emp_data:
        conn.close()
        return '<div><a href="/leaveForm">Employee not found. Go back!</a></div>'

    emp_id = emp_data[0]
    leave_array_csv = emp_data[1] or ""

    # Step 2: Insert leave request into leave_requests table
    cursor.execute('''
        INSERT INTO leave_requests (from_date, to_date, number_of_days, leave_reason, leave_type, employee_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (from_date, to_date, number_of_days, reason, leave_type, emp_id))
    conn.commit()

    new_leave_id = cursor.lastrowid  # Get ID of newly created leave request

    # Step 3: Update the employee's leave_array field
    leave_array = leave_array_csv.split(',') if leave_array_csv else []

    if len(leave_array) < 100:
        leave_array.append(str(new_leave_id))
    else:
        leave_array = [str(new_leave_id)]  # Reset array when limit is reached

    updated_leave_csv = ','.join(leave_array)

    # Update employee row with new leave_array
    cursor.execute('''
        UPDATE employees
        SET leave_array = ?
        WHERE id = ?
    ''', (updated_leave_csv, emp_id))

    conn.commit()
    conn.close()

    return '<div><a href="/leaveForm">Leave submitted successfully. Go back!</a></div>'


@app.route('/submit', methods=['POST'])
def submit():
    name = request.form['name']
    email = request.form['email']
    employee_id = request.form['employee_id']
    phone = request.form['phone']
    address = ''

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

    # Filter out only the required columns from each row
    print("Exporting rows:", rows)
    export_rows = [(row[1], row[2], row[3], row[4], row[7], row[8], row[9], row[10]) for row in rows]

    # Define only the required column headers
    columns = ['Name', 'Email', 'Employee ID', 'Phone', 'Leave Reason', 'Leave Type', 'From', 'To']

    df = pd.DataFrame(export_rows, columns=columns)

    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)

    timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    filename = f"{timestamp}.xlsx"

    return send_file(output,
                     download_name=filename,
                     as_attachment=True,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.route('/leave_type', methods=['POST'])
def leave_type_filter():
    selected_type = request.form['reason']
    print("Selected leave type:", selected_type)

    conn = sqlite3.connect('employee.db')
    cursor = conn.cursor()

    # Step 1: Get all leave requests with the selected leave_reason
        # Step 1: Find employees whose latest leave type matches selected_type
    cursor.execute('''
        SELECT e.*, lr.leave_reason, lr.leave_type, lr.from_date, lr.to_date
        FROM employees e
        JOIN (
            SELECT employee_id, MAX(id) as max_id
            FROM leave_requests
            GROUP BY employee_id
        ) latest ON latest.employee_id = e.id
        JOIN leave_requests lr ON lr.id = latest.max_id
        WHERE lr.leave_type = ?
    ''', (selected_type,))

    employees = cursor.fetchall()

    enriched_employees = []
    for emp in employees:
        # emp contains: all fields from employees + 4 leave fields
        enriched_employees.append(emp)

    session['export_data'] = enriched_employees

    # Step 3: For each employee, attach the latest leave_reason (if current)
    enriched_employees = []
    for emp in employees:
        emp_id = emp[0]
        cursor.execute('''
            SELECT leave_reason,leave_type,from_date, to_date
            FROM leave_requests
            WHERE employee_id = ?
            ORDER BY id DESC LIMIT 1
        ''', (emp_id,))
        leave_info = cursor.fetchone()
        latest_reason = ''
        leaveType = ''
        fromDate = ''
        toDate = ''
        if leave_info:
            reason,type, from_date_str, to_date_str = leave_info
            try:
                current_date = datetime.now().date()
                leave_end_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
                if current_date <= leave_end_date:
                    latest_reason = reason
                    leaveType = type
                    fromDate = from_date_str
                    toDate = to_date_str
            except ValueError:
                pass
        enriched_employees.append(emp + (latest_reason, leaveType, fromDate, toDate))

    session['export_data'] = enriched_employees
    conn.close()

    return render_template('show_employee.html', employees=enriched_employees, names=selected_type, searched=True)



@app.route('/leaveForm')
def leave_form():
    return render_template('leave_form.html')


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
