from fastapi import FastAPI,Depends
from typing import List, Annotated
from kafka import KafkaConsumer
from sqlalchemy.orm import Session
import json
import threading
from database import SessionLocal
from models import Base, TodosArchive
from database import engine

app = FastAPI()

# Ініціалізація Kafka-консумера
consumer = KafkaConsumer(
    'my_topic',
    bootstrap_servers='localhost:9092',
    group_id='consumer-group-id',
    auto_offset_reset='earliest',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

messages = []
Base.metadata.create_all(bind=engine)



def consume_messages():
    """
    Функція для обробки отриманих повідомлень із Kafka та збереження їх у базу даних.
    """
    db = SessionLocal()
    try:
        for message in consumer:
            try:
                archive_todo = message.value
                if isinstance(archive_todo, dict) and 'title' in archive_todo:
                    print(f"Archiving Todo: {archive_todo['title']}")
                    # Збереження в базу даних
                    todo_record = TodosArchive(**archive_todo)
                    db.add(todo_record)
                    db.commit()
                    db.refresh(todo_record)
                else:
                    print(f"Invalid message format: {message.value}")
            except Exception as e:
                print(f"Error processing message: {e}")
    finally:
        db.close()

# Запуск споживача в окремому потоці
threading.Thread(target=consume_messages, daemon=True).start()

@app.get("/messages/")
async def get_messages():
    """
    Отримати всі архівовані повідомлення з бази даних.
    """
    db = SessionLocal()
    try:
        todos = db.query(TodosArchive).all()
        return {"Archived todos": [todo.__dict__ for todo in todos]}
    finally:
        db.close()