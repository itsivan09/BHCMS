import logging
import re
from datetime import date, datetime, timedelta

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from models import (
    HouseholdProfile,
    ImmunizationSchedule,
    InventoryItem,
    Notification,
    OperationTimbang,
    PUROK_CHOICES,
    Patient,
    PrenatalRecord,
    User,
    db,
)
from utils import is_valid_full_name_format, role_required, sanitize_input

logger = logging.getLogger(__name__)

maternal_bp = Blueprint('maternal', __name__)

FULL_NAME_FORMAT_HINT = 'Use: Last Name First Name (optional: Second Name and/or M.I.)'


@maternal_bp.route('/midwife_dashboard')
@login_required
@role_required('Midwife', 'Admin')
def midwife_dashboard():
    try:
        pregnant_patients = Patient.query.filter_by(is_pregnant=True).all()
        prenatal_data = []
        for patient in pregnant_patients:
            prenatal_record = PrenatalRecord.query.filter_by(patient_id=patient.id, is_active=True).first()
            if prenatal_record:
                try:
                    days_until_delivery = prenatal_record.days_until_delivery()
                except Exception as prenatal_error:
                    # Skip malformed legacy rows instead of failing the entire dashboard.
                    logger.warning(
                        'Skipping prenatal record %s for patient %s: %s',
                        prenatal_record.id,
                        patient.id,
                        prenatal_error,
                    )
                    continue

                prenatal_data.append({
                    'patient': patient,
                    'record': prenatal_record,
                    'days_until_delivery': days_until_delivery
                })
        prenatal_data.sort(key=lambda x: x['days_until_delivery'])

        today = date.today()
        upcoming_vaccines = ImmunizationSchedule.query.filter(
            ImmunizationSchedule.scheduled_date.between(today, today + timedelta(days=7)),
            ImmunizationSchedule.is_completed == False
        ).all()
        overdue_vaccines = ImmunizationSchedule.query.filter(
            ImmunizationSchedule.scheduled_date < today,
            ImmunizationSchedule.is_completed == False
        ).all()

        try:
            alert_vaccines = ImmunizationSchedule.query.filter(
                ImmunizationSchedule.scheduled_date.between(today, today + timedelta(days=3)),
                ImmunizationSchedule.is_completed == False
            ).options(
                joinedload(ImmunizationSchedule.patient)
            ).all()
            target_users = User.query.filter(User.role.in_(['Midwife', 'Admin'])).all()
            today_start = datetime.combine(today, datetime.min.time())
            tomorrow_start = today_start + timedelta(days=1)
            already_notified_ids = {
                row[0] for row in db.session.query(Notification.related_item_id)
                .filter(
                    Notification.type == 'appointment',
                    Notification.related_item_type == 'immunization',
                    Notification.created_at >= today_start,
                    Notification.created_at < tomorrow_start,
                    Notification.related_item_id.isnot(None)
                ).all()
            }
            for sched in alert_vaccines:
                if sched.id in already_notified_ids:
                    continue
                vax = sched.vaccine_name
                pname = sched.patient.full_name
                sdate = sched.scheduled_date
                days_left = (sdate - today).days
                urgency = 'Today' if days_left == 0 else ('Tomorrow' if days_left == 1 else f'In {days_left} Days')
                for user in target_users:
                    db.session.add(Notification(
                        user_id=user.id, type='appointment',
                        title=f'Vaccine Due {urgency}: {vax} – {pname}',
                        message=f'{pname} is due for {vax} on {sdate.strftime("%B %d, %Y")}. Please prepare and administer on schedule.',
                        related_item_id=sched.id, related_item_type='immunization'
                    ))
                already_notified_ids.add(sched.id)
            db.session.commit()
        except Exception as notify_error:
            db.session.rollback()
            logger.warning(f'Auto-notify skipped: {notify_error}')

        all_households = HouseholdProfile.query.order_by(HouseholdProfile.created_at.desc()).all()
        recent_opt = OperationTimbang.query.order_by(OperationTimbang.measurement_date.desc()).limit(20).all()
        malnourished_children = OperationTimbang.query.filter(
            OperationTimbang.requires_followup == True
        ).order_by(OperationTimbang.measurement_date.desc()).all()

        purok_stats = {}
        for profile in all_households:
            if profile.purok not in purok_stats:
                purok_stats[profile.purok] = {'households': 0, 'members': 0}
            purok_stats[profile.purok]['households'] += 1
            purok_stats[profile.purok]['members'] += profile.number_of_members or 0

        total_patients = Patient.query.count()

        return render_template('midwife_dashboard.html',
                               pregnant_patients=prenatal_data,
                               upcoming_vaccines=upcoming_vaccines,
                               overdue_vaccines=overdue_vaccines,
                               total_patients=total_patients,
                               purok_stats=purok_stats,
                               malnourished_children=malnourished_children,
                               household_profiles=all_households,
                               opt_records=recent_opt,
                               household_count=len(all_households))
    except Exception as e:
        logger.error(f'Error loading midwife dashboard: {str(e)}')
        flash('An error occurred while loading the dashboard.', 'danger')
        return redirect(url_for('core.dashboard'))


@maternal_bp.route('/prenatal_tracker')
@login_required
@role_required('Midwife', 'Admin')
def prenatal_tracker():
    try:
        records = PrenatalRecord.query.filter_by(is_active=True).all()
        high_risk_count = 0
        near_term_count = 0
        for record in records:
            record.current_weeks = record.current_weeks_of_pregnancy()
            if record.is_high_risk:
                high_risk_count += 1
            if record.estimated_delivery_date:
                days_left = record.days_until_delivery()
                if 0 <= days_left <= 30:
                    near_term_count += 1
        eligible_patients = Patient.query.filter(Patient.gender == 'Female').order_by(Patient.full_name).all()
        return render_template('prenatal_tracker.html',
                               prenatal_records=records,
                               high_risk_count=high_risk_count,
                               near_term_count=near_term_count,
                               eligible_patients=eligible_patients,
                               purok_choices=PUROK_CHOICES,
                               today=date.today().strftime('%Y-%m-%d'))
    except Exception as e:
        logger.error(f'Error loading prenatal tracker: {str(e)}')
        flash(f'Error loading tracker: {str(e)}', 'danger')
        return redirect(url_for('maternal.midwife_dashboard'))


@maternal_bp.route('/prenatal/enroll', methods=['POST'])
@login_required
@role_required('Midwife', 'Admin')
def enroll_prenatal():
    try:
        patient_id_raw = request.form.get('patient_id', '').strip()
        patient_name = sanitize_input(request.form.get('patient_name', '').strip())
        lmp_str = request.form.get('lmp')
        gravida = request.form.get('gravida')
        para = request.form.get('para')
        is_high_risk = 'is_high_risk' in request.form

        if not lmp_str:
            flash('LMP date is required.', 'warning')
            return redirect(url_for('maternal.prenatal_tracker'))

        lmp_date = datetime.strptime(lmp_str, '%Y-%m-%d').date()
        if lmp_date > date.today():
            flash('LMP date cannot be in the future.', 'warning')
            return redirect(url_for('maternal.prenatal_tracker'))

        try:
            gravidity = int(gravida)
            parity = int(para)
        except (TypeError, ValueError):
            flash('Gravida and Para must be valid numbers.', 'warning')
            return redirect(url_for('maternal.prenatal_tracker'))

        if gravidity < 1 or parity < 0:
            flash('Invalid Gravida/Para values.', 'warning')
            return redirect(url_for('maternal.prenatal_tracker'))

        if parity > gravidity:
            flash('Para cannot be greater than Gravida.', 'warning')
            return redirect(url_for('maternal.prenatal_tracker'))

        created_new_patient = False
        patient = None

        if patient_id_raw:
            try:
                patient_id = int(patient_id_raw)
            except (TypeError, ValueError):
                flash('Invalid patient selection.', 'warning')
                return redirect(url_for('maternal.prenatal_tracker'))
            patient = Patient.query.get(patient_id)
            if not patient:
                flash('Selected patient was not found.', 'warning')
                return redirect(url_for('maternal.prenatal_tracker'))
        else:
            if not patient_name:
                flash('Please select a patient or register a new one.', 'warning')
                return redirect(url_for('maternal.prenatal_tracker'))

            if not is_valid_full_name_format(patient_name):
                flash(f'Patient name must follow this format: {FULL_NAME_FORMAT_HINT}', 'danger')
                return redirect(url_for('maternal.prenatal_tracker'))

            new_birth_date_str = request.form.get('new_birth_date', '').strip()
            new_gender = request.form.get('new_gender', '').strip()
            new_purok = request.form.get('new_purok', 'Other').strip() or 'Other'
            new_contact_number = sanitize_input(request.form.get('new_contact_number', '').strip())
            new_email = sanitize_input(request.form.get('new_email', '').strip())

            if not new_birth_date_str or not new_gender:
                flash(f'Patient "{patient_name}" not found. Please provide birth date and gender to register them.', 'danger')
                return redirect(url_for('maternal.prenatal_tracker'))

            if new_email and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', new_email):
                flash('Please enter a valid email address.', 'warning')
                return redirect(url_for('maternal.prenatal_tracker'))

            try:
                new_birth_date = datetime.strptime(new_birth_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid birth date format.', 'danger')
                return redirect(url_for('maternal.prenatal_tracker'))

            if new_birth_date > date.today():
                flash('Birth date cannot be in the future.', 'danger')
                return redirect(url_for('maternal.prenatal_tracker'))

            new_age = (date.today() - new_birth_date).days // 365
            if new_age < 0 or new_age > 150:
                flash('Please enter a valid birth date.', 'danger')
                return redirect(url_for('maternal.prenatal_tracker'))

            existing_match = Patient.query.filter(Patient.full_name.ilike(patient_name)).first()
            if not existing_match:
                existing_match = Patient.query.filter(Patient.full_name.ilike(f'%{patient_name}%')).first()

            if existing_match:
                patient = existing_match
                if new_contact_number and patient.contact_number != new_contact_number:
                    patient.contact_number = new_contact_number
                if new_email and patient.email != new_email:
                    patient.email = new_email
                if new_purok:
                    patient.purok = new_purok
            else:
                patient = Patient(
                    full_name=patient_name,
                    birth_date=new_birth_date,
                    gender=new_gender,
                    purok=new_purok,
                    is_pregnant=False,
                    email=new_email if new_email else None,
                    contact_number=new_contact_number if new_contact_number else None
                )
                db.session.add(patient)
                db.session.flush()
                created_new_patient = True

        if patient.gender != 'Female':
            flash('Only female patients can be enrolled in prenatal tracker.', 'warning')
            return redirect(url_for('maternal.prenatal_tracker'))

        existing_record = PrenatalRecord.query.filter_by(patient_id=patient.id, is_active=True).first()
        if existing_record:
            flash('This patient is already enrolled in an active prenatal record.', 'warning')
            return redirect(url_for('maternal.prenatal_tracker'))

        edd_date = lmp_date + timedelta(days=280)
        today = date.today()
        weeks = (today - lmp_date).days // 7
        if weeks < 0:
            weeks = 0
        patient.is_pregnant = True
        patient.last_menstrual_period = lmp_date
        patient.expected_delivery_date = edd_date
        notes = 'High Risk Pregnancy' if is_high_risk else None
        new_record = PrenatalRecord(
            patient_id=patient.id, weeks_of_pregnancy=weeks,
            estimated_delivery_date=edd_date, gravidity=gravidity,
            parity=parity, is_active=True, notes=notes
        )
        db.session.add(new_record)
        db.session.commit()
        if created_new_patient:
            flash(f'New patient "{patient.full_name}" registered and enrolled in prenatal tracker.', 'success')
        else:
            flash(f'Successfully enrolled {patient.full_name}.', 'success')
        return redirect(url_for('maternal.prenatal_tracker'))
    except Exception as e:
        db.session.rollback()
        logger.error(f'Enrollment error: {str(e)}')
        flash(f'Failed to enroll: {str(e)}', 'danger')
        return redirect(url_for('maternal.prenatal_tracker'))


@maternal_bp.route('/mark_delivered/<int:record_id>', methods=['POST'])
@login_required
@role_required('Midwife', 'Admin')
def mark_delivered(record_id):
    try:
        record = PrenatalRecord.query.get_or_404(record_id)
        patient = record.patient

        record.is_active = False
        if patient:
            patient.is_pregnant = False
            patient.last_menstrual_period = None
            patient.expected_delivery_date = None

        db.session.commit()
        flash('Patient marked as delivered and pregnancy status was updated.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error marking prenatal record {record_id} as delivered: {str(e)}')
        flash('Unable to update delivery status.', 'danger')
    return redirect(url_for('maternal.prenatal_tracker'))


@maternal_bp.route('/immunization_schedule', methods=['GET', 'POST'])
@login_required
@role_required('Midwife', 'Admin')
def immunization_schedule():
    try:
        if request.method == 'POST':
            patient_id = request.form.get('patient_id', '').strip()
            vaccine_name = request.form.get('vaccine_name', '').strip()
            dose_number = request.form.get('dose_number', '').strip()
            scheduled_date = request.form.get('scheduled_date', '').strip()
            notes = request.form.get('notes', '').strip()

            if vaccine_name == '__other__':
                vaccine_name = request.form.get('vaccine_name_other', '').strip()

            if not patient_id:
                flash('Please select a patient.', 'warning')
                return redirect(url_for('maternal.immunization_schedule'))
            if not vaccine_name:
                flash('Please select or enter a vaccine name.', 'warning')
                return redirect(url_for('maternal.immunization_schedule'))
            if not scheduled_date:
                flash('Please choose a scheduled date.', 'warning')
                return redirect(url_for('maternal.immunization_schedule'))

            try:
                patient_id_int = int(patient_id)
            except (ValueError, TypeError):
                flash('Invalid patient selection. Please try again.', 'danger')
                return redirect(url_for('maternal.immunization_schedule'))

            try:
                sched_date_obj = datetime.strptime(scheduled_date, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format. Use YYYY-MM-DD.', 'danger')
                return redirect(url_for('maternal.immunization_schedule'))

            patient = Patient.query.get(patient_id_int)
            if not patient:
                flash('Patient not found. Please search and select again.', 'danger')
                return redirect(url_for('maternal.immunization_schedule'))

            dose_filter = []
            if hasattr(ImmunizationSchedule, 'dose_number') and dose_number:
                dose_filter = [ImmunizationSchedule.dose_number == dose_number]
            existing = ImmunizationSchedule.query.filter(
                ImmunizationSchedule.patient_id == patient_id_int,
                ImmunizationSchedule.vaccine_name == vaccine_name,
                ImmunizationSchedule.scheduled_date == sched_date_obj,
                ImmunizationSchedule.is_completed == False,
                *dose_filter
            ).first()
            if existing:
                flash(
                    f'{vaccine_name} is already scheduled for {patient.full_name} '
                    f'on {sched_date_obj.strftime("%B %d, %Y")}.',
                    'warning'
                )
                return redirect(url_for('maternal.immunization_schedule'))

            age_months = max(
                (date.today().year - patient.birth_date.year) * 12
                + (date.today().month - patient.birth_date.month),
                0
            )

            new_schedule = ImmunizationSchedule(
                patient_id=patient_id_int,
                vaccine_name=vaccine_name,
                scheduled_date=sched_date_obj,
                age_in_months=age_months,
                is_completed=False,
                notes=notes or None,
            )
            if hasattr(ImmunizationSchedule, 'dose_number') and dose_number:
                new_schedule.dose_number = dose_number

            db.session.add(new_schedule)
            db.session.commit()

            logger.info(
                f'Immunization scheduled: {vaccine_name} for {patient.full_name} '
                f'on {sched_date_obj} by {current_user.username}'
            )
            flash(
                f'✓ {vaccine_name} scheduled for {patient.full_name} '
                f'on {sched_date_obj.strftime("%B %d, %Y")}.',
                'success'
            )
            return redirect(url_for('maternal.immunization_schedule'))

        today = date.today()
        pending_vaccines = ImmunizationSchedule.query \
            .options(joinedload(ImmunizationSchedule.patient)) \
            .filter_by(is_completed=False) \
            .order_by(ImmunizationSchedule.scheduled_date.asc()) \
            .all()

        week_end = today + timedelta(days=6)
        all_inventory = InventoryItem.query.all()

        def find_stock(vaccine):
            vax_lower = vaccine.lower()
            for item in all_inventory:
                if vax_lower in item.name.lower() or item.name.lower() in vax_lower:
                    return item
            short = vaccine.split('(')[0].strip().split()[0].lower()
            for item in all_inventory:
                if short in item.name.lower():
                    return item
            return None

        vaccines_data = {'overdue': [], 'due_this_week': [], 'due_later': []}
        for vaccine in pending_vaccines:
            stock_item = find_stock(vaccine.vaccine_name)
            info = {
                'vaccine': vaccine,
                'patient': vaccine.patient,
                'stock_item': stock_item,
                'stock_qty': stock_item.quantity if stock_item else None,
                'stock_found': stock_item is not None,
            }
            if vaccine.scheduled_date < today:
                vaccines_data['overdue'].append(info)
            elif vaccine.scheduled_date <= week_end:
                vaccines_data['due_this_week'].append(info)
            else:
                vaccines_data['due_later'].append(info)

        all_patients = Patient.query.order_by(Patient.full_name).all()

        return render_template('immunization_schedule.html',
                               vaccines_data=vaccines_data,
                               all_patients=all_patients,
                               today=today)

    except Exception as e:
        logger.error(f'Error in immunization_schedule: {str(e)}')
        flash('An error occurred.', 'danger')
        return redirect(url_for('maternal.midwife_dashboard'))


@maternal_bp.route('/immunization/<int:schedule_id>/complete', methods=['POST'])
@login_required
@role_required('Midwife', 'Admin')
def complete_immunization(schedule_id):
    schedule = ImmunizationSchedule.query.get(schedule_id)
    if not schedule:
        flash(f'Immunization record #{schedule_id} not found.', 'danger')
        return redirect(url_for('maternal.immunization_schedule'))
    try:
        vax_name = schedule.vaccine_name
        patient_name = schedule.patient.full_name

        matched = InventoryItem.query.filter(
            func.lower(InventoryItem.name).contains(vax_name.lower())
        ).first()
        if matched is None:
            short = vax_name.split('(')[0].strip().split()[0].lower()
            matched = InventoryItem.query.filter(
                func.lower(InventoryItem.name).contains(short)
            ).first()

        if matched is not None and matched.quantity <= 0:
            flash(
                f'❌ Cannot administer {vax_name}: '
                f'"{matched.name}" is out of stock. Please restock the inventory first.',
                'danger'
            )
            return redirect(url_for('maternal.immunization_schedule'))

        schedule.is_completed = True
        if hasattr(schedule, 'date_administered'):
            schedule.date_administered = datetime.utcnow()
        if hasattr(ImmunizationSchedule, 'administered_by_id'):
            schedule.administered_by_id = current_user.id

        inventory_warning = None
        if matched:
            inv_name = matched.name
            matched.quantity -= 1
            logger.info(
                f'Inventory deducted: "{inv_name}" → {matched.quantity} remaining '
                f'(vaccine: {vax_name}, patient: {patient_name}, by: {current_user.username})'
            )
            if matched.quantity <= matched.min_stock_level:
                for user in User.query.filter(User.role.in_(['Midwife', 'Admin'])).all():
                    db.session.add(Notification(
                        user_id=user.id, type='low_stock',
                        title=f'Low Stock Alert: {inv_name}',
                        message=(
                            f'"{inv_name}" is now at {matched.quantity} unit(s) '
                            f'(minimum threshold: {matched.min_stock_level}). '
                            f'Please restock as soon as possible.'
                        ),
                        related_item_id=matched.id, related_item_type='inventory'
                    ))
        else:
            inventory_warning = (
                f'⚠️ "{vax_name}" was not found in the inventory. '
                f'Stock was NOT automatically deducted — please update the inventory manually.'
            )

        db.session.commit()

        flash(f'✓ {vax_name} administered to {patient_name} successfully.', 'success')
        if matched:
            remaining_msg = (
                f'📦 Inventory updated: "{matched.name}" now has {matched.quantity} unit(s) remaining.'
                if matched.quantity > 0
                else f'📦 Inventory updated: "{matched.name}" is now fully depleted — please restock.'
            )
            flash(remaining_msg, 'info' if matched.quantity > 0 else 'warning')
        if inventory_warning:
            flash(inventory_warning, 'warning')
        logger.info(f'Immunization {schedule_id} ({vax_name} / {patient_name}) marked complete by {current_user.username}')
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error completing immunization {schedule_id}: {str(e)}')
        flash('An error occurred while updating the record.', 'danger')
    return redirect(url_for('maternal.immunization_schedule'))


@maternal_bp.route('/immunization/<int:schedule_id>/delete', methods=['POST'])
@login_required
@role_required('Midwife', 'Admin')
def delete_immunization(schedule_id):
    schedule = ImmunizationSchedule.query.get(schedule_id)
    if not schedule:
        flash(f'Immunization record #{schedule_id} not found.', 'danger')
        return redirect(url_for('maternal.immunization_schedule'))
    try:
        vax_name = schedule.vaccine_name
        patient_name = schedule.patient.full_name

        db.session.delete(schedule)
        db.session.commit()

        flash(f'Entry deleted: {vax_name} – {patient_name}.', 'success')
        logger.info(f'Immunization {schedule_id} ({vax_name} / {patient_name}) deleted by {current_user.username}')
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error deleting immunization {schedule_id}: {str(e)}')
        flash('An error occurred while deleting the entry.', 'danger')
    return redirect(url_for('maternal.immunization_schedule'))


@maternal_bp.route('/immunization/<int:schedule_id>/notify', methods=['POST'])
@login_required
@role_required('Midwife', 'Admin')
def notify_immunization(schedule_id):
    schedule = ImmunizationSchedule.query.get(schedule_id)
    if not schedule:
        flash('Immunization record not found.', 'danger')
        return redirect(url_for('maternal.immunization_schedule'))
    try:
        vax_name = schedule.vaccine_name
        patient_name = schedule.patient.full_name
        sched_date = schedule.scheduled_date
        duplicate = Notification.query.filter(
            Notification.type == 'appointment',
            Notification.related_item_id == schedule_id,
            Notification.related_item_type == 'immunization',
            func.date(Notification.created_at) == date.today()
        ).first()
        if duplicate:
            flash(f'A reminder for {vax_name} ({patient_name}) was already sent today.', 'warning')
            return redirect(url_for('maternal.immunization_schedule'))
        for user in User.query.filter(User.role.in_(['Midwife', 'Admin'])).all():
            db.session.add(Notification(
                user_id=user.id, type='appointment',
                title=f'Vaccine Reminder: {vax_name} – {patient_name}',
                message=f'{patient_name} is due for {vax_name} on {sched_date.strftime("%B %d, %Y")}. Please prepare and administer on schedule.',
                related_item_id=schedule_id, related_item_type='immunization'
            ))
        db.session.commit()
        flash(f'🔔 Reminder sent for {vax_name} – {patient_name}.', 'success')
        logger.info(f'Vaccine reminder created for schedule {schedule_id} by {current_user.username}')
    except Exception as e:
        db.session.rollback()
        logger.error(f'Notify error {schedule_id}: {e}')
        flash('An error occurred while sending the reminder.', 'danger')
    return redirect(url_for('maternal.immunization_schedule'))


@maternal_bp.route('/api/prenatal_stats')
@login_required
@role_required('Midwife', 'Admin')
def prenatal_stats():
    try:
        prenatal_records = PrenatalRecord.query.filter_by(is_active=True).all()
        trimester_counts = {
            '1st Trimester (1-12 weeks)': 0,
            '2nd Trimester (13-26 weeks)': 0,
            '3rd Trimester (27+ weeks)': 0
        }
        for record in prenatal_records:
            weeks = record.current_weeks_of_pregnancy()
            if weeks <= 12:
                trimester_counts['1st Trimester (1-12 weeks)'] += 1
            elif weeks <= 26:
                trimester_counts['2nd Trimester (13-26 weeks)'] += 1
            else:
                trimester_counts['3rd Trimester (27+ weeks)'] += 1
        chart_data = {
            'labels': list(trimester_counts.keys()),
            'datasets': [{'label': 'Pregnant Mothers by Trimester',
                          'data': list(trimester_counts.values()),
                          'backgroundColor': ['#0e7c86', '#2a9d8f', '#d97706'],
                          'borderColor': ['#0a5f67', '#1f7f7a', '#b45309'],
                          'borderWidth': 2}],
            'total_mothers': len(prenatal_records)
        }
        return jsonify(chart_data)
    except Exception as e:
        logger.error(f'Error generating prenatal stats: {str(e)}')
        return jsonify({'error': str(e)}), 500
