from app.models import db

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)

class TeacherSubjectGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('student_group.id'), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('teacher_id', 'subject_id', 'group_id', name='unique_teacher_subject_group'),
    )

    teacher = db.relationship('User', backref='teaching_assignments')
    subject = db.relationship('Subject', backref='group_assignments')
    group = db.relationship('StudentGroup', backref='subject_assignments')
    lessons = db.relationship('Lesson', back_populates='teacher_subject_group', lazy=True)
    grades = db.relationship('Grade', back_populates='teacher_subject_group', lazy=True)

class GradingSystem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    teacher_subject_group_id = db.Column(db.Integer, db.ForeignKey('teacher_subject_group.id'), nullable=False)
    system_type = db.Column(db.String(20), default='points')
    max_points = db.Column(db.Float, default=100.0)
    min_points = db.Column(db.Float, default=0.0)
    passing_grade = db.Column(db.Float, default=60.0)
    custom_grades = db.Column(db.Text)
    custom_pattern = db.Column(db.String(200))
    calculation_method = db.Column(db.String(20), default='average')

    teacher = db.relationship('User', backref='grading_systems')
    assignment = db.relationship('TeacherSubjectGroup', backref='grading_system')
