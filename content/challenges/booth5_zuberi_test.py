from submission import longest_getaway


def test_basic_increasing():
    """Visible: Basic Increasing"""
    assert longest_getaway([1, 2, 3, 4]) == 4


def test_broken_escape():
    """Visible: Broken Escape"""
    assert longest_getaway([5, 4, 3, 2]) == 1


def test_mixed_route():
    """Hidden: Mixed Route -- inferred input (user confirmed picking a reasonable one), not
    provided in the original spec: [1, 2, 1, 2, 3] has longest run 1,2,3 -> length 3."""
    assert longest_getaway([1, 2, 1, 2, 3]) == 3


def test_duplicate_checkpoints():
    """Hidden: Duplicate Checkpoints -- inferred input (user confirmed picking a reasonable
    one), not provided in the original spec: [1, 1, 2] -- the repeated 1 breaks the streak,
    longest run is 1,2 -> length 2."""
    assert longest_getaway([1, 1, 2]) == 2
