import logging
from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from models import InventoryItem, db
from utils import role_required, sanitize_input

logger = logging.getLogger(__name__)

inventory_bp = Blueprint('inventory', __name__)


@inventory_bp.route('/inventory', methods=['GET', 'POST'])
@login_required
def inventory():
    if request.method == 'POST':
        try:
            name = sanitize_input(request.form.get('name', ''))
            category = sanitize_input(request.form.get('category', ''))
            quantity = request.form.get('quantity', '')
            min_stock_level = request.form.get('min_stock_level', '')
            expiry_date_str = request.form.get('expiry_date', '')
            if not name or not quantity:
                flash('Item name and quantity are required.', 'danger')
                return redirect(url_for('inventory.inventory'))
            try:
                quantity = int(quantity)
                min_stock_level = int(min_stock_level) if min_stock_level else 10
                if quantity < 0 or min_stock_level < 0:
                    flash('Quantity cannot be negative.', 'danger')
                    return redirect(url_for('inventory.inventory'))
            except ValueError:
                flash('Quantity must be a valid number.', 'danger')
                return redirect(url_for('inventory.inventory'))
            expiry_date = None
            if expiry_date_str:
                try:
                    expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
                    if expiry_date < date.today():
                        flash('Warning: Expiry date is in the past.', 'warning')
                except ValueError:
                    flash('Invalid expiry date format.', 'danger')
                    return redirect(url_for('inventory.inventory'))
            new_item = InventoryItem(name=name, category=category, quantity=quantity,
                                     min_stock_level=min_stock_level, expiry_date=expiry_date)
            db.session.add(new_item)
            db.session.commit()
            flash(f'Item "{name}" added successfully', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error adding inventory item: {str(e)}')
            flash('An error occurred while adding the item.', 'danger')
    try:
        items = InventoryItem.query.all()
        return render_template('inventory.html', items=items, today=date.today())
    except Exception as e:
        logger.error(f'Error loading inventory page: {str(e)}')
        return render_template('inventory.html', items=[], today=date.today())


@inventory_bp.route('/inventory/<int:item_id>/delete', methods=['POST'])
@login_required
@role_required('Admin', 'Midwife')
def delete_inventory_item(item_id):
    try:
        item = InventoryItem.query.get_or_404(item_id)
        item_name = item.name
        db.session.delete(item)
        db.session.commit()
        flash(f'Inventory item "{item_name}" has been deleted.', 'success')
        return redirect(url_for('inventory.inventory'))
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred: {str(e)}', 'danger')
        return redirect(url_for('inventory.inventory'))
