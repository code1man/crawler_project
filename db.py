# db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

DATABASE_URI = "mysql+pymysql://root:zkd2621023939@localhost:3306/my_demo?charset=utf8mb4"
engine = create_engine(DATABASE_URI, pool_pre_ping=True)
Session = sessionmaker(bind=engine)
# 创建表
Base.metadata.create_all(engine)