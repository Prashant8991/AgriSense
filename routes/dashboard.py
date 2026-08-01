"""
Dashboard, History, and Report routes — all protected by require_auth.
"""
# dashboard.py
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from database import get_conn
from auth_dep import require_auth, FarmerSession

router = APIRouter(tags=["dashboard"])


@router.get("/stats")
async def stats(farmer: FarmerSession = Depends(require_auth)):
    try:
        conn = get_conn()
        cur  = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM detection_history WHERE farmer_id=%s", (farmer.id,))
        total = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM detection_history WHERE farmer_id=%s AND DATE(created_at)=CURRENT_DATE",
            (farmer.id,),
        )
        today = cur.fetchone()[0]

        cur.execute(
            """SELECT disease_name, COUNT(*) AS c FROM detection_history
               WHERE farmer_id=%s AND disease_name IS NOT NULL
               GROUP BY disease_name ORDER BY c DESC LIMIT 1""",
            (farmer.id,),
        )
        row    = cur.fetchone()
        common = row[0] if row else "N/A"

        cur.execute(
            "SELECT disease_name FROM detection_history WHERE farmer_id=%s ORDER BY id DESC LIMIT 1",
            (farmer.id,),
        )
        row  = cur.fetchone()
        last = row[0] if row else "N/A"

        cur.execute(
            """SELECT disease_name, COUNT(*) FROM detection_history
               WHERE farmer_id=%s AND disease_name IS NOT NULL
                 AND created_at >= NOW() - INTERVAL '30 days'
               GROUP BY disease_name ORDER BY COUNT(*) DESC LIMIT 8""",
            (farmer.id,),
        )
        chart_rows = cur.fetchall()

        cur.execute(
            """SELECT DATE(created_at) AS day, COUNT(*) FROM detection_history
               WHERE farmer_id=%s AND created_at >= NOW() - INTERVAL '7 days'
               GROUP BY day ORDER BY day""",
            (farmer.id,),
        )
        trend_rows = cur.fetchall()

        conn.close()

        return {
            "total":         total,
            "today":         today,
            "most_common":   common,
            "last_detected": last,
            "chart":         [{"disease": r[0], "count": r[1]} for r in chart_rows],
            "trend":         [{"day": str(r[0]), "count": r[1]} for r in trend_rows],
        }

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
