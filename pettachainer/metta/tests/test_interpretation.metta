!(import! &self ../petta_chainer)

;; "I saw the man with the telescope": the shared atoms once, and each live
;; reading's sole difference wrapped in `(Interpretation r ...)`.
!(compileadd readingKb (: e_ag (Agent see1 speaker1) (STV 1.0 0.99)))
!(compileadd readingKb (: m_type (Member man1 man) (STV 1.0 0.99)))
!(compileadd readingKb
   (Interpretation r1 (: e_instr (Instrument see1 telescope1) (STV 1.0 0.99))))
!(compileadd readingKb
   (Interpretation r2 (: m_with (With man1 telescope1) (STV 1.0 0.99))))
!(compileadd readingKb
   (: has_rule (Implication (With $x $y) (Has $x $y))
      (CTV (STV 1.0 0.99) (STV 0.0 0.99))))

;; A reading's statement lives in its own context, never in MAIN.
!(test
   (collapse
      (match &kb ((With man1 telescope1) (readingKb $ctx Nil) $prf $tv)
         ($ctx $prf $tv)))
   (((reading r2) m_with (STV 1.0 0.99))))

!(test (kb-readings readingKb) (r1 r2))

;; Per-reading: the inner TV, under that reading only.
!(test
   (collapse
      (query 100 readingKb
         (Interpretation r2 (: $prf (With man1 telescope1) $tv))))
   ((Interpretation r2 (: m_with (With man1 telescope1) (STV 1.0 0.99)))))

!(test
   (collapse
      (query 100 readingKb
         (Interpretation r1 (: $prf (With man1 telescope1) $tv))))
   ())

!(test
   (collapse
      (query 100 readingKb
         (Interpretation $reading (: $prf (With man1 telescope1) $tv))))
   ((Interpretation r2 (: m_with (With man1 telescope1) (STV 1.0 0.99)))))

;; A reading is the shared layer plus its own statements.
!(test
   (collapse
      (query 100 readingKb
         (Interpretation r1 (: $prf (Agent see1 speaker1) $tv))))
   ((Interpretation r1 (: e_ag (Agent see1 speaker1) (STV 1.0 0.99)))))

;; Marginal: content held in one of two readings keeps its strength and has
;; its confidence halved; shared content is answered plainly.
!(test
   (collapse (query 100 readingKb (: $prf (With man1 telescope1) $tv)))
   ((: (readings (r2 m_with)) (With man1 telescope1) (STV 1.0 0.495))))

!(test
   (collapse (query 100 readingKb (: $prf (Agent see1 speaker1) $tv)))
   ((: e_ag (Agent see1 speaker1) (STV 1.0 0.99))))

;; Rules apply inside a reading; a join is executed per reading, so the two
;; readings' contents are never joined.
!(test
   (collapse
      (query 100 readingKb
         (Interpretation r2 (: $prf (Has man1 telescope1) $tv))))
   ((Interpretation r2
       (: (by has_rule m_with) (Has man1 telescope1)
          (STV 1.0 0.9801977747246896)))))

!(test
   (collapse
      (query 100 readingKb
         (: $prf (And (Instrument see1 telescope1) (With man1 telescope1)) $tv)))
   ())

!(test
   (collapse
      (query-many 200 readingKb
         ((: $prf (With man1 telescope1) $tv)
          (Interpretation r1 (: $prf (Instrument see1 telescope1) $tv))
          (: $prf (Agent see1 speaker1) $tv))))
   ((query-result 0
       (: (readings (r2 m_with)) (With man1 telescope1) (STV 1.0 0.495)))
    (query-result 1
       (Interpretation r1
          (: e_instr (Instrument see1 telescope1) (STV 1.0 0.99))))
    (query-result 2 (: e_ag (Agent see1 speaker1) (STV 1.0 0.99)))))

;; Content held by every reading is not discounted.
!(compileadd allReadingsKb
   (Interpretation r1 (: a1 (Agent e1 bob) (STV 1.0 0.99))))
!(compileadd allReadingsKb
   (Interpretation r2 (: a2 (Agent e1 bob) (STV 1.0 0.99))))
!(test
   (collapse (query 100 allReadingsKb (: $prf (Agent e1 bob) $tv)))
   ((: (readings (r1 a1) (r2 a2)) (Agent e1 bob) (STV 1.0 0.99))))

;; Readings are exclusive possibilities, not observations to revise: a denial
;; in one reading and an assertion in the other stay two answers.
!(compileadd splitReadingsKb
   (Interpretation r1 (: n1 (Tall bob) (STV 0.0 0.99))))
!(compileadd splitReadingsKb
   (Interpretation r2 (: y2 (Tall bob) (STV 1.0 0.99))))
!(test
   (collapse (query 100 splitReadingsKb (: $prf (Tall bob) $tv)))
   ((: (readings (r1 n1)) (Tall bob) (STV 0.0 0.495))
    (: (readings (r2 y2)) (Tall bob) (STV 1.0 0.495))))

;; A reading-scoped rule applies inside its reading only.
!(compileadd readingRuleKb (: d1 (Dog fido) (STV 1.0 0.99)))
!(compileadd readingRuleKb
   (Interpretation r1
      (: dogs_bark (Implication (Dog $x) (Barks $x))
         (CTV (STV 1.0 0.99) (STV 0.0 0.99)))))
!(test
   (collapse (query 100 readingRuleKb (: $prf (Barks fido) $tv)))
   ((: (readings (r1 (by dogs_bark d1))) (Barks fido)
       (STV 1.0 0.4900988873623448))))
