from services.settlement.reconciliation import reconcile


def test_reconciliation_requires_checkpoint():
    try:
        reconcile("stl_1", None)
        assert False
    except RuntimeError:
        pass
