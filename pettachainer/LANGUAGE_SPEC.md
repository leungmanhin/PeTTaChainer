# PeTTaChainer Language Spec

This document describes how to write facts, rules, and queries in the PeTTaChainer MeTTa language used in this repository.

If you need an LLM-oriented helper-first spec, use `pettachainer/LLM_RULE_SPEC.md`.

## Core Model

- Knowledge is stored as proof atoms of the form:

```metta
(: proof-id type tv)
```

- A negated STV fact is canonicalized to its inner expression with complemented
  strength and unchanged confidence. For example,
  `(: noLeak (Not (SealLeak old unit-1)) (STV 1.0 1.0))` is stored as
  `(: noLeak (SealLeak old unit-1) (STV 0.0 1.0))`. This ensures ordinary
  population folds see negative observations. `Not` in rules and queries keeps
  its logical meaning.

- In user code, facts/rules are usually inserted with:

```metta
!(compileadd kb (: proof-id type tv))
```

- Incremental pattern mining on insert is off by default. To enable it for a KB:

```metta
!(enable-pattern-mining-on-add kb)
```

This updates mining statistics during `compileadd` without recompiling mined rules on every insert.
When you want to emit the current mined implication rules, run:

```metta
!(materialize-mined-implications kb)
```

- For a one-shot insert that also mines patterns without changing the KB default:

```metta
!(compileadd-mine kb (: proof-id type tv))
```

- Queries use:

```metta
!(query steps kb (: $prf type $tv))
```

`steps` is the search budget. A query's STV may ask for a band of the truth
value, `(STV (Band lo hi) $c)`; see Truth-value bands in queries.

- An implication-derived proof uses the explicit application form:

```metta
(by rule-name premise-proof)
```

The rule name is metadata, while `premise-proof` is the proof dependency that
evidence and cycle walkers traverse. This avoids confusing a rule name that
happens to look like a proof constructor with an actual dependency.

## Types and Truth Values

### STV

Simple truth value:

```metta
(STV strength confidence)
```

- `strength` is belief/probability-like mass in `[0,1]`
- `confidence` is evidence/reliability in `[0,1]`

`STV` is for truth of a proposition, not for numeric value uncertainty.
For example, `(STV 1.0 0.5)` means low confidence that a fact is true,
not "value is around X".

### Distribution TVs

- Exact discrete:
  - `(NatDist ((value probability) ...))`
  - `(FloatDist ((value probability) ...))`
- Scalable particle-based:
  - `ParticleDist` is an opaque reference backed by `&particle_store`
  - Create from explicit weighted samples with:

```metta
(ParticleFromPairs ((x1 w1) (x2 w2) ...))
```

Useful constructors:

```metta
(PointMass 160.0)
(ParticleFromNormal 160.0 2.0)
```

- `PointMass` encodes an exact value as a degenerate distribution.
- `ParticleFromNormal` creates a deterministic normal-like particle approximation.

## Truth vs Value Uncertainty

- Truth uncertainty: use `STV`.
- Value uncertainty: use `Dist` (`ParticleDist`, `FloatDist`, `NatDist`).

Recommended modeling pattern:

- `(HeightDist g1 alice)` with TV `(PointMass 160.0)` for crisp numeric values
- `(HeightDist g1 alice)` with TV `(ParticleFromNormal 160.0 2.0)` for uncertain values
- keep instance membership/existence truth in separate `(Member object class)`
  STV facts if needed

## Fact Syntax

Example:

```metta
!(compileadd kb (: in11 (In room1 kid1) (STV 0.5 1.0)))
```

## Member and Inheritance

`Member` and `Inheritance` have distinct modeling roles:

- `(Member object class)` says that one object belongs to a class.
- `(Inheritance subclass superclass)` says that one class or concept inherits
  from another.

For new knowledge, prefer `Member` for instance-to-class observations:

```metta
!(compileadd kb
    (: tomHuman (Member Tom Human) (STV 0.99 0.9)))

!(compileadd kb
    (: humanMortal (Inheritance Human Mortal) (STV 0.8 0.9)))

!(query 40 kb (: $prf (Member Tom Mortal) $tv))
```

The concrete `Inheritance Human Mortal` assertion is compiled into ordinary
inference views equivalent to:

```metta
(Member $x Human)       -> (Member $x Mortal)
(Inheritance $x Human)  -> (Inheritance $x Mortal)
```

These views are generated automatically. User code should not duplicate them.
The generated member view is marked non-invertible: observing that an object is
Mortal does not by itself prove that it is Human.

`Member` can also appear on either side of an explicit rule:

```metta
!(compileadd kb
    (: seedHuman
       (Implication
          (Member $x Seed)
          (Member $x Human))
       (CTV (STV 1.0 1.0) (STV 0.0 1.0))))
```

### Estimating inheritance from members

A ground query such as:

```metta
!(query 100 kb (: $prf (Inheritance Human Mortal) $tv))
```

can infer class-level inheritance from objects for which both
`(Member object Human)` and `(Member object Mortal)` are provable. The sample
collector uses the normal backward chainer, so rule-derived memberships count
along with directly stored facts. It retains proof identities, rejects
self-supporting cycles, and avoids treating overlapping evidence as independent.

Set a known closed-world population size when one is available:

```metta
!(set-universe-size kb 100.0)
```

The universe size affects the confidence assigned to observed population
coverage. Without it, the member estimator uses its count-based confidence.
Forward chaining can maintain a provisional estimate incrementally after a
ground inheritance query has registered interest; a later backward query folds
the complete currently derivable sample set and refines that estimate.

PeTTaChainer also estimates ground `Inheritance A B` through its
total-implication path using `Inheritance x A` and `Inheritance x B`
observations. Concept priors used by inheritance base-rate folds can be
configured with:

```metta
!(set-concept-prior-confidence kb 0.5)
!(clear-concept-prior-confidence kb)
```

Only class terms are registered as concept nodes by `Member`; the member object
is not. Open queries such as `(Inheritance $subclass $superclass)` remain useful
for retrieving matching ordinary derivations, but variable classes cannot
register a selective incremental member estimate.

Legacy programs in this repository sometimes encode instance membership as
`(Inheritance object class)`. That representation remains supported for
compatibility and participates in inheritance-only reasoning. It is not an
alias for `Member`: adding both forms records two distinct propositions.

## Rule Syntax

An implication has exactly two expression arguments: its antecedent and its
consequent. Write `And` explicitly when either side is a conjunction:

```metta
!(compileadd kb (: ruleName
    (Implication
        (And
            premise1
            premise2
            ...)
        conclusion)
    (STV s c)))
```

A singleton side is written directly, without a unary `And`. There is only one
source form for an implication. Multiple conclusions form one explicit joint
consequent such as `(And conclusion1 conclusion2)` and retain the normal
compound-output projection semantics.

Variables in an ordinary antecedent are implicitly universally quantified. An
antecedent may instead request existential aggregation explicitly with:

```metta
!(compileadd kb
    (: doctorChild
       (Implication
          (Exists ($child)
                (And
                   (Parent $person $child)
                   (Doctor $child)))
          (HasDoctorChild $person))
       (CTV (STV 1.0 1.0) (STV 0.0 1.0))))
```

`Exists` has the form `(Exists ($var ...) body)` and must wrap one complete
side of a stored implication. An antecedent accepts either a matching direct
`ExistentialClaim` or the disjunction obtained by querying its body for every
currently known witness. Free body variables such as `$person` form independent
result groups. The binder scopes over its complete body, so the same `$child`
must satisfy both predicates in the example. Put `And` inside the binder when
its body is conjunctive; an `Exists` nested inside an outer `And` is invalid. A
bound variable name may not be reused on the implication's other side.

An explicit existential conclusion introduces a proposition-level claim:

```metta
!(compileadd kb
    (: generate
       (Implication
          (Seed $x)
          (Exists ($y) (GeneratedBy $x $y)))
       (CTV (STV 1.0 1.0) (STV 0.0 1.0))))
```

For a proof of `(Seed alice)`, the stored result is:

```metta
(ExistentialClaim (GeneratedBy alice (exists-slot 0)))
```

`exists-slot` is a canonical bound position, not an object and not a claim that
a new object distinct from all known objects was generated. Independent rules
for the same quantified body therefore contribute to the same existential
proposition. Variables which occur only in an ordinary, unwrapped conclusion
retain the constructive behavior and become stable `(exists rule index args)`
Skolem terms.

Variables in an ordinary antecedent retain the implication's universal scope
even when they do not occur in the consequent. Use explicit `Exists` when the
antecedent should instead aggregate existential evidence. Variables bound by
an existential antecedent are eliminated by that aggregation and do not become
dependencies of generated consequent witnesses.
Nested existential binders, direct existential queries, and existential terms
in bidirectional implications are currently rejected rather than interpreted
as ordinary predicates.

Two additional complete-premise forms expose an existential's open witness
population without treating it as complete:

```metta
(KnownExistential ($y) (GeneratedBy alice $y))
(ExistentialResidual ($y) (GeneratedBy alice $y))
```

`KnownExistential` folds the matching witness TVs with `OrFormula` to produce
the currently enumerated disjunction D. `ExistentialResidual` also consumes the
corresponding direct `ExistentialClaim` E and calculates the remaining U from
`E = D or U`. The latter uses variance-based confidence propagation rather than
copying the existential confidence onto U. Both forms are lazy FoldAll-backed
premises and their bound variables do not escape into the conclusion.

## Readings (Interpretation)

An ambiguous item, such as a sentence with two live readings that nothing
selects, is stored as its shared statements, asserted normally, plus each
reading's own statements wrapped in the reading they hold under:

```metta
!(compileadd kb (: e_ag (Agent see1 speaker1) (STV 1.0 0.99)))
!(compileadd kb (Interpretation r1 (: e_instr (Instrument see1 telescope1) (STV 1.0 0.99))))
!(compileadd kb (Interpretation r2 (: m_with (With man1 telescope1) (STV 1.0 0.99))))
```

`(Interpretation r statement)` asserts the statement under reading `r` only.
The readings of a KB are mutually exclusive possibilities: the item licenses
each, never several at once. Do not assert reading content plainly or inside
one `And`; that claims every reading holds.

Each reading is a world: the KB's plain statements (the shared layer) plus the
reading's own statements. Rules apply inside a world as they do in MAIN, and a
wrapped rule applies inside its reading only. Reading content never enters
MAIN, and two readings never revise each other. A wrapped `(Not S)` is
canonicalized as in MAIN.

A query takes one of two forms:

- Per reading: `(Interpretation r2 (: $prf (With man1 telescope1) $tv))` is
  answered inside reading `r2` and returns the wrapped statement with its own
  truth value, `(Interpretation r2 (: m_with (With man1 telescope1) (STV 1.0 0.99)))`:
  true under `r2`. Shared content is true under every reading. A variable tag,
  `(Interpretation $r ...)`, asks every live reading; a tag that no statement
  carries is not a live reading and returns nothing.
- Marginal: a plain query is answered in MAIN and, when the KB holds readings,
  inside every reading. An answer MAIN does not give keeps its in-reading
  strength, and its confidence is shared out over the readings: `c' = sum(c) / n`,
  summed over the readings that give the answer at that strength, where `n` is
  the number of live readings (a uniform reading prior; at least two, since only
  an ambiguous item carries readings). The proof names the supporting readings:

```metta
!(query 100 kb (: $prf (With man1 telescope1) $tv))
; (: (readings (r2 m_with)) (With man1 telescope1) (STV 1.0 0.495))
```

Content held by every reading keeps its confidence. Readings that disagree on a
strength stay separate answers: strength 0 under `r1` and 1 under `r2` give two
answers at half confidence each, never a revised mid-band strength. A
conjunction is answered inside each reading, so it binds only where one reading
holds every conjunct; the contents of different readings are never joined.

`query-many` accepts both forms in one batch; MAIN and each reading run their
own shared arena with the full step budget.

Limits:

- A KB holds one ambiguous item: its reading tags are that item's readings.
  Keep separately ambiguous items in separate KBs.
- Marginals are produced for STV answers; other answers are available per
  reading only.
- A statement MAIN answers is answered by MAIN alone.
- Inside a reading, the shared layer is MAIN's stored facts and the rules.
  Views compiled for MAIN only (projections of shared compound facts,
  inheritance lifts) are not rederived there, and base-rate folds read MAIN.
- Query materialization writes MAIN derivations only, so reading answers are
  recomputed by every query.

## Truth-value bands in queries

A vague quantity or a polarity asks for a band of the truth value, not an
exact value: "who rarely swims?" is a strength in a low band, "who often
swims?" a high band, "who can't swim?" a strength near 0, and "which claims are
doubtful?" a low confidence. Write `(Band lo hi)` in the strength or the
confidence slot of the query's STV, or in both:

```metta
!(query 100 kb (: $prf (Inheritance $x swim) (STV (Band 0.05 0.3) $c)))  ; rarely
!(query 100 kb (: $prf (Inheritance $x swim) (STV (Band 0.0 0.05) $c)))  ; can't
!(query 100 kb (: $prf (Claim $x) (STV $s (Band 0.0 0.5))))              ; doubtful
!(query 100 kb (: $prf (Claim $x) (STV (Band 0.8 1.0) (Band 0.9 1.0))))  ; both
```

The query answers what `(STV $s $c)` answers and keeps the answers whose
returned truth value lies in every band. Bounds are inclusive,
`lo <= x <= hi`, so `(Band 0.0 0.05)` keeps a strength of exactly 0. Answers
carry their concrete truth value, never the band, in the order of the unbanded
query.

The band constrains the truth value the query returns for an answer:

- the current belief, after revision. Two assertions of one statement at
  `(STV 1.0 0.9)` and `(STV 0.0 0.9)` answer once, at
  `(STV 0.5 0.9473684210526316)`, which `(Band 0.45 0.55)` keeps and neither
  `(Band 0.0 0.05)` nor `(Band 0.95 1.0)` does. Derivations of one conclusion
  are likewise revised together before the band applies;
- a rule-derived answer's derived truth value;
- the conjunction's truth value for an `And` query;
- over a KB with readings, the marginal answer of a plain query, and the
  in-reading truth value for `(Interpretation r ...)`;
- for an implication, the positive branch of its CTV, which is what an STV
  asks of an implication.

An exact number in a slot is different. `(STV 0.0 $c)` pins the proofs the
search matches before they are revised together: it can return one derivation
at exactly 0.0 that the merged belief no longer holds, and it misses a
statement whose revised strength moved off 0, such as 0.04 or 0.25. A band
takes no part in the search, so it sees the revised belief. A band and a
number combine: `(STV (Band 0.8 1.0) 0.95)` keeps the answers in the strength
band among the proofs pinned at confidence 0.95.

Bands are query-only: the statement validator (`check_stmt`, run by the Python
`add_atom`) requires grounded STV and CTV fields (numbers, not variables,
symbols or expressions), so a statement whose truth value carries a band is
rejected before it reaches the KB. `query-many` applies each root's band to
that root's answers. A materializing query writes the derivations its search
found, as the unbanded query would; the band selects only the returned
answers.

Limits:

- A band fills a slot of the query's top-level `STV` only. As the whole truth
  value, or inside a `CTV` pattern, it is rejected by the query validator
  (`check_query`).
- Both bounds are numbers; `check_query` rejects a variable or symbolic bound.
  A band with `lo > hi` holds no value and answers nothing.
- A `Compute` premise on a strength bound in the query's truth value does not
  constrain the answers; use a band.

## Built-in Premise Forms

### 1) Plain predicates

```metta
(Room $room)
```

### 2) Compute

Runs a function and binds output:

```metta
(Compute + ($a $b) -> $sum)
```

Implication inversion supports one restricted arithmetic subset. A top-level
binary `Compute` using `+` or `-` may be reversed when its result is known and
exactly one direct argument variable is unknown. The other argument must
already be known. For example:

```metta
(Implication
   (And (A $x) (Compute + ($x 1) -> $y))
   (B $y))
```

Given `(B 3)`, the inverse rule computes `$x` with `3 - 1`, then reruns the
original `2 + 1` computation as a validation before producing the antecedent.
Several eligible computations may form a chain; they are reversed from the
consequent back toward the antecedent.

The compiler emits no inverse rule when a computation has zero or multiple
unknown inputs, the unknown is nested inside an argument, the function is not
one of the supported `+`/`-` modes, or another CPU premise such as `FoldAll` is
present. `no_inverse` still disables inversion explicitly. Truth-value
inversion and modus ponens are unchanged; the arithmetic inverse only
reconstructs variable bindings.

The compiler-generated TV computation for a pure top-level `Or` does not
trigger that veto. A rule such as `(Or A B) -> C` may be inverted from `C` to
the whole `Or`; the normal compound-output adapters can then project `A` given
`B`, or vice versa. OR projection uses the noisy-OR inverse and propagates
variance from both the reconstructed total and the known alternative. Ordinary
multi-premise `And` rules remain forward-only unless they contain a supported
reversible `Compute`.

### 3) FoldAll / FoldAllValue

Aggregate over matching facts:

```metta
(FoldAll pattern value init fold-fn -> out)
(FoldAllValue pattern init fold-fn -> out)
```

Typical distribution fold:

```metta
(FoldAllValue (In $room $kid)
              (ParticleFromPairs ((0 1.0)))
              ParticleAddBernoulliFromSTV
              -> $dist)
```

#### Finite weighted subset posterior

`WeightedSubsetPosteriorDP` solves the restricted inverse problem compactly. It
accepts a finite list of candidates, each with an identity, nonnegative exact
contribution, and independent prior probability:

```metta
(Compute WeightedSubsetPosteriorDP
   (((WeightedCandidate pump 5 0.02)
     (WeightedCandidate valve 3 0.10)
     (WeightedCandidate motor 2 0.05))
    5)
   ->
   $posterior)
```

The result is the reusable dynamic-programming table itself:

```metta
(WeightedSubsetDP
   5
   $candidates
   ($prefixRow0 $prefixRow1 ... $prefixRowN)
   ($postfixRow0 $postfixRow1 ... $postfixRowN))
```

Each row contains `(WeightedDPCell accumulatedLoss probabilityMass)` cells and
merges configurations that reach the same loss. Prefix row `i` describes the
candidates before `i`; postfix row `i` describes candidates `i` through the
end. Thus row 0 in the prefix table and row N in the postfix table are both
`(WeightedDPRow ((WeightedDPCell 0 1.0)))`.

`WeightedSubsetPosteriorMass` reads the target cell from the final prefix row.
To project candidate `i`, `WeightedSubsetPosteriorMarginal` selects `i`, then
convolves prefix row `i` with postfix row `i+1` at
`target - candidateContribution`, and divides by the observation mass:

```metta
(Compute WeightedSubsetPosteriorMarginal
   ($posterior pump) -> $probability)
```

The current restricted mode requires unique candidate identities, a finite
candidate list, nonnegative contributions, priors in `[0,1]`, and an exact
target. Storage follows the reachable cells across the `2 * (N + 1)` rows,
rather than the number of fault configurations. For bounded integer losses this
is pseudo-polynomial; arbitrary exact weights can still have exponentially many
distinct reachable sums. Rows are kept in ascending loss order. Each DP step
scales and shifts the two branch rows and merges them linearly, while marginal
projection uses a linear two-pointer prefix/postfix join. If `R` bounds the
reachable losses per row, eager table construction is `O(N * R)`, one marginal
is `O(N + R)`, and storage is `O(N * R)`.

The current operator eagerly constructs all prefix and postfix rows on every
call. This keeps the value pure and identical in both chainers, but a future
implementation could build or cache rows lazily without changing the
`WeightedSubsetDP` contract.

Use `EnumerateWeightedSubsetExplanations` only when every matching fault set is
actually required. It returns the earlier `WeightedSelections` joint value and
is necessarily output-exponential. `WeightedSubsetSumInverse` remains as a
compatibility alias for that exhaustive operation.

`CandidateModules` may contain a canonical list directly, or the list may be
collected with `FoldAll` from individual candidate facts. A fold accumulator
must impose a stable order, preferably using explicit candidate indices;
ordinary match order is not a canonical list order. Candidate collection is
linear and separate from the posterior DP.

### 4) Not

```metta
(Not expr)
```

### 5) GreaterThan / >

Two forms are supported:

- Distribution vs numeric threshold:

```metta
(CntKidIn $room $cnt)
(GreaterThan $cnt 1)
```

Compiled to `DistGreaterThanFormula` over the bound distribution value.

- Distribution vs distribution (compile sugar):

```metta
(CountryHeightDist countryA $distA)
(CountryHeightDist countryB $distB)
(GreaterThan $distA $distB)
```

Compiled to `DistGreaterThanDistFormula`.

### 6) MapDist / Map2Dist / AverageDist

Distribution helper premises with explicit value binders:

```metta
(MapDist f (DistFactA ... $inDist) $inDist -> $outDist)
(Map2Dist f (DistFactA ... $distA) $distA (DistFactB ... $distB) $distB -> $outDist)
(AverageDist (DistFactPattern ... $inDist) $inDist -> $outDist)
```

- `MapDist` compiles to `DistMapFormula`.
- `Map2Dist` compiles to `DistMap2Formula`.
- `AverageDist` compiles to `DistAverageFormula`.

## Distribution Operations

### Threshold probability

```metta
(DistGreaterThanFormula dist threshold)
```

Returns `STV(P(dist > threshold), confidence)`.

### Distribution comparison

```metta
(DistGreaterThanDistFormula distA distB)
```

Returns `STV(P(distA > distB), confidence)`.

### Particle transforms

Unary map:

```metta
(ParticleMap f particleDist)
```

Binary composition:

```metta
(ParticleMap2 f particleDistA particleDistB)
```

### Particle update from STV Bernoulli

```metta
(ParticleAddBernoulliFromSTV particleDist stv)
```

## Particle Computation Confidence

Particle-based threshold and comparison formulas currently return confidence
`1.0`. Particle weights describe the probability distribution itself; their
concentration is not evidence about the reliability of that distribution. The
source fact and rule TVs continue to carry epistemic confidence through normal
proof composition.

The particle budget can resample a distribution and thereby introduce numeric
approximation error. That approximation quality is not represented yet. A
future representation should carry evidence or approximation-quality metadata
separately from both particle weights and the existing `ParticleDist` scale
(which contributes to result strength). This separation is also required if
particle distributions eventually replace STVs: distribution shape, epistemic
support, and representation quality must not be conflated.

## Particle Store Utilities

- `(ParticleStoreCount)` -> number of stored `(particle id x w)` atoms
- `(ParticleStoreClear)` -> clears store and resets particle id counter
- `(ParticleStorePruneKB)` -> keeps only particle ids reachable from current `&kb` facts

## End-to-End Example

```metta
!(compileadd kb (: countryHeightA
    (CountryHeightDist countryA (ParticleFromPairs ((170 0.5) (180 0.5))))
    (STV 1.0 1.0)))

!(compileadd kb (: countryHeightB
    (CountryHeightDist countryB (ParticleFromPairs ((175 1.0))))
    (STV 1.0 1.0)))

!(compileadd kb (: compareHeightsRule
    (Implication
        (And
            (CountryHeightDist countryA $distA)
            (CountryHeightDist countryB $distB)
            (GreaterThan $distA $distB))
        (Taller countryA countryB))
    (STV 1.0 1.0)))

!(query 40 kb (: $prf (Taller countryA countryB) $tv))
```

## Example: Average Height Distribution in a Group

This example computes average height distributions via a rule and queries the derived fact.
Each person height stores the distribution in the term, while the `tv` slot remains `STV`.

```metta
!(compileadd kb (: group1 (Group g1) (STV 1.0 1.0)))
!(compileadd kb (: hd11 (HeightDist g1 alice (PointMass 160.0)) (STV 1.0 1.0)))
!(compileadd kb (: hd12 (HeightDist g1 bob (PointMass 170.0)) (STV 1.0 1.0)))
!(compileadd kb (: hd13 (HeightDist g1 carol (PointMass 180.0)) (STV 1.0 1.0)))

!(compileadd kb (: avgHeightDistG1Rule
    (Implication
        (And
            (Group g1)
            (AverageDist (HeightDist g1 $person $heightDist) $heightDist -> $avgDist))
        (AvgHeightDist g1 $avgDist))
    (STV 1.0 1.0)))

!(query 10 kb
    (: (avgHeightDistG1Rule (conjunction group1 cpu))
       (AvgHeightDist g1 $avgDist)
       $tv))
```

## Example: Rectangle Area Distribution

Area is the product of length and width distributions, derived through a rule.

```metta
!(compileadd kb (: lenA (LengthDist rectA (ParticleFromNormal 10.0 1.0)) (STV 1.0 1.0)))
!(compileadd kb (: widA (WidthDist rectA (ParticleFromNormal 5.0 0.5)) (STV 1.0 1.0)))

!(compileadd kb (: areaDistRule
    (Implication
        (And
            (Rectangle $rect)
            (Map2Dist *
               (LengthDist $rect $lengthDist)
               $lengthDist
               (WidthDist $rect $widthDist)
               $widthDist
               ->
               $areaDist))
        (AreaDist $rect $areaDist))
    (STV 1.0 1.0)))

!(compileadd kb (: rA (Rectangle rectA) (STV 1.0 1.0)))

!(query 120 kb (: $prf (AreaDist rectA $areaDist) $tv))
```

## Notes

- `NatDist`/`FloatDist` remain available for exact small cases.
- `ParticleDist` is preferred for scalability.
- Rule/application truth functions still use STV semantics for implication chaining.
