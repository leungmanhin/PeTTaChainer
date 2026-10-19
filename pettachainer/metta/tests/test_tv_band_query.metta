!(import! &self ../petta_chainer)

;; "Who rarely swims?": `(Band lo hi)` in a slot of the query's STV keeps the
;; answers whose returned TV holds that number in [lo, hi], bounds inclusive.
!(compileadd swimKb (: alice_swim (Inheritance alice swim) (STV 0.15 0.9)))
!(compileadd swimKb (: bob_swim (Inheritance bob swim) (STV 0.85 0.9)))
!(compileadd swimKb (: cara_swim (Inheritance cara swim) (STV 0.45 0.9)))
!(compileadd swimKb (: dan_swim (Inheritance dan swim) (STV 0.0 0.9)))

!(test
   (collapse
      (query 400 swimKb
         (: $prf (Inheritance $x swim) (STV (Band 0.05 0.3) $c))))
   ((: alice_swim (Inheritance alice swim) (STV 0.15 0.9))))

!(test
   (collapse
      (query 400 swimKb
         (: $prf (Inheritance $x swim) (STV (Band 0.0 0.05) $c))))
   ((: dan_swim (Inheritance dan swim) (STV 0.0 0.9))))

!(test
   (collapse
      (query 400 swimKb
         (: $prf (Inheritance $x swim) (STV (Band 0.6 0.9) $c))))
   ((: bob_swim (Inheritance bob swim) (STV 0.85 0.9))))

!(test
   (collapse
      (query 400 swimKb
         (: $prf (Inheritance $x swim) (STV (Band 0.5 0.8) $c))))
   ())

;; Both slots at once; inclusive bounds keep the strength at 0.45 and the
;; confidence at 0.9.
!(test
   (collapse
      (query 400 swimKb
         (: $prf (Inheritance $x swim) (STV (Band 0.1 0.45) (Band 0.9 1.0)))))
   ((: alice_swim (Inheritance alice swim) (STV 0.15 0.9))
    (: cara_swim (Inheritance cara swim) (STV 0.45 0.9))))

;; Each batch root keeps its own band; a root whose band holds no answer emits
;; no row.
!(test
   (collapse
      (query-many 400 swimKb
         ((: $prf (Inheritance $x swim) (STV (Band 0.05 0.3) $c))
          (: $prf (Inheritance $x swim) (STV $s (Band 0.95 1.0)))
          (: $prf (Inheritance $x swim) (STV (Band 0.0 0.05) $c)))))
   ((query-result 0 (: alice_swim (Inheritance alice swim) (STV 0.15 0.9)))
    (query-result 2 (: dan_swim (Inheritance dan swim) (STV 0.0 0.9)))))

;; The band sees the belief revision returns: two assertions of one statement
;; revise into one row at 0.5, and neither raw strength is caught. The exact
;; pin keeps matching stored proofs before the merge.
!(compileadd reviseKb (: eve_yes (Inheritance eve swim) (STV 1.0 0.9)))
!(compileadd reviseKb (: eve_no (Inheritance eve swim) (STV 0.0 0.9)))
!(compileadd reviseKb (: fay_no (Inheritance fay swim) (STV 0.0 0.9)))

!(test
   (collapse
      (query 400 reviseKb
         (: $prf (Inheritance $x swim) (STV (Band 0.45 0.55) $c))))
   ((: (merge/revision eve_yes eve_no) (Inheritance eve swim)
       (STV 0.5 0.9473684210526316))))

!(test
   (collapse
      (query 400 reviseKb
         (: $prf (Inheritance $x swim) (STV (Band 0.0 0.05) $c))))
   ((: fay_no (Inheritance fay swim) (STV 0.0 0.9))))

!(test
   (collapse
      (query 400 reviseKb
         (: $prf (Inheritance $x swim) (STV (Band 0.95 1.0) $c))))
   ())

!(test
   (collapse
      (query 400 reviseKb (: $prf (Inheritance $x swim) (STV 0.0 $c))))
   ((: fay_no (Inheritance fay swim) (STV 0.0 0.9))))

;; Over readings, a plain query's band sees the marginal answers; a
;; reading-scoped query's band sees the in-reading answers.
!(compileadd bandReadingsKb
   (Interpretation r1 (: n1 (Tall bob) (STV 0.0 0.99))))
!(compileadd bandReadingsKb
   (Interpretation r2 (: y2 (Tall bob) (STV 1.0 0.99))))

!(test
   (collapse
      (query 100 bandReadingsKb (: $prf (Tall bob) (STV (Band 0.0 0.05) $c))))
   ((: (readings (r1 n1)) (Tall bob) (STV 0.0 0.495))))

!(test
   (collapse
      (query 100 bandReadingsKb (: $prf (Tall bob) (STV $s (Band 0.9 1.0)))))
   ())

!(test
   (collapse
      (query 100 bandReadingsKb
         (Interpretation $r (: $prf (Tall bob) (STV $s (Band 0.9 1.0))))))
   ((Interpretation r1 (: n1 (Tall bob) (STV 0.0 0.99)))
    (Interpretation r2 (: y2 (Tall bob) (STV 1.0 0.99)))))
