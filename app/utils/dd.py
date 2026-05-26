from app import app, db, TeacherSubjectGroup, Subject

with app.app_context():
    TeacherSubjectGroup.query.delete()
    Subject.query.delete()
    db.session.commit()
    print("Все тестовые предметы и связи удалены")