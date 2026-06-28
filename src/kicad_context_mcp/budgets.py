"""Output-discipline constants and helpers (see README "Output budgets").

The whole point of this server is to *not* dump full netlists into an agent's
context. Every list-returning tool runs its output through these helpers.
"""

# --- caps (section 6 of the design doc) -----------------------------------
OVERVIEW_TOKEN_TARGET = 500   # board_overview soft target
DEFAULT_PAGE = 25             # default list page size
MAX_PAGE = 100               # hard cap on page size
NET_PINS_BEFORE_PAGE = 40     # pins shown for a net before paginating
TRACE_DEFAULT_DEPTH = 1
TRACE_MAX_DEPTH = 3
CHECKS_INLINE_ROWS = 20       # erc/drc detail rows shown inline
LABEL_MAX = 120              # per-item one-line label length


def est_tokens(text: str) -> int:
    """Cheap char-based token estimate. ponytail: len/4, no tiktoken dep."""
    return (len(text) + 3) // 4


def label(s: str) -> str:
    """Clamp a one-line label to LABEL_MAX chars."""
    s = " ".join(str(s).split())
    return s if len(s) <= LABEL_MAX else s[: LABEL_MAX - 1] + "…"


def paginate(items, page: int = 1, page_size: int = DEFAULT_PAGE):
    """Return a bounded slice plus pagination metadata.

    Always returns {items, total, page, page_size, has_more} so the agent
    can tell a truncated list from a complete one.
    """
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), MAX_PAGE))
    total = len(items)
    start = (page - 1) * page_size
    chunk = items[start : start + page_size]
    return {
        "items": chunk,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": start + page_size < total,
    }
