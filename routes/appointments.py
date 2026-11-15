import logging
import re
from datetime import date, datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import Appointment, Notification, PUROK_CHOICES, Patient, User, db
from utils import is_valid_full_name_format, role_required, send_email

logger = logging.getLogger(__name__)

appointments_bp = Blueprint('appointments', __name__)

FULL_NAME_FORMAT_HINT = 'Use: Last Name First Name (optional: Second Name and/or M.I.)'


def _appointment_email_html(patient_name, appt_date_str, appt_time_str, worker_name):
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9f9f9;padding:24px;border-radius:8px;">
        <div style="background:#0e7c86;padding:16px 24px;border-radius:8px 8px 0 0;">
            <h2 style="color:#fff;margin:0;">🏥 BHCMS Appointment Reminder</h2>
        </div>
        <div style="background:#fff;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e0e0e0;">
            <p style="font-size:16px;">Hi <strong>{patient_name}</strong>,</p>
            <p style="font-size:15px;">This is a reminder that you have an upcoming appointment:</p>
            <table style="width:100%;border-collapse:collapse;margin:16px 0;">
                <tr><td style="padding:8px;background:#f0f8f9;font-weight:bold;width:40%;">📅 Date</td>
                    <td style="padding:8px;">{appt_date_str}</td></tr>
                <tr><td style="padding:8px;background:#f0f8f9;font-weight:bold;">⏰ Time</td>
                    <td style="padding:8px;">{appt_time_str}</td></tr>
                <tr><td style="padding:8px;background:#f0f8f9;font-weight:bold;">👤 Healthcare Worker</td>
                    <td style="padding:8px;">{worker_name}</td></tr>
            </table>
            <p style="color:#555;">Please arrive on time. If you need to reschedule, contact the health center.</p>
            <p style="color:#888;font-size:12px;">— Barangay Health Center Management System (BHCMS)</p>
        </div>
    </div>"""


def _notify_appointment_activity(appointment, action: str, actor_name: str):
    patient_name = appointment.patient.full_name
    worker_name = appointment.health_worker.full_name
    appt_date = appointment.appointment_date.strftime('%B %d, %Y')
    appt_time = appointment.appointment_time.strftime('%I:%M %p')

    titles = {
        'booked': f'Appointment Booked: {patient_name}',
        'cancelled': f'Appointment Cancelled: {patient_name}',
        'completed': f'Appointment Completed: {patient_name}'
    }
    messages = {
        'booked': (
            f'{patient_name} was booked with {worker_name} on {appt_date} at {appt_time}. '
            f'Action by {actor_name}.'
        ),
        'cancelled': (
            f'Appointment for {patient_name} with {worker_name} on {appt_date} at {appt_time} '
            f'was cancelled by {actor_name}.'
        ),
        'completed': (
            f'Appointment for {patient_name} with {worker_name} on {appt_date} at {appt_time} '
            f'was marked completed by {actor_name}.'
        )
    }

    recipient_ids = {appointment.health_worker_id}
    staff_users = User.query.filter(User.role.in_(['Admin', 'Midwife'])).all()
    for user in staff_users:
        recipient_ids.add(user.id)

    for recipient_id in recipient_ids:
        db.session.add(Notification(
            user_id=recipient_id,
            type='appointment',
            title=titles.get(action, 'Appointment Update'),
            message=messages.get(action, f'Appointment #{appointment.id} updated by {actor_name}.'),
            related_item_id=appointment.id,
            related_item_type='appointment_activity'
        ))


@appointments_bp.route('/appointments')
@login_required
@role_required('BHW', 'Midwife', 'Admin')
def view_appointments():
    try:
        if current_user.role in ['Admin', 'Midwife']:
            appointments = Appointment.query.order_by(Appointment.appointment_date.desc()).all()
        else:
            appointments = Appointment.query.filter_by(health_worker_id=current_user.id).order_by(Appointment.appointment_date.desc()).all()

        all_patients = Patient.query.order_by(Patient.full_name).all()
        all_workers = User.query.filter(User.role.in_(['Midwife', 'BHW', 'Admin'])).all()
        return render_template(
            'appointments.html',
            appointments=appointments,
            patients=all_patients,
            health_workers=all_workers,
            today=date.today().strftime('%Y-%m-%d'),
            purok_choices=PUROK_CHOICES,
        )
    except Exception as e:
        logger.error(f'Error loading appointments: {str(e)}')
        flash('An error occurred.', 'danger')
        return redirect(url_for('core.dashboard'))


@appointments_bp.route('/appointment/book', methods=['POST'])
@login_required
@role_required('BHW', 'Midwife', 'Admin')
def book_appointment():
    try:
        patient_name = request.form.get('patient_name', '').strip()
        worker_name = request.form.get('worker_name', '').strip()
        reason = request.form.get('reason', '')
        date_str = request.form.get('appointment_date')
        time_str = request.form.get('appointment_time')
        contact_number = request.form.get('contact_number', '').strip()
        email = request.form.get('email', '').strip()

        if not all([patient_name, worker_name, date_str, time_str]):
            flash('All required fields must be filled.', 'warning')
            return redirect(url_for('appointments.view_appointments'))

        if email and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            flash('Please enter a valid email address.', 'warning')
            return redirect(url_for('appointments.view_appointments'))

        patient = Patient.query.filter(Patient.full_name.ilike(patient_name)).first()
        if not patient:
            patient = Patient.query.filter(Patient.full_name.ilike(f'%{patient_name}%')).first()

        if not patient:
            new_birth_date_str = request.form.get('new_birth_date', '').strip()
            new_gender = request.form.get('new_gender', '').strip()
            new_purok = request.form.get('new_purok', 'Other').strip() or 'Other'

            if not is_valid_full_name_format(patient_name):
                flash(f'Patient name must follow this format: {FULL_NAME_FORMAT_HINT}', 'danger')
                return redirect(url_for('appointments.view_appointments'))

            if not new_birth_date_str or not new_gender:
                flash(f'Patient "{patient_name}" not found. Please provide birth date and gender to register them.', 'danger')
                return redirect(url_for('appointments.view_appointments'))
            try:
                new_bday = datetime.strptime(new_birth_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid birth date format.', 'danger')
                return redirect(url_for('appointments.view_appointments'))

            if new_bday > date.today():
                flash('Birth date cannot be in the future.', 'danger')
                return redirect(url_for('appointments.view_appointments'))

            new_age = (date.today() - new_bday).days // 365
            if new_age < 0 or new_age > 150:
                flash('Please enter a valid birth date.', 'danger')
                return redirect(url_for('appointments.view_appointments'))

            patient = Patient(
                full_name=patient_name,
                birth_date=new_bday,
                gender=new_gender,
                purok=new_purok,
                is_pregnant=False,
                email=email if email else None,
                contact_number=contact_number if contact_number else None,
            )
            db.session.add(patient)
            db.session.flush()
            flash(f'New patient "{patient_name}" registered and appointment booked successfully.', 'success')
        else:
            if contact_number and patient.contact_number != contact_number:
                patient.contact_number = contact_number
            if email and patient.email != email:
                patient.email = email

        worker = User.query.filter(User.full_name.ilike(f'%{worker_name}%')).first()
        if not worker:
            worker = current_user
            reason = f"{reason} (Attn: {worker_name})" if reason else f"Attn: {worker_name}"

        appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        appt_time = datetime.strptime(time_str, '%H:%M').time()
        conflict = Appointment.check_conflict(worker.id, appt_date, appt_time)
        if conflict['has_conflict']:
            flash(f"This time slot is unavailable ({conflict['message']}).", 'warning')
            return redirect(url_for('appointments.view_appointments'))

        new_appointment = Appointment(
            patient_id=patient.id,
            health_worker_id=worker.id,
            appointment_date=appt_date,
            appointment_time=appt_time,
            reason=reason,
            status='scheduled'
        )
        db.session.add(new_appointment)
        db.session.flush()
        _notify_appointment_activity(
            new_appointment,
            action='booked',
            actor_name=(current_user.full_name or current_user.username)
        )
        db.session.commit()

        patient_email = getattr(patient, 'email', None)
        if patient_email:
            email_html = _appointment_email_html(
                patient.full_name,
                appt_date.strftime('%B %d, %Y'),
                appt_time.strftime('%I:%M %p'),
                worker.full_name
            )
            email_text = (
                f'BHCMS: Hi {patient.full_name}, your appointment is confirmed on '
                f'{appt_date.strftime("%b %d, %Y")} at {appt_time.strftime("%I:%M %p")} '
                f'with {worker.full_name}.'
            )
            email_result = send_email(
                to_address=patient_email,
                subject=f'BHCMS Appointment Confirmed – {appt_date.strftime("%b %d, %Y")}',
                body_html=email_html,
                body_text=email_text
            )
            if not email_result.get('success'):
                logger.warning(f"Email send failed for appointment {new_appointment.id}: {email_result.get('error')}")

        flash(f'Appointment confirmed for {patient.full_name}.', 'success')
        return redirect(url_for('appointments.view_appointments'))
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error booking appointment: {str(e)}')
        flash('An error occurred while booking.', 'danger')
        return redirect(url_for('appointments.view_appointments'))


@appointments_bp.route('/appointment/check-availability', methods=['GET'])
@login_required
@role_required('BHW', 'Midwife', 'Admin')
def check_availability():
    try:
        worker = User.query.filter(User.full_name.ilike(f'%{request.args.get("worker_name")}%')).first()
        if not worker:
            return jsonify({'available': True})

        conflict = Appointment.check_conflict(
            worker.id,
            datetime.strptime(request.args.get('date'), '%Y-%m-%d').date(),
            datetime.strptime(request.args.get('time'), '%H:%M').time()
        )
        return jsonify({'available': not conflict['has_conflict'], 'message': conflict['message']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@appointments_bp.route('/appointment/<int:appointment_id>/cancel', methods=['POST'])
@login_required
@role_required('BHW', 'Midwife', 'Admin')
def cancel_appointment(appointment_id):
    try:
        appointment = Appointment.query.get_or_404(appointment_id)
        if current_user.id != appointment.health_worker_id and current_user.role not in ['Admin', 'Midwife']:
            flash('Permission denied.', 'danger')
            return redirect(url_for('appointments.view_appointments'))

        appointment.status = 'cancelled'
        _notify_appointment_activity(
            appointment,
            action='cancelled',
            actor_name=(current_user.full_name or current_user.username)
        )
        db.session.commit()
        flash('Appointment cancelled successfully.', 'success')
        return redirect(url_for('appointments.view_appointments'))
    except Exception as e:
        logger.error(f'Error cancelling appointment {appointment_id}: {str(e)}')
        flash('An error occurred.', 'danger')
        return redirect(url_for('appointments.view_appointments'))


@appointments_bp.route('/appointment/<int:appointment_id>/complete', methods=['POST'])
@login_required
@role_required('BHW', 'Midwife', 'Admin')
def complete_appointment(appointment_id):
    try:
        appointment = Appointment.query.get_or_404(appointment_id)
        if current_user.id != appointment.health_worker_id and current_user.role not in ['Admin', 'Midwife']:
            flash('Permission denied.', 'danger')
            return redirect(url_for('appointments.view_appointments'))

        appointment.status = 'completed'
        _notify_appointment_activity(
            appointment,
            action='completed',
            actor_name=(current_user.full_name or current_user.username)
        )
        db.session.commit()
        flash(f'Appointment for {appointment.patient.full_name} marked as completed.', 'success')
        return redirect(url_for('appointments.view_appointments'))
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error completing appointment {appointment_id}: {str(e)}')
        flash('An error occurred.', 'danger')
        return redirect(url_for('appointments.view_appointments'))


@appointments_bp.route('/test-email', methods=['POST'])
@login_required
@role_required('Admin', 'Midwife')
def test_email():
    to_address = request.form.get('test_email_address', '').strip()
    if not to_address or '@' not in to_address:
        flash('Please enter a valid email address to test.', 'warning')
        return redirect(url_for('appointments.view_appointments'))

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:24px;">
        <div style="background:#0e7c86;padding:16px 24px;border-radius:8px 8px 0 0;">
            <h2 style="color:#fff;margin:0;">✅ BHCMS Test Email</h2>
        </div>
        <div style="background:#fff;padding:24px;border:1px solid #e0e0e0;border-radius:0 0 8px 8px;">
            <p>This is a test email from the <strong>Barangay Health Center Management System</strong>.</p>
            <p>Gmail SMTP is configured correctly! Appointment reminders will be delivered to this inbox.</p>
            <p style="color:#888;font-size:12px;">Sent by: {current_user.full_name} ({current_user.role})</p>
        </div>
    </div>"""

    result = send_email(
        to_address=to_address,
        subject='BHCMS – Test Email (Gmail SMTP)',
        body_html=html_body,
        body_text='This is a test email from BHCMS. Gmail SMTP is working correctly.'
    )

    if result.get('success'):
        flash(f'✅ Test email sent successfully to {to_address}!', 'success')
    else:
        flash(f'❌ Test email failed: {result.get("error")}', 'danger')

    return redirect(url_for('appointments.view_appointments'))
