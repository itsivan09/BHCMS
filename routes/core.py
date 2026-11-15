import logging
import os
from datetime import date, datetime

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from werkzeug.utils import secure_filename

from models import CommunityEvent, InventoryItem, Notification, PUROK_CHOICES, Patient, db
from utils import role_required, sanitize_input

logger = logging.getLogger(__name__)

core_bp = Blueprint('core', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def _allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@core_bp.route('/favicon.ico', endpoint='favicon')
def favicon():
    return send_from_directory(
        os.path.join(current_app.root_path, 'static', 'images'),
        'opol_logos.jpg',
        mimetype='image/jpeg'
    )


@core_bp.route('/', endpoint='dashboard')
@login_required
def dashboard():
    try:
        Notification.check_and_create_low_stock_notifications()
        Notification.check_and_create_expiry_notifications()
        total_patients = Patient.query.count()
        pregnant_patients = Patient.query.filter_by(is_pregnant=True).count()
        low_stock_items = InventoryItem.query.filter(InventoryItem.quantity <= InventoryItem.min_stock_level).all()
        purok_distribution = db.session.query(Patient.purok, func.count(Patient.id).label('count')).group_by(Patient.purok).all()
        purok_data = {purok: count for purok, count in purok_distribution}
        unread_notifications_count = Notification.get_unread_count()
        return render_template(
            'dashboard.html',
            total_patients=total_patients,
            pregnant_patients=pregnant_patients,
            low_stock_items=low_stock_items,
            purok_data=purok_data,
            purok_choices=PUROK_CHOICES,
            unread_notifications_count=unread_notifications_count,
        )
    except Exception as e:
        logger.error(f'Error loading dashboard: {str(e)}')
        flash('An error occurred.', 'danger')
        return render_template(
            'dashboard.html',
            total_patients=0,
            pregnant_patients=0,
            low_stock_items=[],
            purok_data={},
            purok_choices=PUROK_CHOICES,
            unread_notifications_count=0,
        )


@core_bp.route('/search_patients', endpoint='search_patients')
@login_required
def search_patients():
    try:
        q = request.args.get('q', '').strip()
        if not q:
            return jsonify([])
        try:
            patients = Patient.query.filter_by(id=int(q)).all()
        except ValueError:
            patients = Patient.query.filter(Patient.full_name.ilike(f'%{q}%')).all()
        return jsonify([
            {
                'id': patient.id,
                'full_name': patient.full_name,
                'purok': patient.purok,
                'birth_date': patient.birth_date.strftime('%b %d, %Y') if patient.birth_date else 'N/A',
                'gender': patient.gender,
                'is_pregnant': patient.is_pregnant,
            }
            for patient in patients
        ])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@core_bp.route('/notifications', endpoint='notifications')
@login_required
def notifications():
    try:
        user_notifications = Notification.get_user_notifications(
            current_user.id if current_user.is_authenticated else None,
            limit=100,
        )
        return render_template('notifications.html', notifications=user_notifications)
    except Exception:
        flash('An error occurred.', 'danger')
        return redirect(url_for('core.dashboard'))


@core_bp.route('/mark_notification_read/<int:notification_id>', methods=['POST'], endpoint='mark_notification_read')
@login_required
def mark_notification_read(notification_id):
    try:
        success = Notification.mark_as_read(notification_id, current_user.id if current_user.is_authenticated else None)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@core_bp.route('/api/notifications/unread_count', endpoint='get_unread_notifications_count')
@login_required
def get_unread_notifications_count():
    try:
        return jsonify({'count': Notification.get_unread_count(current_user.id if current_user.is_authenticated else None)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@core_bp.route('/api/notifications/recent', endpoint='get_recent_notifications')
@login_required
def get_recent_notifications():
    try:
        uid = current_user.id if current_user.is_authenticated else None
        notifications = Notification.get_user_notifications(uid, limit=10)
        return jsonify({
            'notifications': [
                {
                    'id': n.id,
                    'type': n.type,
                    'title': n.title,
                    'message': n.message[:90] + ('...' if len(n.message) > 90 else ''),
                    'is_read': n.is_read,
                    'created_at': n.created_at.strftime('%b %d, %I:%M %p'),
                }
                for n in notifications
            ]
        })
    except Exception:
        return jsonify({'notifications': []}), 500


@core_bp.route('/community-events', methods=['GET', 'POST'], endpoint='community_events')
@login_required
@role_required('BHW', 'Admin')
def community_events():
    try:
        if request.method == 'POST':
            title = sanitize_input(request.form.get('title'))
            event_date_str = request.form.get('event_date')
            location = sanitize_input(request.form.get('location'))
            attendees_count = int(request.form.get('attendees_count', 0))
            topic = sanitize_input(request.form.get('topic'))
            notes = request.form.get('notes')
            image_filename = None

            if 'event_image' in request.files:
                file = request.files['event_image']
                if file and file.filename != '' and _allowed_file(file.filename):
                    ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
                    new_filename = f"event_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
                    supabase_url = current_app.config.get('SUPABASE_URL')
                    supabase_key = current_app.config.get('SUPABASE_KEY')
                    if supabase_url and supabase_key:
                        try:
                            from supabase import create_client
                            sb = create_client(supabase_url, supabase_key)
                            file_bytes = file.read()
                            sb.storage.from_('community-events').upload(
                                path=new_filename,
                                file=file_bytes,
                                file_options={"content-type": file.content_type or "image/jpeg"}
                            )
                            image_filename = sb.storage.from_('community-events').get_public_url(new_filename)
                        except Exception as upload_err:
                            logger.warning(f"Supabase storage upload failed: {upload_err}")
                    if not image_filename:
                        try:
                            file.seek(0)
                            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], new_filename))
                            image_filename = new_filename
                        except Exception as save_err:
                            logger.warning(f"Local file save failed: {save_err}")

            if not title or not event_date_str:
                flash('Event title and date are required.', 'danger')
                return redirect(url_for('core.community_events'))

            db.session.add(CommunityEvent(
                title=title,
                event_date=datetime.strptime(event_date_str, '%Y-%m-%d').date(),
                location=location,
                attendees_count=attendees_count,
                topic=topic,
                notes=notes,
                image_filename=image_filename,
                organizer_id=current_user.id,
            ))
            db.session.commit()
            flash(f'Event "{title}" recorded successfully!', 'success')
            return redirect(url_for('core.community_events'))

        events = CommunityEvent.query.order_by(CommunityEvent.event_date.desc()).all()
        return render_template('community_events.html', events=events)
    except Exception as e:
        logger.error(f'Error in community events: {str(e)}')
        flash(f'An error occurred: {str(e)}', 'danger')
        return redirect(url_for('bhw_dashboard'))
