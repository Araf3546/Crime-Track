from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func
from datetime import datetime

class Crime(db.Model):
    __tablename__ = 'crime'
    __table_args__ = {'extend_existing': True}  
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    location = db.Column(db.String(100))
    data = db.Column(db.String(10000))
    date = db.Column(db.DateTime(timezone=True), default=func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Chat(db.Model):
    __tablename__ = 'chat'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    text = db.Column(db.String(1500))
    timestamp = db.Column(db.DateTime(timezone=True), default=func.now())

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    first_name = db.Column(db.String(150))
    crimes = db.relationship('Crime', backref='user', lazy=True)

class Category(db.Model):
    cat_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    count = db.Column(db.Integer, default=0)

class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)
    crime_reported = db.Column(db.String(10000))
    count = db.Column(db.Integer, default=0)
    emergency_number = db.Column(db.String(15))

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150))
    description = db.Column(db.Text)
    date = db.Column(db.DateTime)
    location = db.Column(db.String(150))
    max_participants = db.Column(db.Integer)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_by_user = db.relationship('User', foreign_keys=[created_by])
    participants = db.relationship('EventParticipant', backref='event', lazy=True)

class EventParticipant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    signup_date = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<EventParticipant Event {self.event_id} User {self.user_id}>'

class Volunteer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    email = db.Column(db.String(150))
    phone = db.Column(db.String(20))
    location = db.Column(db.String(150))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date_created = db.Column(db.DateTime(timezone=True), default=func.now())

    def __repr__(self):
        return f'<Volunteer {self.name}>'

class Feedback(db.Model):
    __tablename__ = 'feedback'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('feedbacks', lazy=True))

    def __repr__(self):
        return f'<Feedback {self.text[:20]}>'
    

class Contribution(db.Model):
    __tablename__ = 'contribution'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)
    score = db.Column(db.Integer, default=1, nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'))  # Add this line
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
    user = db.relationship('User', backref=db.backref('contributions', lazy=True))
    event = db.relationship('Event')  # Add relationship to Event

    def __repr__(self):
        return f'<Contribution {self.activity_type} for User {self.user_id}>'
    
class AppreciationMessage(db.Model):
    __tablename__ = 'appreciation_message'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
    user = db.relationship('User', backref=db.backref('appreciation_messages', lazy=True))

    def __repr__(self):
        return f'<AppreciationMessage for User {self.user_id}>'