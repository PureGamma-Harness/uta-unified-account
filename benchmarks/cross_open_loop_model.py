"""Independent integer-nanosecond arrival schedule and hand workload oracle.

No UTA import, database or process. The schedule itself can represent the
formal 10,000/s, 1,800s case; the pilot entry remains a separately bounded case.
"""
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256

ACCOUNT_PATTERN = (0, 1, 0, 2, 0, 3, 0, 1)


def accounts():
    # Pick two independently hashed identifiers in each native sha256 shard.
    result = {0: [], 1: []}
    for i in range(100):
        name = 'cross-pilot-' + str(i)
        index = int.from_bytes(sha256(name.encode()).digest(), 'big') % 2
        if len(result[index]) < 2:
            result[index].append(name)
        if all(len(v) == 2 for v in result.values()):
            return (result[0][0], result[1][0], result[0][1], result[1][1])
    raise AssertionError('fixed synthetic identifier selection exhausted')


@dataclass(frozen=True)
class ArrivalSchedule:
    rate: int
    duration_ns: int

    def __post_init__(self):
        if type(self.rate) is not int or not 1 <= self.rate <= 100000:
            raise ValueError('rate must be integer 1..100000')
        if type(self.duration_ns) is not int or not 1 <= self.duration_ns <= 86400 * 10**9:
            raise ValueError('duration must be integer ns in (0,24h]')

    @property
    def count(self):
        return self.rate * self.duration_ns // 10**9

    def offsets(self):
        # No completion or previous actual wake-up enters this recurrence.
        for ordinal in range(self.count):
            yield ordinal, ordinal * 10**9 // self.rate


def workload(cohort):
    if type(cohort) is not int or cohort not in (0, 1):
        raise ValueError('the fixed pilot has exactly two cohorts')
    identifiers = accounts()
    counts = [0] * 4
    for ordinal, offset in ArrivalSchedule(16, 6 * 10**9).offsets():
        index = ACCOUNT_PATTERN[ordinal % len(ACCOUNT_PATTERN)]
        invalid = counts[index] % 4 == 3
        counts[index] += 1
        yield {'ordinal': ordinal, 'offset_ns': offset, 'account_id': identifiers[index],
               'command_id': f'cross:{cohort}:{ordinal:04d}', 'order_id': f'order:{cohort}:{ordinal:04d}',
               'quantity': '.005' if invalid else '.01', 'limit_price': '100',
               'symbol': 'BTC-PERP', 'expected_business_rejection': invalid}


def order_reserve(quantity, price):
    # Independent fixed policy: no position, mark100, IM1/10, fee1/2500, USD8.
    q, p = Fraction(quantity), Fraction(price)
    units = abs(q) * p * Fraction(1, 2500) * 10**8
    whole, remainder = divmod(units, 1)
    return abs(q) * max(p, Fraction(100)) / 10 + max(Fraction(0), q * (p - 100)) + Fraction(int(whole) + bool(remainder), 10**8)


def percentiles_ns(samples):
    values = sorted(samples)
    if any(type(v) is not int or v < 0 for v in values):
        raise ValueError('latencies must be nonnegative integer ns')
    if not values:
        return dict(N=0, P50=None, P95=None, P99=None, P999=None, max=None)
    # Exact nearest rank; no division by fills and no interpolation.
    result = {'N': len(values), 'max': values[-1]}
    for label, numerator, denominator in [('P50', 1, 2), ('P95', 95, 100), ('P99', 99, 100), ('P999', 999, 1000)]:
        rank = (len(values) * numerator + denominator - 1) // denominator
        result[label] = values[max(0, rank - 1)]
    return result
