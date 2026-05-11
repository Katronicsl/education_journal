from flask import Blueprint, render_template, request, jsonify, abort, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import db
from app.models.user import User
from app.models.course import University, StudentGroup
from app.models.subject import TeacherSubjectGroup, Subject, GradingSystem
from app.models.lesson import Lesson, Grade, Attendance

from app.utils.decorators import role_required
from app.utils.helpers import format_excel_width, get_passing_grade
from datetime import datetime
from io import BytesIO
import pandas as pd

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')

@teacher_bp.route('/dashboard')
@jwt_required(locations=["cookies"])
def dashboard():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user or (user.role not in ('teacher', 'admin')):
        abort(403)

    assignments = TeacherSubjectGroup.query.filter_by(teacher_id=user.id).all()

    subjects_dict = {}
    for assignment in assignments:
        subject_id = assignment.subject.id
        if subject_id not in subjects_dict:
            subjects_dict[subject_id] = {
                'subject_id': subject_id,
                'subject_name': assignment.subject.name,
                'groups_count': 0,
                'groups': []
            }
        subjects_dict[subject_id]['groups_count'] += 1
        subjects_dict[subject_id]['groups'].append({
            'id': assignment.group.id,
            'name': assignment.group.name
        })

    courses = list(subjects_dict.values())
    unique_groups = set(a.group.id for a in assignments)
    total_students = sum(len(group.students) for group in set(a.group for a in assignments))

    stats = {
        'courses_count': len(courses),
        'total_students': total_students,
        'groups_count': len(unique_groups),
        'new_courses': 0
    }

    # Format avatar path for template
    user.avatar = f'avatars/{user.avatar}' if user.avatar else 'avatar.png'

    return render_template('prod/glavte.html',
                         user=user,
                         stats=stats,
                         courses=courses)

@teacher_bp.route('/student_rating')
@jwt_required(locations=["cookies"])
def student_rating_page():
    """Teacher student rating page"""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user or user.role != 'teacher':
        abort(403)

    rating_data = []

    subjects = db.session.query(Subject)\
        .join(TeacherSubjectGroup, TeacherSubjectGroup.subject_id == Subject.id)\
        .filter(TeacherSubjectGroup.teacher_id == user.id)\
        .distinct().all()

    for subj in subjects:
        raw_grades = db.session.query(
            User,
            StudentGroup.name,
            Grade.value,
            GradingSystem.max_points
        ).join(Grade, Grade.student_id == User.id)\
         .join(TeacherSubjectGroup, Grade.teacher_subject_group_id == TeacherSubjectGroup.id)\
         .join(StudentGroup, User.group_id == StudentGroup.id)\
         .outerjoin(GradingSystem, GradingSystem.teacher_subject_group_id == TeacherSubjectGroup.id)\
         .filter(TeacherSubjectGroup.teacher_id == user.id)\
         .filter(TeacherSubjectGroup.subject_id == subj.id)\
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

        if students_list:
            rating_data.append({
                'subject_id': subj.id,
                'subject_name': subj.name,
                'students': students_list
            })

    # Format avatar path for template
    # Format avatar path for template
    user.avatar = f'avatars/{user.avatar}' if user.avatar else 'avatar.png'

    return render_template('teacher_student_rating.html', user=user, rating_data=rating_data)

@teacher_bp.route('/subject/<int:subject_id>')
@jwt_required(locations=["cookies"])
def subject_groups(subject_id):
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user or user.role != 'teacher':
        abort(403)

    subject = Subject.query.get_or_404(subject_id)

    assignments = TeacherSubjectGroup.query.filter_by(
        teacher_id=user.id,
        subject_id=subject_id
    ).all()

    if not assignments:
        abort(403)

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

    # Format avatar path for template
    # Format avatar path for template
    user.avatar = f'avatars/{user.avatar}' if user.avatar else 'avatar.png'

    return render_template('teacher_subject_groups.html',
                         user=user,
                         subject=subject,
                         groups=groups_data)

@teacher_bp.route('/subject/<int:subject_id>/group/<int:group_id>')
@jwt_required(locations=["cookies"])
def group_management(subject_id, group_id):
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))

    if not user or user.role != 'teacher':
        abort(403)

    assignment = TeacherSubjectGroup.query.filter_by(
        teacher_id=user.id,
        subject_id=subject_id,
        group_id=group_id
    ).first()

    if not assignment:
        abort(403)

    subject = Subject.query.get_or_404(subject_id)
    group = StudentGroup.query.get_or_404(group_id)

    lessons = Lesson.query.filter_by(
        teacher_subject_group_id=assignment.id
    ).order_by(Lesson.date.desc()).all()

    students_data = []
    for student in group.students:
        student_data = {
            'id': student.id,
            'last_name': student.last_name,
            'first_name': student.first_name,
            'middle_name': student.middle_name or ''
        }
        students_data.append(student_data)

    # Format avatar path for template
    # Format avatar path for template
    user.avatar = f'avatars/{user.avatar}' if user.avatar else 'avatar.png'

    return render_template('teacher_group_management.html',
                         user=user,
                         subject=subject,
                         group=group,
                         students_data=students_data,
                         lessons=lessons,
                         assignment_id=assignment.id)

@teacher_bp.route('/grading_system/<int:assignment_id>', methods=['GET', 'POST'])
@jwt_required(locations=["cookies"])
def grading_system(assignment_id):
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))

    if not user or user.role != 'teacher':
        abort(403)

    assignment = TeacherSubjectGroup.query.filter_by(
        id=assignment_id,
        teacher_id=user.id
    ).first_or_404()

    grading_system = GradingSystem.query.filter_by(
        teacher_subject_group_id=assignment_id
    ).first()

    if request.method == 'POST':
        system_type = request.form.get('system_type')

        if not grading_system:
            grading_system = GradingSystem(
                teacher_id=user.id,
                teacher_subject_group_id=assignment_id,
                system_type=system_type
            )
            db.session.add(grading_system)

        grading_system.system_type = system_type
        grading_system.calculation_method = request.form.get('calculation_method', 'average')

        if system_type in ['points', 'percentage']:
            grading_system.max_points = float(request.form.get('max_points', 100))
            grading_system.min_points = float(request.form.get('min_points', 0))
            grading_system.passing_grade = float(request.form.get('passing_grade', 60))
            grading_system.custom_pattern = None
            grading_system.custom_grades = None
        elif system_type == 'custom':
            grading_system.custom_pattern = request.form.get('custom_pattern', '')
            grading_system.custom_grades = request.form.get('custom_examples', '')
            grading_system.max_points = None
            grading_system.min_points = None
            grading_system.passing_grade = None

        db.session.commit()

        from flask import redirect, url_for
        return redirect(url_for('teacher.group_management',
                              subject_id=assignment.subject_id,
                              group_id=assignment.group_id))

    # Format avatar path for template
    # Format avatar path for template
    user.avatar = f'avatars/{user.avatar}' if user.avatar else 'avatar.png'

    return render_template('grading_system.html',
                         user=user,
                         assignment=assignment,
                         grading_system=grading_system)

@teacher_bp.route('/create_lesson', methods=['POST'])
@jwt_required(locations=["cookies"])
def create_lesson():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))

    if not user or user.role != 'teacher':
        return jsonify({'error': 'Forbidden'}), 403

    data = request.json

    assignment = TeacherSubjectGroup.query.filter_by(
        id=data['assignment_id'],
        teacher_id=user.id
    ).first()

    if not assignment:
        return jsonify({'error': 'Forbidden'}), 403

    new_lesson = Lesson(
        teacher_subject_group_id=data['assignment_id'],
        date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
        topic=data['topic'],
        lesson_type=data['lesson_type'],
        description=data.get('description', '')
    )

    db.session.add(new_lesson)
    db.session.commit()

    for student in assignment.group.students:
        attendance = Attendance(
            lesson_id=new_lesson.id,
            student_id=student.id,
            status='present'
        )
        db.session.add(attendance)

    db.session.commit()

    return jsonify({'success': True, 'lesson_id': new_lesson.id})

# @teacher_bp.route('/save_grade', methods=['POST'])
# @jwt_required(locations=["cookies"])
# def save_grade():
#     user_id = get_jwt_identity()
#     user = User.query.get(int(user_id))

#     if not user or user.role != 'teacher':
#         return jsonify({'error': 'Forbidden'}), 403

#     try:
#         data = request.json
#         student_id = data.get('student_id')
#         grade_value_raw = data.get('grade_value')
#         column_id = data.get('lesson_column_id')
#         assignment_id = data.get('teacher_subject_group_id')

#         assignment = TeacherSubjectGroup.query.filter_by(
#             teacher_id=user.id, id=assignment_id
#         ).first()

#         if not assignment:
#             return jsonify({'error': 'Forbidden'}), 403

#         grade = Grade.query.filter_by(
#             student_id=student_id,
#             teacher_subject_group_id=assignment_id,
#             lesson_column_id=column_id
#         ).first()

#         if grade_value_raw is None or str(grade_value_raw).strip() == '':
#             if grade:
#                 db.session.delete(grade)
#                 db.session.commit()
#             return jsonify({'success': True, 'message': 'Grade deleted'})

#         final_display_value = str(grade_value_raw).strip()
#         final_float_value = 0.0

#         try:
#             clean_val = final_display_value.replace(',', '.')
#             final_float_value = float(clean_val)
#         except ValueError:
#             final_float_value = 0.0

#         if grade:
#             grade.value = final_float_value
#             grade.display_value = final_display_value
#         else:
#             grade = Grade(
#                 student_id=student_id,
#                 teacher_subject_group_id=assignment_id,
#                 lesson_column_id=column_id,
#                 value=final_float_value,
#                 display_value=final_display_value,
#                 grade_type='lesson'
#             )
#             db.session.add(grade)

#         db.session.commit()
#         return jsonify({'success': True, 'message': 'Grade saved'})

#     except Exception as e:
#         db.session.rollback()

#         return jsonify({'error': str(e)}), 500

@teacher_bp.route('/export_group_excel', strict_slashes=False)
@teacher_bp.route('/export_group_excel/<int:assignment_id>', strict_slashes=False)
@jwt_required(locations=["cookies"])
def export_group_excel(assignment_id=None):
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user or user.role != 'teacher':
        abort(403)

    # If assignment_id is provided, export specific group data
    if assignment_id:
        if user.role == 'teacher':
            assignment = TeacherSubjectGroup.query.filter_by(id=assignment_id, teacher_id=user.id).first_or_404()
        else:
            assignment = TeacherSubjectGroup.query.filter_by(id=assignment_id).first_or_404()
        group = assignment.group
        subject = assignment.subject
        students = sorted(group.students, key=lambda x: x.last_name)

        grade_lessons = Lesson.query.filter_by(
            teacher_subject_group_id=assignment.id,
            data_type='grades'
        ).order_by(Lesson.date).all()

        grades_data = []
        for student in students:
            row = {'ФИО': f"{student.last_name} {student.first_name} {student.middle_name or ''}"}
            total_score = 0
            count = 0

            for lesson in grade_lessons:
                grade = Grade.query.filter_by(student_id=student.id, lesson_column_id=lesson.lesson_column_id).first()
                col_name = f"{lesson.date.strftime('%d.%m')}\n{lesson.topic}"
                val = grade.display_value if grade and grade.display_value else (grade.value if grade else "")
                row[col_name] = val

                if grade and grade.value is not None:
                    total_score += grade.value
                    count += 1

            row['Средний\nбалл'] = round(total_score / count, 2) if count > 0 else '-'
            grades_data.append(row)

        df_grades = pd.DataFrame(grades_data)

        att_lessons = Lesson.query.filter_by(
            teacher_subject_group_id=assignment.id,
            data_type='attendance'
        ).order_by(Lesson.date).all()

        att_data = []
        for student in students:
            row = {'ФИО': f"{student.last_name} {student.first_name}"}
            present_count = 0

            for lesson in att_lessons:
                att = Attendance.query.filter_by(student_id=student.id, lesson_column_id=lesson.lesson_column_id).first()
                col_name = f"{lesson.date.strftime('%d.%m')}\n{lesson.topic}"
                status = att.status if att else ""
                row[col_name] = status
                if status == '+':
                    present_count += 1

            total = len(att_lessons)
            percent = round((present_count / total * 100)) if total > 0 else 0
            row['Процент\nпосещ.'] = f"{percent}%"
            att_data.append(row)

        df_att = pd.DataFrame(att_data)

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            if not df_grades.empty:
                df_grades.to_excel(writer, sheet_name='Успеваемость', index=False)
            else:
                pd.DataFrame({'Info': ['No data']}).to_excel(writer, sheet_name='Успеваемость', index=False)

            if not df_att.empty:
                df_att.to_excel(writer, sheet_name='Посещаемость', index=False)
            else:
                pd.DataFrame({'Info': ['No data']}).to_excel(writer, sheet_name='Посещаемость', index=False)

            format_excel_width(writer)

        output.seek(0)
        filename = f"Report_{group.name}_{subject.name}.xlsx"
        return send_file(output, download_name=filename, as_attachment=True)

    # If no assignment_id, export all ratings data
    else:
        rating_data = []

        if user.role == 'teacher':
            subjects = db.session.query(Subject)\
                .join(TeacherSubjectGroup, TeacherSubjectGroup.subject_id == Subject.id)\
                .filter(TeacherSubjectGroup.teacher_id == user.id)\
                .distinct().all()
        else:
            subjects = db.session.query(Subject)\
                .join(TeacherSubjectGroup, TeacherSubjectGroup.subject_id == Subject.id)\
                .distinct().all()

        for subj in subjects:
            raw_grades = db.session.query(
                User,
                StudentGroup.name,
                Grade.value,
                GradingSystem.max_points
            ).join(Grade, Grade.student_id == User.id)\
             .join(TeacherSubjectGroup, Grade.teacher_subject_group_id == TeacherSubjectGroup.id)\
             .join(StudentGroup, User.group_id == StudentGroup.id)\
             .outerjoin(GradingSystem, GradingSystem.teacher_subject_group_id == TeacherSubjectGroup.id)\
             .filter(TeacherSubjectGroup.teacher_id == user.id)\
             .filter(TeacherSubjectGroup.subject_id == subj.id)\
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
                    'group_name': s_data['group_name'],
                    'average': round(avg_5_scale, 2)
                })

            students_list.sort(key=lambda x: x['average'], reverse=True)

            if students_list:
                rating_data.append({
                    'subject_name': subj.name,
                    'students': students_list
                })

        # Create Excel export with all ratings
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for item in rating_data:
                df = pd.DataFrame(item['students'])
                if not df.empty:
                    df.to_excel(writer, sheet_name=item['subject_name'][:31], index=False)

            format_excel_width(writer)

        output.seek(0)
        filename = f"Ratings_{user.last_name}_{datetime.now().strftime('%d.%m.%Y')}.xlsx"
        return send_file(output, download_name=filename, as_attachment=True)


# API Routes

@teacher_bp.route('/get_group_students/<int:group_id>')
@jwt_required(locations=["cookies"])
def get_group_students(group_id):
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user or (user.role not in ('teacher', 'admin')):
            return jsonify({'error': 'Доступ запрещен'}), 403
        
        group = StudentGroup.query.get(group_id)
        if not group:
            return jsonify({'error': 'Группа не найдена'}), 404
        
        students = User.query.filter_by(
            group_id=group_id,
            role='student'
        ).order_by(User.last_name, User.first_name).all()
        
        students_data = []
        for student in students:
            students_data.append({
                'id': student.id,
                'last_name': student.last_name,
                'first_name': student.first_name,
                'middle_name': student.middle_name or '',
                'email': student.email
            })
        
        return jsonify({'students': students_data})
        
    except Exception as e:
        print(f"Ошибка получения студентов: {str(e)}")
        return jsonify({'error': 'Ошибка сервера'}), 500


@teacher_bp.route('/get_grading_system')
@jwt_required(locations=["cookies"])
def get_grading_system():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    
    if not user or (user.role not in ('teacher', 'admin')):
        return jsonify({"error": "Forbidden"}), 403

    assignment_id = request.args.get('assignment_id')
    if not assignment_id:
        return jsonify({"error": "assignment_id required"}), 400

    if user.role == 'teacher':
        assignment = TeacherSubjectGroup.query.filter_by(id=assignment_id, teacher_id=user.id).first()
        if not assignment:
            return jsonify({"error": "Assignment not found"}), 404
    else:
        assignment = TeacherSubjectGroup.query.filter_by(id=assignment_id).first()
        if not assignment:
            return jsonify({"error": "Assignment not found"}), 404

    try:
        grading_system = GradingSystem.query.filter_by(
            teacher_subject_group_id=assignment_id
        ).first()
        
        if grading_system:
            response = {
                "type": getattr(grading_system, 'system_type', 'points'),
                "maxPoints": float(grading_system.max_points) if grading_system.max_points is not None else 100,
                "minPoints": float(grading_system.min_points) if grading_system.min_points is not None else 0,
                "passingGrade": float(grading_system.passing_grade) if grading_system.passing_grade is not None else 60,
                "customPattern": getattr(grading_system, 'custom_pattern', ''),
                "customExamples": getattr(grading_system, 'custom_grades', ''),
                "calculationMethod": getattr(grading_system, 'calculation_method', 'average')
            }
        else:
            response = {
                "type": "points",
                "maxPoints": 100,
                "minPoints": 0,
                "passingGrade": 60,
                "customPattern": "",
                "customExamples": "",
                "calculationMethod": "average"
            }
        
        return jsonify(response)
    except Exception as e:
        print(f"ERROR in get_grading_system: {e}") 
        return jsonify({"error": str(e)}), 500


@teacher_bp.route('/get_lessons_data')
@jwt_required(locations=["cookies"])
def get_lessons_data():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    
    if not user or (user.role not in ('teacher', 'admin')):
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    assignment_id = request.args.get('assignment_id')
    data_type = request.args.get('data_type', 'grades')
    
    if user.role == 'teacher':
        assignment = TeacherSubjectGroup.query.filter_by(id=assignment_id, teacher_id=user.id).first()
        if not assignment:
            return jsonify({'error': 'Доступ запрещен'}), 403
    else:
        assignment = TeacherSubjectGroup.query.filter_by(id=assignment_id).first()
        if not assignment:
            return jsonify({'error': 'Assignment not found'}), 404
    
    lessons = Lesson.query.filter_by(
        teacher_subject_group_id=assignment_id,
        data_type=data_type
    ).order_by(Lesson.date).all() 
    
    lessons_data = [{
        'lesson_column_id': lesson.lesson_column_id,
        'date': lesson.date.strftime('%d.%m.%Y'),
        'topic': lesson.topic,
        'is_important': lesson.is_important  
    } for lesson in lessons]
    
    return jsonify(lessons_data)


@teacher_bp.route('/get_attendance')
@jwt_required(locations=["cookies"])
def get_attendance():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    
    if not user or (user.role not in ('teacher', 'admin')):
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    try:
        assignment_id = request.args.get('assignment_id')
        
        if not assignment_id:
            return jsonify({'error': 'Не указан assignment_id'}), 400
        
        assignment = TeacherSubjectGroup.query.filter_by(
            id=assignment_id,
            teacher_id=user.id
        ).first()
        
        if not assignment:
            return jsonify({'error': 'Доступ запрещен'}), 403
        
        attendance_lessons = Lesson.query.filter_by(
            teacher_subject_group_id=assignment_id,
            data_type='attendance'
        ).all()
        
        attendance_lesson_ids = [lesson.id for lesson in attendance_lessons]
        
        attendance_records = Attendance.query.filter(
            Attendance.lesson_id.in_(attendance_lesson_ids)
        ).all()
        
        attendance_data = [{
            'student_id': attendance.student_id,
            'status': attendance.status,
            'lesson_column_id': attendance.lesson.lesson_column_id
        } for attendance in attendance_records]
        
        return jsonify(attendance_data)
        
    except Exception as e:
        print(f"Ошибка в get_attendance: {str(e)}")
        return jsonify({'error': f'Внутренняя ошибка сервера: {str(e)}'}), 500


@teacher_bp.route('/get_grades')
@jwt_required(locations=["cookies"])
def get_grades():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    assignment_id = request.args.get('assignment_id')
    
    grades = Grade.query.filter_by(
        teacher_subject_group_id=assignment_id
    ).all()
    
    grades_data = []
    for grade in grades:
        final_display = getattr(grade, 'display_value', None)
        
        if not final_display:
            if grade.value is not None:
                if isinstance(grade.value, float) and grade.value.is_integer():
                    final_display = str(int(grade.value))
                else:
                    final_display = str(grade.value)
            else:
                final_display = ""

        grades_data.append({
            'student_id': grade.student_id,
            'value': grade.value,
            'display_value': final_display, 
            'lesson_column_id': getattr(grade, 'lesson_column_id', '')
        })
    
    return jsonify(grades_data)


@teacher_bp.route('/save_lesson_data', methods=['POST'])
@jwt_required(locations=["cookies"])
def save_lesson_data():
    user_id = get_jwt_identity()
    try:
        data = request.json
        column_id = data.get('lesson_column_id')
        date_str = data.get('date')
        topic = data.get('topic')
        table_type = data.get('table_type') 
        assignment_id = data.get('teacher_subject_group_id')
        is_important = data.get('is_important', 0) 
        print(is_important)
        
        # Обработка даты 
        date_obj = datetime.now().date() 
        if date_str:
            try:
                date_obj = datetime.strptime(date_str, '%d.%m.%Y').date()
            except ValueError:
                try:
                    temp_date = datetime.strptime(date_str, '%d.%m')
                    current_year = datetime.now().year
                    date_obj = temp_date.replace(year=current_year).date()
                except ValueError:
                    try:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                    except ValueError:
                        pass 

        lesson = Lesson.query.filter_by(
            teacher_subject_group_id=assignment_id,
            lesson_column_id=column_id,
            data_type=table_type 
        ).first()
        
        if lesson:
            lesson.date = date_obj
            lesson.topic = topic
            if table_type == 'grades':
                lesson.is_important = is_important
        else:
            lesson = Lesson(
                teacher_subject_group_id=assignment_id,
                lesson_column_id=column_id,
                date=date_obj,
                topic=topic,
                data_type=table_type,
                is_important=is_important if table_type == 'grades' else 0
            )
            db.session.add(lesson)
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error saving lesson: {e}")
        return jsonify({'error': str(e)}), 500


@teacher_bp.route('/save_grade', methods=['POST'])
@jwt_required(locations=["cookies"])
def save_grade():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    
    if not user or user.role != 'teacher':
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    try:
        data = request.json
        student_id = data.get('student_id')
        grade_value_raw = data.get('grade_value') 
        column_id = data.get('lesson_column_id')
        assignment_id = data.get('teacher_subject_group_id')
        
        assignment = TeacherSubjectGroup.query.filter_by(
            teacher_id=user.id, id=assignment_id
        ).first()
        
        if not assignment: 
            return jsonify({'error': 'Доступ запрещен'}), 403
        
        grade = Grade.query.filter_by(
            student_id=student_id,
            teacher_subject_group_id=assignment_id,
            lesson_column_id=column_id
        ).first()
        
        if grade_value_raw is None or str(grade_value_raw).strip() == '':
            if grade:
                db.session.delete(grade)
                db.session.commit()
            return jsonify({'success': True, 'message': 'Оценка удалена'})

        final_display_value = str(grade_value_raw).strip()
        final_float_value = 0.0

        try:
            clean_val = final_display_value.replace(',', '.')
            final_float_value = float(clean_val)
        except ValueError:
            final_float_value = 0.0
            
        if grade:
            grade.value = final_float_value
            grade.display_value = final_display_value
        else:
            grade = Grade(
                student_id=student_id,
                teacher_subject_group_id=assignment_id,
                lesson_column_id=column_id,
                value=final_float_value,
                display_value=final_display_value,
                grade_type='lesson'
            )
            db.session.add(grade)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Оценка сохранена'})
        
    except Exception as e:
        db.session.rollback()
        print(f"ОШИБКА: {e}")
        return jsonify({'error': str(e)}), 500


@teacher_bp.route('/save_attendance', methods=['POST'])
@jwt_required(locations=["cookies"])
def save_attendance():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    
    if not user or user.role != 'teacher':
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    try:
        data = request.json
        student_id = data.get('student_id')
        attendance_status = data.get('attendance_status')
        column_id = data.get('lesson_column_id')
        assignment_id = data.get('teacher_subject_group_id')
        
        lesson = Lesson.query.filter_by(
            teacher_subject_group_id=assignment_id,
            lesson_column_id=column_id,
            data_type='attendance'
        ).first()
        
        if not lesson:
            lesson = Lesson(
                teacher_subject_group_id=assignment_id,
                lesson_column_id=column_id,
                date=datetime.now().date(),
                topic='Занятие',
                data_type='attendance'
            )
            db.session.add(lesson)
            db.session.commit()
        
        attendance = Attendance.query.filter_by(
            student_id=student_id,
            lesson_id=lesson.id
        ).first()
        
        if not attendance_status or attendance_status == 'none' or attendance_status.strip() == '':
            if attendance:
                db.session.delete(attendance)
        else:
            if attendance:
                attendance.status = attendance_status
            else:
                attendance = Attendance(
                    student_id=student_id,
                    lesson_id=lesson.id,
                    status=attendance_status,
                    lesson_column_id=column_id
                )
                db.session.add(attendance)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Посещаемость сохранена'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Ошибка в save_attendance: {str(e)}")
        return jsonify({'error': str(e)}), 500


@teacher_bp.route('/delete_lesson', methods=['POST'])
@jwt_required(locations=["cookies"])
def delete_lesson():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    
    if not user or user.role != 'teacher':
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    try:
        data = request.json
        print("Удаление занятия:", data)
        
        assignment = TeacherSubjectGroup.query.filter_by(
            id=data['teacher_subject_group_id'],
            teacher_id=user.id
        ).first()
        
        if not assignment:
            return jsonify({'error': 'Доступ запрещен'}), 403
        
        lesson = Lesson.query.filter_by(
            teacher_subject_group_id=data['teacher_subject_group_id'],
            lesson_column_id=data.get('lesson_column_id')
        ).first()
        
        if lesson:
            grades_to_delete = Grade.query.filter_by(
                lesson_column_id=data.get('lesson_column_id')
            ).all()
            for grade in grades_to_delete:
                db.session.delete(grade)
            
            attendance_to_delete = Attendance.query.filter_by(
                lesson_column_id=data.get('lesson_column_id')
            ).all()
            for attendance in attendance_to_delete:
                db.session.delete(attendance)
            
            db.session.delete(lesson)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Занятие и все связанные данные удалены'})
        else:
            return jsonify({'success': True, 'message': 'Занятие не найдено'})
            
    except Exception as e:
        db.session.rollback()
        print(f"Ошибка в delete_lesson: {str(e)}")
        return jsonify({'error': f'Ошибка удаления: {str(e)}'}), 500
