import logging
from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import HouseholdProfile, OperationTimbang, PUROK_CHOICES, Patient, db
from utils import is_valid_full_name_format, role_required, sanitize_input

logger = logging.getLogger(__name__)

bhw_bp = Blueprint('bhw', __name__)

FULL_NAME_FORMAT_HINT = 'Use: Last Name First Name (optional: Second Name and/or M.I.)'


def _parse_birth_date_or_none(birth_date_str):
    try:
        return datetime.strptime((birth_date_str or '').strip(), '%Y-%m-%d').date()
    except ValueError:
        return None


@bhw_bp.route('/bhw_dashboard')
@login_required
@role_required('BHW', 'Admin', 'Midwife')
def bhw_dashboard():
    try:
        if current_user.role in ['Midwife', 'Admin']:
            household_profiles = HouseholdProfile.query.all()
            opt_records = OperationTimbang.query.all()
            malnourished_children = OperationTimbang.query.filter(OperationTimbang.requires_followup == True).all()
        else:
            household_profiles = HouseholdProfile.query.filter_by(created_by_id=current_user.id).all()
            opt_records = OperationTimbang.query.filter_by(recorded_by_id=current_user.id).all()
            malnourished_children = OperationTimbang.query.filter(
                OperationTimbang.recorded_by_id == current_user.id,
                OperationTimbang.requires_followup == True).all()
        purok_stats = {}
        for profile in household_profiles:
            if profile.purok not in purok_stats:
                purok_stats[profile.purok] = {'households': 0, 'members': 0}
            purok_stats[profile.purok]['households'] += 1
            purok_stats[profile.purok]['members'] += profile.number_of_members
        return render_template('bhw_dashboard.html',
                               household_count=len(household_profiles),
                               opt_count=len(opt_records),
                               opt_records=opt_records,
                               followup_count=len(malnourished_children),
                               purok_stats=purok_stats,
                               malnourished_children=malnourished_children)
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'Error loading BHW Dashboard: {str(e)}', 'danger')
        return redirect(url_for('core.dashboard'))


@bhw_bp.route('/household-profile', methods=['GET', 'POST'])
@login_required
@role_required('BHW', 'Admin', 'Midwife')
def household_profile():
    try:
        if request.method == 'POST':
            household_head_name = sanitize_input(request.form.get('household_head_name', ''))
            if not is_valid_full_name_format(household_head_name):
                flash(f'Head name must follow this format: {FULL_NAME_FORMAT_HINT}', 'danger')
                return redirect(url_for('bhw.household_profile'))

            household = HouseholdProfile(
                household_head_name=household_head_name,
                purok=request.form.get('purok'),
                address=request.form.get('address'),
                number_of_members=int(request.form.get('number_of_members', 0)),
                water_source=request.form.get('water_source'),
                sanitation_type=request.form.get('sanitation_type'),
                electricity=request.form.get('electricity') == 'on',
                contact_number=request.form.get('contact_number'),
                notes=request.form.get('notes'),
                created_by_id=current_user.id
            )
            db.session.add(household)
            db.session.commit()
            flash('Household profile recorded successfully!', 'success')
            return redirect(url_for('bhw.bhw_dashboard'))
        return render_template('household_profile.html', puroks=PUROK_CHOICES)
    except Exception as e:
        logger.error(f'Error in household_profile: {str(e)}')
        flash(f'An error occurred: {str(e)}', 'danger')
        return redirect(url_for('bhw.bhw_dashboard'))


@bhw_bp.route('/operation-timbang', methods=['GET', 'POST'])
@login_required
@role_required('BHW', 'Admin')
def operation_timbang():
    if request.method == 'POST':
        try:
            full_name = sanitize_input(request.form.get('full_name'))
            birth_date_str = request.form.get('birth_date')
            gender = request.form.get('gender')
            purok = request.form.get('purok')
            weight = float(request.form.get('weight'))
            height = float(request.form.get('height'))
            notes = request.form.get('notes')

            if not is_valid_full_name_format(full_name):
                flash(f'Full name must follow this format: {FULL_NAME_FORMAT_HINT}', 'danger')
                return redirect(url_for('bhw.operation_timbang'))

            birth_date = _parse_birth_date_or_none(birth_date_str)
            if not birth_date:
                flash('Invalid birth date format.', 'danger')
                return redirect(url_for('bhw.operation_timbang'))

            if birth_date > date.today():
                flash('Birth date cannot be in the future.', 'danger')
                return redirect(url_for('bhw.operation_timbang'))

            age = (date.today() - birth_date).days // 365
            if age < 0 or age > 18:
                flash('OPT registration is for children under 19 years old only.', 'danger')
                return redirect(url_for('bhw.operation_timbang'))

            new_patient = Patient(full_name=full_name, birth_date=birth_date,
                                  gender=gender, purok=purok, is_pregnant=False)
            db.session.add(new_patient)
            db.session.flush()
            opt_record = OperationTimbang(patient_id=new_patient.id, weight_kg=weight,
                                          height_cm=height, recorded_by_id=current_user.id, notes=notes)
            opt_record.calculate_bmi()
            opt_record.assess_nutritional_status()
            db.session.add(opt_record)
            db.session.commit()
            flash(f'Success! {full_name} registered. Status: {opt_record.nutritional_status}', 'success')
            return redirect(url_for('bhw.operation_timbang_history', patient_id=new_patient.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
            return redirect(url_for('bhw.operation_timbang'))
    return render_template('operation_timbang.html', purok_choices=PUROK_CHOICES)


@bhw_bp.route('/operation-timbang/history/<int:patient_id>')
@login_required
@role_required('BHW', 'Admin', 'Midwife')
def operation_timbang_history(patient_id):
    try:
        patient = Patient.query.get_or_404(patient_id)
        opt_records = OperationTimbang.query.filter_by(patient_id=patient_id).order_by(
            OperationTimbang.measurement_date.desc()).all()
        return render_template('opt_history.html', patient=patient, opt_records=opt_records)
    except Exception:
        flash('An error occurred.', 'danger')
        return redirect(url_for('bhw.bhw_dashboard'))
