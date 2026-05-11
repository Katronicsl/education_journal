from app import app, db, TeacherSubjectGroup, Subject

with app.app_context():
    # Удаляем все связи
    TeacherSubjectGroup.query.delete()
    # Удаляем все предметы
    Subject.query.delete()
    db.session.commit()
    print("Все тестовые предметы и связи удалены")