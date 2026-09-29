import threading

import pytest
from django.db import IntegrityError, connection, transaction


def assert_violates(constraint_name, func):
    """Run func and assert the database rejects it with the named constraint."""
    with pytest.raises(IntegrityError, match=constraint_name), transaction.atomic():
        func()


def run_concurrently(func, args):
    """
    Call func(arg) for every arg, each on its own thread, all released at the same
    instant by a barrier. Returns one result per arg: the return value or the exception.

    Needs @pytest.mark.django_db(transaction=True): each thread uses its own DB
    connection, so it can only see committed data.
    """
    barrier = threading.Barrier(len(args))
    results = [None] * len(args)

    def worker(index, arg):
        try:
            barrier.wait()
            results[index] = func(arg)
        except Exception as exc:
            results[index] = exc
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(i, arg)) for i, arg in enumerate(args)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    return results
