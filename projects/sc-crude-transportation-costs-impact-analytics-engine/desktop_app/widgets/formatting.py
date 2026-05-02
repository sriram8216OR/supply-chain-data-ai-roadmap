"""Shared formatting helpers used across pages."""

from __future__ import annotations


def fmt_usd(amount: float, scale: str = "auto") -> str:
    """Format a USD amount with appropriate scale suffix.

    scale options:
      "auto" — choose B/M/K/none based on magnitude
      "B"    — always billions, 2 decimals
      "M"    — always millions, 1 decimal
    """
    if scale == "auto":
        if abs(amount) >= 1e9:
            return f"${amount / 1e9:.2f}B"
        elif abs(amount) >= 1e6:
            return f"${amount / 1e6:.1f}M"
        elif abs(amount) >= 1e3:
            return f"${amount / 1e3:.0f}K"
        else:
            return f"${amount:.0f}"
    elif scale == "B":
        return f"${amount / 1e9:.2f}B"
    elif scale == "M":
        return f"${amount / 1e6:.1f}M"
    return f"${amount:,.0f}"
