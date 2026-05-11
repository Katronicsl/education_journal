from flask import Blueprint, render_template, request, jsonify, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import db
from app.models.user import User
from app.models.subject import TeacherSubjectGroup
from app.models.lesson import Lesson, Grade, Attendance
from datetime import datetime
from io import BytesIO
import pandas as pd

student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.route('/dashboard')
@jwt_required(locations=["cookies"])
def dashboard():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))

    if not user or user.role != 'student':
        abort(403)

    if not user.group:
        return render_template('index.html', message="You are not assigned to a group")

    group_assignments = TeacherSubjectGroup.query.filter_by(group_id=user.group.id).all()

    courses_data = []
    teachers_set = set()

    for assignment in group_assignments:
        teachers_set.add(assignment.teacher.id)
        grades = Grade.query.filter(
            Grade.teacher_subject_group_id == assignment.id,
            Grade.student_id == user.id
        ).all()
        
        # Calculate average grade for the subject
        valid_grades = [g.value for g in grades if g.value is not None]
        average_grade = round(sum(valid_grades) / len(valid_grades), 2) if valid_grades else 0
        
        courses_data.append({
            'assignment_id': assignment.id,
            'subject_name': assignment.subject.name,
            'teacher_name': f"{assignment.teacher.last_name} {assignment.teacher.first_name}",
            'group_name': assignment.group.name,
            'grades_count': len(grades),
            'average_grade': average_grade
        })

    excused_variants = ['УП', 'уп', 'Уп', 'YP', 'yp', 'Yp', 'excused', 'valid', 'Б', 'б', 'B', 'b']
    unexcused_variants = ['НП', 'нп', 'Нп', 'NP', 'np', 'Np', 'HP', 'hp', 'Н', 'н', 'H', 'h', 'N', 'n', '-', 'absent', 'missing']

    missed_excused = Attendance.query.filter(
        Attendance.student_id == user.id,
        Attendance.status.in_(excused_variants)
    ).count()

    missed_unexcused = Attendance.query.filter(
        Attendance.student_id == user.id,
        Attendance.status.in_(unexcused_variants)
    ).count()

    debt_grades = Grade.query.filter(
        Grade.student_id == user.id,
        Grade.value < 2.5,
        Grade.value != None
    ).count()

    stats = {
        'subjects_count': len(courses_data),
        'teachers_count': len(teachers_set),
        'missed_excused': missed_excused,
        'missed_unexcused': missed_unexcused,
        'debts_count': debt_grades
    }

    def get_student_rank(filter_criteria):
        all_students = User.query.filter_by(role='student', **filter_criteria).all()
        student_grades = {}
        for s in all_students:
            grades = Grade.query.filter_by(student_id=s.id).all()
            avg_grade = sum(g.value for g in grades if g.value) / len([g for g in grades if g.value]) if grades else 0
            student_grades[s.id] = avg_grade

        sorted_grades = sorted(student_grades.items(), key=lambda x: x[1], reverse=True)
        rank = next((i + 1 for i, (sid, _) in enumerate(sorted_grades) if sid == user.id), 0)
        return rank, len(sorted_grades)

    r_course_val, r_course_total = get_student_rank({'course_id': user.course_id})
    r_univ_val, r_univ_total = get_student_rank({'university_id': user.university_id})

    rankings = {
        'course': f"{r_course_val} / {r_course_total}",
        'univ': f"{r_univ_val} / {r_univ_total}"
    }

    # Format avatar path for template
    # Format avatar path for template
    user.avatar = f'avatars/{user.avatar}' if user.avatar else 'avatar.png'

    return render_template('prod/glav.html',
                         user=user,
                         courses=courses_data,
                         stats=stats,
                         rankings=rankings,
                         group=user.group)

@student_bp.route('/assignment/<int:assignment_id>')
@jwt_required(locations=["cookies"])
def view_assignment(assignment_id):
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))

    if not user or user.role != 'student':
        abort(403)

    assignment = TeacherSubjectGroup.query.get_or_404(assignment_id)

    if assignment.group_id != user.group_id:
        abort(403)

    # Format avatar path for template
    # Format avatar path for template
    user.avatar = f'avatars/{user.avatar}' if user.avatar else 'avatar.png'

    return render_template('student_grades.html',
                         user=user,
                         subject=assignment.subject,
                         group=assignment.group,
                         teacher=assignment.teacher,
                         assignment_id=assignment.id)

@student_bp.route('/rating')
@jwt_required(locations=["cookies"])
def rating():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))

    if not user or user.role != 'student':
        abort(403)

    def get_group_leaderboard(scope):
        from app.models.course import StudentGroup, Course
        from app.models.subject import GradingSystem
        
        groups_query = StudentGroup.query
        
        if scope == 'course':
            groups_query = groups_query.filter_by(course_id=user.course_id)
        elif scope == 'univ':
            groups_query = groups_query.join(Course).filter(Course.university_id == user.university_id)
            
        groups = groups_query.all()
        
        leaderboard = []

        for gr in groups:
            grades_data = db.session.query(
                Grade.value,
                GradingSystem.max_points
            ).join(TeacherSubjectGroup, Grade.teacher_subject_group_id == TeacherSubjectGroup.id)\
             .outerjoin(GradingSystem, GradingSystem.teacher_subject_group_id == TeacherSubjectGroup.id)\
             .filter(Grade.student_id.in_([s.id for s in gr.students]))\
             .all()

            total_normalized_score = 0
            count = 0

            for val, max_p in grades_data:
                if val is None: 
                    continue
                
                current_max = max_p if max_p else (5.0 if val <= 5.0 and val > 0 else 100.0)
                
                if current_max == 0: 
                    current_max = 100 

                normalized = (val / current_max) * 5.0
                
                total_normalized_score += normalized
                count += 1

            if count > 0:
                group_avg = round(total_normalized_score / count, 2)
            else:
                group_avg = 0.0

            if count > 0: 
                leaderboard.append({
                    'name': gr.name,
                    'course_name': gr.course.name,
                    'students_count': len(gr.students),
                    'average': group_avg,
                    'is_my_group': (gr.id == user.group_id)
                })

        leaderboard.sort(key=lambda x: x['average'], reverse=True)

        current_rank = 1
        for i in range(len(leaderboard)):
            if i > 0 and leaderboard[i]['average'] < leaderboard[i-1]['average']:
                current_rank += 1
            leaderboard[i]['rank'] = current_rank
            
        return leaderboard

    groups_course = get_group_leaderboard('course')
    groups_univ = get_group_leaderboard('univ')

    # Format avatar path for template
    # Format avatar path for template
    user.avatar = f'avatars/{user.avatar}' if user.avatar else 'avatar.png'

    return render_template('rating.html',
                         user=user,
                         groups_course=groups_course,
                         groups_univ=groups_univ)

@student_bp.route('/api/get_grades')
@jwt_required(locations=["cookies"])
def get_grades():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))

    if not user or user.role != 'student':
        return jsonify({'error': 'Forbidden'}), 403

    assignment_id = request.args.get('assignment_id')
    student_id = request.args.get('student_id')

    if int(student_id) != user.id:
        return jsonify({'error': 'Forbidden'}), 403

    grades = Grade.query.filter_by(
        teacher_subject_group_id=assignment_id,
        student_id=student_id
    ).all()

    grades_data = [{
        'id': grade.id,
        'value': grade.value,
        'display_value': grade.display_value,
        'lesson_column_id': grade.lesson_column_id
    } for grade in grades]

    return jsonify(grades_data)

@student_bp.route('/api/get_attendance')
@jwt_required(locations=["cookies"])
def get_attendance():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))

    if not user or user.role != 'student':
        return jsonify({'error': 'Forbidden'}), 403

    assignment_id = request.args.get('assignment_id')
    student_id = request.args.get('student_id')

    if int(student_id) != user.id:
        return jsonify({'error': 'Forbidden'}), 403

    lessons = Lesson.query.filter_by(
        teacher_subject_group_id=assignment_id,
        data_type='attendance'
    ).all()

    attendance_data = []
    for lesson in lessons:
        att = Attendance.query.filter_by(student_id=user.id, lesson_id=lesson.id).first()
        attendance_data.append({
            'lesson_column_id': lesson.lesson_column_id,
            'status': att.status if att else '',
            'date': lesson.date.strftime('%d.%m.%Y')
        })

    return jsonify(attendance_data)

@student_bp.route('/api/get_all_grades')
@jwt_required(locations=["cookies"])
def get_all_grades():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user or user.role != 'student':
        return jsonify({'error': 'Forbidden'}), 403

    assignment_id = request.args.get('assignment_id')
    assignment = TeacherSubjectGroup.query.get(assignment_id)

    if not assignment or assignment.group_id != user.group_id:
        return jsonify({'error': 'Forbidden'}), 403

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

@student_bp.route('/api/get_all_attendance')
@jwt_required(locations=["cookies"])
def get_all_attendance():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user or user.role != 'student':
        return jsonify({'error': 'Forbidden'}), 403

    assignment_id = request.args.get('assignment_id')
    assignment = TeacherSubjectGroup.query.get(assignment_id)

    if not assignment or assignment.group_id != user.group_id:
        return jsonify({'error': 'Forbidden'}), 403

    lessons = Lesson.query.filter_by(teacher_subject_group_id=assignment_id, data_type='attendance').all()
    lesson_ids = [l.id for l in lessons]

    if not lesson_ids:
        return jsonify([])

    records = Attendance.query.filter(Attendance.lesson_id.in_(lesson_ids)).all()

    return jsonify([{
        'student_id': r.student_id,
        'status': r.status,
        'lesson_column_id': r.lesson.lesson_column_id
    } for r in records])

@student_bp.route('/api/get_grading_system')
@jwt_required(locations=["cookies"])
def get_grading_system():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user or user.role != 'student':
        return jsonify({'error': 'Forbidden'}), 403

    assignment_id = request.args.get('assignment_id')
    from app.models.subject import GradingSystem
    grading_system = GradingSystem.query.filter_by(teacher_subject_group_id=assignment_id).first()

    if grading_system:
        return jsonify({
            "type": getattr(grading_system, 'system_type', 'points'),
            "maxPoints": grading_system.max_points,
            "minPoints": grading_system.min_points,
            "passingGrade": grading_system.passing_grade})

    return jsonify({
        "type": "points",
        "maxPoints": 100,
        "passingGrade": 60})

@student_bp.route('/api/get_lessons_data')
@jwt_required(locations=["cookies"])
def get_lessons_data():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user or user.role != 'student':
        return jsonify({'error': 'Forbidden'}), 403

    assignment_id = request.args.get('assignment_id')
    assignment = TeacherSubjectGroup.query.get(assignment_id)

    if not assignment or assignment.group_id != user.group_id:
        return jsonify({'error': 'Forbidden'}), 403

    lessons = Lesson.query.filter_by(teacher_subject_group_id=assignment_id, data_type='grades').all()
    if not lessons:
        lessons = Lesson.query.filter_by(teacher_subject_group_id=assignment_id, data_type='attendance').all()

    return jsonify([{
        'lesson_column_id': l.lesson_column_id,
        'date': l.date.strftime('%d.%m.%Y'),
        'topic': l.topic,
        'is_important': l.is_important
    } for l in lessons])

@student_bp.route('/api/get_group_students')
@jwt_required(locations=["cookies"])
def get_group_students():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user or user.role != 'student':
        return jsonify({'error': 'Forbidden'}), 403

    assignment_id = request.args.get('assignment_id')
    assignment = TeacherSubjectGroup.query.get(assignment_id)

    if not assignment or assignment.group_id != user.group_id:
        return jsonify({'error': 'Forbidden'}), 403

    students = User.query.filter_by(group_id=assignment.group_id, role='student').order_by(User.last_name).all()

    return jsonify({
        'students': [{
            'id': s.id,
            'last_name': s.last_name,
            'first_name': s.first_name
        } for s in students]
    })
