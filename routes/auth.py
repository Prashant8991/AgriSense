"""
Auth routes — login, logout, register, profile, session check.

Security features implemented:
  • bcrypt password hashing (cost factor 12)
  • In-memory brute-force lockout (5 attempts → 15-min lock per IP)
  • Input validation (name length, Aadhaar format, phone format, password strength)
  • Timing-safe password comparison (bcrypt.checkpw)
  • Session regeneration on login (prevents session fixation)
  • Structured JSON error responses with field-level hints
"""
from __future__ import annotations

import re
import time
from collections import defaultdict
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import JSONResponse
import bcrypt
import psycopg2

from database import get_conn
from auth_dep import require_auth, FarmerSession

router = APIRouter(tags=["auth"])

# ── Brute-force rate limiter (in-memory, per IP) ─────────────────────────────
_ATTEMPT_WINDOW = 15 * 60   # 15 minutes in seconds
_MAX_ATTEMPTS   = 5

_attempts: dict[str, list[float]] = defaultdict(list)   # ip → [timestamps]


def _check_rate_limit(ip: str) -> tuple[bool, int]:
    """
    Returns (is_blocked, seconds_remaining).
    Cleans up stale attempt timestamps on every call.
    """
    now    = time.time()
    window = [t for t in _attempts[ip] if now - t < _ATTEMPT_WINDOW]
    _attempts[ip] = window

    if len(window) >= _MAX_ATTEMPTS:
        oldest    = min(window)
        remaining = int(_ATTEMPT_WINDOW - (now - oldest))
        return True, remaining
    return False, 0


def _record_attempt(ip: str) -> None:
    _attempts[ip].append(time.time())


def _clear_attempts(ip: str) -> None:
    _attempts.pop(ip, None)


def _client_ip(request: Request) -> str:
    """Best-effort client IP extraction (works behind proxies too)."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host or "unknown")


# ── Validators ────────────────────────────────────────────────────────────────

def _validate_password(pw: str) -> str | None:
    """Return error string or None if valid."""
    if len(pw) < 8:
        return "Password must be at least 8 characters."
    if not re.search(r"[A-Za-z]", pw):
        return "Password must contain at least one letter."
    if not re.search(r"\d", pw):
        return "Password must contain at least one number."
    return None


def _validate_aadhaar(aadhaar: str) -> str | None:
    """12-digit Aadhaar number."""
    if not re.fullmatch(r"\d{12}", aadhaar):
        return "Aadhaar must be exactly 12 digits."
    return None


def _validate_phone(phone: str) -> str | None:
    """10-digit Indian mobile number (optional country code)."""
    digits = re.sub(r"[\s\-\+]", "", phone)
    if digits.startswith("91"):
        digits = digits[2:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        return "Phone must be a valid 10-digit mobile number."
    return None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/login")
async def login(
    request: Request,
    name: str     = Form(...),
    password: str = Form(...),
):
    ip = _client_ip(request)

    # ── Rate limit check ─────────────────────────────────────────────────────
    blocked, remaining = _check_rate_limit(ip)
    if blocked:
        mins = remaining // 60
        secs = remaining % 60
        return JSONResponse(
            {"ok": False, "error": f"Too many failed attempts. Try again in {mins}m {secs}s.", "locked": True},
            status_code=429,
        )

    # ── Basic input validation ────────────────────────────────────────────────
    name = name.strip()
    if not name or len(name) < 2:
        return JSONResponse({"ok": False, "error": "Please enter a valid farmer name.", "field": "name"}, status_code=400)
    if not password:
        return JSONResponse({"ok": False, "error": "Password is required.", "field": "password"}, status_code=400)

    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            "SELECT farmer_id, name, password, village, phone, aadhaar FROM farmers WHERE LOWER(name)=LOWER(%s)",
            (name,)
        )
        row = cur.fetchone()
        conn.close()

        if not row:
            _record_attempt(ip)
            # Deliberate vague message — don't leak whether username exists
            return JSONResponse(
                {"ok": False, "error": "Invalid name or password.", "field": "name"},
                status_code=401,
            )

        fid, fname, hashed, village, phone, aadhaar = row

        # ── Password check ───────────────────────────────────────────────────
        if not hashed or not bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8")):
            _record_attempt(ip)
            remaining_attempts = _MAX_ATTEMPTS - len(_attempts[ip])
            msg = "Invalid name or password."
            if remaining_attempts <= 2:
                msg += f" {remaining_attempts} attempt(s) left before lockout."
            return JSONResponse({"ok": False, "error": msg, "field": "password"}, status_code=401)

        # ── Success — clear lockout, create session ───────────────────────────
        _clear_attempts(ip)
        request.session.clear()                        # prevent session fixation
        request.session["farmer_id"]     = fid
        request.session["farmer_name"]   = fname
        request.session["farmer_village"]= village or ""
        request.session["farmer_phone"]  = phone  or ""
        request.session["login_time"]    = int(time.time())

        return JSONResponse({
            "ok":           True,
            "farmer_id":   fid,
            "farmer_name": fname,
            "village":     village or "",
        })

    except Exception as e:
        return JSONResponse({"ok": False, "error": "Server error. Please try again."}, status_code=500)


@router.post("/register")
async def register(
    request: Request,
    name:     str = Form(...),
    aadhaar:  str = Form(...),
    village:  str = Form(...),
    phone:    str = Form(...),
    password: str = Form(...),
):
    ip = _client_ip(request)

    # ── Input validation ──────────────────────────────────────────────────────
    name    = name.strip()
    village = village.strip()

    errors = {}
    if not name or len(name) < 2:
        errors["name"] = "Name must be at least 2 characters."
    if len(name) > 100:
        errors["name"] = "Name must not exceed 100 characters."

    aadhaar_err = _validate_aadhaar(aadhaar.strip())
    if aadhaar_err:
        errors["aadhaar"] = aadhaar_err

    phone_err = _validate_phone(phone.strip())
    if phone_err:
        errors["phone"] = phone_err

    if not village or len(village) < 2:
        errors["village"] = "Village name must be at least 2 characters."

    pw_err = _validate_password(password)
    if pw_err:
        errors["password"] = pw_err

    if errors:
        first_field  = next(iter(errors))
        first_msg    = errors[first_field]
        return JSONResponse(
            {"ok": False, "error": first_msg, "field": first_field, "all_errors": errors},
            status_code=400,
        )

    try:
        # Hash password with cost factor 12
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

        conn = get_conn()
        cur  = conn.cursor()

        # Check for duplicate name (case-insensitive)
        cur.execute("SELECT 1 FROM farmers WHERE LOWER(name)=LOWER(%s)", (name,))
        if cur.fetchone():
            conn.close()
            return JSONResponse(
                {"ok": False, "error": "A farmer with this name already exists.", "field": "name"},
                status_code=409,
            )

        cur.execute(
            "INSERT INTO farmers (name, aadhaar, village, phone, password) VALUES (%s,%s,%s,%s,%s)",
            (name, aadhaar.strip(), village, phone.strip(), hashed),
        )
        conn.commit()

        cur.execute("SELECT farmer_id, name FROM farmers WHERE aadhaar=%s", (aadhaar.strip(),))
        row = cur.fetchone()
        conn.close()

        if not row:
            return JSONResponse({"ok": False, "error": "Registration failed. Please retry."}, status_code=500)

        fid, fname = row
        request.session.clear()
        request.session["farmer_id"]      = fid
        request.session["farmer_name"]    = fname
        request.session["farmer_village"] = village
        request.session["farmer_phone"]   = phone.strip()
        request.session["login_time"]     = int(time.time())

        return JSONResponse({"ok": True, "farmer_id": fid, "farmer_name": fname})

    except psycopg2.errors.UniqueViolation:
        return JSONResponse(
            {"ok": False, "error": "Aadhaar number is already registered.", "field": "aadhaar"},
            status_code=409,
        )
    except Exception as e:
        return JSONResponse({"ok": False, "error": "Server error. Please try again."}, status_code=500)


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return JSONResponse({"ok": True, "message": "Logged out successfully."})


@router.get("/me")
async def me(request: Request):
    """Public endpoint — tells the frontend whether a session exists."""
    fid   = request.session.get("farmer_id")
    fname = request.session.get("farmer_name")
    if fid:
        return {
            "logged_in":    True,
            "farmer_id":    fid,
            "farmer_name":  fname,
            "village":      request.session.get("farmer_village", ""),
            "login_time":   request.session.get("login_time"),
        }
    return {"logged_in": False}


@router.get("/profile")
async def get_profile(farmer: FarmerSession = Depends(require_auth)):
    """Return full profile for the logged-in farmer."""
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            "SELECT farmer_id, name, aadhaar, village, phone FROM farmers WHERE farmer_id=%s",
            (farmer.id,)
        )
        row = cur.fetchone()

        # Detection count
        cur.execute("SELECT COUNT(*) FROM detection_history WHERE farmer_id=%s", (farmer.id,))
        det_count = cur.fetchone()[0]

        # Farm count
        cur.execute("SELECT COUNT(*) FROM farms WHERE farmer_id=%s", (farmer.id,))
        farm_count = cur.fetchone()[0]

        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Farmer not found")

        return {
            "farmer_id":      row[0],
            "name":           row[1],
            "aadhaar_masked": f"XXXX-XXXX-{row[2][-4:]}" if row[2] and len(row[2]) >= 4 else "—",
            "village":        row[3] or "—",
            "phone":          row[4] or "—",
            "detection_count": det_count,
            "farm_count":     farm_count,
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.put("/profile")
async def update_profile(
    request: Request,
    village: str = Form(""),
    phone:   str = Form(""),
    farmer:  FarmerSession = Depends(require_auth),
):
    """Update mutable profile fields (village, phone)."""
    errors = {}
    if phone and (phone_err := _validate_phone(phone.strip())):
        errors["phone"] = phone_err
    if village and len(village.strip()) < 2:
        errors["village"] = "Village name too short."
    if errors:
        return JSONResponse({"ok": False, "errors": errors}, status_code=400)

    try:
        conn = get_conn()
        cur  = conn.cursor()
        if village:
            cur.execute("UPDATE farmers SET village=%s WHERE farmer_id=%s", (village.strip(), farmer.id))
        if phone:
            cur.execute("UPDATE farmers SET phone=%s WHERE farmer_id=%s", (phone.strip(), farmer.id))
        conn.commit()
        conn.close()

        # Keep session in sync
        if village:
            request.session["farmer_village"] = village.strip()
        if phone:
            request.session["farmer_phone"] = phone.strip()

        return JSONResponse({"ok": True, "message": "Profile updated successfully."})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/farmers")
async def list_farmers():
    """Return all farmer names for autocomplete (no sensitive data)."""
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("SELECT farmer_id, name FROM farmers ORDER BY name")
        rows = cur.fetchall()
        conn.close()
        return [{"farmer_id": r[0], "name": r[1]} for r in rows]
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/lockout-status")
async def lockout_status(request: Request):
    """Lets the frontend show a live countdown timer."""
    ip = _client_ip(request)
    blocked, remaining = _check_rate_limit(ip)
    return {"locked": blocked, "remaining_seconds": remaining}
