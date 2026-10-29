"""Independent HQ audit of simulated referral graph, not a real payment or team-bot run.

Exhaustively compare 625 four-node directed-parent graphs to a separately
implemented Kahn topological oracle. The oracle does not reuse the product's
path-walking cycle detector, and does not approve referral business policy.
"""
import itertools
import unittest
from team14_referral_scenarios import simulate_referral
from team14_persistent import SimError


def oracle_has_cycle(edges):
    """Independently remove zero-indegree vertices until the graph is empty."""
    nodes = set()
    incoming = {}
    outgoing = {}
    for child, parent in edges:
        nodes.update((child, parent))
        outgoing.setdefault(child, []).append(parent)
        incoming[parent] = incoming.get(parent, 0) + 1
        incoming.setdefault(child, incoming.get(child, 0))
    queue = [node for node in nodes if incoming.get(node, 0) == 0]
    removed = 0
    while queue:
        node = queue.pop()
        removed += 1
        for parent in outgoing.get(node, ()):
            incoming[parent] -= 1
            if incoming[parent] == 0:
                queue.append(parent)
    return removed != len(nodes)


class IndependentReferralOracleTests(unittest.TestCase):
    def test_all_625_four_node_parent_graphs_match_independent_oracle(self):
        nodes = tuple("abcd")
        checked = 0
        cycles = 0
        for parents in itertools.product((None,) + nodes, repeat=len(nodes)):
            edges = [(node, parent) for node, parent in zip(nodes, parents)
                     if parent is not None]
            expected_cycle = oracle_has_cycle(edges)
            if expected_cycle:
                cycles += 1
                with self.subTest(parents=parents):
                    with self.assertRaises(SimError) as ctx:
                        simulate_referral(10001, edges, (300, 100), 2000)
                    self.assertEqual(ctx.exception.code, "CONFLICT")
            else:
                with self.subTest(parents=parents):
                    result = simulate_referral(10001, edges, (300, 100), 2000)
                    self.assertEqual(
                        result["gross"],
                        result["teacher"] + result["platform"] + sum(result["rewards"]),
                    )
                    self.assertFalse(result["real_money"])
                    self.assertFalse(result["payment_enabled"])
                    self.assertFalse(result["policy_approved"])
            checked += 1
        self.assertEqual(checked, 625)
        self.assertGreater(cycles, 0)
        self.assertLess(cycles, checked)

    def test_edge_order_does_not_change_graph_validation_or_mock_amounts(self):
        edges = [("a", "b"), ("c", "b"), ("b", "d"), ("e", "d")]
        expected = simulate_referral(10001, edges)
        for order in itertools.permutations(edges):
            with self.subTest(order=order):
                self.assertEqual(simulate_referral(10001, order), expected)


if __name__ == "__main__":
    unittest.main()
