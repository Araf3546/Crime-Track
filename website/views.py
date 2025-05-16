from flask import Blueprint, jsonify, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from .models import Crime, User, Category, Chat, Volunteer, Event, EventParticipant, Feedback
from . import db
from datetime import datetime
from collections import defaultdict
from collections import Counter
import folium
from geopy.geocoders import Nominatim
import requests
import random
from sqlalchemy import func as sql_func
from .models import Contribution, AppreciationMessage

views = Blueprint('views', __name__)

response = None
brac_location = [23.7725, 90.4253]
default_location = brac_location  
zoom_level = 14
searched_location = None 
m = folium.Map(
    location=default_location,
    zoom_start=zoom_level,
    tiles='cartodbdark_matter'
)
crime_locations = []


@views.route('/', methods=['GET', 'POST'])
@login_required
def home():
    chats = Chat.query.all()
    crimes = Crime.query.all()
    categories = Category.query.all()
    
    for crime in crimes:
        crime.user = User.query.get(crime.user_id)
        if crime.location and crime.location not in crime_locations:
            crime_locations.append(crime.location)
            

    return render_template("home.html",
                          user=current_user, 
                          crimes=crimes, 
                          categories=categories, 
                          chats=chats)

@views.route('/send-chat', methods=['POST'])
@login_required
def send_chat():
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'status': 'error', 'message': 'Invalid request'}), 400

    text = request.form.get('text')
    if not text or len(text.strip()) < 1:
        return jsonify({'status': 'error', 'message': 'Message cannot be empty'}), 400

    new_message = Chat(user_id=current_user.id, text=text)
    db.session.add(new_message)
    db.session.commit()

    return jsonify({
        'status': 'success',
        'chat': {
            'id': new_message.id,
            'text': new_message.text,
            'timestamp': new_message.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'can_delete': current_user.id == new_message.user_id or current_user.id == 1
        }
    })

@views.route('/delete-chat/<int:chat_id>', methods=['POST'])
@login_required
def delete_chat(chat_id):
    chat = Chat.query.filter_by(id=chat_id).first_or_404()
    if current_user.id != chat.user_id and current_user.id != 1:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'You can only delete your own messages!'}), 403
        flash('You can only delete your own messages!', category='error')
        return redirect(url_for('views.home'))
    
    db.session.delete(chat)
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'status': 'success', 'message': 'Chat message deleted!', 'chat_id': chat_id})
    else:
        flash('Chat message deleted!', category='success')
        return redirect(url_for('views.home'))

@views.route('/upcoming-events')
@login_required
def upcoming_events():
    events = Event.query.filter(Event.date > datetime.now()).all()
    
    if current_user.id != 1:
        for event in events:
            event.is_interested = EventParticipant.query.filter_by(
                event_id=event.id, 
                user_id=current_user.id
            ).first() is not None
    
    return render_template('upcoming_events.html', events=events, user=current_user)

@views.context_processor
def inject_upcoming_events():
    upcoming_events = Event.query.filter(Event.date > datetime.now()).count()
    return {'upcoming_events': upcoming_events}

@views.route('/manage-events', methods=['GET'])
@login_required
def manage_events():
    if current_user.id != 1:
        flash('Access denied!', category='error')
        return redirect(url_for('views.home'))
    
    events = Event.query.all()
    for event in events:
        event.interested_users = EventParticipant.query.filter_by(event_id=event.id).count()
    return render_template('manage_events.html', user=current_user, events=events)

@views.route('/view-event/<int:event_id>')
@login_required
def view_event(event_id):
    event = Event.query.get_or_404(event_id)
    is_interested = EventParticipant.query.filter_by(
        event_id=event_id, 
        user_id=current_user.id
    ).first() is not None
    return render_template('view_event.html', event=event, user=current_user, is_interested=is_interested)


@views.route('/event-participants/<int:event_id>')
@login_required
def event_participants(event_id):
    if current_user.id != 1:
        return jsonify({'error': 'Unauthorized'}), 403
        
    participants = EventParticipant.query.filter_by(event_id=event_id)\
        .join(User).with_entities(User.email, EventParticipant.signup_date).all()
    return jsonify({'participants': [
        {'email': p.email, 'signup_date': p.signup_date.strftime('%Y-%m-%d %H:%M')} 
        for p in participants
    ]})

@views.route('/create-event', methods=['GET', 'POST'])
@login_required
def create_event():
    if current_user.id != 1:
        flash('Access denied!', category='error')
        return redirect(url_for('views.home'))
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        date = datetime.strptime(request.form.get('date'), '%Y-%m-%dT%H:%M')
        location = request.form.get('location')
        max_participants = request.form.get('max_participants')
        new_event = Event(
            title=title,
            description=description,
            date=date,
            location=location,
            max_participants=max_participants,
            created_by=current_user.id
        )
        db.session.add(new_event)
        db.session.commit()
        flash('Event created successfully!', category='success')
        return redirect(url_for('views.manage_events'))
    return render_template('create_event.html', user=current_user)

@views.route('/edit-event/<int:event_id>', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    if current_user.id != 1:
        flash('Access denied!', category='error')
        return redirect(url_for('views.home'))
    event = Event.query.get_or_404(event_id)
    if request.method == 'POST':
        event.title = request.form.get('title')
        event.description = request.form.get('description')
        event.date = datetime.strptime(request.form.get('date'), '%Y-%m-%dT%H:%M')
        event.location = request.form.get('location')
        event.max_participants = request.form.get('max_participants')
        db.session.commit()
        flash('Event updated successfully!', category='success')
        return redirect(url_for('views.manage_events'))
    return render_template('edit_event.html', event=event, user=current_user)

@views.route('/delete-event/<int:event_id>', methods=['POST'])
@login_required
def delete_event(event_id):
    event = Event.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Event deleted successfully'}), 200

@views.route('/admin-tools', methods=['GET', 'POST'])
@login_required
def admin_tools():
    if current_user.id != 1:
        flash('Access denied!', category='error')
        return redirect(url_for('views.home'))

    crimes = Crime.query.all()
    for crime in crimes:
        crime.user = User.query.get(crime.user_id)
    categories = Category.query.all()

    if request.method == 'POST':
        if 'add-category' in request.form:
            name = request.form.get('category-name')
            if Category.query.filter_by(name=name).first():
                flash('Category already exists.', category='error')
            else:
                new_category = Category(name=name)
                db.session.add(new_category)
                db.session.commit()
                flash('Category added successfully!', category='success')

        elif 'remove-category' in request.form:
            cat_id = request.form.get('category-id')
            category = Category.query.get(cat_id)
            if category:
                db.session.delete(category)
                db.session.commit()
                flash('Category removed successfully!', category='success')
            else:
                flash('Category not found.', category='error')
    
    return render_template('admin_tools.html', user=current_user, crimes=crimes, categories=categories)

@views.route('/stats', methods=['GET'])
@login_required
def stats():
    crimes = Crime.query.all()
    location_filter = request.args.get('location', '')
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')

    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    else:
        start_date = datetime.min  
    
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    else:
        end_date = datetime.max 

    filtered_crimes = [
        crime for crime in crimes
        if (start_date <= crime.date <= end_date) and (location_filter == '' or crime.location == location_filter)
    ]

    # Calculate counts only from filtered crimes
    location_counts = Counter([crime.location for crime in filtered_crimes])
    locations = list(location_counts.keys())
    counts = list(location_counts.values())

    return render_template('stats.html',
        user=current_user,
        locations=locations,
        counts=counts,
        location_filter=location_filter,
        crime_count=len(filtered_crimes),
        location_counts=location_counts,
        crimes=filtered_crimes)  # Changed from crimes to filtered_crimes

@views.route('/delete-crime/<int:crime_id>', methods=['POST'])
@login_required
def delete_crime(crime_id):
    if current_user.id != 1:  
        flash('Access denied!', category='error')
        return redirect(url_for('views.home'))

    crime = Crime.query.get(crime_id)
    if crime:
        db.session.delete(crime)
        db.session.commit()
        flash('Crime deleted successfully!', category='success')
    else:
        flash('Crime not found.', category='error')
    return redirect(url_for('views.admin_tools'))  

# @views.route('/report_crime', methods=['GET', 'POST'])
# @login_required
# def report_crime():
#     crimes = Crime.query.all()
#     categories = Category.query.all()
#     if request.method == 'POST': 
#         title = request.form.get('Title')  
#         location = request.form.get('Location')  
#         data = request.form.get('Description')  
#         category_id = request.form.get('category-id')  

#         if not title or len(title) < 3:
#             flash('Title is too short!', category='error')
#         elif not location or len(location) < 3:
#             flash('Location is too short!', category='error')
#         elif not data or len(data) < 5:
#             flash('Description is too short!', category='error')
#         else:
#             new_crime = Crime(
#                 title=title,
#                 location=location,
#                 data=data,
#                 user_id=current_user.id
#             )
#             db.session.add(new_crime)

#             selected_category = Category.query.filter_by(cat_id=category_id).first()
#             if selected_category:
#                 selected_category.count += 1
#                 db.session.commit()
#                 flash('Crime posted and category updated!', category='success')
#             else:
#                 flash('Invalid category selected!', category='error')
    
#     return render_template("report_crime.html", user=current_user, crimes=crimes, categories=categories)

@views.route('/report_crime', methods=['GET', 'POST'])
@login_required
def report_crime():
    crimes = Crime.query.all()
    categories = Category.query.all()
    if request.method == 'POST': 
        title = request.form.get('Title')  
        location = request.form.get('Location')  
        data = request.form.get('Description')  
        category_id = request.form.get('category-id')  

        if not title or len(title) < 3:
            flash('Title is too short!', category='error')
        elif not location or len(location) < 3:
            flash('Location is too short!', category='error')
        elif not data or len(data) < 5:
            flash('Description is too short!', category='error')
        else:
            new_crime = Crime(
                title=title,
                location=location,
                data=data,
                user_id=current_user.id
            )
            db.session.add(new_crime)

            # Track contribution for crime report
            contribution = Contribution(
                user_id=current_user.id,
                activity_type='crime_report',
                score=1
            )
            db.session.add(contribution)

            selected_category = Category.query.filter_by(cat_id=category_id).first()
            if selected_category:
                selected_category.count += 1
                db.session.commit()
                flash('Crime posted and category updated!', category='success')
            else:
                flash('Invalid category selected!', category='error')
    
    return render_template("report_crime.html", user=current_user, crimes=crimes, categories=categories)


@views.route('/law_enforcement', methods=['GET', 'POST'])
@login_required
def law_enforcement():
    if current_user.id != 1: 
        flash('Access denied!', category='error')
        return redirect(url_for('views.home'))

    crimes = Crime.query.all()  
    for crime in crimes:
        crime.user = User.query.get(crime.user_id)
    return render_template('law_enforcement.html', user=current_user, crimes=crimes)

@views.route('/community_resources', methods=['GET'])
@login_required
def community_resources():
    return render_template('community_resources.html', user=current_user)

@views.route('/public_awareness', methods=['GET'])
@login_required
def public_awareness():
    return render_template('public_awareness.html', user=current_user)

@views.route('/educational_resources', methods=['GET'])
@login_required
def educational_resources():
    return render_template('educational_resources.html', user=current_user)

def get_upcoming_events():
    """Helper function to get upcoming events"""
    upcoming_events = Event.query.filter(Event.date > datetime.now()).count()
    return render_template('upcoming_events.html', 
        user=current_user,
        upcoming_events=upcoming_events,
        new_events=upcoming_events > 0
    )

@views.route('/show_interest/<int:event_id>', methods=['POST'])
@login_required
def show_interest(event_id):
    if current_user.id == 1:
        return jsonify({'error': 'Admin cannot show interest in events'}), 400
        
    existing = EventParticipant.query.filter_by(
        event_id=event_id, 
        user_id=current_user.id
    ).first()
    
    if existing:
        db.session.delete(existing)
        message = 'Removed interest from event'
        # Remove contribution
        Contribution.query.filter_by(
            user_id=current_user.id,
            activity_type='event_interest',
            event_id=event_id
        ).delete()
    else:
        participant = EventParticipant(event_id=event_id, user_id=current_user.id)
        db.session.add(participant)
        # Check if user already has a contribution for this event
        prior_contribution = Contribution.query.filter_by(
            user_id=current_user.id,
            activity_type='event_interest',
            event_id=event_id
        ).first()
        if not prior_contribution:
            # Add contribution only if no prior contribution exists
            contribution = Contribution(
                user_id=current_user.id,
                activity_type='event_interest',
                score=1,
                event_id=event_id  # Include event_id to track unique event contributions
            )
            db.session.add(contribution)
        message = 'Showed interest in event'
    
    db.session.commit()
    return jsonify({
        'message': message,
        'is_interested': existing is None
    })

def clear_markers():
    global m, default_location, zoom_level
    m = folium.Map(
        location=default_location,
        zoom_start=zoom_level,
        tiles='cartodbdark_matter',
    )

def safe_geocode(location_str, attempts=3, timeout=5):
    """Helper function to safely geocode locations with retries"""
    if not location_str:
        return None
        
    geolocator = Nominatim(user_agent="crime_map", timeout=timeout)
    
    for _ in range(attempts):
        try:
            return geolocator.geocode(location_str)
        except Exception as e:
            print(f"Geocoding error for {location_str}: {str(e)}")
            continue
    return None

@views.route('/live-map', methods=['GET', 'POST'])
@login_required
def live_map():
    global response, brac_location, default_location, zoom_level, searched_location, m
    response = None
    clear_markers()
    m = folium.Map(
        location=default_location,
        zoom_start=zoom_level,
        tiles='cartodbdark_matter'
    )
    
    # Add BRAC University marker
    folium.CircleMarker(
        location=brac_location,
        radius=10,
        color="blue",
        fill=True,
        fill_color="blue",
        fill_opacity=0.6,
        popup="BRAC University"
    ).add_to(m)
    
    # Add all crime locations from database
    crimes = Crime.query.all()
    for crime in crimes:
        if crime.location:
            location = safe_geocode(crime.location)
            if location:
                folium.CircleMarker(
                    location=[location.latitude, location.longitude],
                    radius=random.randint(10,50),
                    color="red",
                    fill=True,
                    fill_color="red",
                    fill_opacity=0.4,
                    popup=f"Crime: {crime.title}<br>Location: {crime.location}<br>Date: {crime.date.strftime('%Y-%m-%d')}"
                ).add_to(m)
    
    # Handle search functionality
    if request.method == 'POST':
        search_query = request.form.get('location')
        if search_query:
            location = safe_geocode(search_query)
            if location:
                searched_location = [location.latitude, location.longitude]
                folium.Marker(
                    searched_location,
                    popup=location.address,
                    tooltip="Searched Location",
                    icon=folium.Icon(color="green")
                ).add_to(m)
                m.location = searched_location
            else:
                flash('Location could not be found. Please try again.', category='error')

    # Handle user location centering
    elif 'center_on_user' in request.args:
        clear_markers()
        response = requests.get("https://ipinfo.io/json")
        if response and response.status_code == 200:
            data = response.json()
            location = data.get("loc", "")
            if location:
                latitude, longitude = map(float, location.split(","))
                user_location = [float(latitude), float(longitude)]
                folium.CircleMarker(
                    location=user_location,
                    radius=15,
                    color="blue",
                    fill=True,
                    fill_color="blue",
                    fill_opacity=0.6,
                    popup="Your Location"
                ).add_to(m)
                folium.Marker(user_location, popup="Your Location", icon=folium.Icon(color="red")).add_to(m)
                m.location = user_location
            else:
                folium.CircleMarker(
                    location=brac_location,
                    radius=10,
                    color="blue",
                    fill=True,
                    fill_color="blue",
                    fill_opacity=0.6,
                    popup="BRAC University"
                ).add_to(m)
                folium.Marker(brac_location, popup="BRAC University", icon=folium.Icon(color="red")).add_to(m)
                m.location = brac_location
 
    map_html = m._repr_html_()
    return render_template('live_map.html', map_html=map_html, user=current_user)


@views.route('/volunteer_signup', methods=['GET', 'POST'])
@login_required
def volunteer_signup():
    if request.method == 'POST':
        phone = request.form.get('phone')
        location = request.form.get('location')
        
        if not phone or len(phone) < 10:
            flash('Invalid phone number!', category='error')
        elif not location or len(location) < 3:
            flash('Location is too short!', category='error')
        else:
            new_volunteer = Volunteer(
                name=current_user.first_name,
                email=current_user.email,
                phone=phone,
                location=location,
                user_id=current_user.id
            )
            db.session.add(new_volunteer)

            # Track contribution for volunteer signup
            contribution = Contribution(
                user_id=current_user.id,
                activity_type='volunteer_signup',
                score=1
            )
            db.session.add(contribution)

            db.session.commit()
            flash('Volunteer application sent successfully!', category='success')
            return redirect(url_for('views.home'))

    return render_template("volunteer_signup.html", user=current_user)


@views.route('/feedbacks', methods=['GET', 'POST'])
@login_required
def feedback():
    if request.method == 'POST':
        feedback_text = request.form.get('feedback')
        if feedback_text:
            new_feedback = Feedback(
                text=feedback_text,
                user_id=current_user.id
            )
            db.session.add(new_feedback)
            db.session.commit()
            flash("Thank you for your feedback!", category='success')
            return redirect(url_for('views.home'))
        else:
            flash("Feedback cannot be empty.", category='error')
    return render_template('feedback.html', user=current_user)

@views.route('/user_contributions')
@login_required
def user_contributions():
    contributions = Contribution.query.filter_by(user_id=current_user.id).order_by(Contribution.created_at.desc()).all()
    total_score = sum(c.score for c in contributions)
    messages = AppreciationMessage.query.filter_by(user_id=current_user.id).order_by(AppreciationMessage.created_at.desc()).all()
    return render_template('user_contributions.html', user=current_user, contributions=contributions, total_score=total_score, messages=messages)

@views.route('/admin_contributions', methods=['GET', 'POST'])
@login_required
def admin_contributions():
    if current_user.id != 1:
        flash('Access denied!', category='error')
        return redirect(url_for('views.home'))

    # Get top 3 scorers
    top_scorers = db.session.query(
        User.id,
        User.first_name,
        sql_func.sum(Contribution.score).label('total_score'),
        sql_func.max(Contribution.created_at).label('last_activity')
    ).join(Contribution).group_by(User.id, User.first_name).order_by(
        sql_func.sum(Contribution.score).desc(),
        sql_func.max(Contribution.created_at).desc()
    ).limit(3).all()

    # Get all users with contributions for messaging
    users_with_contributions = db.session.query(
        User.id,
        User.first_name,
        sql_func.sum(Contribution.score).label('total_score')
    ).join(Contribution).group_by(User.id, User.first_name).all()

    if request.method == 'POST':
        user_id = request.form.get('user_id')
        message = request.form.get('message')
        if user_id and message:
            appreciation = AppreciationMessage(
                user_id=user_id,
                message=message
            )
            db.session.add(appreciation)
            db.session.commit()
            flash('Appreciation message sent!', category='success')
        else:
            flash('User and message are required!', category='error')

    return render_template(
        'admin_contributions.html',
        user=current_user,
        top_scorers=top_scorers,
        users_with_contributions=users_with_contributions
    )

@views.route('/user_contributions/<int:user_id>')
@login_required
def view_user_contributions(user_id):
    if current_user.id != 1:
        flash('Access denied!', category='error')
        return redirect(url_for('views.home'))
    
    user = User.query.get_or_404(user_id)
    contributions = Contribution.query.filter_by(user_id=user_id).order_by(Contribution.created_at.desc()).all()
    total_score = sum(c.score for c in contributions)
    return render_template(
        'view_user_contributions.html',
        user=current_user,
        target_user=user,
        contributions=contributions,
        total_score=total_score
    )