from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

SQLALCHEMY_DATABASE_URL = 'postgresql://todo_postgre_sql_5oqk_user:yAz6bMxcDqCLx6fyrjW0r0FIEeomAdN6@dpg-ctvtn1rv2p9s7399osrg-a/todo_postgre_sql_5oqk'

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={'check_same_thread': False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
