import unittest

from pettachainer import check_query, check_stmt


class TestPlnValidator(unittest.TestCase):
    def test_check_stmt_accepts_supported_forms(self):
        for stmt in (
            "(: s1 (Dog fido) (STV 1.0 1.0))",
            "(: s2 (HeightDist g1 alice) (PointMass 170.0))",
            "(: s3 (CountDist g1) (NatDist ((0 0.5) (1 0.5))))",
            "(: s4 (CountDist g1) (ParticleDist 0 1.0))",
            "(: r1 (Implication (Dog $x) (Animal $x)) (CTV (STV 0.9 0.8) (STV 0.1 0.7)))",
        ):
            with self.subTest(stmt=stmt):
                self.assertEqual(check_stmt(stmt), 1.0)

    def test_check_stmt_rejects_invalid_forms(self):
        for stmt in (
            "(: $prf (Dog fido) (STV 1.0 1.0))",
            "(: s5 (Dog fido) (CustomTV 0.9))",
            "(: r2 (Rule) (CTV (STV 0.9 0.8)))",
            "(: r3 (Rule) (CTV (STV 0.9 0.8) (CustomTV 0.1)))",
            "(: r4 (Rule) (CTV (PointMass 0.9) (STV 0.1 0.7)))",
            "!(compileadd kb (Dog fido))",
            "!(compileadd kb (: s2 (Dog fido) (STV 1.0 1.0)))",
        ):
            with self.subTest(stmt=stmt):
                self.assertEqual(check_stmt(stmt), 0.0)

    def test_check_stmt_requires_numeric_truth_values(self):
        # A band is query-only; a stored truth value is concrete.
        for stmt in (
            "(: b1 (Dog fido) (STV (Band 0.1 0.3) 0.9))",
            "(: b2 (Dog fido) (STV 0.5 (Band 0.8 1.0)))",
            "(: b3 (Rule) (CTV (STV (Band 0.8 1.0) 0.8) (STV 0.1 0.7)))",
            "(Interpretation r1 (: b4 (Dog fido) (STV (Band 0.1 0.3) 0.9)))",
            "(: b5 (Dog fido) (Band 0.1 0.3))",
            "(: v1 (Dog fido) (STV $s 0.9))",
            "(: v2 (Dog fido) (STV high 0.99))",
        ):
            with self.subTest(stmt=stmt):
                self.assertEqual(check_stmt(stmt), 0.0)
        self.assertEqual(check_stmt("(: n1 (Dog fido) (STV 1 0))"), 1.0)

    def test_check_stmt_accepts_reading_scoped_statements(self):
        for stmt in (
            "(Interpretation r2 (: m_with (With man telescope) (STV 1.0 0.99)))",
            "(Interpretation r1 (: r (Implication (Dog $x) (Animal $x)) (CTV (STV 0.9 0.8) (STV 0.1 0.7))))",
        ):
            with self.subTest(stmt=stmt):
                self.assertEqual(check_stmt(stmt), 1.0)
        for stmt in (
            "(Interpretation $r (: m_with (With man telescope) (STV 1.0 0.99)))",
            "(Interpretation (r 2) (: m_with (With man telescope) (STV 1.0 0.99)))",
            "(Interpretation r2 (: $prf (With man telescope) (STV 1.0 0.99)))",
            "(Interpretation r2 (: m_with (With man telescope) (CustomTV 0.9)))",
            "(Interpretation r2 m_with)",
        ):
            with self.subTest(stmt=stmt):
                self.assertEqual(check_stmt(stmt), 0.0)

    def test_check_query_accepts_inner_form(self):
        self.assertEqual(check_query("(: $prf (Dog fido) $tv)"), 1.0)

    def test_check_query_accepts_reading_scoped_queries(self):
        self.assertEqual(check_query("(Interpretation r2 (: $prf (Dog fido) $tv))"), 1.0)
        self.assertEqual(check_query("(Interpretation $r (: $prf (Dog fido) $tv))"), 1.0)
        self.assertEqual(check_query("(Interpretation r2 (: proof1 (Dog fido) $tv))"), 0.0)

    def test_check_query_rejects_invalid_forms(self):
        for query in (
            "(: proof1 (Dog fido) $tv)",
            "!(query 10 kb (Dog fido))",
            "!(query 10 kb (: $prf (Dog fido) $tv))",
        ):
            with self.subTest(query=query):
                self.assertEqual(check_query(query), 0.0)

    def test_check_query_accepts_bands_in_the_stv_slots(self):
        for query in (
            "(: $prf (Dog $x) (STV (Band 0.05 0.3) $c))",
            "(: $prf (Dog $x) (STV $s (Band 0.8 1.0)))",
            "(: $prf (Dog $x) (STV (Band 0 1) (Band 0.5 1)))",
            "(: $prf (Dog $x) (STV (Band 0.8 1.0) 0.95))",
            "(Interpretation $r (: $prf (Dog $x) (STV (Band 0.05 0.3) $c)))",
            "(: $prf (Dog $x) (STV 0.0 $c))",
            "(: $prf (Rule) (CTV (STV 1.0 $c) $neg))",
        ):
            with self.subTest(query=query):
                self.assertEqual(check_query(query), 1.0)

    def test_check_query_rejects_misplaced_or_malformed_bands(self):
        for query in (
            "(: $prf (Dog $x) (STV (Band low high) $c))",
            "(: $prf (Dog $x) (STV (Band $low 0.3) $c))",
            "(: $prf (Dog $x) (STV (Band 0.3) $c))",
            "(: $prf (Dog $x) (STV $s (Band 0.1 0.2 0.3)))",
            "(: $prf (Dog $x) (Band 0.0 1.0))",
            "(: $prf (Rule) (CTV (STV (Band 0.5 1.0) $c) $neg))",
            "(: $prf (Rule) (CTV $pos (STV $s (Band 0.0 0.1))))",
        ):
            with self.subTest(query=query):
                self.assertEqual(check_query(query), 0.0)


if __name__ == "__main__":
    unittest.main()
