import logging
import os
import re
import tempfile
from datetime import datetime
from io import BytesIO

try:
    import pdfkit
except ImportError:
    pdfkit = None
from flask import Blueprint, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from models import Consultation, DispensedMedicine, InventoryItem, OperationTimbang, Patient, PrenatalRecord, db
from utils import role_required

logger = logging.getLogger(__name__)

consultations_bp = Blueprint('consultations', __name__)


@consultations_bp.route('/patient/<int:patient_id>/consultations', methods=['GET'])
@login_required
def consultation_history(patient_id):
    try:
        patient = Patient.query.get_or_404(patient_id)
        consultations = Consultation.query.filter_by(patient_id=patient_id).order_by(Consultation.date.desc()).all()
        return render_template('consultation_history.html', patient=patient, consultations=consultations)
    except Exception as e:
        logger.error(f'Error loading consultation history for patient {patient_id}: {str(e)}')
        flash(f'Error loading consultation history: {str(e)}', 'danger')
        return redirect(url_for('patients.patients'))


@consultations_bp.route('/patient/<int:patient_id>/consultation/add', methods=['GET', 'POST'])
@login_required
def add_consultation(patient_id):
    try:
        patient = Patient.query.get_or_404(patient_id)
        if request.method == 'POST':
            try:
                is_bhw = current_user.role == 'BHW'
                chief_complaint = request.form.get('chief_complaint')
                diagnosis = request.form.get('diagnosis', '').strip()

                consultation_type = request.form.get('consultation_type', 'General')
                if is_bhw:
                    consultation_type = 'Monitoring'

                if is_bhw:
                    if diagnosis:
                        diagnosis = f'[Pending Midwife Review] {diagnosis}'
                    else:
                        diagnosis = '[Pending Midwife Review]'

                if not chief_complaint:
                    flash('Chief complaint is required.', 'danger')
                    return redirect(url_for('consultations.add_consultation', patient_id=patient_id))
                if not is_bhw and not diagnosis:
                    flash('Chief complaint and diagnosis are required.', 'danger')
                    return redirect(url_for('consultations.add_consultation', patient_id=patient_id))

                new_consultation = Consultation(
                    patient_id=patient_id,
                    health_worker_id=current_user.id,
                    consultation_type=consultation_type,
                    chief_complaint=chief_complaint,
                    diagnosis=diagnosis,
                    notes=request.form.get('notes'),
                    temperature=float(request.form.get('temperature')) if request.form.get('temperature') else None,
                    blood_pressure_systolic=int(request.form.get('blood_pressure_systolic')) if request.form.get('blood_pressure_systolic') else None,
                    blood_pressure_diastolic=int(request.form.get('blood_pressure_diastolic')) if request.form.get('blood_pressure_diastolic') else None,
                    weight=float(request.form.get('weight')) if request.form.get('weight') else None,
                    height=float(request.form.get('height')) if request.form.get('height') else None,
                    respiratory_rate=int(request.form.get('respiratory_rate')) if request.form.get('respiratory_rate') else None,
                    date=datetime.now(),
                )
                db.session.add(new_consultation)
                db.session.flush()

                medicine_ids = [] if is_bhw else request.form.getlist('medicine_id[]')
                medicine_quantities = request.form.getlist('medicine_quantity[]')
                medicine_dosages = request.form.getlist('medicine_dosage[]')
                medicine_instructions = request.form.getlist('medicine_instruction[]')
                medicine_routes = request.form.getlist('medicine_route[]')
                medicine_frequencies = request.form.getlist('medicine_frequency[]')
                medicine_durations = request.form.getlist('medicine_duration[]')
                medicine_warnings = request.form.getlist('medicine_warnings[]')

                if medicine_ids:
                    for med_id, quantity, dosage, instruction, route, frequency, duration, warning in zip(
                        medicine_ids,
                        medicine_quantities,
                        medicine_dosages,
                        medicine_instructions,
                        medicine_routes,
                        medicine_frequencies,
                        medicine_durations,
                        medicine_warnings,
                    ):
                        if med_id and quantity:
                            try:
                                med_id = int(med_id)
                                quantity = int(quantity)
                                inventory_item = InventoryItem.query.get(med_id)
                                if not inventory_item:
                                    continue
                                if quantity <= 0:
                                    continue
                                if quantity > inventory_item.quantity:
                                    flash(
                                        f'Insufficient stock for {inventory_item.name}. Available: {inventory_item.quantity}.',
                                        'warning',
                                    )
                                    continue
                                db.session.add(DispensedMedicine(
                                    consultation_id=new_consultation.id,
                                    inventory_item_id=med_id,
                                    quantity_dispensed=quantity,
                                    dosage=dosage,
                                    instructions=instruction,
                                    route=route,
                                    frequency=frequency,
                                    duration=duration,
                                    warnings=warning,
                                    dispensed_by=current_user.id,
                                ))
                                inventory_item.quantity -= quantity
                            except Exception as e:
                                logger.error(f'Error saving medicine {med_id}: {e}')
                                continue
                db.session.commit()
                flash('Consultation recorded successfully', 'success')
                return redirect(url_for('consultations.consultation_history', patient_id=patient_id))
            except Exception as e:
                db.session.rollback()
                flash(f'An error occurred: {str(e)}', 'danger')
                return redirect(url_for('consultations.add_consultation', patient_id=patient_id))
        medicines_list = [
            {
                'id': item.id,
                'name': item.name,
                'quantity': item.quantity,
                'unit': item.unit,
                'min_stock_level': item.min_stock_level,
            }
            for item in InventoryItem.query.filter_by(category='Medicine').all()
        ]
        is_bhw = current_user.role == 'BHW'
        return render_template('add_consultation.html', patient=patient, medicines=medicines_list, is_bhw=is_bhw)
    except Exception:
        flash('An error occurred.', 'danger')
        return redirect(url_for('patients.patients'))


@consultations_bp.route('/dispensed-medicines/<int:consultation_id>', methods=['GET'])
@login_required
def view_dispensed_medicines(consultation_id):
    try:
        Consultation.query.get_or_404(consultation_id)
        return jsonify([
            {
                'id': dm.id,
                'medicine_name': dm.inventory_item.name,
                'quantity_dispensed': dm.quantity_dispensed,
                'unit': dm.inventory_item.unit,
                'dosage': dm.dosage,
                'instructions': dm.instructions,
            }
            for dm in DispensedMedicine.query.filter_by(consultation_id=consultation_id).all()
        ])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@consultations_bp.route('/consultation/<int:consultation_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('Midwife', 'Admin')
def edit_consultation(consultation_id):
    try:
        consultation = Consultation.query.get_or_404(consultation_id)
        patient = Patient.query.get_or_404(consultation.patient_id)
        medicines_list = [
            {
                'id': item.id,
                'name': item.name,
                'quantity': item.quantity,
                'unit': item.unit,
                'min_stock_level': item.min_stock_level,
            }
            for item in InventoryItem.query.filter_by(category='Medicine').all()
        ]
        if request.method == 'POST':
            try:
                consultation.chief_complaint = request.form.get('chief_complaint', consultation.chief_complaint)
                consultation.diagnosis = request.form.get('diagnosis', consultation.diagnosis).strip()
                consultation.notes = request.form.get('notes')
                consultation.consultation_type = request.form.get('consultation_type', consultation.consultation_type)
                consultation.temperature = float(request.form.get('temperature')) if request.form.get('temperature') else None
                consultation.blood_pressure_systolic = int(request.form.get('blood_pressure_systolic')) if request.form.get('blood_pressure_systolic') else None
                consultation.blood_pressure_diastolic = int(request.form.get('blood_pressure_diastolic')) if request.form.get('blood_pressure_diastolic') else None
                consultation.weight = float(request.form.get('weight')) if request.form.get('weight') else None
                consultation.height = float(request.form.get('height')) if request.form.get('height') else None
                consultation.respiratory_rate = int(request.form.get('respiratory_rate')) if request.form.get('respiratory_rate') else None
                if not consultation.chief_complaint or not consultation.diagnosis:
                    flash('Chief complaint and diagnosis are required.', 'danger')
                    return redirect(url_for('consultations.edit_consultation', consultation_id=consultation_id))

                medicine_ids = request.form.getlist('medicine_id[]')
                medicine_quantities = request.form.getlist('medicine_quantity[]')
                medicine_dosages = request.form.getlist('medicine_dosage[]')
                medicine_instructions = request.form.getlist('medicine_instruction[]')
                medicine_routes = request.form.getlist('medicine_route[]')
                medicine_frequencies = request.form.getlist('medicine_frequency[]')
                medicine_durations = request.form.getlist('medicine_duration[]')
                medicine_warnings = request.form.getlist('medicine_warnings[]')

                if medicine_ids:
                    for med_id, quantity, dosage, instruction, route, frequency, duration, warning in zip(
                        medicine_ids,
                        medicine_quantities,
                        medicine_dosages,
                        medicine_instructions,
                        medicine_routes,
                        medicine_frequencies,
                        medicine_durations,
                        medicine_warnings,
                    ):
                        if med_id and quantity:
                            try:
                                med_id = int(med_id)
                                quantity = int(quantity)
                                inventory_item = InventoryItem.query.get(med_id)
                                if not inventory_item:
                                    continue
                                if quantity <= 0:
                                    continue
                                if quantity > inventory_item.quantity:
                                    flash(
                                        f'Insufficient stock for {inventory_item.name}. Available: {inventory_item.quantity}.',
                                        'warning',
                                    )
                                    continue
                                db.session.add(DispensedMedicine(
                                    consultation_id=consultation.id,
                                    inventory_item_id=med_id,
                                    quantity_dispensed=quantity,
                                    dosage=dosage,
                                    instructions=instruction,
                                    route=route,
                                    frequency=frequency,
                                    duration=duration,
                                    warnings=warning,
                                    dispensed_by=current_user.id,
                                ))
                                inventory_item.quantity -= quantity
                            except Exception as e:
                                logger.error(f'Error saving medicine {med_id}: {e}')
                                continue
                db.session.commit()
                flash('Consultation updated successfully.', 'success')
                return redirect(url_for('consultations.consultation_history', patient_id=patient.id))
            except Exception as e:
                db.session.rollback()
                flash(f'An error occurred: {str(e)}', 'danger')
                return redirect(url_for('consultations.edit_consultation', consultation_id=consultation_id))
        return render_template('edit_consultation.html', consultation=consultation, patient=patient, medicines=medicines_list)
    except Exception as e:
        logger.error(f'Error in edit_consultation: {str(e)}')
        flash(f'An error occurred: {str(e)}', 'danger')
        return redirect(url_for('patients.patients'))


@consultations_bp.route('/consultation/<int:consultation_id>/delete', methods=['POST'])
@login_required
@role_required('Midwife', 'Admin')
def delete_consultation(consultation_id):
    try:
        consultation = Consultation.query.get_or_404(consultation_id)
        patient_id = consultation.patient_id
        Patient.query.get_or_404(patient_id)
        for dm in consultation.dispensed_medicines:
            item = InventoryItem.query.get(dm.inventory_item_id)
            if item:
                item.quantity += dm.quantity_dispensed
            db.session.delete(dm)
        db.session.delete(consultation)
        db.session.commit()
        flash('Consultation deleted successfully.', 'success')
        return redirect(url_for('consultations.consultation_history', patient_id=patient_id))
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred: {str(e)}', 'danger')
        return redirect(url_for('patients.patients'))


@consultations_bp.route('/consultation/<int:consultation_id>/remove-medicine/<int:dm_id>', methods=['POST'])
@login_required
@role_required('Midwife', 'Admin')
def remove_dispensed_medicine(consultation_id, dm_id):
    try:
        dm = DispensedMedicine.query.get_or_404(dm_id)
        item = InventoryItem.query.get(dm.inventory_item_id)
        if item:
            item.quantity += dm.quantity_dispensed
        db.session.delete(dm)
        db.session.commit()
        flash('Medicine removed and inventory restored.', 'success')
        return redirect(url_for('consultations.edit_consultation', consultation_id=consultation_id))
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred: {str(e)}', 'danger')
        return redirect(url_for('consultations.edit_consultation', consultation_id=consultation_id))


def generate_patient_pdf(patient_id):
    try:
        patient = Patient.query.get(patient_id)
        if not patient:
            raise ValueError(f'Patient {patient_id} not found')
        consultations = Consultation.query.filter_by(patient_id=patient_id).order_by(Consultation.date.desc()).all()
        prenatal_record = PrenatalRecord.query.filter_by(patient_id=patient_id, is_active=True).first()
        operation_timbang = OperationTimbang.query.filter_by(patient_id=patient_id).order_by(OperationTimbang.measurement_date.desc()).all()
        html_content = render_template('patient_details.html', patient=patient, consultations=consultations,
                                       prenatal_record=prenatal_record, operation_timbang=operation_timbang,
                                       generated_date=datetime.now())
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as tmp:
            tmp.write(html_content)
            tmp_path = tmp.name
        try:
            if not pdfkit:
                raise RuntimeError("pdfkit not installed or supported")
            pdf = pdfkit.from_file(tmp_path, False, options={
                'page-size': 'A4', 'margin-top': '0.75in', 'margin-right': '0.75in',
                'margin-bottom': '0.75in', 'margin-left': '0.75in', 'encoding': 'UTF-8',
                'no-outline': None, 'enable-local-file-access': None,
            })
            file_obj = BytesIO(pdf)
            file_obj.seek(0)
            return file_obj
        except Exception:
            file_obj = BytesIO(html_content.encode('utf-8'))
            file_obj.seek(0)
            return file_obj
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
    except Exception as e:
        logger.error(f'PDF error: {str(e)}')
        raise


@consultations_bp.route('/export_pdf/<int:patient_id>')
@login_required
def export_patient_pdf(patient_id):
    try:
        patient = Patient.query.get_or_404(patient_id)
        file_obj = generate_patient_pdf(patient_id)
        safe_name = re.sub(r'[^\w\s-]', '', patient.full_name).replace(' ', '_')
        file_obj.seek(0)
        start = file_obj.read(4)
        file_obj.seek(0)
        if start == b'%PDF':
            filename = f'Patient_{safe_name}_{datetime.now().strftime("%Y%m%d")}.pdf'
            mime = 'application/pdf'
        else:
            filename = f'Patient_{safe_name}_{datetime.now().strftime("%Y%m%d")}.html'
            mime = 'text/html'
        return send_file(file_obj, mimetype=mime, as_attachment=True, download_name=filename)
    except Exception as e:
        logger.error(f'Error exporting patient PDF for patient {patient_id}: {str(e)}')
        flash('An error occurred while generating the report.', 'danger')
        return redirect(url_for('patients.patients'))
