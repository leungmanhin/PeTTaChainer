!(import! &self ../petta_chainer)

;; `clause-event` names the event of a sealed clause: the subject of its first
;; atom, the clause's own (Member event class).
!(test
   (clause-event
      (And (Member sk_open_1 open) (Agent sk_open_1 sk_lamine_1)))
   sk_open_1)
!(test (clause-event (Member sk_sleep_1 sleep)) sk_sleep_1)
!(test
   (collapse
      (clause-event
         (And (Agent sk_open_1 sk_lamine_1) (Member sk_open_1 open))))
   ())
!(test (collapse (clause-event sk_apple_1)) ())

;; A rule concluding a bound term is a template, never a rule whose variable
;; conclusion would unify with every goal. Without a sealed term it leaves
;; nothing in the conclusion index.
!(compileadd templateKb
   (: entailed
      (Implication (And (Entails $m) (Theme $m $c)) $c)
      (CTV (STV 1.0 0.9) (STV 0.0 1.0))))
!(compileadd templateKb (: e1_entails (Entails sk_manage_1) (STV 1.0 0.99)))
!(test
   (collapse
      (match ccls_index (($type (templateKb $ctx $vars) $prf $tv) $id $args)
         $type))
   ())

;; An entity Theme binds no term: still nothing.
!(compileadd templateKb (: e2_theme (Theme sk_eat_1 sk_apple_1) (STV 1.0 0.99)))
!(test
   (collapse
      (match ccls_index (($type (templateKb $ctx $vars) $prf $tv) $id $args)
         $type))
   ())

;; A stored sealed term yields one instance, whose conclusion is the term's
;; conjunction with the clause's event computed into the tense atom.
!(compileadd sealedKb
   (: e1_theme
      (Theme sk_manage_1
         (And (Member sk_open_1 open) (Agent sk_open_1 sk_lamine_1)))
      (STV 1.0 0.99)))
!(compileadd sealedKb (: e1_past (Past sk_manage_1) (STV 1.0 0.99)))
!(compileadd sealedKb (: e1_entails (Entails sk_manage_1) (STV 1.0 0.99)))
!(compileadd sealedKb
   (: entailed_past
      (Implication
         (And (Entails $m) (Theme $m $c) (Past $m)
              (Compute clause-event ($c) -> $o))
         (And $c (Past $o)))
      (CTV (STV 1.0 0.9) (STV 0.0 1.0))))
!(test
   (collapse
      (match ccls_index
         (($type (sealedKb $ctx $vars) (by entailed_past $prf) $tv) $id $args)
         $type))
   ((And (Member sk_open_1 open) (Agent sk_open_1 sk_lamine_1)
         (Past sk_open_1))))

!(test
   (collapse (query 400 sealedKb (: $prf (Past sk_open_1) $tv)))
   ((: (marginal-proj 2
         (by entailed_past (conjunction e1_entails e1_theme e1_past cpu)))
       (Past sk_open_1) (STV 1.0 0.8760223702918006))))
!(test
   (collapse
      (query 400 sealedKb
         (: $prf
            (And (Member sk_open_1 open) (Agent sk_open_1 sk_lamine_1)
                 (Past sk_open_1))
            $tv)))
   ((: (by entailed_past (conjunction e1_entails e1_theme e1_past cpu))
       (And (Member sk_open_1 open) (Agent sk_open_1 sk_lamine_1)
            (Past sk_open_1))
       (STV 1.0 0.8760223702918006))))

;; The precluding twin concludes one negated conjunction over the flattened
;; term, and nothing positive.
!(compileadd deniedKb
   (: f1_theme
      (Theme sk_fail_1
         (And (Member sk_arrive_1 arrive) (Agent sk_arrive_1 sk_teodor_1)))
      (STV 1.0 0.99)))
!(compileadd deniedKb (: f1_past (Past sk_fail_1) (STV 1.0 0.99)))
!(compileadd deniedKb (: f1_precludes (Precludes sk_fail_1) (STV 1.0 0.99)))
!(compileadd deniedKb
   (: precluded_past
      (Implication
         (And (Precludes $m) (Theme $m $c) (Past $m)
              (Compute clause-event ($c) -> $o))
         (Not (And $c (Past $o))))
      (CTV (STV 1.0 0.9) (STV 0.0 1.0))))
!(test
   (collapse
      (query 400 deniedKb
         (: $prf
            (Not (And (Member sk_arrive_1 arrive)
                      (Agent sk_arrive_1 sk_teodor_1)
                      (Past sk_arrive_1)))
            $tv)))
   ((: (negated (negated
         (by precluded_past
            (conjunction f1_precludes f1_theme f1_past cpu))))
       (Not (And (Member sk_arrive_1 arrive)
                 (Agent sk_arrive_1 sk_teodor_1)
                 (Past sk_arrive_1)))
       (STV 1.0 0.8760223702918006))))
!(test
   (collapse (query 400 deniedKb (: $prf (Member sk_arrive_1 arrive) $tv)))
   ())
!(test
   (collapse (query 400 deniedKb (: $prf (Past sk_arrive_1) $tv)))
   ())
