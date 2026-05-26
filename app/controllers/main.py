from flask import Blueprint, render_template, request, jsonify, make_response, redirect, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import db
from app.models.user import User
from app.models.course import University, Course, StudentGroup
import base64
import os

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def home():
    return render_template('index.html')

@main_bp.route('/register/student')
def register_student():
    """For backward compatibility, redirect to auth register"""
    from flask import redirect, url_for as flask_url_for
    return redirect(flask_url_for('auth.register'))

@main_bp.route('/register')
def register():
    """Student registration (for blueprint naming)"""
    from app.utils.helpers import get_universities_data
    univs_data = get_universities_data()
    return render_template('register/student.html', univs_data=univs_data)

@main_bp.route('/profile', methods=['GET', 'POST'])
@jwt_required(locations=["cookies"])
def profile():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))

    if not user:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        if request.form.get('first_name'):
            user.first_name = request.form.get('first_name')
        if request.form.get('last_name'):
            user.last_name = request.form.get('last_name')
        if request.form.get('middle_name'):
            user.middle_name = request.form.get('middle_name')
        if request.form.get('email'):
            user.email = request.form.get('email')
        if request.form.get('phone'):
            user.phone = request.form.get('phone')
        if request.form.get('department'):
            user.department = request.form.get('department')
        
        avatar_data = request.form.get('avatar_data')
        if avatar_data:
            try:
                if ',' in avatar_data:
                    avatar_data = avatar_data.split(',')[1]
                
                image_data = base64.b64decode(avatar_data)
                
                avatars_dir = os.path.join('app', 'static', 'avatars')
                os.makedirs(avatars_dir, exist_ok=True)
                
                filename = f"avatar_{user.id}.png"
                filepath = os.path.join(avatars_dir, filename)
                
                with open(filepath, 'wb') as f:
                    f.write(image_data)
                
                user.avatar = filename
            except Exception as e:
                print(f"Error saving avatar: {e}")
        elif 'avatar' in request.files:
            file = request.files['avatar']
            if file and file.filename:
                avatars_dir = os.path.join('app', 'static', 'avatars')
                os.makedirs(avatars_dir, exist_ok=True)
                
                filename = f"avatar_{user.id}.png"
                filepath = os.path.join(avatars_dir, filename)
                file.save(filepath)
                user.avatar = filename
        
        db.session.add(user)
        db.session.commit()

    if user.avatar:
        avatar_to_show = f'avatars/{user.avatar}'
    else:
        avatar_to_show = 'avatar.png'

    user_data = {
        'id': user.id,
        'last_name': user.last_name,
        'first_name': user.first_name,
        'middle_name': user.middle_name or '',
        'email': user.email,
        'role': user.role,
        'avatar': avatar_to_show,
        'group_name': user.group.name if user.group else None,
        'department': user.department,
        'phone': getattr(user, 'phone', '')
    }

    return render_template('profile.html', user=user_data)

@main_bp.route('/api/courses/<int:univ_id>')
def api_courses(univ_id):
    courses = Course.query.filter_by(university_id=univ_id).all()
    return jsonify([{"id": c.id, "name": c.name} for c in courses])

@main_bp.route('/api/groups/<int:course_id>')
def api_groups(course_id):
    groups = StudentGroup.query.filter_by(course_id=course_id).all()
    return jsonify([{"id": g.id, "name": g.name} for g in groups])
