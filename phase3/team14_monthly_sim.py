"""Isolated, in-memory, TEST-ONLY monthly lesson ledger. No provider or DB integration."""
from dataclasses import dataclass, field

class ContractError(ValueError):
    pass

@dataclass
class Month:
    lesson_prices: tuple[int, ...]
    commission_bps: int = 2000  # hypothetical, NOT approved
    referral_bps: int = 300    # hypothetical, NOT approved
    completed: set[int] = field(default_factory=set)
    refunded: dict[int, int] = field(default_factory=dict)
    operations: dict[str, tuple] = field(default_factory=dict)
    entries: list[tuple] = field(default_factory=list)

    def __post_init__(self):
        if not self.lesson_prices or any(type(p) is not int or p <= 0 for p in self.lesson_prices):
            raise ContractError("positive integer KRW prices required")
        if any(type(b) is not int or not 0 <= b <= 10000 for b in (self.commission_bps, self.referral_bps)):
            raise ContractError("invalid test rates")
        if self.commission_bps + self.referral_bps > 10000:
            raise ContractError("rates exceed gross")
        self.lesson_prices = tuple(self.lesson_prices)

    def _once(self, key, signature, fn):
        if not isinstance(key, str) or not key:
            raise ContractError("operation id required")
        if key in self.operations:
            if self.operations[key] != signature:
                raise ContractError("idempotency key reused with different request")
            return False
        fn()
        self.operations[key] = signature
        return True

    def _index(self, index):
        if type(index) is not int or not 0 <= index < len(self.lesson_prices):
            raise ContractError("invalid lesson index")

    def complete(self, index, operation_id):
        self._index(index)
        def apply():
            if index in self.completed or index in self.refunded:
                raise ContractError("already settled or refunded")
            price = self.lesson_prices[index]
            teacher = price * (10000-self.commission_bps) // 10000
            referral = price * self.referral_bps // 10000
            platform = price - teacher - referral
            self.entries.extend((index, name, value, operation_id) for name, value in
                                (("teacher_accrual", teacher), ("referral_accrual", referral),
                                 ("platform_remainder", platform)))
            self.completed.add(index)
        return self._once(operation_id, ("complete", index), apply)

    def refund(self, index, amount, operation_id):
        self._index(index)
        if type(amount) is not int or amount <= 0:
            raise ContractError("positive integer refund required")
        def apply():
            if index in self.completed:
                raise ContractError("completed lesson needs manual dispute resolution")
            if self.refunded.get(index, 0) + amount > self.lesson_prices[index]:
                raise ContractError("refund exceeds lesson price")
            self.refunded[index] = self.refunded.get(index, 0) + amount
            self.entries.append((index, "refund_reversal", -amount, operation_id))
        return self._once(operation_id, ("refund", index, amount), apply)

    def totals(self):
        gross = sum(self.lesson_prices)
        teacher = sum(e[2] for e in self.entries if e[1] == "teacher_accrual")
        referral = sum(e[2] for e in self.entries if e[1] == "referral_accrual")
        platform = sum(e[2] for e in self.entries if e[1] == "platform_remainder")
        refunds = sum(self.refunded.values())
        pending = gross - sum(self.lesson_prices[i] for i in self.completed) - refunds
        if teacher + referral + platform + refunds + pending != gross:
            raise AssertionError("ledger conservation failure")
        return dict(gross=gross, teacher=teacher, referral=referral,
                    platform=platform, refunded=refunds, pending=pending,
                    real_money=False, rates_approved=False)
