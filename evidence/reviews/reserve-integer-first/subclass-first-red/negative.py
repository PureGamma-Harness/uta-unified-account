from decimal import Decimal
from uta.reserve_kernel import ReserveInputs,calculate_reserve
from uta.reserve_integer import calculate_integer_reserve
class ConditionalMargin(ReserveInputs):
    def __getattribute__(self,name):
        if name=="initial_margin_rate": raise RuntimeError("synthetic margin must not be read in reduce-only")
        return super().__getattribute__(name)
x=ConditionalMargin(Decimal(1),Decimal(0),Decimal(100),Decimal(100),True,Decimal(".1"),Decimal(0),Decimal(0),Decimal(".001"),8)
expected=calculate_reserve(x)
assert expected==Decimal(".1")
actual=calculate_integer_reserve(x)
assert actual.as_tuple()==expected.as_tuple()
print("PASS reference-compatible subclass fallback")
