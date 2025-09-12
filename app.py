import re
import numpy as np
import cv2
import easyocr
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, Column, Integer, LargeBinary, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from database import engine, Base

# --------- Database Setup ----------
DB_USER = "shramjivi_user"
DB_PASSWORD = "xpXXTQAcdvNNS2q48JfyZb9IRvamuFut'"
DB_HOST = "dpg-d2on9gndiees73fksfbg-a"
DB_PORT = "5432"
DB_NAME = "shramjivi"

DATABASE_URL = "postgresql+psycopg2://shramjivi_user:xpXXTQAcdvNNS2q48JfyZb9IRvamuFut@dpg-d2on9gndiees73fksfbg-a.oregon-postgres.render.com:5432/shramjivi"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class NotificationImageMember(Base):
    __tablename__ = "notifications_imagemembers"
    id = Column(Integer, primary_key=True, index=True)
    image = Column(LargeBinary, nullable=False)

Base.metadata.create_all(bind=engine)

# --------- FastAPI Setup ----------
app = FastAPI(title="OCR API")
reader = easyocr.Reader(['mr'], gpu=False)

# --------- OCR & Helpers ----------
def normalize_number(text):
    marathi_to_eng = str.maketrans("०१२३४५६७८९", "0123456789")
    return (text or "").translate(marathi_to_eng)

def digits_only(s):
    return re.sub(r'\D', '', normalize_number(s or ""))

def keep_date_chars(s):
    return re.sub(r'[^0-9/-]', '', normalize_number(s or ""))

def extract_fields(text_lines):
    text = " ".join(text_lines or [])
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
    if m: data["Receipt No"] = normalize_number(m.group(1))

    m = re.search(r"(?:दिनांक|तारीख|Date)[:\s]*([0-9०-९/-]+)", text)
    if m: data["Date"] = keep_date_chars(m.group(1))

    m = re.search(r"(?:मोबा\.?नं|Mobile)[:\s]*([0-9०-९]{10,})", text)
    if m: data["Mobile No"] = normalize_number(m.group(1))

    m = re.search(r"(?:एकूण|रक्कम|Total)[:\s]*([0-9०-९]+)", text)
    if m: data["Rs"] = normalize_number(m.group(1))

    for i, line in enumerate(text_lines):
        if "श्री" in line or "श्रीम" in line and i+1 < len(text_lines):
            data["Name"] = text_lines[i+1]
        if "पत्ता" in line or "गाव" in line and i+1 < len(text_lines):
            data["Address"] = text_lines[i+1]
        if "वय" in line and i+1 < len(text_lines):
            age = digits_only(text_lines[i+1])
            if age: data["Age"] = age
        if "ग्रामपंचायत" in line and i+1 < len(text_lines):
            data["Grampanchayat"] = text_lines[i+1]
        if "तालुका" in line and i+1 < len(text_lines):
            data["Taluka"] = text_lines[i+1]
        if "जिल्हा" in line and i+1 < len(text_lines):
            data["District"] = text_lines[i+1]
    return data

# --------- FastAPI Endpoint ----------


@app.get("/")
def home():
    return {"message": "API running"}

@app.post("/ocr/")
async def ocr_api(file: UploadFile = File(...)):
    # Read image bytes
    contents = await file.read()
    arr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)

    # OCR
    results = reader.readtext(img, detail=0)
    extracted_data = extract_fields(results)

    # Save image in DB
    db = SessionLocal()
    try:
        new_image = NotificationImageMember(image=contents)  # only this
        db.add(new_image)
        db.commit()
        db.refresh(new_image)
        extracted_data["db_id"] = new_image.id
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

    return JSONResponse(content=extracted_data)