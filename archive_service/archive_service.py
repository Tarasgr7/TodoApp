from fastapi import FastAPI
from kafka import KafkaConsumer
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import json

app = FastAPI()

# Налаштування бази даних SQLite
DATABASE_URL = "sqlite:///./archive.db"
Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Todo(Base):
    __tablename__ = "todos"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String, index=True)
    priority = Column(Integer)
    complete = Column(Boolean, default=False)

Base.metadata.create_all(bind=engine)

# Kafka Consumer
def consume_kafka():
    consumer = KafkaConsumer(
        'todo_topic',
        bootstrap_servers=['localhost:9092'],
        auto_offset_reset='earliest',
        group_id='archive_service',
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )
    db = SessionLocal()
    for message in consumer:
        todo_data = message.value
        # Збереження в базу даних
        new_todo = Todo(**todo_data)
        db.add(new_todo)
        db.commit()
        print(f"Archived Todo: {todo_data}")

import threading
threading.Thread(target=consume_kafka, daemon=True).start()

@app.get("/")
def health_check():
    return {"status": "Archive service running"}
