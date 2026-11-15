import logging
from datetime import datetime, timedelta

from flask import Blueprint, flash, jsonify, redirect, render_template, send_file, url_for
from flask_login import login_required

from models import Consultation, InventoryItem, Patient
from services.export_service import (
    build_inventory_rows,
    build_patients_rows,
    inventory_csv_filename,
    inventory_xlsx_filename,
    patients_csv_filename,
    patients_xlsx_filename,
    rows_to_csv_bytes,
    rows_to_xlsx_bytes,
)
from services.reporting_service import build_demographic_payload, build_morbidity_payload
from utils import role_required

logger = logging.getLogger(__name__)

reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/api/morbidity-stats')
@login_required
@role_required('Admin', 'Midwife')
def morbidity_stats():
    try:
        consultations = Consultation.query.filter(Consultation.date >= datetime.now() - timedelta(days=30)).all()
        return jsonify(build_morbidity_payload(consultations))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@reports_bp.route('/api/demographic-report')
@login_required
@role_required('Admin', 'Midwife')
def demographic_report():
    try:
        all_patients = Patient.query.all()
        pregnant_count = Patient.query.filter_by(is_pregnant=True).count()
        return jsonify(build_demographic_payload(all_patients, pregnant_count))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@reports_bp.route('/reports')
@login_required
@role_required('Admin', 'Midwife')
def reports():
    try:
        return render_template('reports.html')
    except Exception as e:
        logger.error(f'Error loading reports page: {str(e)}')
        flash('An error occurred.', 'danger')
        return redirect(url_for('core.dashboard'))


@reports_bp.route('/export/patients.csv')
@login_required
@role_required('Admin', 'Midwife')
def export_patients_csv():
    try:
        rows = build_patients_rows(Patient.query.all())
        csv_buffer = rows_to_csv_bytes(rows)
        return send_file(csv_buffer, mimetype='text/csv', as_attachment=True, download_name=patients_csv_filename())
    except Exception as e:
        logger.error(f'Error exporting patients CSV: {str(e)}')
        flash('An error occurred while exporting.', 'danger')
        return redirect(url_for('patients.patients'))


@reports_bp.route('/export/patients.xlsx')
@login_required
@role_required('Admin', 'Midwife')
def export_patients_xlsx():
    try:
        rows = build_patients_rows(Patient.query.all())
        xlsx_buffer = rows_to_xlsx_bytes('Patients', rows)
        return send_file(
            xlsx_buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=patients_xlsx_filename(),
        )
    except Exception as e:
        logger.error(f'Error exporting patients XLSX: {str(e)}')
        flash('An error occurred while exporting.', 'danger')
        return redirect(url_for('patients.patients'))


@reports_bp.route('/export/inventory.csv')
@login_required
@role_required('Admin', 'Midwife')
def export_inventory_csv():
    try:
        rows = build_inventory_rows(InventoryItem.query.all())
        csv_buffer = rows_to_csv_bytes(rows)
        return send_file(csv_buffer, mimetype='text/csv', as_attachment=True, download_name=inventory_csv_filename())
    except Exception as e:
        logger.error(f'Error exporting inventory CSV: {str(e)}')
        flash('An error occurred while exporting.', 'danger')
        return redirect(url_for('inventory.inventory'))


@reports_bp.route('/export/inventory.xlsx')
@login_required
@role_required('Admin', 'Midwife')
def export_inventory_xlsx():
    try:
        rows = build_inventory_rows(InventoryItem.query.all())
        xlsx_buffer = rows_to_xlsx_bytes('Inventory', rows)
        return send_file(
            xlsx_buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=inventory_xlsx_filename(),
        )
    except Exception as e:
        logger.error(f'Error exporting inventory XLSX: {str(e)}')
        flash('An error occurred while exporting.', 'danger')
        return redirect(url_for('inventory.inventory'))
