import os
import re
import numpy as np
import cv2
import easyocr

from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db


app = FastAPI(title="OCR API")

MAX_FILE_SIZE = 8 * 1024 * 1024
MAX_IMAGE_DIM = 1024  

def preprocess_image_bytes(file_bytes):
    arr = np.frombuffer(file_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)

    h, w = img.shape
    if max(h, w) > MAX_IMAGE_DIM:
        scale = MAX_IMAGE_DIM / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)))

    img = cv2.fastNlMeansDenoising(img, None, 30, 7, 21)

    img = cv2.adaptiveThreshold(img, 255,
                                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, 35, 11)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2,2))
    img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel)
    return img

def normalize_number(text):
    marathi_to_eng = str.maketrans("०१२३४५६७८९", "0123456789")
    return (text or "").translate(marathi_to_eng)

def extract_fields(text_lines):
    text = " ".join(text_lines or [])

    def digits_only(s): return re.sub(r'\D', '', normalize_number(s or ""))
    def keep_date_chars(s): return re.sub(r'[^0-9/-]', '', normalize_number(s or ""))

    data = {
        "Receipt No": None,
        "Date": None,
        "Name": None,
        "Address": None,
        "Age": None,
        "Mobile No": None,
        "Grampanchayat": None,
        "Taluka": None,
        "District": None,
        "Rs": 100
    }

    m = re.search(r"(?:पावती.?नं|पावती.?क्रमांक|Receipt.?No)[:\s]*([0-9०-९]+)", text)
    if m:
        data["Receipt No"] = normalize_number(m.group(1))
    else:
        for i, line in enumerate(text_lines):
            if "पावती" in line and i+1 < len(text_lines):
                num = digits_only(text_lines[i+1])
                if num: data["Receipt No"] = num

    m = re.search(r"(?:दिनांक|तारीख|Date)[:\s]*([0-9०-९/-]+)", text)
    if m: data["Date"] = keep_date_chars(m.group(1))

    m = re.search(r"(?:मोबा\.?नं|Mobile)[:\s]*([0-9०-९]{10,})", text)
    if m: data["Mobile No"] = normalize_number(m.group(1))

    m = re.search(r"(?:एकूण|रक्कम|Total)[:\s]*([0-9०-९]+)", text)
    if m: data["Rs"] = normalize_number(m.group(1))

    for i, line in enumerate(text_lines):
        if "श्री" in line or "श्रीम" in line:
            if i+1 < len(text_lines): data["Name"] = text_lines[i+1]
        if "पत्ता" in line or "गाव" in line:
            if i+1 < len(text_lines): data["Address"] = text_lines[i+1]
        if "वय" in line:
            if i+1 < len(text_lines):
                age = digits_only(text_lines[i+1])
                if age: data["Age"] = age
        if "ग्रामपंचायत" in line:
            if i+1 < len(text_lines): data["Grampanchayat"] = text_lines[i+1]
        if "तालुका" in line:
            if i+1 < len(text_lines): data["Taluka"] = text_lines[i+1]
        if "जिल्हा" in line:
            if i+1 < len(text_lines): data["District"] = text_lines[i+1]

    return data

reader = easyocr.Reader(['mr'], gpu=False) 
-
@app.post("/ocr/")
async def ocr_api(
    file: UploadFile = File(...),
    member_image_id: int = Form(...),
    uploaded_by_id: int = Form(...),
    db: Session = Depends(get_db)
):
    contents = await file.read()

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Max 8MB allowed.")

    db_image = MemberImage(
        image=contents,
        member_image_id=member_image_id,
        uploaded_by_id=uploaded_by_id
    )
    db.add(db_image)
    db.commit()
    db.refresh(db_image)

    img = preprocess_image_bytes(contents)

    results = reader.readtext(img, detail=0)

    fields = extract_fields(results)
    fields["db_id"] = db_image.id

    return JSONResponse(content=fields)