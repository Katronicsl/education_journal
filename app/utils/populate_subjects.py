import json
import sys
import os


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.models import db
from app.models.user import User
from app.models.subject import TeacherSubjectGroup
from app.models.subject import Subject
from app.models.course import StudentGroup


from app import create_app
flask_app = create_app()

def populate_subjects_from_file(filepath=None):
    if filepath is None:
        filepath = os.path.join(os.path.dirname(__file__), 'subjects_data.json')
    with flask_app.app_context():
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        groups_cache = {g.name: g for g in StudentGroup.query.all()}
        subjects_cache = {s.name: s for s in Subject.query.all()}

        for group_entry in data:
            group_name = group_entry['group']
            group = groups_cache.get(group_name)
            
            if not group:
                continue

            for subj_data in group_entry['subjects']:
                target_teacher_email = subj_data['teacher_email']
                subject_name = subj_data['name'].strip()
                
                subject = subjects_cache.get(subject_name)
                if not subject:
                    subject = Subject(name=subject_name)
                    db.session.add(subject)
                    db.session.flush()
                    subjects_cache[subject_name] = subject

                university_id = group.course.university.id
                all_university_teachers = User.query.filter(
                    User.role == 'teacher',
                    User.universities.any(id=university_id)
                ).all()

                target_teachers = [t for t in all_university_teachers if t.email == target_teacher_email]
                
                if not target_teachers:
                    continue

                for teacher in target_teachers:
                    existing_assignment = TeacherSubjectGroup.query.filter_by(
                        teacher_id=teacher.id,
                        subject_id=subject.id,
                        group_id=group.id
                    ).first()
                    
                    if not existing_assignment:
                        new_assignment = TeacherSubjectGroup(
                            teacher_id=teacher.id,
                            subject_id=subject.id, 
                            group_id=group.id
                        )
                        db.session.add(new_assignment)

        db.session.commit()

if __name__ == '__main__':
    populate_subjects_from_file()