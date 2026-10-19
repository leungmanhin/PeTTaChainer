import re
import unittest

from pettachainer import PeTTaChainer

# "Who rarely swims?": a vague quantity asks for a band of the truth value.
# `(Band lo hi)` fills the strength or confidence slot of the query's STV, bounds
# inclusive, and keeps the answers whose returned TV lies in it.
ALICE = "(: alice_swim (Inheritance alice swim) (STV 0.15 0.9))"  # rarely
BOB = "(: bob_swim (Inheritance bob swim) (STV 0.85 0.9))"  # often
CARA = "(: cara_swim (Inheritance cara swim) (STV 0.45 0.9))"  # sometimes
DAN = "(: dan_swim (Inheritance dan swim) (STV 0.0 0.9))"  # never
SWIMMERS = [ALICE, BOB, CARA, DAN]

_STV = re.compile(r"\(STV ([0-9.eE+-]+) ([0-9.eE+-]+)\)\)*$")


def stv(answer):
    match = _STV.search(answer)
    if match is None:
        raise AssertionError(f"answer has no STV: {answer}")
    return float(match.group(1)), float(match.group(2))


def swim(tv):
    return f"(: $prf (Inheritance $x swim) {tv})"


def kb(*statements):
    handler = PeTTaChainer()
    for statement in statements:
        handler.add_atom(statement)
    return handler


class TestTruthValueBands(unittest.TestCase):
    def setUp(self):
        self.handler = kb(*SWIMMERS)

    def ask(self, query, handler=None):
        return (handler or self.handler).query(query, steps=400, timeout_sec=0)

    def test_strength_band_returns_exactly_the_answers_inside_it(self):
        self.assertEqual(self.ask(swim("(STV (Band 0.05 0.3) $c)")), [ALICE])
        self.assertEqual(self.ask(swim("(STV (Band 0.0 0.05) $c)")), [DAN])
        self.assertEqual(self.ask(swim("(STV (Band 0.6 0.9) $c)")), [BOB])
        self.assertEqual(self.ask(swim("(STV (Band 0.5 0.8) $c)")), [])
        self.assertEqual(self.ask(swim("(STV (Band 0.3 0.05) $c)")), [])

    def test_band_query_is_the_open_query_kept_by_its_returned_tv(self):
        # The rows keep the concrete TV and the order of `(STV $s $c)`.
        everything = self.ask(swim("(STV $s $c)"))
        self.assertEqual(everything, SWIMMERS)
        for low, high in ((0.05, 0.3), (0.1, 0.5), (0.4, 1.0), (0.0, 1.0)):
            with self.subTest(band=(low, high)):
                answers = self.ask(swim(f"(STV (Band {low} {high}) $c)"))
                self.assertEqual(
                    answers,
                    [a for a in everything if low <= stv(a)[0] <= high],
                )
                self.assertNotIn("Band", " ".join(answers))

    def test_bounds_are_inclusive(self):
        self.assertEqual(self.ask(swim("(STV (Band 0.15 0.45) $c)")), [ALICE, CARA])
        self.assertEqual(self.ask(swim("(STV (Band 0.0 0.0) $c)")), [DAN])
        self.assertEqual(self.ask(swim("(STV $s (Band 0.9 0.9))")), SWIMMERS)

    def test_confidence_band_and_both_bands(self):
        handler = kb(
            "(: p1 (Claim one) (STV 0.9 0.3))",
            "(: p2 (Claim two) (STV 0.9 0.95))",
            "(: p3 (Claim three) (STV 0.2 0.95))",
        )
        doubtful = self.ask("(: $prf (Claim $x) (STV $s (Band 0.0 0.5)))", handler)
        self.assertEqual(doubtful, ["(: p1 (Claim one) (STV 0.9 0.3))"])
        established = self.ask("(: $prf (Claim $x) (STV $s (Band 0.9 1.0)))", handler)
        self.assertEqual(
            established,
            ["(: p2 (Claim two) (STV 0.9 0.95))", "(: p3 (Claim three) (STV 0.2 0.95))"],
        )
        both = self.ask("(: $prf (Claim $x) (STV (Band 0.8 1.0) (Band 0.9 1.0)))", handler)
        self.assertEqual(both, ["(: p2 (Claim two) (STV 0.9 0.95))"])
        # A band and an exact number combine; the number keeps pinning.
        mixed = self.ask("(: $prf (Claim $x) (STV (Band 0.8 1.0) 0.95))", handler)
        self.assertEqual(mixed, ["(: p2 (Claim two) (STV 0.9 0.95))"])

    def test_band_sees_the_belief_revised_from_two_assertions(self):
        # Measured: 1.0/0.9 and 0.0/0.9 on one proposition revise into a
        # single canonical row at (STV 0.5 0.9473684210526316).
        handler = kb(
            "(: eve_yes (Inheritance eve swim) (STV 1.0 0.9))",
            "(: eve_no (Inheritance eve swim) (STV 0.0 0.9))",
            "(: fay_no (Inheritance fay swim) (STV 0.0 0.9))",
        )
        merged = (
            "(: (merge/revision eve_yes eve_no) (Inheritance eve swim) "
            "(STV 0.5 0.9473684210526316))"
        )
        fay = "(: fay_no (Inheritance fay swim) (STV 0.0 0.9))"
        self.assertEqual(self.ask(swim("$tv"), handler), [merged, fay])
        self.assertEqual(self.ask(swim("(STV (Band 0.45 0.55) $c)"), handler), [merged])
        # Neither raw assertion's strength is the belief any more.
        self.assertEqual(self.ask(swim("(STV (Band 0.0 0.05) $c)"), handler), [fay])
        self.assertEqual(self.ask(swim("(STV (Band 0.95 1.0) $c)"), handler), [])

    def test_band_sees_merged_derivations_the_exact_pin_does_not(self):
        handler = kb(
            "(: fido_dog (Dog fido) (STV 0.8 0.9))",
            "(: fido_cute (Cute fido) (STV 0.9 0.9))",
            "(: dog_pet (Implication (Dog $x) (Pet $x)) (CTV (STV 0.9 0.9) (STV 0.1 0.9)))",
            "(: cute_pet (Implication (Cute $x) (Pet $x)) (CTV (STV 0.3 0.9) (STV 0.1 0.9)))",
        )
        # The two derivations, 0.74 and 0.28 alone, revise into one answer.
        merged = self.ask("(: $prf (Pet $x) $tv)", handler)
        self.assertEqual(len(merged), 1)
        self.assertIn("merge/revision", merged[0])
        self.assertAlmostEqual(stv(merged[0])[0], 0.5121117360301717)
        self.assertEqual(self.ask("(: $prf (Pet $x) (STV (Band 0.5 0.55) $c))", handler), merged)
        self.assertEqual(self.ask("(: $prf (Pet $x) (STV (Band 0.25 0.3) $c))", handler), [])
        self.assertEqual(self.ask("(: $prf (Pet $x) (STV (Band 0.7 0.8) $c))", handler), [])
        # The exact pin still matches one derivation before the merge.
        self.assertEqual(
            self.ask("(: $prf (Pet $x) (STV 0.28 $c))", handler),
            ["(: (by cute_pet fido_cute) (Pet fido) (STV 0.28 0.9122169642672002))"],
        )

    def test_exact_pin_is_unchanged(self):
        handler = kb(
            "(: eve_yes (Inheritance eve swim) (STV 1.0 0.9))",
            "(: eve_no (Inheritance eve swim) (STV 0.0 0.9))",
            "(: fay_no (Inheritance fay swim) (STV 0.0 0.9))",
        )
        self.assertEqual(
            self.ask(swim("(STV 0.0 $c)"), handler),
            ["(: fay_no (Inheritance fay swim) (STV 0.0 0.9))"],
        )
        self.assertEqual(self.ask(swim("(STV 1.0 $c)"), handler), [])
        self.assertEqual(self.ask(swim("(STV 0.0 $c)")), [DAN])

    def test_rule_derived_answers_are_kept_by_their_derived_tv(self):
        handler = kb(
            "(: fido_dog (Dog fido) (STV 0.8 0.9))",
            "(: rex_dog (Dog rex) (STV 1.0 0.9))",
            "(: dog_animal (Implication (Dog $x) (Animal $x)) "
            "(CTV (STV 1.0 0.9) (STV 0.0 0.9)))",
        )
        derived = self.ask("(: $prf (Animal $x) (STV $s $c))", handler)
        self.assertEqual(len(derived), 2)
        fido = [a for a in derived if "(Animal fido)" in a]
        rex = [a for a in derived if "(Animal rex)" in a]
        self.assertIn("(by dog_animal fido_dog)", fido[0])
        self.assertEqual(self.ask("(: $prf (Animal $x) (STV (Band 0.7 0.9) $c))", handler), fido)
        self.assertEqual(self.ask("(: $prf (Animal $x) (STV (Band 0.95 1.0) $c))", handler), rex)
        # The derived confidence decides a confidence band, not the premise's.
        high_confidence = self.ask("(: $prf (Animal $x) (STV $s (Band 0.85 1.0)))", handler)
        self.assertEqual(high_confidence, fido)
        self.assertLess(stv(rex[0])[1], 0.85)

    def test_band_on_a_concrete_inheritance_query(self):
        answers = self.ask("(: $prf (Inheritance alice swim) (STV (Band 0.05 0.3) $c))")
        self.assertEqual(len(answers), 1)
        self.assertEqual(stv(answers[0])[0], 0.15)
        self.assertEqual(self.ask("(: $prf (Inheritance bob swim) (STV (Band 0.05 0.3) $c))"), [])

    def test_band_on_a_conjunction_constrains_the_conjunction_tv(self):
        handler = kb(
            ALICE,
            BOB,
            "(: alice_run (Inheritance alice run) (STV 0.9 0.9))",
            "(: bob_run (Inheritance bob run) (STV 0.95 0.9))",
        )
        both = "(: $prf (And (Inheritance $x swim) (Inheritance $x run)) {})"
        joined = self.ask(both.format("$tv"), handler)
        alice = [a for a in joined if "alice_swim alice_run" in a]
        bob = [a for a in joined if "bob_swim bob_run" in a]
        self.assertEqual(stv(alice[0])[0], 0.135)
        # 0.15 (alice swims) is outside the band; their conjunction is inside.
        self.assertEqual(self.ask(both.format("(STV (Band 0.1 0.14) $c)"), handler), alice)
        self.assertEqual(self.ask(both.format("(STV (Band 0.8 0.85) $c)"), handler), bob)
        self.assertEqual(self.ask(both.format("(STV (Band 0.86 1.0) $c)"), handler), [])

    def test_band_on_an_implication_reads_the_positive_branch(self):
        handler = kb(
            "(: fido_dog (Dog fido) (STV 0.8 0.9))",
            "(: dog_animal (Implication (Dog $x) (Animal $x)) "
            "(CTV (STV 1.0 0.9) (STV 0.0 0.9)))",
        )
        query = "(: $prf (Implication (Dog $x) (Animal $x)) (STV (Band {} {}) $c))"
        strong = self.ask(query.format(0.9, 1.0), handler)
        self.assertEqual(len(strong), 1)
        self.assertIn("(CTV (STV 1.0 ", strong[0])
        self.assertEqual(self.ask(query.format(0.0, 0.5), handler), [])

    def test_band_applies_to_reading_marginals(self):
        handler = kb(
            "(Interpretation r1 (: n1 (Tall bob) (STV 0.0 0.99)))",
            "(Interpretation r2 (: y2 (Tall bob) (STV 1.0 0.99)))",
            "(: t_ann (Tall ann) (STV 0.9 0.99))",
        )
        ann = "(: t_ann (Tall ann) (STV 0.9 0.99))"
        not_tall = "(: (readings (r1 n1)) (Tall bob) (STV 0.0 0.495))"
        tall = "(: (readings (r2 y2)) (Tall bob) (STV 1.0 0.495))"
        self.assertEqual(self.ask("(: $p (Tall $x) $tv)", handler), [ann, not_tall, tall])
        self.assertEqual(
            self.ask("(: $p (Tall $x) (STV (Band 0.0 0.05) $c))", handler), [not_tall]
        )
        # The marginal confidence is what the band sees, not the in-reading one.
        self.assertEqual(
            self.ask("(: $p (Tall $x) (STV $s (Band 0.9 1.0)))", handler), [ann]
        )
        self.assertEqual(
            self.ask("(: $p (Tall $x) (STV $s (Band 0.4 0.5)))", handler),
            [not_tall, tall],
        )
        self.assertEqual(
            self.ask("(Interpretation r2 (: $p (Tall bob) (STV $s (Band 0.9 1.0))))", handler),
            ["(Interpretation r2 (: y2 (Tall bob) (STV 1.0 0.99)))"],
        )
        self.assertEqual(
            self.ask("(Interpretation $r (: $p (Tall bob) (STV (Band 0.0 0.05) $c)))", handler),
            ["(Interpretation r1 (: n1 (Tall bob) (STV 0.0 0.99)))"],
        )

    def test_query_many_applies_each_roots_band(self):
        results = self.handler.query_many(
            [
                swim("(STV (Band 0.05 0.3) $c)"),
                swim("$tv"),
                swim("(STV (Band 0.0 0.05) $c)"),
                swim("(STV (Band 0.5 0.8) $c)"),
                swim("(STV $s (Band 0.9 1.0))"),
            ],
            steps=400,
            timeout_sec=0,
        )
        self.assertEqual(results, [[ALICE], SWIMMERS, [DAN], [], SWIMMERS])

    def test_band_is_query_only(self):
        handler = PeTTaChainer()
        for statement in (
            "(: b1 (Inheritance bob swim) (STV (Band 0.05 0.3) 0.9))",
            "(: b2 (Inheritance bob swim) (STV 0.5 (Band 0.8 1.0)))",
            "(Interpretation r1 (: b3 (Inheritance bob swim) (STV (Band 0.05 0.3) 0.9)))",
        ):
            with self.subTest(statement=statement):
                with self.assertRaises(ValueError):
                    handler.add_atom(statement)
        # Nothing reached the KB: the proposition still takes a plain statement.
        handler.add_atom("(: b4 (Inheritance bob swim) (STV 0.5 0.9))")
        self.assertEqual(
            self.ask(swim("$tv"), handler),
            ["(: b4 (Inheritance bob swim) (STV 0.5 0.9))"],
        )

    def test_misplaced_or_malformed_band_is_rejected(self):
        for query in (
            swim("(STV (Band low high) $c)"),
            swim("(STV (Band 0.3) $c)"),
            swim("(Band 0.0 1.0)"),
            "(: $prf (Implication (Dog $x) (Animal $x)) (CTV (STV (Band 0.5 1.0) $c) $n))",
        ):
            with self.subTest(query=query):
                with self.assertRaises(ValueError):
                    self.ask(query)


if __name__ == "__main__":
    unittest.main()
