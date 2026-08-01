"""
auth_dep.py — Centralised FastAPI authentication dependency.

Usage in any route:
    from auth_dep import require_auth, FarmerSession

    @router.get("/protected")
    async def protected(farmer: FarmerSession = Depends(require_auth)):
        return {"hello": farmer.name}
"""
from __future__ import annotations
from dataclasses import dataclass
from fastapi import Request, HTTPException, Depends


@dataclass
class FarmerSession:
    """Thin wrapper around session data for typed access."""
    id:   int
    name: str


def get_session_farmer(request: Request) -> FarmerSession | None:
    """Return FarmerSession if logged-in, else None. No exception raised."""
    fid   = request.session.get("farmer_id")
    fname = request.session.get("farmer_name")
    if fid and fname:
        return FarmerSession(id=int(fid), name=str(fname))
    return None


def require_auth(request: Request) -> FarmerSession:
    """
    FastAPI Depends() guard.
    Raises HTTP 401 (for API routes) if no valid session exists.
    Use this on every protected API endpoint.
    """
    farmer = get_session_farmer(request)
    if not farmer:
        raise HTTPException(
            status_code=401,
            detail={"ok": False, "error": "Authentication required. Please login.", "redirect": "/"},
        )
    return farmer
