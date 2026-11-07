import pytest

from scripts.generate_demo import generate


@pytest.mark.parametrize("orders,seed", [(0, 42), (1_000_001, 42), (100, -1), (100, 2**31)])
def test_invalid_generation_limits_do_not_connect(orders, seed):
    with pytest.raises(ValueError):
        generate(None, target="demo", orders=orders, seed=seed)
