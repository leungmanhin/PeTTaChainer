;; Public query orchestration sits above the backward chainer. Keeping these
;; wrappers out of compiled_query_runtime lets compilation/storage remain a
;; foundational dependency of both chainers.

(: append-annotated-statements
   (-[det]-> (List AnnotatedStatement) (List AnnotatedStatement)
       (List AnnotatedStatement)))
(= (append-annotated-statements () $right) $right)
(= (append-annotated-statements
      (cons $statement $rest) $right)
   (cons $statement
      (append-annotated-statements $rest $right)))

(: pretty-result-list
   (-[det]-> Atom (List AnnotatedStatement)))
(= (pretty-result-list $result)
   ;; pretty is semidet, so this list contains at most one value. Its declared
   ;; result now propagates through collapse without a boundary ascription.
   (let $raw-results
      (collapse (pretty $result))
      $raw-results))

(: pretty-results
   (-[det]-> (List Atom) (List AnnotatedStatement)))
(= (pretty-results ()) ())
(= (pretty-results (cons $result $rest))
   (let*
      (($head-results (pretty-result-list $result))
       ($rest-results (pretty-results $rest)))
      (append-annotated-statements
         $head-results $rest-results)))

(: externalize-results
   (-[nondet]-> (List RuntimeResult) (List Atom)))
(= (externalize-results ()) ())
(= (externalize-results (cons $result $rest))
   (cons
      (externalize-proof-structure $result)
      (externalize-results $rest)))

(: IndexedQuery Type)
(: indexed-query (-[det]-> Number AnnotatedStatement IndexedQuery))
(: IndexedCompiledQuery Type)
(: indexed-compiled-query
   (-[det]-> Number CompiledQuery IndexedCompiledQuery))
(: IndexedRuntimeResults Type)
(: indexed-runtime-results
   (-[det]-> Number (List RuntimeResult) IndexedRuntimeResults))

(: append-runtime-additions
   (-[det]-> (List RuntimeAddition) (List RuntimeAddition)
       (List RuntimeAddition)))
(= (append-runtime-additions () $right) $right)
(= (append-runtime-additions (cons $head $tail) $right)
   (cons $head (append-runtime-additions $tail $right)))

(: append-indexed-compiled-queries
   (-[det]-> (List IndexedCompiledQuery) (List IndexedCompiledQuery)
       (List IndexedCompiledQuery)))
(= (append-indexed-compiled-queries () $right) $right)
(= (append-indexed-compiled-queries (cons $head $tail) $right)
   (cons $head
      (append-indexed-compiled-queries $tail $right)))

(: append-query-batch-results
   (-[det]-> (List QueryBatchResult) (List QueryBatchResult)
       (List QueryBatchResult)))
(= (append-query-batch-results () $right) $right)
(= (append-query-batch-results (cons $head $tail) $right)
   (cons $head (append-query-batch-results $tail $right)))

(: index-queries-from
   (-[det]-> Number (List AnnotatedStatement) (List IndexedQuery)))
(= (index-queries-from $_index ()) ())
(= (index-queries-from $index (cons $statement $rest))
   (cons
      (indexed-query $index $statement)
      (index-queries-from (+ $index 1) $rest)))

(: compile-indexed-query
   (-[nondet]-> KB IndexedQuery (List IndexedCompiledQuery)))
(= (compile-indexed-query $kb (indexed-query $index $statement))
   (let*
      (($statement-copy (copy_term $statement))
       ($materialized
          (the AnnotatedStatement
             (materialize-stmt-lambdas $statement-copy)))
       ($compiled (collapse (mm2compileQuery $kb $materialized))))
      (map-flat
         (|-> ((compiled-query $goal $adds))
            (if (or (is-var $goal) (is-var $adds))
               (empty)
               (indexed-compiled-query $index
                  (compiled-query $goal $adds))))
         $compiled)))

(: attach-indexed-runtime-results
   (-[det]-> (List IndexedCompiledQuery)
       (List (List RuntimeResult))
       (List IndexedRuntimeResults)))
(= (attach-indexed-runtime-results () ()) ())
(= (attach-indexed-runtime-results
      (cons (indexed-compiled-query $index $_query) $queries)
      (cons $results $rest-results))
   (cons
      (indexed-runtime-results $index $results)
      (attach-indexed-runtime-results $queries $rest-results)))

(: IndexedAnswers Type)
(: indexed-answers
   (-[det]-> Number (List AnnotatedStatement) IndexedAnswers))

(: indexed-runtime-answers
   (-[nondet]-> IndexedRuntimeResults IndexedAnswers))
(= (indexed-runtime-answers
      (indexed-runtime-results $index $results))
   (indexed-answers $index
      (pretty-results (externalize-results $results))))

(: append-indexed-answers
   (-[det]-> (List IndexedAnswers) (List IndexedAnswers)
       (List IndexedAnswers)))
(= (append-indexed-answers () $right) $right)
(= (append-indexed-answers (cons $head $tail) $right)
   (cons $head (append-indexed-answers $tail $right)))

(: run-compiled-query-many
   (-[nondet]-> Number (List IndexedCompiledQuery)
       Bool (List IndexedAnswers)))
(= (run-compiled-query-many
      $steps $compiled-queries $materialize?)
   (let*
      (($_clear-temp-before (clear-temp-query-adds))
       ($adds
          (list_to_set
             (foldr-flat append-runtime-additions ()
                (map-flat
                   (|-> ((indexed-compiled-query $_index
                            (compiled-query $_goal $query-adds)))
                      $query-adds)
                   $compiled-queries))))
       ($_inject
          (collapse (once (inject-compiled-adds $adds))))
       ($goals
          (map-flat
             (|-> ((indexed-compiled-query $_index
                      (compiled-query $goal $_adds)))
                (typed-runtime-premise $goal))
             $compiled-queries))
       ($runtime-results
          (if $materialize?
             (chainer-many-materialize $steps $goals)
             (chainer-many $steps $goals)))
       ($indexed-results
          (attach-indexed-runtime-results
             $compiled-queries $runtime-results))
       ($answers
          (map-flat indexed-runtime-answers $indexed-results))
       ($_clear-temp-after (clear-temp-query-adds)))
      $answers))

;; --- Readings ----------------------------------------------------------------
;; A statement is answered in a world: MAIN, or one reading's context
;; `(reading r)` (the shared layer plus that reading's statements). The query is
;; compiled against the KB as usual and re-rooted in the world.
;;
;; A plain statement is answered in MAIN and, when the KB holds readings, inside
;; every reading. A reading answer that MAIN does not give becomes a marginal
;; answer: the in-reading strength is kept, and the confidence is the share of
;; the readings giving that answer, sum(c) / n over the n live readings (a
;; uniform reading prior; n is at least two, as only an ambiguous item carries
;; readings). Readings are exclusive possibilities, not repeated observations:
;; answers of different strength stay separate answers and are never revised
;; together. `(Interpretation r S)` is answered inside live reading r only,
;; inside every live reading when r is a variable, and its answers keep the
;; wrapper.

(: ReadingGroup Type)
(: reading-group
   (-[det]-> Statement Number Number (List Proof) ReadingGroup))

(: NoReading Type)
(: no-reading NoReading)

(: live-reading-count (-[det]-> (List ReadingTag) Number))
(= (live-reading-count $readings) (max 2 (length $readings)))

(: retarget-compiled-query
   (-[det]-> KB (| ReadingTag NoReading) CompiledQuery CompiledQuery))
(= (retarget-compiled-query $kb $tag $query)
   (if (== $tag no-reading) $query
      (the CompiledQuery
         (retarget-kb-contexts $kb (reading-ctx (the ReadingTag $tag)) false
            $query))))

(: answer-type (-[det]-> AnnotatedStatement Statement))
(= (answer-type (: $_prf $type $_tv)) $type)
(= (answer-type (Interpretation $_tag $answer)) (answer-type $answer))

(: statement-member? (-[det]-> Statement (List Statement) Bool))
(= (statement-member? $_type ()) false)
(= (statement-member? $type (cons $head $tail))
   (if (=alpha $type $head) true (statement-member? $type $tail)))

;; Readings giving one statement at one strength share one marginal answer.
(: add-reading-support
   (-[det]-> (List ReadingGroup) Proof Statement Number Number
       (List ReadingGroup)))
(= (add-reading-support () $support $type $s $c)
   (cons (reading-group $type $s $c (cons $support ())) ()))
(= (add-reading-support
      (cons (reading-group $gtype $gs $gc $supports) $rest)
      $support $type $s $c)
   (if (if (=alpha $gtype $type) (== $gs $s) false)
      (cons
         (reading-group $gtype $gs (+ $gc $c)
            (append-stored-proof $supports $support))
         $rest)
      (cons (reading-group $gtype $gs $gc $supports)
         (add-reading-support $rest $support $type $s $c))))

(: add-reading-answer
   (-[det]-> (List Statement) (List ReadingGroup) AnnotatedStatement
       (List ReadingGroup)))
(= (add-reading-answer $main-types $groups $answer)
   (case $answer (
      ((Interpretation $tag (: $prf $type (STV $s $c)))
         (if (statement-member? $type $main-types) $groups
            (add-reading-support $groups
               (brand Proof (quote ($tag $prf))) $type $s $c)))
      ($_other $groups))))

(: reading-marginal-answer
   (-[det]-> Number ReadingGroup AnnotatedStatement))
(= (reading-marginal-answer $live
      (reading-group $type $s $confidence-sum $supports))
   (let*
      (($prf (brand Proof (cons readings $supports)))
       ($c (/ $confidence-sum $live)))
      (: $prf $type (STV $s $c))))

(: reading-marginal-results
   (-[det]-> Number (List AnnotatedStatement) (List AnnotatedStatement)
       (List AnnotatedStatement)))
(= (reading-marginal-results $live $main $reading-answers)
   (map-flat (reading-marginal-answer $live)
      (fold-flat (add-reading-answer (map-flat answer-type $main)) ()
         $reading-answers)))

(: run-compiled-query
   (-[nondet]-> Number Bool CompiledQuery (List AnnotatedStatement)))
(= (run-compiled-query $steps $materialize? (compiled-query $goal $adds))
   (if (or (is-var $goal) (is-var $adds))
      (empty)
      (let*
         (($_clear-temp-before (clear-temp-query-adds))
          ($_
             (collapse
                (once (inject-compiled-adds $adds))))
          ($results
             (if $materialize?
                (chainer-materialize
                   $steps (typed-runtime-premise $goal))
                (chainer $steps (typed-runtime-premise $goal))))
          ($externalized (externalize-results $results))
          ($pres (pretty-results $externalized))
          ($_clear-temp-after (clear-temp-query-adds)))
         $pres)))

(: query-world-results
   (-[nondet]-> Number KB Bool AnnotatedStatement (| ReadingTag NoReading)
       (List AnnotatedStatement)))
(= (query-world-results $steps $kb $materialize? $stmt $tag)
   (let*
      (($stmt1
          (the AnnotatedStatement
             (materialize-stmt-lambdas (copy_term $stmt))))
       ($compiled-queries
          (map-flat (retarget-compiled-query $kb $tag)
             (collapse (mm2compileQuery $kb $stmt1)))))
      (fold-flat append-annotated-statements ()
         (map-flat
            (run-compiled-query $steps $materialize?)
            $compiled-queries))))

(: query-readings-results
   (-[nondet]-> Number KB Bool AnnotatedStatement (List ReadingTag)
       (List AnnotatedStatement)))
(= (query-readings-results $steps $kb $materialize? $stmt $tags)
   (fold-flat append-annotated-statements ()
      (map-flat
         (query-world-results $steps $kb $materialize? $stmt)
         $tags)))

;; The live readings a reading-scoped query names: all of them for a variable.
(: tag-readings (-[det]-> KB Atom (List ReadingTag)))
(= (tag-readings $kb $tag)
   (if (is-var $tag) (kb-readings $kb)
      (if (kb-reading? $kb $tag)
         (cons (brand ReadingTag $tag) ())
         ())))

(: reading-aware-query
   (-[nondet]-> Number KB Bool AnnotatedStatement
       (List AnnotatedStatement)))
(= (reading-aware-query $steps $kb $materialize? $stmt)
   (case $stmt (
      ((Interpretation $tag $inner)
         (query-readings-results $steps $kb $materialize? $inner
            (tag-readings $kb $tag)))
      ($_plain
         (let*
            (($main
                (query-world-results
                   $steps $kb $materialize? $stmt no-reading))
             ($readings (kb-readings $kb)))
            (if (== $readings ()) $main
               (append-annotated-statements $main
                  (reading-marginal-results
                     (live-reading-count $readings)
                     $main
                     (query-readings-results
                        $steps $kb $materialize? $stmt $readings)))))))))

;; Batches run one shared arena per world. Plain roots run in MAIN and, for
;; their marginals, in every live reading; a reading-scoped root runs in its
;; live reading(s) only. Answers are then reassembled in input order.
(: reading-root? (-[det]-> AnnotatedStatement Bool))
(= (reading-root? $stmt)
   (case $stmt (
      ((Interpretation $_tag $_inner) true)
      ($_plain false))))

;; The roots a world answers, as a zero- or one-element list.
(: world-indexed-query
   (-[det]-> (| ReadingTag NoReading) IndexedQuery (List IndexedQuery)))
(= (world-indexed-query $world-tag (indexed-query $index $stmt))
   (case $stmt (
      ((Interpretation $tag $inner)
         (if (== $world-tag no-reading) ()
            (if (if (is-var $tag) true (== $tag $world-tag))
               (cons (indexed-query $index $inner) ())
               ())))
      ($_plain (cons (indexed-query $index $stmt) ())))))

(: append-indexed-queries
   (-[det]-> (List IndexedQuery) (List IndexedQuery) (List IndexedQuery)))
(= (append-indexed-queries () $right) $right)
(= (append-indexed-queries (cons $head $tail) $right)
   (cons $head (append-indexed-queries $tail $right)))

(: retarget-indexed-compiled-query
   (-[det]-> KB (| ReadingTag NoReading) IndexedCompiledQuery
       IndexedCompiledQuery))
(= (retarget-indexed-compiled-query $kb $tag
      (indexed-compiled-query $index $query))
   (indexed-compiled-query $index
      (retarget-compiled-query $kb $tag $query)))

(: query-many-world-answers
   (-[nondet]-> Number KB Bool (List IndexedQuery) (| ReadingTag NoReading)
       (List IndexedAnswers)))
(= (query-many-world-answers $steps $kb $materialize? $indexed $tag)
   (let $queries
      (foldr-flat append-indexed-queries ()
         (map-flat (world-indexed-query $tag) $indexed))
      (if (== $queries ()) ()
         (run-compiled-query-many $steps
            (map-flat (retarget-indexed-compiled-query $kb $tag)
               (foldr-flat append-indexed-compiled-queries ()
                  (map-flat (compile-indexed-query $kb) $queries)))
            $materialize?))))

(: index-answers
   (-[det]-> Number (List AnnotatedStatement) IndexedAnswers
       (List AnnotatedStatement)))
(= (index-answers $index $answers (indexed-answers $answer-index $more))
   (if (== $answer-index $index)
      (append-annotated-statements $answers $more)
      $answers))

;; One root's answers: MAIN answers plus reading marginals for a plain root,
;; the in-reading answers for a reading-scoped root.
(: root-answers
   (-[det]-> (List ReadingTag) Bool (List AnnotatedStatement)
       (List AnnotatedStatement) (List AnnotatedStatement)))
(= (root-answers $readings $reading-root? $main $in-readings)
   (if $reading-root? $in-readings
      (append-annotated-statements $main
         (reading-marginal-results
            (live-reading-count $readings) $main $in-readings))))

(: query-answer-row
   (-[det]-> Number AnnotatedStatement QueryBatchResult))
(= (query-answer-row $index $answer) (query-result $index $answer))

(: indexed-answers-rows
   (-[nondet]-> IndexedAnswers (List QueryBatchResult)))
(= (indexed-answers-rows (indexed-answers $index $answers))
   (map-flat (query-answer-row $index) $answers))

(: indexed-query-rows
   (-[det]-> (List ReadingTag) (List IndexedAnswers) (List IndexedAnswers)
       IndexedQuery (List QueryBatchResult)))
(= (indexed-query-rows $readings $main-answers $reading-answers
      (indexed-query $index $stmt))
   (map-flat (query-answer-row $index)
      (root-answers $readings (reading-root? $stmt)
         (fold-flat (index-answers $index) () $main-answers)
         (fold-flat (index-answers $index) () $reading-answers))))

(: query-many-mode
   (-[nondet]-> Number KB (List AnnotatedStatement) Bool
       QueryBatchResult))
(= (query-many-mode $steps $kb $statements $materialize?)
   (let*
      (($indexed (index-queries-from 0 $statements))
       ($readings (kb-readings $kb))
       ($main-answers
          (query-many-world-answers
             $steps $kb $materialize? $indexed no-reading))
       ($rows
          (if (== $readings ())
             (foldr-flat append-query-batch-results ()
                (map-flat indexed-answers-rows $main-answers))
             (let $reading-answers
                (foldr-flat append-indexed-answers ()
                   (map-flat
                      (query-many-world-answers
                         $steps $kb $materialize? $indexed)
                      $readings))
                (foldr-flat append-query-batch-results ()
                   (map-flat
                      (indexed-query-rows
                         $readings $main-answers $reading-answers)
                      $indexed))))))
      (superpose $rows)))

(: query
   (-[nondet]-> Number KB AnnotatedStatement AnnotatedStatement))
(= (query $steps $kb $stmt)
   (let $answers (reading-aware-query $steps $kb false $stmt)
      (superpose $answers)))

(: query-materialize
   (-[nondet]-> Number KB AnnotatedStatement AnnotatedStatement))
(= (query-materialize $steps $kb $stmt)
   (let $answers (reading-aware-query $steps $kb true $stmt)
      (superpose $answers)))

(: query-many
   (-[nondet]-> Number KB (List AnnotatedStatement) QueryBatchResult))
(= (query-many $steps $kb $statements)
   (query-many-mode $steps $kb $statements false))

(: query-many-materialize
   (-[nondet]-> Number KB (List AnnotatedStatement) QueryBatchResult))
(= (query-many-materialize $steps $kb $statements)
   (query-many-mode $steps $kb $statements true))
