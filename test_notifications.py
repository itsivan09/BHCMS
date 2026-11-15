#!/usr/bin/env python3
"""
Test script for notification system.
Adds test inventory items with low stock to trigger notifications.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import InventoryItem, Notification, DispensedMedicine

def test_notifications():
    """Test the notification system by creating low stock items."""

    with app.app_context():
        print("Testing Notification System")
        print("=" * 40)

        # Clear existing notifications and inventory for clean test
        DispensedMedicine.query.delete()
        Notification.query.delete()
        InventoryItem.query.delete()
        db.session.commit()

        print("1. Creating test inventory items...")

        # Create items with different stock levels
        test_items = [
            {
                'name': 'Paracetamol 500mg',
                'category': 'Medicine',
                'quantity': 5,  # Low stock (below default min_stock_level of 10)
                'min_stock_level': 10,
                'unit': 'tablets'
            },
            {
                'name': 'Amoxicillin 250mg',
                'category': 'Medicine',
                'quantity': 2,  # Very low stock
                'min_stock_level': 15,
                'unit': 'capsules'
            },
            {
                'name': 'Bandages 5cm',
                'category': 'Supply',
                'quantity': 25,  # Good stock
                'min_stock_level': 20,
                'unit': 'pieces'
            },
            {
                'name': 'Surgical Gloves',
                'category': 'Supply',
                'quantity': 8,  # Low stock
                'min_stock_level': 10,
                'unit': 'pairs'
            }
        ]

        for item_data in test_items:
            item = InventoryItem(**item_data)
            db.session.add(item)

        db.session.commit()
        print(f"   ✓ Created {len(test_items)} inventory items")

        print("\n2. Checking notification generation...")

        # Check and create notifications
        Notification.check_and_create_low_stock_notifications()

        # Get all notifications
        notifications = Notification.query.all()

        print(f"   ✓ Generated {len(notifications)} notifications")

        print("\n3. Notification Details:")
        for i, notification in enumerate(notifications, 1):
            print(f"   {i}. {notification.title}")
            print(f"      Type: {notification.type}")
            print(f"      Message: {notification.message}")
            print(f"      Read: {notification.is_read}")
            print(f"      Created: {notification.created_at}")
            print()

        print("4. Testing notification counts...")

        # Test unread count
        unread_count = Notification.get_unread_count()
        print(f"   ✓ Unread notifications: {unread_count}")

        # Test user notifications
        user_notifications = Notification.get_user_notifications(None, limit=10)
        print(f"   ✓ Total user notifications: {len(user_notifications)}")

        print("\n5. Testing mark as read...")

        if notifications:
            # Mark first notification as read
            first_notification = notifications[0]
            success = Notification.mark_as_read(first_notification.id)
            print(f"   ✓ Marked notification as read: {success}")

            # Check updated count
            updated_count = Notification.get_unread_count()
            print(f"   ✓ Updated unread count: {updated_count}")

        print("\n✅ Notification system test completed successfully!")

        # Summary
        low_stock_items = InventoryItem.query.filter(InventoryItem.quantity <= InventoryItem.min_stock_level).count()
        total_notifications = Notification.query.count()
        unread_notifications = Notification.get_unread_count()

        print("\n📊 Test Summary:")
        print(f"   • Low stock items: {low_stock_items}")
        print(f"   • Total notifications: {total_notifications}")
        print(f"   • Unread notifications: {unread_notifications}")

if __name__ == '__main__':
    test_notifications()