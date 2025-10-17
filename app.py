from flask import Flask, render_template, request, redirect, url_for, session, flash
from models import db, User, Student, Course, Enrollment, Grade, Payment, News, Schedule, init_db

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sms_demo.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'dev-secret-key'

db.init_app(app)

@app.route('/', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            session['user_id'] = user.id
            session['role'] = user.role
            session['username'] = user.username
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password")
    return render_template('login.html')

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if not require_login():
        return redirect(url_for('login'))
    if request.method == 'POST':
        user = User.query.get(session['user_id'])
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        if user.password == current_password:
            user.password = new_password
            db.session.commit()
            flash('Password changed successfully')
            return redirect(url_for('dashboard'))
        else:
            flash('Current password is incorrect')
    return render_template('change_password.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

def require_login():
    return 'user_id' in session

@app.route('/dashboard')
def dashboard():
    if not require_login():
        return redirect(url_for('login'))
    role = session.get('role')
    username = session.get('username')
    stats = {
        'students': Student.query.count(),
        'courses': Course.query.count(),
        'news': News.query.count()
    }
    latest_news = News.query.order_by(News.id.desc()).limit(3).all()
    schedules = []
    if role == 'lecturer':
        lecturer_courses = Course.query.filter_by(lecturer=username).all()
        course_ids = [c.id for c in lecturer_courses]
        schedules = Schedule.query.filter(Schedule.course_id.in_(course_ids)).all()
    elif role == 'student':
        schedules = Schedule.query.all()
    else:
        schedules = Schedule.query.all()
    schedules.sort(key=lambda x: (x.day_of_week, x.start_time))
    return render_template('dashboard.html',
                         role=role,
                         username=username,
                         stats=stats,
                         latest_news=latest_news,
                         schedules=schedules)

@app.route('/students')
def students():
    if not require_login(): return redirect(url_for('login'))
    students = Student.query.all()
    return render_template('students.html', students=students)

@app.route('/students/new', methods=['GET','POST'])
def student_new():
    if not require_login(): return redirect(url_for('login'))
    if request.method == 'POST':
        s = Student(
            student_id=request.form['student_id'],
            full_name=request.form['full_name'],
            dob=request.form['dob'],
            email=request.form['email']
        )
        db.session.add(s)
        db.session.commit()
        return redirect(url_for('students'))
    return render_template('student_form.html', student=None)

@app.route('/students/<int:sid>/edit', methods=['GET','POST'])
def student_edit(sid):
    if not require_login(): return redirect(url_for('login'))
    s = Student.query.get_or_404(sid)
    if request.method == 'POST':
        s.student_id = request.form['student_id']
        s.full_name = request.form['full_name']
        s.dob = request.form['dob']
        s.email = request.form['email']
        db.session.commit()
        return redirect(url_for('students'))
    return render_template('student_form.html', student=s)

@app.route('/students/<int:sid>/delete', methods=['POST'])
def student_delete(sid):
    if not require_login(): return redirect(url_for('login'))
    s = Student.query.get_or_404(sid)
    db.session.delete(s)
    db.session.commit()
    return redirect(url_for('students'))

@app.route('/courses', methods=['GET', 'POST'])
def courses():
    if not require_login():
        return redirect(url_for('login'))
    if request.method == 'POST' and session.get('role') == 'admin':
        code = request.form['code']
        name = request.form['name']
        credits = int(request.form['credits'])
        lecturer = request.form['lecturer']
        if Course.query.filter_by(code=code).first():
            flash('Mã môn học đã tồn tại, vui lòng nhập mã khác!', 'danger')
        else:
            c = Course(code=code, name=name, credits=credits, lecturer=lecturer)
            db.session.add(c)
            db.session.commit()
            flash('Thêm môn học thành công!', 'success')

    all_courses = Course.query.all()
    lecturers = list({c.lecturer for c in all_courses if c.lecturer})

    # Lấy danh sách giảng viên đã chọn từ request
    selected_lecturers = request.args.getlist('lecturer[]')

    # Lọc các môn học theo giảng viên đã chọn
    if selected_lecturers:
        filtered_courses = [c for c in all_courses if c.lecturer in selected_lecturers]
        other_courses = [c for c in all_courses if c.lecturer not in selected_lecturers]
    else:
        filtered_courses = all_courses
        other_courses = []

    enrolled_course_ids = []
    if session.get('role') == 'student':
        student = Student.query.filter_by(student_id=session['username']).first()
        if student:
            enrolled_course_ids = [e.course_id for e in Enrollment.query.filter_by(student_id=student.id).all()]

    return render_template(
        'courses.html',
        lecturers=lecturers,
        selected_lecturers=selected_lecturers,
        filtered_courses=filtered_courses,
        other_courses=other_courses,
        all_courses=all_courses,
        enrolled_course_ids=enrolled_course_ids
    )

@app.route('/enroll', methods=['POST'])
def enroll():
    if not require_login() or session.get('role') != 'student':
        return redirect(url_for('login'))
    course_id = int(request.form['course_id'])
    student = Student.query.filter_by(student_id=session['username']).first()
    if not student:
        flash('Không tìm thấy sinh viên')
        return redirect(url_for('courses'))
    exist = Enrollment.query.filter_by(student_id=student.id, course_id=course_id).first()
    if exist:
        flash('Bạn đã đăng ký môn học này')
    else:
        enrollment = Enrollment(student_id=student.id, course_id=course_id)
        db.session.add(enrollment)
        db.session.commit()
        flash('Đăng ký môn học thành công')
    return redirect(url_for('courses'))

@app.route('/unenroll', methods=['POST'])
def unenroll():
    if not require_login() or session.get('role') != 'student':
        return redirect(url_for('login'))
    course_id = int(request.form['course_id'])
    student = Student.query.filter_by(student_id=session['username']).first()
    enrollment = Enrollment.query.filter_by(student_id=student.id, course_id=course_id).first()
    if enrollment:
        db.session.delete(enrollment)
        db.session.commit()
        flash('Hủy đăng ký thành công')
    else:
        flash('Bạn chưa đăng ký môn này')
    return redirect(url_for('courses'))

@app.route('/my_courses')
def my_courses():
    if not require_login() or session.get('role') != 'student':
        return redirect(url_for('login'))
    student = Student.query.filter_by(student_id=session['username']).first()
    enrollments = Enrollment.query.filter_by(student_id=student.id).all()
    courses = [Course.query.get(e.course_id) for e in enrollments]
    return render_template('my_courses.html', courses=courses)

@app.route('/grades', methods=['GET','POST'])
def grades():
    if not require_login():
        return redirect(url_for('login'))
    role = session.get('role')
    username = session.get('username')
    if role == 'student':
        student = Student.query.filter_by(student_id=username).first()
        if student:
            grades = db.session.query(Grade, Course)\
                .join(Course, Grade.course_id == Course.id)\
                .filter(Grade.student_id == student.id, Grade.status == 'confirmed')\
                .all()
            formatted_grades = []
            for grade, course in grades:
                grade.course = course
                formatted_grades.append(grade)
            return render_template('grades.html', 
                                grades=formatted_grades,
                                role=role,
                                student=student)
        return redirect(url_for('dashboard'))
    courses = []
    if role == 'lecturer':
        courses = Course.query.filter_by(lecturer=username).all()
    elif role == 'admin':
        courses = Course.query.all()
    students = Student.query.all()
    if request.method == 'POST':
        if role == 'lecturer':
            student_id = int(request.form['student_id'])
            course_id = int(request.form['course_id'])
            course = Course.query.get(course_id)
            if course and course.lecturer == username:
                value = float(request.form['grade'])
                g = Grade(
                    student_id=student_id,
                    course_id=course_id,
                    value=value,
                    status='pending',
                    submitted_by=username,
                    submitted_at=db.func.current_timestamp()
                )
                db.session.add(g)
                db.session.commit()
                flash('Điểm đã được nhập và đang chờ xác nhận từ Admin')
            else:
                flash('Bạn không có quyền nhập điểm cho môn học này')
        elif role == 'admin' and 'confirm_grade' in request.form:
            grade_id = int(request.form['grade_id'])
            grade = Grade.query.get(grade_id)
            if grade and grade.status == 'pending':
                grade.status = 'confirmed'
                grade.confirmed_by = username
                grade.confirmed_at = db.func.current_timestamp()
                db.session.commit()
                flash('Đã xác nhận điểm')
            else:
                flash('Không thể xác nhận điểm này')
        return redirect(url_for('grades'))
    if role == 'lecturer':
        course_ids = [c.id for c in courses]
        grades = db.session.query(Grade, Student, Course)\
            .join(Student, Grade.student_id == Student.id)\
            .join(Course, Grade.course_id == Course.id)\
            .filter(Grade.course_id.in_(course_ids))\
            .all()
    else:
        grades = db.session.query(Grade, Student, Course)\
            .join(Student, Grade.student_id == Student.id)\
            .join(Course, Grade.course_id == Course.id)\
            .all()
    formatted_grades = []
    for grade, student, course in grades:
        grade.student = student
        grade.course = course
        formatted_grades.append(grade)
    return render_template('grades.html',
                         grades=formatted_grades,
                         students=students,
                         courses=courses,
                         role=role,
                         username=username)

@app.route('/payments', methods=['GET', 'POST'])
def payments():
    if not require_login(): 
        return redirect(url_for('login'))

    role = session.get('role')

    # --- Khi admin thêm phiếu mới ---
    if request.method == 'POST' and role == 'admin':
        student_id = int(request.form['student_id'])
        amount = float(request.form['amount'])
        status = request.form['status']

        payment = Payment(student_id=student_id, amount=amount, status=status)
        db.session.add(payment)
        db.session.commit()
        flash("Đã thêm khoản thanh toán mới", "success")

    # --- Khi sinh viên xác nhận đã nộp ---
    if request.args.get('action') == 'confirm' and role == 'student':
        payment_id = int(request.args.get('id'))
        payment = Payment.query.get(payment_id)
        if payment and payment.status == 'pending':
            payment.status = 'paid'
            db.session.commit()
            flash("Xác nhận đã nộp tiền thành công!", "success")
        else:
            flash("Phiếu không hợp lệ hoặc đã xác nhận trước đó.", "warning")

    # --- Dữ liệu hiển thị ---
    payments = Payment.query.all()
    students = Student.query.all()

    # --- Thống kê ---
    total_paid = db.session.query(db.func.sum(Payment.amount)).filter(Payment.status == "paid").scalar() or 0
    total_pending = db.session.query(db.func.sum(Payment.amount)).filter(Payment.status == "pending").scalar() or 0
    total_withdrawn = db.session.query(db.func.sum(Payment.amount)).filter(Payment.status == "withdrawn").scalar() or 0
    total_free = db.session.query(db.func.sum(Payment.amount)).filter(Payment.status == "free").scalar() or 0

    data = {
        "khoan_phai_nop": total_pending,
        "khoan_duoc_mien": total_free,
        "khoan_da_nop": total_paid,
        "khoan_da_rut": total_withdrawn,
        "tong_no_chung": total_pending - total_paid,
        "tong_du_chung": total_paid - total_withdrawn,
        "phieu_da_thu": total_paid,
        "phieu_da_rut": total_withdrawn,
        "phieu_hoa_don": 0
    }

    return render_template(
        'payments.html',
        payments=payments,
        students=students,
        data=data,
        role=role
    )

@app.route('/news', methods=['GET','POST'])
def news():
    if not require_login(): return redirect(url_for('login'))
    if request.method == 'POST':
        n = News(title=request.form['title'], content=request.form['content'])
        db.session.add(n); db.session.commit()
    items = News.query.order_by(News.id.desc()).all()
    return render_template('news.html', items=items)

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)
