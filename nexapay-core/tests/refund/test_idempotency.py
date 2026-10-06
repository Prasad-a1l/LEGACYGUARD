from services.refund.service import REFUND_SERVICE


def test_refund_requires_idempotency_key():
    try:
        REFUND_SERVICE.create("pay_1", 100, "test", None)
        assert False, "should reject"
    except ValueError:
        pass
