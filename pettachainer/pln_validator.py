"""Shared PLN syntax validation helpers for evaluated PLN expressions."""

from petta import PeTTa

TV_PATTERNS = (
    "STV $123s $123c",
    "CTV (STV $123ps $123pc) (STV $123ns $123nc)",
    "NatDist $123pairs",
    "FloatDist $123pairs",
    "ParticleDist $123ref",
    "ParticleDist $123ref $123scale",
    "PointMass $123x",
    "ParticleFromNormal $123mu $123sigma",
    "ParticleFromPairs $123pairs",
)


def _run_check(code: str) -> float:
    try:
        return float(PeTTa().process_metta_string(code)[0])
    except Exception:
        return 0.0


def _tv_supported_expr(tv_var: str = "$123tv") -> str:
    expr = "0.0"
    for pattern in reversed(TV_PATTERNS):
        expr = f"(if (= {tv_var} ({pattern})) 1.0 {expr})"
    return expr


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
    be a symbol or a variable (every live reading).
    """

    return _check_shape(
        text.strip(),
        "(if (== (get-metatype $123prf) Variable) 1.0 0.0)",
        "(or (== (get-metatype $123tag) Symbol) "
        "(== (get-metatype $123tag) Variable))",
    )
