"""
Filename: test_cra_kernel.py
"""
import unittest
from decimal import Decimal
from cra_mathematical_kernel import CRAMathematicalKernel

class TestCRAMathematicalKernel(unittest.TestCase):
    def setUp(self):
        self.kernel = CRAMathematicalKernel("10000000.00", "1713000000.00", "44000000000.00")
        self.s0 = (Decimal("10000000.00"), Decimal("1713000000.00"), Decimal("44000000000.00"))

    def test_invariant_valuation(self):
        self.assertEqual(self.kernel.invariant_valuation, Decimal("45723000000.00"))

    def test_transitions_conserve_valuation(self):
        s1 = self.kernel.transition_l3_to_l2(self.s0, "100000000.00")
        self.assertEqual(sum(s1), self.kernel.invariant_valuation)

    def test_weight_closure(self):
        w = self.kernel.compute_weights(self.s0)
        self.assertEqual(sum(w), Decimal("1.00000000"))

    def test_bounds_breach_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.kernel.transition_l3_to_l2(self.s0, "50000000000.00")

    def test_state_root_determinism(self):
        r1 = self.kernel.compute_state_root(self.s0, 0)
        r2 = self.kernel.compute_state_root(self.s0, 0)
        self.assertEqual(r1, r2)

if __name__ == "__main__":
    unittest.main()
