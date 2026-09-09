from services.orders import rupiah


def test_rupiah():
    assert rupiah(12500) == "Rp12.500"
