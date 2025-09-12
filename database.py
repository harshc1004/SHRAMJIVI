from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+psycopg2://shramjivi_user:xpXXTQAcdvNNS2q48JfyZb9IRvamuFut@dpg-d2on9gndiees73fksfbg-a.oregon-postgres.render.com:5432/shramjivi"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)  # <- important!
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()