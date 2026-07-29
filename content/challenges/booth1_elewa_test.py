from submission import validate_workflow


def test_valid_workflow():
    """Visible: Valid Workflow"""
    assert validate_workflow([1, 2, 3, 4]) == True


def test_duplicate_task():
    """Visible: Duplicate Task"""
    assert validate_workflow([1, 2, 2, 3]) == False


def test_workflow_starts_incorrectly():
    """Hidden: Workflow Starts Incorrectly"""
    assert validate_workflow([2, 3, 4]) == False


def test_skipped_task():
    """Hidden: Skipped Task"""
    assert validate_workflow([1, 2, 4]) == False


def test_empty_workflow():
    """Hidden: Empty Workflow"""
    assert validate_workflow([]) == False


def test_single_task_workflow():
    """Hidden: Single Task Workflow"""
    assert validate_workflow([1]) == True
