from app import divide, transfer


def test_divide_happy():
    assert divide(10, 2) == 5


def test_transfer_does_not_check_funds():
    bal = {"a": 5, "b": 0}
    transfer(bal, "a", "b", 100)
    # Demonstrates insufficient-funds bug is currently allowed
    assert bal["a"] == -95