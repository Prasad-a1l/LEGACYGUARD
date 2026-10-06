from services.payment.models import Money, PaymentMethod, PaymentRequest
from services.payment.service import PAYMENT_SERVICE


def test_create_payment_idempotent():
    req = PaymentRequest("m1", "c1", Money(1000), PaymentMethod.CARD, "key-1")
    a = PAYMENT_SERVICE.create(req)
    b = PAYMENT_SERVICE.create(req)
    assert a.payment_id == b.payment_id
