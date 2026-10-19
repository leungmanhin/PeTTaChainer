"""Shared PLN syntax validation helpers for evaluated PLN expressions."""

from petta import PeTTa

# Stored truth-value shapes, each with the fields that must hold grounded
# values. A stored STV is concrete: a variable, a symbol or an expression such
# as a query band in a field is rejected.
TV_PATTERNS = (
    ("STV $123s $123c", ("$123s", "$123c")),
    (
        "CTV (STV $123ps $123pc) (STV $123ns $123nc)",
        ("$123ps", "$123pc", "$123ns", "$123nc"),
    ),
    ("NatDist $123pairs", ()),
    ("FloatDist $123pairs", ()),
    ("ParticleDist $123ref", ()),
    ("ParticleDist $123ref $123scale", ()),
    ("PointMass $123x", ()),
    ("ParticleFromNormal $123mu $123sigma", ()),
    ("ParticleFromPairs $123pairs", ()),
)


def _run_check(code: str) -> float:
    try:
        return float(PeTTa().process_metta_string(code)[0])
    except Exception:
        return 0.0


def _all(conditions) -> str:
    """1.0 when every MeTTa Bool condition holds, else 0.0."""
    expr = "1.0"
    for condition in reversed(conditions):
        expr = f"(if {condition} {expr} 0.0)"
    return expr


def _metatype(term: str, metatype: str) -> str:
    # get-metatype stays cheap on an unbound term, unlike get-type.
    return f"(== (get-metatype {term}) {metatype})"


def _tv_supported_expr(tv_var: str = "$123tv") -> str:
    expr = "0.0"
    for pattern, fields in reversed(TV_PATTERNS):
        expr = (
            f"(if (= {tv_var} ({pattern})) "
            f"{_all([_metatype(field, 'Grounded') for field in fields])} {expr})"
        )
    return expr


def _band_slot_ok(slot: str) -> str:
    """MeTTa Bool: an expression in a query STV slot is `(Band lo hi)` with
    grounded bounds."""
    lo, hi = f"{slot}lo", f"{slot}hi"
    return (
        f"(if {_metatype(slot, 'Expression')} "
        f"(if (= {slot} (Band {lo} {hi})) "
        f"(if {_metatype(lo, 'Grounded')} {_metatype(hi, 'Grounded')} false) "
        "false) true)"
    )


def _query_tv_expr() -> str:
    """A band may fill the strength or confidence slot of the query's STV only:
    not the whole truth value, nor a slot of a CTV pattern."""
    ctv_slots = [
        f"(not {_metatype(field, 'Expression')})"
        for field in ("$123ps", "$123pc", "$123ns", "$123nc")
    ]
    return (
        "(if (== (get-metatype $123tv) Variable) 1.0 "
        "(if (= $123tv (STV $123s $123c)) "
        f"{_all([_band_slot_ok('$123s'), _band_slot_ok('$123c')])} "
        "(if (= $123tv (CTV (STV $123ps $123pc) (STV $123ns $123nc))) "
        f"{_all(ctv_slots)} "
        "(if (= $123tv (Band $123lo $123hi)) 0.0 1.0))))"
    )


def _check_shape(expr: str, body: str, reading_tag_ok: str) -> float:
    """Check `(: prf stmt tv)`, bare or wrapped as `(Interpretation tag ...)`."""

    return _run_check(
        f"!(if (= {expr} (Interpretation $123tag (: $123prf $123stmt $123tv))) "
        f"(if {reading_tag_ok} {body} 0.0) "
        f"(if (= {expr} (: $123prf $123stmt $123tv)) {body} 0.0))"
    )


def check_stmt(text: str) -> float:
    """Return 1.0 for valid evaluated statement forms, else 0.0.

    A statement may be scoped to one reading of an ambiguous item as
    `(Interpretation r (: prf stmt tv))`; the reading tag must be a symbol.
    STV and CTV fields must be grounded values (numbers), so a query band is
    never stored.
    """

    return _check_shape(
        text.strip(),
        "(if (== (get-metatype $123prf) Variable) 0.0 "
        f"(if (== (get-metatype $123tv) Variable) 0.0 {_tv_supported_expr()}))",
        "(== (get-metatype $123tag) Symbol)",
    )


def check_query(text: str) -> float:
    """Return 1.0 for valid evaluated query forms, else 0.0.

    `(Interpretation r (: $prf stmt $tv))` asks within reading r; the tag may
    be a symbol or a variable (every live reading). `(Band lo hi)`, with
    grounded (numeric) bounds, may fill the strength or confidence slot of the
    query's STV and nowhere else in its truth value.
    """

    text = text.strip()
    # Every check compiles afresh; only a query that spells `Band` can misplace
    # one, so the others skip the truth-value checks.
    tv_ok = _query_tv_expr() if "Band" in text else "1.0"
    return _check_shape(
        text,
        f"(if (== (get-metatype $123prf) Variable) {tv_ok} 0.0)",
        "(or (== (get-metatype $123tag) Symbol) "
        "(== (get-metatype $123tag) Variable))",
    )
