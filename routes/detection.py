"""
Detection routes — model-based image prediction & AI expert mode.
Protected by require_auth dependency.
"""
import os
import uuid
import shutil
import numpy as np
from PIL import Image
from fastapi import APIRouter, Request, File, UploadFile, Form, Depends
from fastapi.responses import JSONResponse
from groq import Groq

from database import get_conn
from auth_dep import require_auth, FarmerSession

from models.disease_classifier import DiseaseClassifier

router = APIRouter(tags=["detection"])

# ── Initialize Classifier ───────────────────────────────────────────────────
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plant_disease_model.h5")
CLASSES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "classes.json")

classifier = DiseaseClassifier(MODEL_PATH, CLASSES_PATH)

import os
from dotenv import load_dotenv

load_dotenv()

# ── Groq client ───────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client  = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

UPLOAD_DIR   = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _save_history(farmer_id, mode, disease_name, confidence, image_path, leaf, color, symptoms):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            """INSERT INTO detection_history
               (farmer_id, mode, disease_name, confidence, image_path, leaf_name, leaf_color, symptoms)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (farmer_id, mode, disease_name, confidence, image_path, leaf, color, symptoms),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print("History save error:", e)


@router.post("/model")
async def detect_model(
    image:  UploadFile = File(...),
    farmer: FarmerSession = Depends(require_auth),
):
    # Validate file extension
    ext = os.path.splitext(image.filename or "")[1].lower()
    ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
    MAX_FILE_MB = 10
    
    if ext not in ALLOWED_EXT:
        return JSONResponse({"ok": False, "error": f"Unsupported file type '{ext}'. Use JPG, PNG or WEBP."}, status_code=400)

    # Read and validate file size
    content = await image.read()
    if len(content) > MAX_FILE_MB * 1024 * 1024:
        return JSONResponse({"ok": False, "error": f"Image too large. Maximum size is {MAX_FILE_MB} MB."}, status_code=413)

    fname     = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_DIR, fname)
    with open(save_path, "wb") as f:
        f.write(content)

    try:
        # Generate disease prediction and heatmap
        disease, confidence, heatmap_path = classifier.predict(save_path, generate_heatmap=True)

        treatment_resp = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{
                "role": "user",
                "content": (
                    f"Provide concise treatment, recommended medicine, dosage, and prevention tips "
                    f"for the plant disease: {disease}. Use a structured format with bullet points."
                )
            }],
        )
        treatment = treatment_resp.choices[0].message.content

        relative_path = f"/static/uploads/{fname}"
        # Use heatmap_path if it exists, ensure it starts with /
        heatmap_url = f"/{heatmap_path}" if heatmap_path else None
        
        _save_history(farmer.id, "model", disease, confidence, relative_path, None, None, None)

        return JSONResponse({
            "ok":         True,
            "disease":    disease,
            "confidence": confidence,
            "treatment":  treatment,
            "image_url":  relative_path,
            "heatmap_url": heatmap_url,
        })

    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# ── Webcam Streaming ──────────────────────────────────────────────────────────
import cv2
import time
from fastapi.responses import StreamingResponse

def gen_frames():
    # Load model once before the loop
    try:
        model, class_names = classifier.load()
        grad_model = classifier.get_grad_models()
    except Exception as e:
        print(f"Error initializing model for camera: {e}")
        return

    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        print("Error: Could not open camera.")
        return

    try:
        while True:
            success, frame = camera.read()
            if not success:
                print("Error: Failed to capture frame.")
                break
            
            try:
                # Preprocess for model
                img_res = cv2.resize(frame, (224, 224))
                img_input = np.expand_dims(img_res / 255.0, axis=0)
                
                # Predict using the already loaded model
                preds = model.predict(img_input, verbose=0)
                idx = int(np.argmax(preds))
                confidence = round(float(preds[0][idx]) * 100, 2)
                disease = class_names[idx] if class_names else f"Class_{idx}"
                
                # Generate Grad-CAM for live frame with circles and banner
                if grad_model:
                    frame = classifier.live_gradcam(frame, idx, disease, confidence)
                
                ret, buffer = cv2.imencode('.jpg', frame)
                if not ret:
                    continue
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            except Exception as e:
                print(f"Error in gen_frames loop: {e}")
                break
    finally:
        print("Releasing camera handle...")
        camera.release()

@router.get("/video_feed")
async def video_feed(farmer: FarmerSession = Depends(require_auth)):
    return StreamingResponse(gen_frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.post("/ai")
async def detect_ai(
    leaf:     str = Form(...),
    color:    str = Form(...),
    symptoms: str = Form(""),
    farmer:   FarmerSession = Depends(require_auth),
):
    leaf     = leaf.strip()
    color    = color.strip()
    symptoms = symptoms.strip()

    if not leaf or not color:
        return JSONResponse({"ok": False, "error": "Leaf type and colour are required."}, status_code=400)

    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{
                "role": "user",
                "content": (
                    f"A farmer described a plant problem:\n"
                    f"- Leaf type: {leaf}\n"
                    f"- Leaf colour: {color}\n"
                    f"- Symptoms: {symptoms or 'None specified'}\n\n"
                    f"Identify the most likely plant disease and provide structured treatment advice "
                    f"with medicine names, dosage, and prevention tips."
                )
            }],
        )
        diagnosis = resp.choices[0].message.content
        _save_history(farmer.id, "ai", "AI-Diagnosis", None, None, leaf, color, symptoms)
        return JSONResponse({"ok": True, "diagnosis": diagnosis})

    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
