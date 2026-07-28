from submission import flag_suspicious_employees


def test_clean_payroll_returns_empty_list():
    records = [
        {
            "employee_id": "E001",
            "national_id": "12345678",
            "bank_account": "KE001",
            "employment_status": "active",
            "net_pay": 45000,
        },
        {
            "employee_id": "E002",
            "national_id": "87654321",
            "bank_account": "KE002",
            "employment_status": "active",
            "net_pay": 38000,
        },
    ]
    assert flag_suspicious_employees(records) == []


def test_flags_missing_id_and_inactive_paid_employee():
    records = [
        {
            "employee_id": "E010",
            "national_id": "   ",
            "bank_account": "KE010",
            "employment_status": "active",
            "net_pay": 20000,
        },
        {
            "employee_id": "E009",
            "national_id": "90000009",
            "bank_account": "KE009",
            "employment_status": "INACTIVE",
            "net_pay": 12000,
        },
    ]
    assert flag_suspicious_employees(records) == ["E009", "E010"]


def test_flags_both_employees_sharing_a_normalized_account():
    records = [
        {
            "employee_id": "E003",
            "national_id": "30000003",
            "bank_account": " ke 77 ab ",
            "employment_status": "active",
            "net_pay": 25000,
        },
        {
            "employee_id": "E004",
            "national_id": "40000004",
            "bank_account": "KE77AB",
            "employment_status": "active",
            "net_pay": 27000,
        },
    ]
    assert flag_suspicious_employees(records) == ["E003", "E004"]
