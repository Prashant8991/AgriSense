"""
Farm routes — register a farm for the logged-in farmer.
Protected by require_auth dependency.
"""
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import JSONResponse
from database import get_conn
from auth_dep import require_auth, FarmerSession

router = APIRouter(tags=["farm"])


@router.post("/register")
async def register_farm(
    crop_type:  str = Form(...),
    area_acres: str = Form(...),
    soil_type:  str = Form(...),
    latitude:   float = Form(None),
    longitude:  float = Form(None),
    farmer: FarmerSession = Depends(require_auth),
):
    if not crop_type.strip() or not soil_type.strip():
        return JSONResponse({"ok": False, "error": "Crop type and soil type are required."}, status_code=400)
    try:
        area = float(area_acres)
        if area <= 0:
            raise ValueError
    except ValueError:
        return JSONResponse({"ok": False, "error": "Area must be a positive number."}, status_code=400)

    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            "INSERT INTO farms (farmer_id, crop_type, area_acres, soil_type, latitude, longitude) VALUES (%s,%s,%s,%s,%s,%s)",
            (farmer.id, crop_type.strip(), area, soil_type.strip(), latitude, longitude),
        )
        conn.commit()
        conn.close()
        return JSONResponse({"ok": True, "message": "Farm registered successfully."})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/my-farms")
async def my_farms(farmer: FarmerSession = Depends(require_auth)):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            "SELECT farm_id, crop_type, area_acres, soil_type, latitude, longitude FROM farms WHERE farmer_id=%s ORDER BY farm_id DESC",
            (farmer.id,),
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "farm_id": r[0], 
                "crop_type": r[1], 
                "area_acres": float(r[2]) if r[2] else 0, 
                "soil_type": r[3],
                "latitude": r[4],
                "longitude": r[5]
            }
            for r in rows
        ]
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/map-data")
async def get_map_data(farmer: FarmerSession = Depends(require_auth)):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        
        # We fetch all farms and try to find the latest detection related to that crop for this farmer
        cur.execute(
            """
            SELECT f.farm_id, f.crop_type, f.latitude, f.longitude,
                   (SELECT disease_name FROM detection_history 
                    WHERE farmer_id = f.farmer_id 
                    AND disease_name ILIKE f.crop_type || '%%'
                    ORDER BY created_at DESC LIMIT 1) as latest_disease,
                   (SELECT confidence FROM detection_history 
                    WHERE farmer_id = f.farmer_id 
                    AND disease_name ILIKE f.crop_type || '%%'
                    ORDER BY created_at DESC LIMIT 1) as confidence,
                   (SELECT created_at FROM detection_history 
                    WHERE farmer_id = f.farmer_id 
                    AND disease_name ILIKE f.crop_type || '%%'
                    ORDER BY created_at DESC LIMIT 1) as detection_date
            FROM farms f
            WHERE f.farmer_id = %s
            """,
            (farmer.id,)
        )
        rows = cur.fetchall()
        conn.close()
        
        results = []
        for r in rows:
            latest_disease = r[4]
            # Use float(r[5]) if it exists, otherwise confidence is None
            raw_confidence = r[5]
            confidence = float(raw_confidence) if raw_confidence is not None else None
            
            # DEFAULT: If no detection record exists, status is 'Healthy'
            status = "Healthy"
            
            if latest_disease:
                # Disease identified, now categorize based on name and confidence
                low_disease = latest_disease.lower()
                
                if "healthy" in low_disease:
                    status = "Healthy"
                else:
                    # Not 'healthy' - evaluate confidence
                    if confidence and confidence >= 85:
                        status = "High Risk"
                    else:
                        status = "Disease Detected"
            
            results.append({
                "farm_id": r[0],
                "crop_type": r[1],
                "latitude": r[2],
                "longitude": r[3],
                "latest_disease": latest_disease or "No scans yet",
                "confidence": confidence,
                "detection_date": r[6].strftime("%Y-%m-%d") if r[6] else "N/A",
                "status": status
            })
        return results
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


from services.weather_service import get_weather_data, predict_disease_risk
from services.ndvi_service import get_ndvi_data

@router.get("/farm-ndvi/{farm_id}")
async def get_farm_ndvi(farm_id: int, farmer: FarmerSession = Depends(require_auth)):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        
        # 1. Fetch farm coordinates
        cur.execute(
            "SELECT latitude, longitude FROM farms WHERE farm_id=%s AND farmer_id=%s",
            (farm_id, farmer.id),
        )
        row = cur.fetchone()
        conn.close()
        
        if not row:
            return JSONResponse({"ok": False, "error": "Farm not found."}, status_code=404)
        
        lat, lon = row
        if not lat or not lon:
            return JSONResponse({"ok": False, "error": "Farm coordinates missing."}, status_code=400)
        
        # 2. Call NDVI service
        ndvi_info = get_ndvi_data(lat, lon)
        
        if not ndvi_info or "error" in ndvi_info:
            return JSONResponse({"ok": False, "error": ndvi_info.get("error", "Failed to fetch NDVI data.")}, status_code=500)
        
        # Return structured NDVI data
        return {
            "ok": True,
            "farm_id": farm_id,
            "ndvi_value": ndvi_info["ndvi_value"],
            "crop_health": ndvi_info["crop_health"],
            "last_satellite_date": ndvi_info.get("date", "N/A")
        }
        
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@router.get("/farm-weather/{farm_id}")
async def get_farm_weather(farm_id: int, farmer: FarmerSession = Depends(require_auth)):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        
        # 1. Fetch farm coordinates
        cur.execute(
            "SELECT latitude, longitude, crop_type FROM farms WHERE farm_id=%s AND farmer_id=%s",
            (farm_id, farmer.id),
        )
        row = cur.fetchone()
        conn.close()
        
        if not row:
            return JSONResponse({"ok": False, "error": "Farm not found."}, status_code=404)
        
        lat, lon, crop = row
        if not lat or not lon:
            return JSONResponse({"ok": False, "error": "Farm coordinates missing."}, status_code=400)
        
        # 2. Call weather service
        weather = get_weather_data(lat, lon)
        if not weather:
            return JSONResponse({"ok": False, "error": "Failed to fetch weather data."}, status_code=500)
        
        # 3. Predict disease risk
        risk_info = predict_disease_risk(weather["temperature"], weather["humidity"], weather["rainfall"])
        
        # Combine data
        return {
            "ok": True,
            "farm_id": farm_id,
            "crop": crop,
            "temperature": weather["temperature"],
            "humidity": weather["humidity"],
            "rainfall": weather["rainfall"],
            "wind_speed": weather["wind_speed"],
            "condition": weather["weather_condition"],
            "disease_risk": risk_info["disease_risk"],
            "possible_disease": risk_info["possible_disease"]
        }
        
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@router.delete("/{farm_id}")
async def delete_farm(farm_id: int, farmer: FarmerSession = Depends(require_auth)):
    """Delete a farm owned by the current farmer (ownership checked)."""
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            "DELETE FROM farms WHERE farm_id=%s AND farmer_id=%s",
            (farm_id, farmer.id),
        )
        deleted = cur.rowcount
        conn.commit()
        conn.close()
        if deleted:
            return JSONResponse({"ok": True})
        return JSONResponse({"ok": False, "error": "Farm not found or access denied."}, status_code=404)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
