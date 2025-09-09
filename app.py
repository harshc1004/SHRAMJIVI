import re
import json
import numpy as np
import cv2
import easyocr

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

app = FastAPI(title="OCR API")

# Preprocessing (adapted from your code)
def preprocess_image_bytes(file_bytes):
    # decode bytes -> grayscale image
    arr = np.frombuffer(file_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)

    # noise reduction
    img = cv2.fastNlMeansDenoising(img, None, 30, 7, 21)

    # adaptive threshold
    img = cv2.adaptiveThreshold(img, 255,
                                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, 35, 11)

    # morphological closing
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2,2))
    img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel)

    return img

# Helpers 
def normalize_number(text):
    marathi_to_eng = str.maketrans("०१२३४५६७८९", "0123456789")
    return (text or "").translate(marathi_to_eng)

# Field extraction (your logic)
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

    # Receipt No
    m = re.search(r"(?:पावती.?नं|पावती.?क्रमांक|Receipt.?No)[:\s]*([0-9०-९]+)", text)
    if m:
        data["Receipt No"] = normalize_number(m.group(1))
    else:
        for i, line in enumerate(text_lines):
            if "पावती" in line and i+1 < len(text_lines):
                num = digits_only(text_lines[i+1])
                if num: data["Receipt No"] = num

    # Date
    m = re.search(r"(?:दिनांक|तारीख|Date)[:\s]*([0-9०-९/-]+)", text)
    if m: data["Date"] = keep_date_chars(m.group(1))

    # Mobile
    m = re.search(r"(?:मोबा\.?नं|Mobile)[:\s]*([0-9०-९]{10,})", text)
    if m: data["Mobile No"] = normalize_number(m.group(1))

    # Amount
    m = re.search(r"(?:एकूण|रक्कम|Total)[:\s]*([0-9०-९]+)", text)
    if m: data["Rs"] = normalize_number(m.group(1))

    # Sequential lookup
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

# Load OCR model once (module import time) 
# This may download model files the first time — keep reader global
reader = easyocr.Reader(['mr'], gpu=False)  # use gpu=True if you have CUDA properly configured

# ----- API route -----
@app.post("/ocr/")
async def ocr_api(file: UploadFile = File(...)):
    # read bytes from uploaded file
    contents = await file.read()

    # preprocess image
    img = preprocess_image_bytes(contents)

    # run easyocr (detail=0 returns list of strings)
    results = reader.readtext(img, detail=0)

    # extract structured fields
    fields = extract_fields(results)

    # return JSON
    return JSONResponse(content=fields)