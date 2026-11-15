import csv
import io
from datetime import datetime
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill


PATIENT_HEADERS = ['ID', 'Full Name', 'Birth Date', 'Age', 'Gender', 'Purok', 'Address', 'Contact', 'Pregnant', 'Created Date']
INVENTORY_HEADERS = ['ID', 'Item Name', 'Category', 'Quantity', 'Unit', 'Min Stock', 'Expiry Date', 'Price', 'Status', 'Created Date']


HEADER_FILL = PatternFill(start_color='0e7c86', end_color='0e7c86', fill_type='solid')
HEADER_FONT = Font(color='FFFFFF', bold=True)


def _timestamped_filename(prefix: str, extension: str) -> str:
    return f'{prefix}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.{extension}'


def build_patients_rows(patients):
    rows = [PATIENT_HEADERS]
    for patient in patients:
        rows.append([
            patient.id,
            patient.full_name,
            patient.birth_date.strftime('%Y-%m-%d'),
            patient.age,
            patient.gender,
            patient.purok,
            patient.address or '',
            patient.contact_number or '',
            'Yes' if patient.is_pregnant else 'No',
            patient.created_at.strftime('%Y-%m-%d %H:%M'),
        ])
    return rows


def build_inventory_rows(items):
    rows = [INVENTORY_HEADERS]
    for item in items:
        status = 'Expired' if item.is_expired else ('Low Stock' if item.is_low_stock else 'Good')
        rows.append([
            item.id,
            item.name,
            item.category,
            item.quantity,
            item.unit,
            item.min_stock_level,
            item.expiry_date.strftime('%Y-%m-%d') if item.expiry_date else 'N/A',
            item.price_per_unit or '',
            status,
            item.created_at.strftime('%Y-%m-%d %H:%M'),
        ])
    return rows


def rows_to_csv_bytes(rows):
    buffer = io.StringIO()
    csv.writer(buffer).writerows(rows)
    return BytesIO(buffer.getvalue().encode())


def rows_to_xlsx_bytes(sheet_title: str, rows):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet_title

    for row in rows:
        worksheet.append(row)

    for cell in worksheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT

    for column in worksheet.columns:
        worksheet.column_dimensions[column[0].column_letter].width = min(
            max((len(str(cell.value)) for cell in column if cell.value), default=0) + 2,
            50,
        )

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def patients_csv_filename():
    return _timestamped_filename('Patients_Export', 'csv')


def patients_xlsx_filename():
    return _timestamped_filename('Patients_Export', 'xlsx')


def inventory_csv_filename():
    return _timestamped_filename('Inventory_Export', 'csv')


def inventory_xlsx_filename():
    return _timestamped_filename('Inventory_Export', 'xlsx')
