import pytest
from django.db import IntegrityError, transaction


def assert_violates(constraint_name, func):
    """Run func and assert the database rejects it with the named constraint."""
    with pytest.raises(IntegrityError, match=constraint_name), transaction.atomic():
        func()
