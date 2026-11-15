from models import InventoryItem


def test_add_inventory_item(client, seed_users, login_as):
    login_as("admin")
    response = client.post(
        "/inventory",
        data={
            "name": "Paracetamol Test",
            "category": "Medicine",
            "quantity": "20",
            "min_stock_level": "5",
            "expiry_date": "2030-01-01",
        },
        follow_redirects=False,
    )
    assert response.status_code in (200, 302, 303)
    assert InventoryItem.query.filter_by(name="Paracetamol Test").first() is not None


def test_delete_inventory_item(client, seed_users, login_as):
    login_as("admin")
    item = InventoryItem(name="Item To Delete", category="Supply", quantity=5, min_stock_level=1)
    from models import db

    db.session.add(item)
    db.session.commit()

    response = client.post(f"/inventory/{item.id}/delete", follow_redirects=False)
    assert response.status_code in (302, 303)
    assert InventoryItem.query.get(item.id) is None
