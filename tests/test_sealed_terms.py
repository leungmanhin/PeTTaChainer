import re
import time
import unittest

from pettachainer import PeTTaChainer, check_stmt

# A parser seals a non-finite complement as one term under the matrix event's
# Theme and marks what the verb implies about it. These rules conclude the
# sealed term itself (a bound-term conclusion), at the matrix event's tense.
CTV = "(CTV (STV 1.0 0.9) (STV 0.0 1.0))"
CLAUSE = "(Compute clause-event ($c) -> $o)"
RULES = [
    f"(: theme_entailed (Implication (And (Entails $m) (Theme $m $c) {CLAUSE}) $c) {CTV})",
    f"(: theme_entailed_past (Implication (And (Entails $m) (Theme $m $c) (Past $m) {CLAUSE}) (And $c (Past $o))) {CTV})",
    f"(: theme_entailed_future (Implication (And (Entails $m) (Theme $m $c) (Future $m) {CLAUSE}) (And $c (Future $o))) {CTV})",
    f"(: theme_precluded (Implication (And (Precludes $m) (Theme $m $c) {CLAUSE}) (Not $c)) {CTV})",
    f"(: theme_precluded_past (Implication (And (Precludes $m) (Theme $m $c) (Past $m) {CLAUSE}) (Not (And $c (Past $o)))) {CTV})",
    f"(: theme_precluded_future (Implication (And (Precludes $m) (Theme $m $c) (Future $m) {CLAUSE}) (Not (And $c (Future $o)))) {CTV})",
]

# "Lamine managed to open the shed."
OPEN = "(And (Member sk_open_1 open) (Agent sk_open_1 sk_lamine_1) (Patient sk_open_1 sk_shed_1))"
MANAGE = [
    '(: n1 (Name sk_lamine_1 "Lamine") (STV 1.0 0.99))',
    "(: x1 (Member sk_shed_1 shed) (STV 1.0 0.99))",
    "(: e1_member (Member sk_manage_1 manage) (STV 1.0 0.99))",
    "(: e1_agent (Agent sk_manage_1 sk_lamine_1) (STV 1.0 0.99))",
    f"(: e1_theme (Theme sk_manage_1 {OPEN}) (STV 1.0 0.99))",
    "(: e1_past (Past sk_manage_1) (STV 1.0 0.99))",
]
ENTAILS = "(: e1_entails (Entails sk_manage_1) (STV 1.0 0.99))"

# "Teodor failed to arrive."
ARRIVE = "(And (Member sk_arrive_1 arrive) (Agent sk_arrive_1 sk_teodor_1))"
FAIL = [
    '(: n2 (Name sk_teodor_1 "Teodor") (STV 1.0 0.99))',
    "(: f1_member (Member sk_fail_1 fail) (STV 1.0 0.99))",
    f"(: f1_theme (Theme sk_fail_1 {ARRIVE}) (STV 1.0 0.99))",
    "(: f1_past (Past sk_fail_1) (STV 1.0 0.99))",
    "(: f1_precludes (Precludes sk_fail_1) (STV 1.0 0.99))",
]

# "Yusra will get Lamine to send the quilt quickly": four conjuncts, one an
# attachment of the clause's event, under a future matrix.
SEND = (
    "(And (Member sk_send_1 send) (Agent sk_send_1 sk_lamine_1)"
    " (Theme sk_send_1 sk_quilt_1) (Manner sk_send_1 quickly))"
)
GET = [
    "(: x2 (Member sk_quilt_1 quilt) (STV 1.0 0.99))",
    "(: g1_member (Member sk_get_1 get) (STV 1.0 0.99))",
    f"(: g1_theme (Theme sk_get_1 {SEND}) (STV 1.0 0.99))",
    "(: g1_future (Future sk_get_1) (STV 1.0 0.99))",
    "(: g1_entails (Entails sk_get_1) (STV 1.0 0.99))",
]

# A date rule beside them: derivations unrelated to sealed terms.
DATES = [
    "(: t1 (Time sk_bake_1 sk_time_1) (STV 1.0 0.99))",
    "(: t1b (BeforeBy sk_time_1 sk_now_1 1 day) (STV 1.0 0.99))",
    "(: nd (Day sk_now_1 18) (STV 1.0 0.99))",
    f"(: days_before_day (Implication (And (BeforeBy $t $a $n day) (Day $a $d) (Compute - ($d $n) -> $e)) (Day $t $e)) {CTV})",
]

_STV = re.compile(r"\(STV ([0-9.eE+-]+) ([0-9.eE+-]+)\)\)*$")


def stv(answer):
    match = _STV.search(answer)
    if match is None:
        raise AssertionError(f"answer has no STV: {answer}")
    return float(match.group(1)), float(match.group(2))


def kb(*statements):
    handler = PeTTaChainer()
    for statement in statements:
        handler.add_atom(statement)
    return handler


def ask(handler, statement):
    return handler.query(f"(: $prf {statement} $tv)", steps=400, timeout_sec=0)


class TestSealedTermProjection(unittest.TestCase):
    def assert_derived(self, handler, statement, rule):
        answers = ask(handler, statement)
        self.assertEqual(len(answers), 1, answers)
        self.assertIn(f"(by {rule} ", answers[0])
        self.assertIn(statement, answers[0])
        strength, confidence = stv(answers[0])
        self.assertEqual(strength, 1.0)
        self.assertGreater(confidence, 0.85)
        return answers[0]

    def assert_nothing_positive(self, handler, statement):
        for answer in ask(handler, statement):
            self.assertEqual(stv(answer)[0], 0.0, answer)

    def test_the_rules_are_valid_statements(self):
        for rule in RULES:
            with self.subTest(rule=rule):
                self.assertEqual(check_stmt(rule), 1.0)

    def test_each_conjunct_and_the_tense_are_derived_with_provenance(self):
        handler = kb(*MANAGE, ENTAILS, *RULES)
        for conjunct in (
            "(Member sk_open_1 open)",
            "(Agent sk_open_1 sk_lamine_1)",
            "(Patient sk_open_1 sk_shed_1)",
        ):
            with self.subTest(conjunct=conjunct):
                self.assert_derived(handler, conjunct, "theme_entailed")
        answer = self.assert_derived(handler, "(Past sk_open_1)", "theme_entailed_past")
        self.assertIn("(marginal-proj 3 (by theme_entailed_past", answer)
        # The tense attaches to the clause's own event, never another one.
        self.assertEqual(ask(handler, "(Future sk_open_1)"), [])
        self.assertEqual(
            ask(handler, "(Past $e)"),
            [
                "(: e1_past (Past sk_manage_1) (STV 1.0 0.99))",
                answer,
            ],
        )

    def test_the_whole_conjunction_is_queryable(self):
        handler = kb(*MANAGE, ENTAILS, *RULES)
        whole = OPEN[:-1] + " (Past sk_open_1))"
        self.assertEqual(
            ask(handler, whole),
            [
                f"(: (by theme_entailed_past (conjunction e1_entails e1_theme e1_past cpu)) {whole} "
                "(STV 1.0 0.8760223702918006))"
            ],
        )
        answers = ask(handler, OPEN)
        self.assertEqual(len(answers), 1, answers)
        self.assertIn("(by theme_entailed (conjunction e1_entails e1_theme cpu))", answers[0])
        self.assertEqual(stv(answers[0])[0], 1.0)

    def test_rules_added_before_the_sealed_fact(self):
        handler = kb(*RULES, *MANAGE, ENTAILS)
        self.assert_derived(handler, "(Past sk_open_1)", "theme_entailed_past")
        self.assert_derived(handler, "(Patient sk_open_1 sk_shed_1)", "theme_entailed")

    def test_a_one_atom_term_derives_that_atom(self):
        handler = kb(
            "(: e1_member (Member sk_try_1 try) (STV 1.0 0.99))",
            "(: e1_theme (Theme sk_try_1 (Member sk_sleep_1 sleep)) (STV 1.0 0.99))",
            "(: e1_past (Past sk_try_1) (STV 1.0 0.99))",
            "(: e1_entails (Entails sk_try_1) (STV 1.0 0.99))",
            *RULES,
        )
        self.assertEqual(
            ask(handler, "(Member sk_sleep_1 sleep)"),
            [
                "(: (by theme_entailed (conjunction e1_entails e1_theme cpu)) "
                "(Member sk_sleep_1 sleep) (STV 1.0 0.8838458362635058))"
            ],
        )
        self.assert_derived(handler, "(Past sk_sleep_1)", "theme_entailed_past")
        self.assert_derived(
            handler, "(And (Member sk_sleep_1 sleep) (Past sk_sleep_1))", "theme_entailed_past"
        )

    def test_four_conjuncts_with_an_attachment_at_the_future(self):
        handler = kb(*GET, *RULES)
        for conjunct in (
            "(Member sk_send_1 send)",
            "(Agent sk_send_1 sk_lamine_1)",
            "(Theme sk_send_1 sk_quilt_1)",
            "(Manner sk_send_1 quickly)",
        ):
            with self.subTest(conjunct=conjunct):
                self.assert_derived(handler, conjunct, "theme_entailed")
        answer = self.assert_derived(handler, "(Future sk_send_1)", "theme_entailed_future")
        self.assertIn("(marginal-proj 4 (by theme_entailed_future", answer)
        self.assertEqual(ask(handler, "(Past sk_send_1)"), [])
        self.assert_derived(handler, SEND[:-1] + " (Future sk_send_1))", "theme_entailed_future")

    def test_a_precluded_clause_is_one_flattened_negation(self):
        handler = kb(*FAIL, *RULES)
        denied = "(Not (And (Member sk_arrive_1 arrive) (Agent sk_arrive_1 sk_teodor_1) (Past sk_arrive_1)))"
        self.assertEqual(
            ask(handler, denied),
            [
                "(: (negated (negated (by theme_precluded_past "
                f"(conjunction f1_precludes f1_theme f1_past cpu)))) {denied} "
                "(STV 1.0 0.8760223702918006))"
            ],
        )
        self.assert_derived(handler, f"(Not {ARRIVE})", "theme_precluded")
        # Nothing positive leaks from the negation.
        self.assertEqual(ask(handler, "(Member sk_arrive_1 arrive)"), [])
        for statement in (
            "(Agent sk_arrive_1 sk_teodor_1)",
            "(Past sk_arrive_1)",
            ARRIVE,
            ARRIVE[:-1] + " (Past sk_arrive_1))",
        ):
            with self.subTest(statement=statement):
                self.assert_nothing_positive(handler, statement)

    def test_nothing_is_derived_without_the_marker(self):
        handler = kb(*MANAGE, *RULES)
        for statement in (
            "(Member sk_open_1 open)",
            "(Past sk_open_1)",
            OPEN,
            "(Not (And (Member sk_open_1 open) (Agent sk_open_1 sk_lamine_1) (Patient sk_open_1 sk_shed_1) (Past sk_open_1)))",
        ):
            with self.subTest(statement=statement):
                self.assertEqual(ask(handler, statement), [])

    def test_a_marker_inside_a_denied_bundle_derives_nothing(self):
        # "Lamine didn't manage to open the shed": the parser denies the whole
        # matrix clause, so neither the marker nor the sealed term is a fact.
        denied = (
            "(: s1_not (Not (And (Member sk_manage_1 manage) (Agent sk_manage_1 sk_lamine_1)"
            f" (Theme sk_manage_1 {OPEN}) (Past sk_manage_1) (Entails sk_manage_1))) (STV 1.0 0.99))"
        )
        handler = kb(*MANAGE[:2], denied, *RULES)
        for statement in ("(Member sk_open_1 open)", "(Past sk_open_1)", "(Patient sk_open_1 sk_shed_1)"):
            with self.subTest(statement=statement):
                self.assertEqual(ask(handler, statement), [])
        # With the sealed term stored plainly, a marker denied beside it derives
        # nothing positive either.
        handler = kb(*MANAGE, "(: s2_not (Not (And (Entails sk_manage_1) (Past sk_manage_1))) (STV 1.0 0.99))", *RULES)
        for statement in ("(Member sk_open_1 open)", "(Past sk_open_1)"):
            with self.subTest(statement=statement):
                self.assert_nothing_positive(handler, statement)

    def test_clause_event_names_the_clause_event(self):
        handler = PeTTaChainer()
        self.assertEqual(
            handler.handler.process_metta_string(f"!(clause-event {OPEN})"), ["sk_open_1"]
        )
        self.assertEqual(
            handler.handler.process_metta_string("!(clause-event (Member sk_sleep_1 sleep))"),
            ["sk_sleep_1"],
        )
        self.assertEqual(
            handler.handler.process_metta_string(
                "!(collapse (clause-event (And (Agent sk_open_1 sk_lamine_1) (Member sk_open_1 open))))"
            ),
            ["()"],
        )

    def test_queries_stay_fast_with_the_rules_loaded(self):
        def timed(handler, statement):
            start = time.perf_counter()
            answers = ask(handler, statement)
            return answers, time.perf_counter() - start

        unmarked = kb(*MANAGE, *FAIL[:-1], *DATES, *RULES)
        ask(unmarked, '(Name sk_lamine_1 "Lamine")')  # warm-up
        answers, seconds = timed(unmarked, "(Agent sk_manage_1 $x)")
        self.assertEqual(answers, ["(: e1_agent (Agent sk_manage_1 sk_lamine_1) (STV 1.0 0.99))"])
        self.assertLess(seconds, 0.5)
        answers, seconds = timed(unmarked, "(Day sk_time_1 $d)")
        self.assertEqual(len(answers), 1)
        self.assertIn("(Day sk_time_1 17)", answers[0])
        self.assertLess(seconds, 0.5)

        marked = kb(*MANAGE, ENTAILS, *FAIL, *DATES, *RULES)
        ask(marked, '(Name sk_lamine_1 "Lamine")')  # warm-up
        answers, seconds = timed(marked, "(Past sk_open_1)")
        self.assertEqual(len(answers), 1)
        self.assertIn("theme_entailed_past", answers[0])
        self.assertLess(seconds, 2.0)
        answers, seconds = timed(marked, "(Agent sk_manage_1 $x)")
        self.assertEqual(answers, ["(: e1_agent (Agent sk_manage_1 sk_lamine_1) (STV 1.0 0.99))"])
        self.assertLess(seconds, 0.5)


if __name__ == "__main__":
    unittest.main()
