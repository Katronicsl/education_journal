from flask import Blueprint, render_template, request, redirect, url_for, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import db
from app.models.user import User
from app.utils.decorators import role_required
from app.utils.helpers import format_excel_width
from app.models.course import University, Course, StudentGroup
from app.models.subject import TeacherSubjectGroup, Subject, GradingSystem
from app.models.lesson import Lesson, Grade, Attendance
from app.utils.helpers import get_passing_grade
from flask import abort
from io import BytesIO
from datetime import datetime
import pandas as pd
import re
from app.models import db

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def build_group_overview_data(group_id):
    group = StudentGroup.query.get_or_404(group_id)
    assignments = TeacherSubjectGroup.query.filter_by(group_id=group_id).all()
    subject_ids = list({a.subject_id for a in assignments})
    subjects = Subject.query.filter(Subject.id.in_(subject_ids)).all() if subject_ids else []
    students = User.query.filter_by(group_id=group_id, role='student').order_by(User.last_name, User.first_name).all()
    data = []

    for student in students:
        row = {
            'student_id': student.id,
            'name': f"{student.last_name} {student.first_name}",
            'subjects': {},
            'overall': None
        }
        totals = []

        for subj in subjects:
            raw = db.session.query(Grade.value, GradingSystem.max_points) \
                .join(TeacherSubjectGroup, Grade.teacher_subject_group_id == TeacherSubjectGroup.id) \
                .outerjoin(GradingSystem, GradingSystem.teacher_subject_group_id == TeacherSubjectGroup.id) \
                .filter(Grade.student_id == student.id) \
                .filter(TeacherSubjectGroup.subject_id == subj.id) \
                .all()

            vals = []
            for val, max_p in raw:
                if val is None:
                    continue
                current_max = max_p if max_p else (5.0 if (val <= 5.0 and val > 0) else 100.0)
                if current_max <= 0:
                    current_max = 100
                vals.append((val / current_max) * 5.0)

            avg = round(sum(vals) / len(vals), 2) if vals else None
            if avg is not None:
                totals.append(avg)

            row['subjects'][subj.id] = avg

        row['overall'] = round(sum(totals) / len(totals), 2) if totals else None
        data.append(row)

    return group, subjects, students, data

@admin_bp.route('/dashboard')
@jwt_required(locations=["cookies"])
def dashboard():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user or user.role != 'admin':
        from flask import abort
        abort(403)
    return redirect(url_for('admin.pending_teachers'))

@admin_bp.route('/pending_teachers', strict_slashes=False)
@role_required('admin')
def pending_teachers():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    
    teachers = User.query.filter_by(role='teacher_pending').all()
    
    user_data = {
        'last_name': user.last_name,
        'first_name': user.first_name,
        'middle_name': user.middle_name or '',
        'avatar': f'avatars/{user.avatar}' if user.avatar else 'avatar.png'
    }
    
    return render_template('pending_teachers.html', teachers=teachers, user=user_data)

@admin_bp.route('/approve_teacher/<int:user_id>', methods=['POST'])
@role_required('admin')
def approve_teacher(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == 'teacher_pending':
        user.role = 'teacher'
        db.session.commit()
    return redirect(url_for('admin.pending_teachers'))

@admin_bp.route('/reject_teacher/<int:user_id>', methods=['POST'])
@role_required('admin')
def reject_teacher(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == 'teacher_pending':
        db.session.delete(user)
        db.session.commit()
    return redirect(url_for('admin.pending_teachers'))

@admin_bp.route('/change_login', methods=['GET', 'POST'])
@role_required('admin')
def change_login():
    from flask import flash
    identity = get_jwt_identity()
    user = User.query.get(identity['id'])
    message = ''
    error = False

    if not user.can_change_login:
        message = 'You cannot change login'
        error = True

    if request.method == 'POST':
        pass

    return render_template('change_login.html', message=message, error=error)

@admin_bp.route('/init_db')
def init_db():
    """Initialize database"""
    db.create_all()
    return "Database initialized"


@admin_bp.route('/student_rating')
@role_required('admin')
def student_rating_page():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))

    rating_data = []

 
    subjects = db.session.query(Subject).all()

    for subj in subjects:
        raw_grades = db.session.query(
            User,
            StudentGroup.name,
            Grade.value,
            GradingSystem.max_points
        ).join(Grade, Grade.student_id == User.id) \
         .join(TeacherSubjectGroup, Grade.teacher_subject_group_id == TeacherSubjectGroup.id) \
         .join(StudentGroup, User.group_id == StudentGroup.id) \
         .outerjoin(GradingSystem, GradingSystem.teacher_subject_group_id == TeacherSubjectGroup.id) \
         .filter(TeacherSubjectGroup.subject_id == subj.id) \
         .filter(User.role == 'student')\
         .all()

        students_map = {}

        for student_obj, group_name, val, max_p in raw_grades:
            if val is None:
                continue

            if max_p:
                current_max = max_p
            else:
                current_max = 5.0 if (val <= 5.0 and val > 0) else 100.0

            if current_max <= 0:
                current_max = 100

            normalized_score = (val / current_max) * 5.0

            if student_obj.id not in students_map:
                students_map[student_obj.id] = {
                    'name': f"{student_obj.last_name} {student_obj.first_name}",
                    'avatar': f'avatars/{student_obj.avatar}' if student_obj.avatar else 'avatar.png',
                    'group_name': group_name,
                    'scores': []
                }

            students_map[student_obj.id]['scores'].append(normalized_score)

        students_list = []
        for s_data in students_map.values():
            scores = s_data['scores']
            if not scores:
                continue

            avg_5_scale = sum(scores) / len(scores)

            students_list.append({
                'name': s_data['name'],
                'avatar': s_data['avatar'],
                'group_name': s_data['group_name'],
                'average': round(avg_5_scale, 2)
            })

        students_list.sort(key=lambda x: x['average'], reverse=True)

        current_rank = 1
        for i in range(len(students_list)):
            if i > 0 and students_list[i]['average'] < students_list[i-1]['average']:
                current_rank += 1
            students_list[i]['rank'] = current_rank


        rating_data.append({
            'subject_id': subj.id,
            'subject_name': subj.name,
            'students': students_list
        })


    user.avatar = f'avatars/{user.avatar}' if user.avatar else 'avatar.png'

    return render_template('admin_student_rating.html', user=user, rating_data=rating_data)


@admin_bp.route('/subject/<int:subject_id>')
@role_required('admin')
def subject_groups(subject_id):
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    subject = Subject.query.get_or_404(subject_id)

    assignments = TeacherSubjectGroup.query.filter_by(subject_id=subject_id).all()

    groups_data = []
    for assignment in assignments:
        group = assignment.group
        groups_data.append({
            'group_id': group.id,
            'group_name': group.name,
            'course_name': group.course.name,
            'university_name': group.course.university.name,
            'students_count': len(group.students)
        })

    user.avatar = f'avatars/{user.avatar}' if user.avatar else 'avatar.png'

    return render_template('admin_subject_groups.html', user=user, subject=subject, groups=groups_data)


@admin_bp.route('/groups')
@role_required('admin')
def groups_list():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))

    groups = StudentGroup.query.order_by(StudentGroup.name).all()
    groups_data = []
    for g in groups:
        groups_data.append({
            'id': g.id,
            'name': g.name,
            'course_name': g.course.name if g.course else '',
            'university_name': g.course.university.name if g.course and g.course.university else '',
            'students_count': len(g.students)
        })


    user.avatar = f'avatars/{user.avatar}' if user.avatar else 'avatar.png'

    return render_template('admin_groups.html', user=user, groups=groups_data)


def normalize_course_name(name):
    normalized = re.sub(r'\s+', ' ', name.strip())
    if not normalized:
        return normalized
    if normalized.isdigit():
        return f"{normalized} курс"
    match = re.fullmatch(r'(\d+)\s*курс', normalized, flags=re.I)
    if match:
        return f"{match.group(1)} курс"
    return normalized


@admin_bp.route('/structure', methods=['GET', 'POST'])
@role_required('admin')
def structure_management():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    message = request.args.get('message', '')
    error = request.args.get('error', '0') == '1'

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add_university':
            university_name = request.form.get('university_name', '').strip()
            if not university_name:
                message = 'Введите название университета.'
                error = True
            elif University.query.filter_by(name=university_name).first():
                message = 'Университет с таким названием уже существует.'
                error = True
            else:
                db.session.add(University(name=university_name))
                db.session.commit()
                message = 'Университет успешно добавлен.'

        elif action == 'add_course':
            university_id = request.form.get('university_id')
            course_name = normalize_course_name(request.form.get('course_name', ''))
            university = University.query.get(university_id)
            if not university or not course_name:
                message = 'Выберите университет и введите название курса.'
                error = True
            elif Course.query.filter_by(name=course_name, university_id=university.id).first():
                message = 'Курс с таким названием уже существует для выбранного университета.'
                error = True
            else:
                db.session.add(Course(name=course_name, university=university))
                db.session.commit()
                message = 'Курс успешно добавлен.'

        elif action == 'add_group':
            course_id = request.form.get('course_id')
            group_name = request.form.get('group_name', '').strip()
            course = Course.query.get(course_id)
            if not course or not group_name:
                message = 'Выберите курс и введите название группы.'
                error = True
            elif StudentGroup.query.filter_by(name=group_name, course_id=course.id).first():
                message = 'Группа с таким названием уже существует для выбранного курса.'
                error = True
            else:
                db.session.add(StudentGroup(name=group_name, course=course))
                db.session.commit()
                message = 'Группа успешно добавлена.'

    universities = University.query.order_by(University.name).all()
    courses = Course.query.order_by(Course.name).all()
    return render_template('admin_structure.html', user=user, universities=universities, courses=courses, message=message, error=error)


@admin_bp.route('/universities')
@role_required('admin')
def universities_management():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    universities = University.query.order_by(University.name).all()
    message = request.args.get('message', '')
    error = request.args.get('error', '0') == '1'
    user.avatar = f'avatars/{user.avatar}' if user.avatar else 'avatar.png'
    return render_template('admin_universities.html', user=user, universities=universities, message=message, error=error)


@admin_bp.route('/university/<int:university_id>/edit')
@role_required('admin')
def edit_university_page(university_id):
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    university = University.query.get_or_404(university_id)
    message = request.args.get('message', '')
    error = request.args.get('error', '0') == '1'
    user.avatar = f'avatars/{user.avatar}' if user.avatar else 'avatar.png'
    return render_template('admin_university_edit.html', user=user, university=university, message=message, error=error)


@admin_bp.route('/course/<int:course_id>/edit')
@role_required('admin')
def edit_course_page(course_id):
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    course = Course.query.get_or_404(course_id)
    message = request.args.get('message', '')
    error = request.args.get('error', '0') == '1'
    user.avatar = f'avatars/{user.avatar}' if user.avatar else 'avatar.png'
    return render_template('admin_course_edit.html', user=user, course=course, message=message, error=error)


@admin_bp.route('/group/<int:group_id>/edit')
@role_required('admin')
def edit_group_page(group_id):
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    group = StudentGroup.query.get_or_404(group_id)
    students = User.query.filter_by(group_id=group.id, role='student').order_by(User.last_name, User.first_name).all()
    message = request.args.get('message', '')
    error = request.args.get('error', '0') == '1'
    user.avatar = f'avatars/{user.avatar}' if user.avatar else 'avatar.png'
    return render_template('admin_group_edit.html', user=user, group=group, students=students, message=message, error=error)


@admin_bp.route('/student/<int:student_id>/edit')
@role_required('admin')
def edit_student_page(student_id):
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    student = User.query.get_or_404(student_id)
    if student.role != 'student':
        return redirect(url_for('admin.groups_list'))
    universities = University.query.order_by(University.name).all()
    courses = Course.query.order_by(Course.name).all()
    groups = StudentGroup.query.order_by(StudentGroup.name).all()
    message = request.args.get('message', '')
    error = request.args.get('error', '0') == '1'
    user.avatar = f'avatars/{user.avatar}' if user.avatar else 'avatar.png'
    return render_template(
        'admin_student_edit.html',
        user=user,
        student=student,
        universities=universities,
        courses=courses,
        groups=groups,
        message=message,
        error=error
    )


@admin_bp.route('/delete_university/<int:university_id>', methods=['POST'])
@role_required('admin')
def delete_university(university_id):
    university = University.query.get_or_404(university_id)
    if university.courses:
        return redirect(url_for('admin.structure_management', message='Сначала удалите все курсы этого университета.', error=1))
    db.session.delete(university)
    db.session.commit()
    return redirect(url_for('admin.structure_management', message='Университет удалён.', error=0))


@admin_bp.route('/edit_university/<int:university_id>', methods=['POST'])
@role_required('admin')
def edit_university(university_id):
    university = University.query.get_or_404(university_id)
    new_name = request.form.get('name', '').strip()
    if not new_name:
        return redirect(url_for('admin.edit_university_page', university_id=university.id, message='Введите название университета.', error=1))
    existing = University.query.filter(University.name == new_name, University.id != university.id).first()
    if existing:
        return redirect(url_for('admin.edit_university_page', university_id=university.id, message='Университет с таким названием уже существует.', error=1))
    university.name = new_name
    db.session.commit()
    return redirect(url_for('admin.edit_university_page', university_id=university.id, message='Название университета обновлено.', error=0))


@admin_bp.route('/edit_course/<int:course_id>', methods=['POST'])
@role_required('admin')
def edit_course(course_id):
    course = Course.query.get_or_404(course_id)
    new_name = normalize_course_name(request.form.get('name', ''))
    if not new_name:
        return redirect(url_for('admin.edit_course_page', course_id=course.id, message='Введите название курса.', error=1))
    existing = Course.query.filter(
        Course.name == new_name,
        Course.university_id == course.university_id,
        Course.id != course.id
    ).first()
    if existing:
        return redirect(url_for('admin.edit_course_page', course_id=course.id, message='Курс с таким названием уже есть в этом университете.', error=1))
    course.name = new_name
    db.session.commit()
    return redirect(url_for('admin.edit_course_page', course_id=course.id, message='Курс обновлен.', error=0))


@admin_bp.route('/delete_course/<int:course_id>', methods=['POST'])
@role_required('admin')
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    university_id = course.university_id
    if course.groups:
        return redirect(url_for('admin.edit_university_page', university_id=university_id, message='Сначала удалите все группы этого курса.', error=1))
    db.session.delete(course)
    db.session.commit()
    return redirect(url_for('admin.edit_university_page', university_id=university_id, message='Курс удален.', error=0))


@admin_bp.route('/edit_group/<int:group_id>', methods=['POST'])
@role_required('admin')
def edit_group(group_id):
    group = StudentGroup.query.get_or_404(group_id)
    new_name = request.form.get('name', '').strip()
    if not new_name:
        return redirect(url_for('admin.edit_group_page', group_id=group.id, message='Введите название группы.', error=1))
    existing = StudentGroup.query.filter(
        StudentGroup.name == new_name,
        StudentGroup.course_id == group.course_id,
        StudentGroup.id != group.id
    ).first()
    if existing:
        return redirect(url_for('admin.edit_group_page', group_id=group.id, message='Группа с таким названием уже есть на этом курсе.', error=1))
    group.name = new_name
    db.session.commit()
    return redirect(url_for('admin.edit_group_page', group_id=group.id, message='Группа обновлена.', error=0))


@admin_bp.route('/student/<int:student_id>/edit', methods=['POST'])
@role_required('admin')
def edit_student(student_id):
    student = User.query.get_or_404(student_id)
    if student.role != 'student':
        return redirect(url_for('admin.groups_list'))

    last_name = request.form.get('last_name', '').strip()
    first_name = request.form.get('first_name', '').strip()
    middle_name = request.form.get('middle_name', '').strip()
    email = request.form.get('email', '').lower().strip()
    university_id = request.form.get('university_id')
    course_id = request.form.get('course_id')
    group_id = request.form.get('group_id')

    if not all([last_name, first_name, email]):
        return redirect(url_for('admin.edit_student_page', student_id=student.id, message='Заполните фамилию, имя и email.', error=1))

    existing = User.query.filter(User.email == email, User.id != student.id).first()
    if existing:
        return redirect(url_for('admin.edit_student_page', student_id=student.id, message='Пользователь с таким email уже существует.', error=1))

    student.last_name = last_name
    student.first_name = first_name
    student.middle_name = middle_name
    student.email = email

    if (university_id or course_id) and not group_id:
        return redirect(url_for('admin.edit_student_page', student_id=student.id, message='Выберите группу или оставьте все поля обучения пустыми.', error=1))

    if group_id:
        group = StudentGroup.query.get(group_id)
        if not group:
            return redirect(url_for('admin.edit_student_page', student_id=student.id, message='Выбранная группа не найдена.', error=1))
        if course_id and str(group.course_id) != str(course_id):
            return redirect(url_for('admin.edit_student_page', student_id=student.id, message='Выбранная группа не относится к выбранному курсу.', error=1))
        if university_id and str(group.course.university_id) != str(university_id):
            return redirect(url_for('admin.edit_student_page', student_id=student.id, message='Выбранная группа не относится к выбранному университету.', error=1))
        student.group = group
        student.course = group.course
        student.university = group.course.university
    else:
        student.group = None
        student.course = None
        student.university = None

    db.session.commit()
    return redirect(url_for('admin.edit_student_page', student_id=student.id, message='Данные студента обновлены.', error=0))


@admin_bp.route('/delete_group/<int:group_id>', methods=['POST'])
@role_required('admin')
def delete_group(group_id):
    group = StudentGroup.query.get_or_404(group_id)
    course_id = group.course_id
    if group.students:
        return redirect(url_for('admin.edit_course_page', course_id=course_id, message='Сначала переведите или удалите студентов из группы.', error=1))
    if group.subject_assignments:
        return redirect(url_for('admin.edit_course_page', course_id=course_id, message='Сначала удалите назначенные предметы у группы.', error=1))
    db.session.delete(group)
    db.session.commit()
    return redirect(url_for('admin.edit_course_page', course_id=course_id, message='Группа удалена.', error=0))


@admin_bp.route('/delete_student/<int:student_id>', methods=['POST'])
@role_required('admin')
def delete_student(student_id):
    student = User.query.get_or_404(student_id)
    if student.role != 'student':
        return redirect(url_for('admin.groups_list'))

    group_id = student.group_id
    if student.grades or student.attendance:
        if group_id:
            return redirect(url_for('admin.edit_group_page', group_id=group_id, message='У студента есть оценки или посещаемость. Сначала удалите связанные данные.', error=1))
        return redirect(url_for('admin.groups_list'))

    db.session.delete(student)
    db.session.commit()

    if group_id:
        return redirect(url_for('admin.edit_group_page', group_id=group_id, message='Студент удален.', error=0))
    return redirect(url_for('admin.groups_list'))


@admin_bp.route('/teachers')
@role_required('admin')
def admin_teachers():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    teachers = User.query.filter_by(role='teacher').order_by(User.last_name, User.first_name).all()
    universities = University.query.order_by(University.name).all()
    message = request.args.get('message', '')
    error = request.args.get('error', '0') == '1'
    user.avatar = f'avatars/{user.avatar}' if user.avatar else 'avatar.png'
    return render_template('admin_teachers.html', user=user, teachers=teachers, universities=universities, message=message, error=error)


@admin_bp.route('/delete_teacher/<int:user_id>', methods=['POST'])
@role_required('admin')
def delete_teacher(user_id):
    teacher = User.query.get_or_404(user_id)
    if teacher.role != 'teacher':
        return redirect(url_for('admin.admin_teachers', message='Невозможно удалить этого пользователя.', error=1))
    if teacher.teaching_assignments:
        return redirect(url_for('admin.admin_teachers', message='Сначала удалите назначения преподавателя.', error=1))
    db.session.delete(teacher)
    db.session.commit()
    return redirect(url_for('admin.admin_teachers', message='Преподаватель удалён.', error=0))


@admin_bp.route('/teacher/<int:user_id>/universities', methods=['POST'])
@role_required('admin')
def update_teacher_universities(user_id):
    teacher = User.query.get_or_404(user_id)
    if teacher.role != 'teacher':
        return redirect(url_for('admin.admin_teachers', message='Невозможно изменить университеты этого пользователя.', error=1))
    university_ids = request.form.getlist('universities')
    if not university_ids:
        return redirect(url_for('admin.admin_teachers', message='Выберите хотя бы один университет для преподавателя.', error=1))
    universities = University.query.filter(University.id.in_(university_ids)).all()
    if not universities:
        return redirect(url_for('admin.admin_teachers', message='Выбранные университеты не найдены.', error=1))
    teacher.universities = universities
    db.session.commit()
    return redirect(url_for('admin.admin_teachers', message='Университеты преподавателя обновлены.', error=0))


@admin_bp.route('/group/<int:group_id>/assign_subject', methods=['GET', 'POST'])
@role_required('admin')
def assign_subject_to_group(group_id):
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    group = StudentGroup.query.get_or_404(group_id)
    teachers = User.query.filter_by(role='teacher').order_by(User.last_name, User.first_name).all()
    subjects = Subject.query.order_by(Subject.name).all()
    message = ''
    error = False

    if request.method == 'POST':
        subject_id = request.form.get('subject_id')
        new_subject_name = request.form.get('new_subject_name', '').strip()
        teacher_id = request.form.get('teacher_id')

        if not teacher_id:
            message = 'Выберите преподавателя.'
            error = True
        else:
            teacher = User.query.filter_by(id=teacher_id, role='teacher').first()
            if not teacher:
                message = 'Выбран неверный преподаватель.'
                error = True

        subject = None
        if not error:
            if new_subject_name:
                subject = Subject.query.filter_by(name=new_subject_name).first()
                if not subject:
                    subject = Subject(name=new_subject_name)
                    db.session.add(subject)
                    db.session.flush()
            elif subject_id:
                subject = Subject.query.get(subject_id)

            if not subject:
                message = 'Выберите существующий предмет или введите новое название предмета.'
                error = True

        if not error:
            assignment = TeacherSubjectGroup.query.filter_by(group_id=group.id, subject_id=subject.id).first()
            if assignment:
                assignment.teacher_id = teacher.id
                message = f'Преподаватель для предмета "{subject.name}" в группе "{group.name}" обновлён.'
            else:
                assignment = TeacherSubjectGroup(teacher=teacher, subject=subject, group=group)
                db.session.add(assignment)
                teacher_name = f"{teacher.last_name} {teacher.first_name} {teacher.middle_name or ''}".strip()
                message = f'Предмет "{subject.name}" назначен группе "{group.name}" и закреплён за преподавателем {teacher_name}.'
            db.session.commit()

    return render_template('admin_assign_subject.html', user=user, group=group, teachers=teachers, subjects=subjects, message=message, error=error)


@admin_bp.route('/group/<int:group_id>')
@role_required('admin')
def group_subjects(group_id):
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))

    group = StudentGroup.query.get_or_404(group_id)
    assignments = TeacherSubjectGroup.query.filter_by(group_id=group_id).all()

    subjects = []
    for a in assignments:
        subjects.append({
            'assignment_id': a.id,
            'subject_id': a.subject.id,
            'subject_name': a.subject.name,
            'teacher_name': f"{a.teacher.last_name} {a.teacher.first_name} {a.teacher.middle_name or ''}".strip() if getattr(a, 'teacher', None) else ''
        })

    user.avatar = f'avatars/{user.avatar}' if user.avatar else 'avatar.png'

    return render_template('admin_group_subjects.html', user=user, group=group, subjects=subjects)


@admin_bp.route('/group/<int:group_id>/delete_assignment/<int:assignment_id>', methods=['POST'])
@role_required('admin')
def delete_group_subject(group_id, assignment_id):
    assignment = TeacherSubjectGroup.query.filter_by(id=assignment_id, group_id=group_id).first_or_404()
    if assignment.grades or getattr(assignment, 'grading_system', None):
        return redirect(url_for('admin.group_subjects', group_id=group_id))
    db.session.delete(assignment)
    db.session.commit()
    return redirect(url_for('admin.group_subjects', group_id=group_id))


@admin_bp.route('/group/<int:group_id>/overview')
@role_required('admin')
def group_overview(group_id):
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))

    group, subjects, students, data = build_group_overview_data(group_id)
    all_groups = StudentGroup.query.order_by(StudentGroup.name).all()
    available_students = User.query.filter(
        User.role == 'student',
        db.or_(User.group_id != group_id, User.group_id.is_(None))
    ).order_by(User.last_name, User.first_name).all()
    message = request.args.get('message', '')
    error = request.args.get('error', '0') == '1'

    user.avatar = f'avatars/{user.avatar}' if user.avatar else 'avatar.png'

    return render_template(
        'admin_group_overview.html',
        user=user,
        group=group,
        subjects=subjects,
        data=data,
        students=students,
        all_groups=all_groups,
        available_students=available_students,
        message=message,
        error=error
    )


@admin_bp.route('/group/<int:group_id>/overview/export')
@role_required('admin')
def export_group_overview_excel(group_id):
    group, subjects, students, data = build_group_overview_data(group_id)

    rows = []
    for row in data:
        export_row = {'Студент': row['name']}
        for subject in subjects:
            value = row['subjects'].get(subject.id)
            export_row[subject.name] = value if value is not None else '-'
        export_row['Итог'] = row['overall'] if row['overall'] is not None else '-'
        rows.append(export_row)

    df = pd.DataFrame(rows)
    if df.empty:
        columns = ['Студент'] + [subject.name for subject in subjects] + ['Итог']
        df = pd.DataFrame(columns=columns)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Обзор группы', index=False)
        format_excel_width(writer)

    output.seek(0)
    safe_group_name = re.sub(r'[\\/:*?"<>|]+', '_', group.name).strip() or 'group'
    filename = f"Group_{safe_group_name}_{datetime.now().strftime('%d.%m.%Y')}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True)


@admin_bp.route('/group/<int:group_id>/student/<int:student_id>/move', methods=['POST'])
@role_required('admin')
def move_student(group_id, student_id):
    student = User.query.get_or_404(student_id)
    if student.role != 'student':
        return redirect(url_for('admin.group_overview', group_id=group_id, message='Можно переносить только студентов.', error=1))
    new_group_id = request.form.get('group_id')
    new_group = StudentGroup.query.get(new_group_id)
    if not new_group:
        return redirect(url_for('admin.group_overview', group_id=group_id, message='Выберите группу для перевода.', error=1))
    student.group = new_group
    student.course = new_group.course
    student.university = new_group.course.university
    db.session.commit()
    return redirect(url_for('admin.group_overview', group_id=group_id, message='Студент переведен в другую группу.', error=0))


@admin_bp.route('/group/<int:group_id>/student/<int:student_id>/remove', methods=['POST'])
@role_required('admin')
def remove_student_from_group(group_id, student_id):
    student = User.query.get_or_404(student_id)
    if student.role != 'student' or student.group_id != group_id:
        return redirect(url_for('admin.group_overview', group_id=group_id, message='Студент не найден в этой группе.', error=1))
    student.group = None
    student.course = None
    student.university = None
    db.session.commit()
    return redirect(url_for('admin.group_overview', group_id=group_id, message='Студент удален из группы.', error=0))


@admin_bp.route('/group/<int:group_id>/student/add', methods=['POST'])
@role_required('admin')
def add_student_to_group(group_id):
    group = StudentGroup.query.get_or_404(group_id)
    student_id = request.form.get('student_id')
    student = User.query.filter_by(id=student_id, role='student').first()
    if not student:
        return redirect(url_for('admin.group_overview', group_id=group_id, message='Выберите студента.', error=1))
    student.group = group
    student.course = group.course
    student.university = group.course.university
    db.session.commit()
    return redirect(url_for('admin.group_overview', group_id=group_id, message='Студент добавлен в группу.', error=0))

@admin_bp.route('/group/<int:group_id>/subject/<int:subject_id>')
@jwt_required(locations=["cookies"])
def group_management(subject_id, group_id):
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))

    assignment = TeacherSubjectGroup.query.filter_by(subject_id=subject_id, group_id=group_id).first_or_404()

    subject = Subject.query.get_or_404(subject_id)
    group = StudentGroup.query.get_or_404(group_id)
    teacher = User.query.get_or_404(assignment.teacher_id)

    lessons = Lesson.query.filter_by(teacher_subject_group_id=assignment.id).order_by(Lesson.date.desc()).all()

    students_data = []
    for student in group.students:
        student_data = {
            'id': student.id,
            'last_name': student.last_name,
            'first_name': student.first_name,
            'middle_name': student.middle_name or ''
        }
        students_data.append(student_data)

    user.avatar = f'avatars/{user.avatar}' if user.avatar else 'avatar.png'

    return render_template('admin_group_management.html', user=user, subject=subject, group=group, teacher=teacher, students_data=students_data, lessons=lessons, assignment_id=assignment.id)



@admin_bp.route('/api/get_lessons_data')
@jwt_required(locations=["cookies"])
def api_get_lessons_data():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    
    if not user or user.role != 'admin':
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    assignment_id = request.args.get('assignment_id')
    data_type = request.args.get('data_type', None)
    
    print(f"\n=== DEBUG: api_get_lessons_data called with assignment_id={assignment_id}, data_type={data_type} ===")
    
    assignment = TeacherSubjectGroup.query.filter_by(id=int(assignment_id)).first()
    if not assignment:
        print(f"ERROR: Assignment {assignment_id} not found")
        return jsonify({'error': 'Assignment not found'}), 404
    
    if data_type:
        lessons = Lesson.query.filter_by(
            teacher_subject_group_id=assignment_id,
            data_type=data_type
        ).order_by(Lesson.date).all()
        print(f"DEBUG: Found {len(lessons)} lessons with data_type={data_type}")
    else:
        lessons = Lesson.query.filter_by(
            teacher_subject_group_id=assignment_id
        ).order_by(Lesson.date).all()
        print(f"DEBUG: Found {len(lessons)} total lessons")
    
    for l in lessons:
        print(f"  - ID: {l.id}, Column: {l.lesson_column_id}, Type: {l.data_type}, Date: {l.date}")
    
    lessons_data = [{
        'lesson_column_id': lesson.lesson_column_id,
        'lesson_id': lesson.id,
        'date': lesson.date.strftime('%d.%m.%Y'),
        'topic': lesson.topic,
        'is_important': lesson.is_important,
        'data_type': lesson.data_type  
    } for lesson in lessons]
    
    print(f"DEBUG: Returning {len(lessons_data)} lessons")
    print(f"=== END DEBUG ===\n")
    return jsonify(lessons_data)


@admin_bp.route('/api/get_all_grades')
@jwt_required(locations=["cookies"])
def api_get_all_grades():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    
    if not user or user.role != 'admin':
        return jsonify({'error': 'Доступ запрещен'}), 403

    assignment_id = request.args.get('assignment_id')
    assignment = TeacherSubjectGroup.query.get(int(assignment_id))

    if not assignment:
        return jsonify({'error': 'Assignment not found'}), 404

    grades = Grade.query.filter_by(teacher_subject_group_id=assignment_id).all()

    grades_data = []
    for g in grades:
        disp = getattr(g, 'display_value', None)
        if not disp:
            if g.value is not None:
                disp = str(int(g.value)) if g.value.is_integer() else str(g.value)
            else:
                disp = ""

        grades_data.append({
            'student_id': g.student_id,
            'value': g.value,
            'display_value': disp,
            'lesson_column_id': getattr(g, 'lesson_column_id', '')
        })
    return jsonify(grades_data)


@admin_bp.route('/api/get_attendance_data')
@jwt_required(locations=["cookies"])
def api_get_attendance_data():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    
    if not user or user.role != 'admin':
        return jsonify({'error': 'Доступ запрещен'}), 403

    assignment_id = request.args.get('assignment_id')
    print(f"\n=== DEBUG: api_get_attendance_data called with assignment_id={assignment_id} ===")
    
    assignment = TeacherSubjectGroup.query.get(int(assignment_id))

    if not assignment:
        print(f"ERROR: Assignment {assignment_id} not found")
        return jsonify({'error': 'Assignment not found'}), 404

    lessons = Lesson.query.filter_by(teacher_subject_group_id=assignment_id).all()
    lesson_ids = [l.id for l in lessons]
    
    print(f"DEBUG: Found {len(lessons)} total lessons for assignment {assignment_id}")
    for l in lessons:
        print(f"  - Lesson ID: {l.id}, Column ID: {l.lesson_column_id}, Data Type: {l.data_type}, Date: {l.date}")

    if not lesson_ids:
        print(f"WARNING: No lessons found for assignment {assignment_id}")
        return jsonify([])

    total_attendance = Attendance.query.count()
    print(f"DEBUG: Total attendance records in database: {total_attendance}")
    
    records = Attendance.query.filter(Attendance.lesson_id.in_(lesson_ids)).all()
    print(f"DEBUG: Found {len(records)} attendance records for these lessons")
    
    for r in records:
        print(f"  - Student ID: {r.student_id}, Lesson ID: {r.lesson_id}, Status: {r.status}")
    
    lesson_map = {l.id: l.lesson_column_id for l in lessons}

    result = [{
        'student_id': r.student_id,
        'lesson_id': r.lesson_id,
        'lesson_column_id': lesson_map.get(r.lesson_id, ''),
        'status': r.status
    } for r in records]
    
    print(f"DEBUG: Returning {len(result)} attendance records")
    print(f"=== END DEBUG ===\n")
    return jsonify(result)


@admin_bp.route('/api/get_group_students')
@jwt_required(locations=["cookies"])
def api_get_group_students():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    
    if not user or user.role != 'admin':
        return jsonify({'error': 'Доступ запрещен'}), 403

    assignment_id = request.args.get('assignment_id')
    assignment = TeacherSubjectGroup.query.get(int(assignment_id))

    if not assignment:
        return jsonify({'error': 'Assignment not found'}), 404

    students = User.query.filter_by(group_id=assignment.group_id, role='student').order_by(User.last_name).all()

    return jsonify({
        'students': [{
            'id': s.id,
            'last_name': s.last_name,
            'first_name': s.first_name
        } for s in students]
    })


@admin_bp.route('/api/get_grading_system')
@jwt_required(locations=["cookies"])
def api_get_grading_system():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user or user.role != 'admin':
            return jsonify({'error': 'Доступ запрещен'}), 403

        assignment_id = request.args.get('assignment_id')
        if not assignment_id:
            return jsonify({
                'type': 'points',
                'maxPoints': 100,
                'minPoints': 0,
                'passingGrade': 60,
                'calculationMethod': 'average'
            })
            
        assignment = TeacherSubjectGroup.query.get(int(assignment_id))

        if not assignment:
            return jsonify({
                'type': 'points',
                'maxPoints': 100,
                'minPoints': 0,
                'passingGrade': 60,
                'calculationMethod': 'average'
            })

        grading_system = GradingSystem.query.filter_by(subject_id=assignment.subject_id).first()
        if not grading_system:
            return jsonify({
                'type': 'points',
                'maxPoints': 100,
                'minPoints': 0,
                'passingGrade': 60,
                'calculationMethod': 'average'
            })

        return jsonify({
            'type': grading_system.type,
            'maxPoints': grading_system.max_points,
            'minPoints': grading_system.min_points,
            'passingGrade': grading_system.passing_grade,
            'calculationMethod': getattr(grading_system, 'calculation_method', 'average')
        })
    except Exception as e:
        print(f"ERROR in api_get_grading_system: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'type': 'points',
            'maxPoints': 100,
            'minPoints': 0,
            'passingGrade': 60,
            'calculationMethod': 'average'
        })
