from flask import Flask, jsonify, request, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from marshmallow import fields, Schema
from datetime import datetime
import os
from passlib.hash import pbkdf2_sha256 as sha256
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
#ok

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SECRET_KEY'] = os.getenv('SECRETS')
db = SQLAlchemy(app)
migrate = Migrate(app,db)
admin = Admin(app)
jwt = JWTManager(app)


#testing jenkins
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80),nullable=False, unique=True)
    password = db.Column(db.String(120), nullable=False)

    def create_user(self):
        db.session.add(self)
        db.session.commit()

    @classmethod
    def find_by_username(cls,username):
        cls.query.filter_by(username=username).first()

    @staticmethod
    def generate_hash(password):
        return sha256.hash(password)

    @staticmethod
    def verify_hash(password, hash):
        return sha256.verify(password,hash)

    def __repr__(self):
        return f"User('{self.username}')"

class UserSchema(Schema):
    class Meta:
        model = User
        sqla_session = db.session

    id = fields.Integer(dump_only=True)
    username = fields.String(required=True)
    password = fields.String(required=True)


mycourse = db.Table('mycourse',
            db.Column('id', db.Integer, primary_key=True),
            db.Column('student_id',db.Integer,db.ForeignKey('student.id')),
            db.Column('subject_id', db.Integer, db.ForeignKey('subject.id')))


class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sub_name = db.Column(db.String(20), nullable=False)
    created_on = db.Column(db.DateTime, default=datetime.utcnow)
    updated_on = db.Column(db.DateTime, default=datetime.utcnow)
    students = db.relationship('Student', secondary=mycourse,
    backref=db.backref('subjects', lazy='dynamic'), lazy='dynamic')

    def __repr__(self):
        return f"Sub('{self.sub_name}')"




class SubjectSchema(Schema):
    class Meta:
        model = Subject
        ordered = True
        sqla_session = db.session

    id = fields.Integer(dump_only=True)
    sub_name = fields.String(required=True)
    created_on = fields.DateTime()
    updated_on = fields.DateTime()
    students = fields.Nested('StudentSchema', many=True, only=('firstname','lastname'))


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    firstname = db.Column(db.String(100), nullable=False)
    lastname = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(50), nullable=False)
    level = db.Column(db.Integer,nullable=False)
    stud_id = db.Column(db.String(6), nullable=False)
    date_joined = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"Student('{self.firstname}','{self.department}')"



class StudentSchema(Schema):
    class Meta:
        model = Student
        ordered = True
        sqla_session = db.session

    id = fields.Integer(dump_only=True)
    firstname = fields.String(required=True)
    lastname = fields.String(required=True)
    department = fields.String(required=True)
    level = fields.Integer(required=True)
    stud_id = fields.String(required=True)
    date_joined = fields.DateTime()
    subjects = fields.Nested('SubjectSchema', many=True, only=('sub_name',))


admin.add_view(ModelView(Student,db.session))
admin.add_view(ModelView(Subject,db.session))


@app.route('/user/signup', methods=['POST'])
def register_user():
    try:
        data = request.get_json()
        data['password'] = User.generate_hash(data['password'])
        print(data)
        userschema = UserSchema()
        user = userschema.load(data)
        print(user)
        newuser = User(username=user['username'],password=user['password'])
        User.create_user(newuser)
        return jsonify({'success':'resource created'})
    except Exception as e:
        print(e)
        return jsonify({'error':'invalid input'})

@app.route('/user/login', methods=['POST'])
def login_user():
    try:
        data = request.get_json()
        print(data['username'])
        current_user = User.query.filter_by(username=data['username']).first()
        print(current_user)
        if not current_user:
            return make_response(jsonify({'error':'username or password incorrect'}),404)
        if User.verify_hash(data['password'], current_user.password):
            access_token = create_access_token(identity=data['username'])
            return jsonify({'message':f"logged in as {data['username']}",
                            'access_token':access_token
                            })
        else:
            return make_response(jsonify({'error':'username or password incorrect'}))
    except Exception as e:
        print(e)
        return jsonify({'error':'invalid input'})





@app.route('/api/v1/students', methods=['GET'])
@jwt_required()
def get_students():
    data = Student.query.all()
    students = StudentSchema(exclude=('subjects',)).dump(data, many=True)
    for std in students:
        std['date_joined'] = std['date_joined'][:10]
    return make_response(jsonify({'students':students}))

@app.route('/api/v1/student/<int:id>', methods=['GET'])
@jwt_required()
def get_student(id):
    data = Student.query.get(id)
    if data:
        student = StudentSchema(exclude=('subjects',)).dump(data)
        student['date_joined'] = student['date_joined'][:10]
        return make_response(jsonify({'student':student}))
    else:
        return jsonify({'error':'resource not found'})

@app.route('/api/v1/students', methods=['POST'])
@jwt_required()
def create_student():
    data = request.get_json()
    try:
        student = StudentSchema().load(data)
        student = Student(firstname=student['firstname'],lastname=student['lastname'],
                department=student['department'],level=student['level'],stud_id=student['stud_id'])
        db.session.add(student)
        db.session.commit()
        return jsonify({'success':'resource created'})
    except Exception:
        return jsonify({'error':'resource was not created'})

@app.route('/api/v1/student/<int:id>', methods=['PUT'])
@jwt_required()
def update_student(id):
    data = request.get_json()
    student = Student.query.get(id)
    if student:
        if data.get('firstname'):
            student.firstname = data['firstname']
        if data.get('lastname'):
            student.lastname = data['lastname']
        if data.get('department'):
            student.department = data['department']
        if data.get('level'):
            student.level = data['level']
        db.session.commit()
        return jsonify({'success':'resource updated'})
    else:
        return jsonify({'error':'resource not found'})

@app.route('/api/v1/student/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_student(id):
    student = Student.query.get(id)
    if student:
        db.session.delete(student)
        db.session.commit()
        return jsonify({'success':'resource deleted'})
    else:
        return jsonify({'error':'reosource not found'})

@app.route('/api/v1/subjects', methods=['GET'])
@jwt_required()
def get_subjects():
    data = Subject.query.all()
    subjects = SubjectSchema(exclude=('students','updated_on')).dump(data, many=True)
    for subj in subjects:
    	subj['created_on'] = subj['created_on'][:10]
    	#subj['updated_on'] = subj['updated_on'][:10]
    return make_response(jsonify({'subjects':subjects}))

@app.route('/api/v1/subject/<int:id>', methods=['GET'])
@jwt_required()
def get_subject(id):
    data = Subject.query.get(id)
    if data:
        subject = SubjectSchema(only=('id','sub_name',)).dump(data)
        return jsonify({'subject':subject})
    else:
        return jsonify({'error':'resource not found'})

@app.route('/api/v1/subject', methods=['POST'])
@jwt_required()
def create_subject():
    data = request.get_json()
    subject = SubjectSchema().load(data)
    try:
        subject = Subject(sub_name=subject['sub_name'])
        db.session.add(subject)
        db.session.commit()
        return jsonify({'success':'resource created'})
    except Exception as e:
        return jsonify({'error':'resource was not created'})

@app.route('/api/v1/subject/<int:id>', methods=['PUT'])
@jwt_required()
def update_subject(id):
    data = request.get_json()
    subject = Subject.query.get(id)
    if subject:
        if data.get('sub_name'):
            subject.sub_name = data['sub_name']
            subject.updated_on = datetime.utcnow()
        db.session.commit()
        return jsonify({'success':'resource updated'})
    else:
        return jsonify({'error':'resource not found'})

@app.route('/api/v1/subject/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_subject(id):
    subject = Subject.query.get(id)
    if subject:
        db.session.delete(subject)
        db.session.commit()
        return jsonify({'success':'resource deleted'})
    else:
        return jsonify({'error':'reosource not found'})

@app.route('/api/v1/student/<int:id>/subjects', methods=['GET'])
@jwt_required()
def get_student_subjects(id):
    data = Student.query.get(id)
    if data:
        student = StudentSchema(exclude=('date_joined','department','level','stud_id')).dump(data)
        #student['date_joined'] = student['date_joined'][:10]
        return make_response(jsonify({'student':student}))
    else:
        return jsonify({'error':'resource not found'})

@app.route('/api/v1/subject/<int:id>/students', methods=['GET'])
@jwt_required()
def get_subject_students(id):
    data = Subject.query.get(id)
    if data:
        subject = SubjectSchema(only=('id','sub_name','students')).dump(data)
        return jsonify({'subject':subject})
    else:
        return jsonify({'error':'resource not found'})

@app.route('/api/v1/student/<int:id>/subject/<int:pk>', methods=['PUT'])
@jwt_required()
def add_student_subject(id,pk):
    stud = Student.query.get(id)
    subj = Subject.query.get(pk)
    if stud and subj:
        if subj in stud.subjects.all():
            return jsonify({'error':'resource already exist'})
        subj.students.append(stud)
        db.session.commit()
        return jsonify({'success':f'subject added to student id {id}'})
    else:
        return jsonify({'error':'resource not found'})

@app.route('/api/v1/student/<int:id>/subject/<int:pk>', methods=['DELETE'])
@jwt_required()
def delete_student_subject(id,pk):
    stud = Student.query.get(id)
    subj = Subject.query.get(pk)
    if stud and subj:
        if not subj in stud.subjects.all():
            return({'error':'student cannot delete resource'})
        stud.subjects.remove(subj)
        db.session.commit()
        return({'success':'resource has been deleted'})
    else:
        return jsonify({'error':'resource not found'})

@app.errorhandler(404)
def page_not_found(e):
	return make_response(jsonify({'error':'not found'}),404)

@app.errorhandler(500)
def server_error(e):
	return make_response(jsonify({'error':'an uncaught exception occurred'}),500)

@app.errorhandler(403)
def forbidden(e):
	return make_response(jsonify({'error':'resource access forbidden'}))

@app.errorhandler(405)
def forbidden(e):
	return make_response(jsonify({'error':'method not allowed'}),405)






if __name__ == '__main__':
    app.run(debug=True, port=5000)
