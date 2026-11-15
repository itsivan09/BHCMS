import logging
import re
from datetime import date, datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import (
    Appointment,
    Consultation,
    DispensedMedicine,
    ImmunizationSchedule,
    OperationTimbang,
    PUROK_CHOICES,
    Patient,
    PrenatalRecord,
    db,
)
from utils import is_valid_full_name_format, role_required, sanitize_input

logger = logging.getLogger(__name__)

patients_bp = Blueprint('patients', __name__)

FULL_NAME_FORMAT_HINT = 'Use: Last Name First Name (optional: Second Name and/or M.I.)'


@patients_bp.route('/patients', methods=['GET', 'POST'])
@login_required
def patients():
    if request.method == 'POST':
        if current_user.role not in ['BHW', 'Midwife', 'Admin']:
            flash('Access denied. You are not allowed to add patients.', 'danger')
            return redirect(url_for('patients.patients'))
        try:
            full_name = sanitize_input(request.form.get('full_name', ''))
            birth_date_str = request.form.get('birth_date', '')
            gender = sanitize_input(request.form.get('gender', ''))
            purok = sanitize_input(request.form.get('purok', ''))
            address = sanitize_input(request.form.get('address', ''))
            email = sanitize_input(request.form.get('email', ''))
            contact_number = sanitize_input(request.form.get('contact_number', ''))
            if not full_name or not birth_date_str or not gender or not purok:
                flash('Full name, birth date, gender, and purok are required.', 'danger')
                return redirect(url_for('patients.patients'))
            if len(full_name) < 2 or len(full_name) > 100:
                flash('Full name must be between 2 and 100 characters.', 'danger')
                return redirect(url_for('patients.patients'))
            if not is_valid_full_name_format(full_name):
                flash(f'Full name must follow this format: {FULL_NAME_FORMAT_HINT}', 'danger')
                return redirect(url_for('patients.patients'))
            if purok not in PUROK_CHOICES:
                flash('Invalid purok/zone selected.', 'danger')
                return redirect(url_for('patients.patients'))
            try:
                bday = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
                if bday > date.today():
                    flash('Birth date cannot be in the future.', 'danger')
                    return redirect(url_for('patients.patients'))
                age = (date.today() - bday).days // 365
                if age < 0 or age > 150:
                    flash('Please enter a valid birth date.', 'danger')
                    return redirect(url_for('patients.patients'))
            except ValueError:
                flash('Invalid birth date format.', 'danger')
                return redirect(url_for('patients.patients'))
            if contact_number and not re.match(r'^[0-9\-\+\(\)\s]{7,20}$', contact_number):
                flash('Please enter a valid contact number.', 'danger')
                return redirect(url_for('patients.patients'))
            if email and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
                flash('Please enter a valid email address.', 'danger')
                return redirect(url_for('patients.patients'))
            is_pregnant = 'is_pregnant' in request.form
            new_patient = Patient(full_name=full_name, birth_date=bday, is_pregnant=is_pregnant,
                                  gender=gender, purok=purok, address=address,
                                  email=(email or None), contact_number=contact_number)
            db.session.add(new_patient)
            db.session.commit()
            flash('Patient added successfully', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error adding patient: {str(e)}')
            flash('An error occurred while adding the patient.', 'danger')
    try:
        all_patients = Patient.query.all()
        return render_template('patients.html', patients=all_patients, purok_choices=PUROK_CHOICES)
    except Exception as e:
        logger.error(f'Error loading patients page: {str(e)}')
        return render_template('patients.html', patients=[], purok_choices=PUROK_CHOICES)


@patients_bp.route('/patient/update', methods=['POST'])
@login_required
def update_patient():
    try:
        patient_id = request.form.get('patient_id')
        patient = Patient.query.get_or_404(patient_id)

        full_name = sanitize_input(request.form.get('full_name', ''))
        birth_date_str = request.form.get('birth_date', '')
        gender = sanitize_input(request.form.get('gender', ''))
        purok = sanitize_input(request.form.get('purok', ''))
        address = sanitize_input(request.form.get('address', ''))
        email = sanitize_input(request.form.get('email', ''))
        contact_number = sanitize_input(request.form.get('contact_number', ''))

        if not full_name or not birth_date_str or not gender or not purok:
            flash('Full name, birth date, gender, and purok are required.', 'danger')
            return redirect(url_for('patients.patients'))

        if len(full_name) < 2 or len(full_name) > 100:
            flash('Full name must be between 2 and 100 characters.', 'danger')
            return redirect(url_for('patients.patients'))

        if not is_valid_full_name_format(full_name):
            flash(f'Full name must follow this format: {FULL_NAME_FORMAT_HINT}', 'danger')
            return redirect(url_for('patients.patients'))

        if purok not in PUROK_CHOICES:
            flash('Invalid purok/zone selected.', 'danger')
            return redirect(url_for('patients.patients'))

        try:
            bday = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid birth date format.', 'danger')
            return redirect(url_for('patients.patients'))

        if bday > date.today():
            flash('Birth date cannot be in the future.', 'danger')
            return redirect(url_for('patients.patients'))

        age = (date.today() - bday).days // 365
        if age < 0 or age > 150:
            flash('Please enter a valid birth date.', 'danger')
            return redirect(url_for('patients.patients'))

        if contact_number and not re.match(r'^[0-9\-\+\(\)\s]{7,20}$', contact_number):
            flash('Please enter a valid contact number.', 'danger')
            return redirect(url_for('patients.patients'))
        if email and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            flash('Please enter a valid email address.', 'danger')
            return redirect(url_for('patients.patients'))

        patient.full_name = full_name
        patient.birth_date = bday
        patient.gender = gender
        patient.purok = purok
        patient.address = address
        patient.email = email or None
        patient.contact_number = contact_number
        patient.is_pregnant = 'is_pregnant' in request.form
        db.session.commit()
        flash(f'Record for {patient.full_name} updated successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating record: {str(e)}', 'danger')
    return redirect(url_for('patients.patients'))


@patients_bp.route('/api/patient/<int:patient_id>/history')
@login_required
def get_patient_history_api(patient_id):
    try:
        consultations = Consultation.query.filter_by(patient_id=patient_id).order_by(Consultation.date.desc()).all()
        return jsonify([{'date': c.date.strftime('%b %d, %Y'), 'type': c.consultation_type,
                         'complaint': c.chief_complaint, 'diagnosis': c.diagnosis or 'N/A',
                         'bp': f"{c.blood_pressure_systolic}/{c.blood_pressure_diastolic}" if c.blood_pressure_systolic else 'N/A'}
                        for c in consultations])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@patients_bp.route('/patient/<int:patient_id>/delete', methods=['POST'])
@login_required
@role_required('Midwife', 'Admin')
def delete_patient(patient_id):
    try:
        patient = Patient.query.get_or_404(patient_id)
        patient_name = patient.full_name
        DispensedMedicine.query.filter(
            DispensedMedicine.consultation_id.in_(
                db.session.query(Consultation.id).filter_by(patient_id=patient_id)
            )).delete(synchronize_session=False)
        Consultation.query.filter_by(patient_id=patient_id).delete()
        PrenatalRecord.query.filter_by(patient_id=patient_id).delete()
        OperationTimbang.query.filter_by(patient_id=patient_id).delete()
        Appointment.query.filter_by(patient_id=patient_id).delete()
        ImmunizationSchedule.query.filter_by(patient_id=patient_id).delete()
        db.session.delete(patient)
        db.session.commit()
        flash(f'Patient {patient_name} has been deleted successfully.', 'success')
        return redirect(url_for('patients.patients'))
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred: {str(e)}', 'danger')
        return redirect(url_for('patients.patients'))
