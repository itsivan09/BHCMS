from utils import has_permission, is_valid_full_name_format, normalize_ph_contact_number


class DummyUser:
    def __init__(self, role):
        self.role = role


def test_is_valid_full_name_format_accepts_expected_value():
    assert is_valid_full_name_format("Dela Cruz Maria") is True


def test_is_valid_full_name_format_rejects_bad_value():
    assert is_valid_full_name_format("invalid_name") is False


def test_normalize_ph_contact_number_handles_common_formats():
    assert normalize_ph_contact_number("09171234567") == "+639171234567"
    assert normalize_ph_contact_number("+639171234567") == "+639171234567"


def test_has_permission_by_role():
    assert has_permission(DummyUser("Admin"), "delete") is True
    assert has_permission(DummyUser("Midwife"), "edit") is True
    assert has_permission(DummyUser("BHW"), "delete") is False
