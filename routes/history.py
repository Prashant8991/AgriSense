"""
History routes — CRUD + PDF export, all protected by require_auth.
"""
import io
from fastapi import APIRouter, Request, Query, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from database import get_conn
from auth_dep import require_auth, FarmerSession

router = APIRouter(tags=["history"])


@router.get("/list")
async def list_history(
    search:    str = Query(""),
    mode:      str = Query("all"),
    date_from: str = Query(""),
    date_to:   str = Query(""),
    farmer:    FarmerSession = Depends(require_auth),
):
    try:
        conn  = get_conn()
        cur   = conn.cursor()
        query = """SELECT id, mode, disease_name, confidence, image_path,
                          leaf_name, leaf_color, symptoms, created_at
                   FROM detection_history WHERE farmer_id=%s"""
        params = [farmer.id]

        if search:
            query += " AND disease_name ILIKE %s"
            params.append(f"%{search}%")
        if mode and mode.lower() != "all":
            query += " AND mode=%s"
            params.append(mode.lower())
        if date_from:
            query += " AND created_at >= %s"
            params.append(date_from)
        if date_to:
            query += " AND created_at <= %s"
            params.append(date_to + " 23:59:59")

        query += " ORDER BY id DESC LIMIT 200"
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        conn.close()

        return [
            {
                "id":           r[0],
                "mode":         r[1],
                "disease_name": r[2],
                "confidence":   float(r[3]) if r[3] else None,
                "image_path":   r[4],
                "leaf_name":    r[5],
                "leaf_color":   r[6],
                "symptoms":     r[7],
                "created_at":   str(r[8]),
            }
            for r in rows
        ]
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.delete("/{record_id}")
async def delete_record(
    record_id: int,
    farmer:    FarmerSession = Depends(require_auth),
):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            "DELETE FROM detection_history WHERE id=%s AND farmer_id=%s",
            (record_id, farmer.id),
        )
        deleted = cur.rowcount
        conn.commit()
        conn.close()
        if deleted:
            return JSONResponse({"ok": True})
        return JSONResponse({"ok": False, "error": "Record not found or access denied."}, status_code=404)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/export-pdf")
async def export_pdf(
    request: Request,
    farmer:  FarmerSession = Depends(require_auth),
):
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors

    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            """SELECT mode, disease_name, confidence, leaf_name, leaf_color, symptoms, created_at
               FROM detection_history WHERE farmer_id=%s ORDER BY id DESC""",
            (farmer.id,),
        )
        rows = cur.fetchall()
        conn.close()

        buffer = io.BytesIO()
        doc    = SimpleDocTemplate(buffer, pagesize=letter,
                                   leftMargin=40, rightMargin=40, topMargin=50, bottomMargin=40)
        styles = getSampleStyleSheet()
        story  = []

        story.append(Paragraph("AgriSense Pro — Detection History Report", styles["Title"]))
        story.append(Paragraph(f"Farmer: <b>{farmer.name}</b>", styles["Normal"]))
        story.append(Spacer(1, 14))

        table_data = [["#", "Mode", "Disease / Diagnosis", "Confidence", "Leaf", "Colour", "Date"]]
        for i, r in enumerate(rows, 1):
            table_data.append([
                str(i),
                r[0] or "—",
                r[1] or "—",
                f"{r[2]:.1f}%" if r[2] else "—",
                r[3] or "—",
                r[4] or "—",
                str(r[6])[:10] if r[6] else "—",
            ])

        t = Table(table_data, repeatRows=1, colWidths=[25, 45, 145, 60, 70, 60, 70])
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#1E7A52")),
            ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, -1), 8),
            ("PADDING",      (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0FBF5")]),
            ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#CCEAD8")),
            ("ALIGN",        (0, 0), (-1, -1), "LEFT"),
        ]))
        story.append(t)
        doc.build(story)
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="agrisense_history_{farmer.id}.pdf"'},
        )

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
