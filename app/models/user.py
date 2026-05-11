from app.models import db
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()

teachers_universities = db.Table(
    'teachers_universities',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('university_id', db.Integer, db.ForeignKey('university.id'), primary_key=True)
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    last_name = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    middle_name = db.Column(db.String(100))
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    avatar = db.Column(db.String(200))
    department = db.Column(db.String(150))
    can_change_login = db.Column(db.Integer, default=1)
    university_id = db.Column(db.Integer, db.ForeignKey('university.id'), nullable=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey('student_group.id'), nullable=True)

    university = db.relationship('University')
    course = db.relationship('Course')
    group = db.relationship('StudentGroup', backref='students')

    universities = db.relationship(
        'University',
        secondary=teachers_universities,
        backref=db.backref('teachers', lazy='dynamic')
    )

    grades = db.relationship('Grade', back_populates='student', lazy=True)
    attendance = db.relationship('Attendance', back_populates='student', lazy=True)

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
