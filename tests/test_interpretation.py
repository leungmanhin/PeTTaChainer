import re
import unittest

from pettachainer import PeTTaChainer

# "I saw the man with the telescope": two live readings, nothing selecting one.
# The shared atoms are asserted once; each reading's sole difference is wrapped.
SHARED = [
    "(: sp_type (Member sk_speaker_1 speaker) (STV 1.0 0.99))",
    "(: m_type (Member sk_man_1 man) (STV 1.0 0.99))",
    "(: t_type (Member sk_telescope_1 telescope) (STV 1.0 0.99))",
    "(: e_ev (Member sk_see_1 see) (STV 1.0 0.99))",
    "(: e_ag (Agent sk_see_1 sk_speaker_1) (STV 1.0 0.99))",
    "(: e_st (Stimulus sk_see_1 sk_man_1) (STV 1.0 0.99))",
    "(: e_tns (Past sk_see_1) (STV 1.0 0.99))",
]
READINGS = [
    "(Interpretation r1 (: e_instr (Instrument sk_see_1 sk_telescope_1) (STV 1.0 0.99)))",
    "(Interpretation r2 (: m_with (With sk_man_1 sk_telescope_1) (STV 1.0 0.99)))",
]
WITH = "(With sk_man_1 sk_telescope_1)"

_STV = re.compile(r"\(STV ([0-9.eE+-]+) ([0-9.eE+-]+)\)\)*$")


def stv(answer):
    match = _STV.search(answer)
    if match is None:
        raise AssertionError(f"answer has no STV: {answer}")
    return float(match.group(1)), float(match.group(2))


class TestInterpretationReadings(unittest.TestCase):
    def setUp(self):
        self.handler = PeTTaChainer()
        for statement in SHARED + READINGS:
            self.handler.add_atom(statement)

    def ask(self, query, handler=None):
        return (handler or self.handler).query(query, steps=400, timeout_sec=0)

    def test_wrapper_is_accepted(self):
        handler = PeTTaChainer()
        compiled = handler.add_atom(READINGS[1])
        self.assertTrue(compiled)
        with self.assertRaises(ValueError):
            handler.add_atom("(Interpretation $r (: m (With a b) (STV 1.0 0.9)))")

    def test_per_reading_query_binds_with_the_inner_truth_value(self):
        self.assertEqual(
            self.ask(f"(Interpretation r2 (: $p {WITH} $tv))"),
            [f"(Interpretation r2 (: m_with {WITH} (STV 1.0 0.99)))"],
        )
        # A variable reading names every live reading that holds the content.
        self.assertEqual(
            self.ask(f"(Interpretation $r (: $p {WITH} $tv))"),
            [f"(Interpretation r2 (: m_with {WITH} (STV 1.0 0.99)))"],
        )

    def test_query_under_the_wrong_reading_does_not_bind(self):
        self.assertEqual(self.ask(f"(Interpretation r1 (: $p {WITH} $tv))"), [])
        self.assertEqual(self.ask(f"(Interpretation r3 (: $p {WITH} $tv))"), [])

    def test_marginal_keeps_strength_and_discounts_confidence_by_reading_share(self):
        # "Did the man have the telescope?" -> yes, at half the confidence.
        answers = self.ask(f"(: $p {WITH} $tv)")
        self.assertEqual(len(answers), 1)
        self.assertIn("(readings (r2 m_with))", answers[0])
        strength, confidence = stv(answers[0])
        self.assertEqual(strength, 1.0)
        self.assertAlmostEqual(confidence, 0.99 * 1 / 2)

        instrument = self.ask("(: $p (Instrument sk_see_1 sk_telescope_1) $tv)")
        self.assertEqual(len(instrument), 1)
        self.assertEqual(stv(instrument[0]), (1.0, 0.495))

    def test_readings_are_not_asserted_plainly(self):
        # Neither reading's content is a plain fact, and no plain answer carries
        # the full inner confidence.
        with self.assertRaises(ValueError):
            self.handler.select_facts(WITH)
        for answer in self.ask(f"(: $p {WITH} $tv)"):
            self.assertLess(stv(answer)[1], 0.99)
        # Nor are both readings asserted together: their contents never join.
        self.assertEqual(
            self.ask(
                f"(: $p (And (Instrument sk_see_1 sk_telescope_1) {WITH}) $tv)"
            ),
            [],
        )

    def test_shared_content_is_not_discounted(self):
        self.assertEqual(
            self.ask("(: $p (Agent sk_see_1 sk_speaker_1) $tv)"),
            ["(: e_ag (Agent sk_see_1 sk_speaker_1) (STV 1.0 0.99))"],
        )
        # The shared layer holds under every reading.
        self.assertEqual(
            self.ask("(Interpretation r1 (: $p (Agent sk_see_1 sk_speaker_1) $tv))"),
            ["(Interpretation r1 (: e_ag (Agent sk_see_1 sk_speaker_1) (STV 1.0 0.99)))"],
        )
        # Content held by every reading keeps its full confidence (k = n).
        handler = PeTTaChainer()
        handler.add_atom("(Interpretation r1 (: a1 (Agent e1 bob) (STV 1.0 0.99)))")
        handler.add_atom("(Interpretation r2 (: a2 (Agent e1 bob) (STV 1.0 0.99)))")
        answers = self.ask("(: $p (Agent e1 bob) $tv)", handler)
        self.assertEqual(len(answers), 1)
        self.assertIn("(readings (r1 a1) (r2 a2))", answers[0])
        self.assertEqual(stv(answers[0]), (1.0, 0.99))

    def test_readings_are_not_revision_blended(self):
        handler = PeTTaChainer()
        handler.add_atom("(Interpretation r1 (: n1 (Tall bob) (STV 0.0 0.99)))")
        handler.add_atom("(Interpretation r2 (: y2 (Tall bob) (STV 1.0 0.99)))")
        answers = self.ask("(: $p (Tall bob) $tv)", handler)
        self.assertEqual(
            sorted(stv(answer) for answer in answers), [(0.0, 0.495), (1.0, 0.495)]
        )
        self.assertNotIn("merge/revision", " ".join(answers))

    def test_rules_and_joins_are_executed_per_reading(self):
        self.handler.add_atom(
            "(: has_rule (Implication (With $x $y) (Has $x $y)) "
            "(CTV (STV 1.0 0.99) (STV 0.0 0.99)))"
        )
        in_reading = self.ask(
            "(Interpretation r2 (: $p (Has sk_man_1 sk_telescope_1) $tv))"
        )
        self.assertEqual(len(in_reading), 1)
        self.assertIn("(by has_rule m_with)", in_reading[0])

        marginal = self.ask("(: $p (Has sk_man_1 sk_telescope_1) $tv)")
        self.assertEqual(len(marginal), 1)
        self.assertAlmostEqual(stv(marginal[0])[1], stv(in_reading[0])[1] / 2)

        joined = self.ask(f"(: $p (And (Member $m man) (With $m $t)) $tv)")
        self.assertEqual(len(joined), 1)
        self.assertIn("(readings (r2 (conjunction m_type m_with)))", joined[0])

    def test_query_many_answers_both_modes(self):
        results = self.handler.query_many(
            [
                f"(: $p {WITH} $tv)",
                "(Interpretation r1 (: $p (Instrument sk_see_1 sk_telescope_1) $tv))",
                "(: $p (Agent sk_see_1 sk_speaker_1) $tv)",
                f"(Interpretation r1 (: $p {WITH} $tv))",
            ],
            steps=400,
            timeout_sec=0,
        )
        self.assertEqual(len(results), 4)
        self.assertEqual(len(results[0]), 1)
        self.assertEqual(stv(results[0][0]), (1.0, 0.495))
        self.assertEqual(
            results[1],
            [
                "(Interpretation r1 (: e_instr (Instrument sk_see_1 sk_telescope_1) "
                "(STV 1.0 0.99)))"
            ],
        )
        self.assertEqual(
            results[2], ["(: e_ag (Agent sk_see_1 sk_speaker_1) (STV 1.0 0.99))"]
        )
        self.assertEqual(results[3], [])

    def test_remove_statement_retracts_a_reading_statement(self):
        self.handler.remove_statement("m_with")
        self.assertEqual(self.ask(f"(: $p {WITH} $tv)"), [])
        self.assertEqual(self.ask(f"(Interpretation r2 (: $p {WITH} $tv))"), [])
        self.assertNotIn(READINGS[1], [atom for atom, _ in self.handler._added_atoms])


if __name__ == "__main__":
    unittest.main()
