from app.models import db
from datetime import datetime

class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_subject_group_id = db.Column(db.Integer, db.ForeignKey('teacher_subject_group.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    topic = db.Column(db.String(300))
    lesson_type = db.Column(db.String(20))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.now())
    lesson_column_id = db.Column(db.String(50))
    data_type = db.Column(db.String(20), default='grades')
    is_important = db.Column(db.SmallInteger, default=False)

    teacher_subject_group = db.relationship('TeacherSubjectGroup', back_populates='lessons')
    attendance = db.relationship('Attendance', back_populates='lesson', cascade='all, delete-orphan')

class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    teacher_subject_group_id = db.Column(db.Integer, db.ForeignKey('teacher_subject_group.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=True)
    value = db.Column(db.Float, nullable=False)
    display_value = db.Column(db.String(50))
    grade_type = db.Column(db.String(50))
    comment = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=db.func.now())
    lesson_column_id = db.Column(db.String(50))

    student = db.relationship('User', back_populates='grades')
    teacher_subject_group = db.relationship('TeacherSubjectGroup', back_populates='grades')

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, default=db.func.now())
    lesson_column_id = db.Column(db.String(50))

    lesson = db.relationship('Lesson', back_populates='attendance')
    student = db.relationship('User', back_populates='attendance')
