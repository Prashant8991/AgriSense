"""
Report routes — protected by require_auth.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from database import get_conn
from auth_dep import require_auth, FarmerSession

router = APIRouter(tags=["report"])


@router.get("/")
async def get_report(farmer: FarmerSession = Depends(require_auth)):
    try:
        conn = get_conn()
        cur  = conn.cursor()

        cur.execute(
            """SELECT mode, disease_name, confidence, leaf_name, leaf_color, symptoms, created_at
               FROM detection_history
               WHERE farmer_id=%s
               ORDER BY created_at DESC""",
            (farmer.id,),
        )
        rows = cur.fetchall()

        legacy = []
        try:
            cur.execute(
                """SELECT fa.name, fm.crop_type, d.disease_name, ci.confidence_score, ci.detected_at
                   FROM crop_images ci
                   JOIN farms fm ON ci.farm_id = fm.farm_id
                   JOIN farmers fa ON fm.farmer_id = fa.farmer_id
                   JOIN diseases d ON ci.disease_id = d.disease_id
                   WHERE fm.farmer_id=%s
                   ORDER BY ci.detected_at DESC""",
                (farmer.id,),
            )
            legacy = [
                {"farmer": r[0], "crop": r[1], "disease": r[2],
                 "confidence": float(r[3]) if r[3] else None, "date": str(r[4])}
                for r in cur.fetchall()
            ]
        except Exception:
            pass  # legacy table may not exist

        conn.close()

        return {
            "farmer_name": farmer.name,
            "history": [
                {
                    "mode":         r[0],
                    "disease_name": r[1],
                    "confidence":   float(r[2]) if r[2] else None,
                    "leaf_name":    r[3],
                    "leaf_color":   r[4],
                    "symptoms":     r[5],
                    "created_at":   str(r[6]),
                }
                for r in rows
            ],
            "legacy": legacy,
        }

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
