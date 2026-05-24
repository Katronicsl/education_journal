from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from flask_jwt_extended import create_access_token
from app.models import db
from app.models.user import User, bcrypt
from app.models.course import University, Course, StudentGroup
from app.utils.helpers import get_universities_data

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register/teacher', methods=['GET', 'POST'])
def register_teacher():
    universities = University.query.order_by(University.name).all()
    if request.method == 'GET':
        return render_template('register/teacher.html', universities=universities)

    data = request.form
    last_name = data.get('last_name', '').strip()
    first_name = data.get('first_name', '').strip()
    middle_name = data.get('middle_name', '').strip()
    email = data.get('email', '').lower()
    password = data.get('password', '')
    selected_univs_ids = data.getlist('universities')

    if not all([last_name, first_name, email, password]) or not selected_univs_ids:
        return render_template('register/teacher.html',
                             message="Заполните все обязательные поля и выберите университеты",
                             error=True, universities=universities)

    if User.query.filter_by(email=email).first():
        return render_template('register/teacher.html',
                             message="Пользователь с таким email уже есть",
                             error=True, universities=universities)

    pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    selected_univs = University.query.filter(University.id.in_(selected_univs_ids)).all()

    new_user = User(
        last_name=last_name,
        first_name=first_name,
        middle_name=middle_name,
        email=email,
        password_hash=pw_hash,
        role='teacher_pending',
        universities=selected_univs
    )
    db.session.add(new_user)
    db.session.commit()

    return render_template('register/teacher.html',
                         message="Регистрация прошла. Ожидайте подтверждения от администратора.",
                         error=False, universities=universities)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Student registration page"""
    univs_data = get_universities_data()

    if request.method == 'GET':
        return render_template('register/student.html', univs_data=univs_data)

    data = request.form
    last_name = data.get('last_name', '').strip()
    first_name = data.get('first_name', '').strip()
    middle_name = data.get('middle_name', '').strip()
    email = data.get('email', '').lower()
    password = data.get('password', '')
    university_name = data.get('university')
    course_name = data.get('course')
    group_name = data.get('group')

    if not all([last_name, first_name, email, password]):
        return render_template('register/student.html',
                             message="Заполните все обязательные поля",
                             error=True, univs_data=univs_data)

    if User.query.filter_by(email=email).first():
        return render_template('register/student.html',
                             message="Пользователь с таким email уже есть",
                             error=True, univs_data=univs_data)

    if not all([university_name, course_name, group_name]):
        return render_template('register/student.html',
                             message="Выберите университет, курс и группу",
                             error=True, univs_data=univs_data)

    university = University.query.filter_by(name=university_name).first()
    if not university:
        return render_template('register/student.html',
                             message="Выбран некорректный университет",
                             error=True, univs_data=univs_data)

    course = Course.query.filter_by(name=course_name, university_id=university.id).first()
    if not course:
        return render_template('register/student.html',
                             message="Выбран некорректный курс",
                             error=True, univs_data=univs_data)

    group = StudentGroup.query.filter_by(name=group_name, course_id=course.id).first()
    if not group:
        return render_template('register/student.html',
                             message="Выбран некорректная группа",
                             error=True, univs_data=univs_data)

    pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    new_user = User(
        last_name=last_name,
        first_name=first_name,
        middle_name=middle_name,
        email=email,
        password_hash=pw_hash,
        role='student',
        university=university,
        course=course,
        group=group
    )
    db.session.add(new_user)
    db.session.commit()

    access_token = create_access_token(identity=str(new_user.id))
    response = redirect(url_for('student.dashboard'))
    response.set_cookie('access_token_cookie', access_token)
    return response

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    email = request.form.get('email', '').lower().strip()
    password = request.form.get('password', '').strip()
    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return render_template('login.html', message="Неверный email или пароль", error=True)

    if user.role == 'teacher_pending':
        return render_template('login.html',
                               message="Ваш аккаунт преподавателя ожидает подтверждения администратора",
                               error=True)

    access_token = create_access_token(identity=str(user.id))
    response = None

    if user.role == 'student':
        response = redirect(url_for('student.dashboard'))
    elif user.role == 'teacher':
        response = redirect(url_for('teacher.dashboard'))
    elif user.role == 'admin':
        response = redirect(url_for('admin.dashboard'))
    else:
        response = redirect(url_for('main.profile'))

    response.set_cookie('access_token_cookie', access_token)
    return response

@auth_bp.route('/logout')
def logout():
    from flask import make_response
    response = make_response(redirect(url_for('auth.login')))
    response.delete_cookie('access_token_cookie', path='/')
    response.delete_cookie('refresh_token_cookie', path='/')
    response.delete_cookie('csrf_access_token', path='/')
    return response

















