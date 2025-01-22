from fastapi import FastAPI,Depends
from kafka import KafkaConsumer
import json
import threading
import smtplib
from email.message import EmailMessage
from starlette.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader
import os
from dotenv import load_dotenv

load_dotenv()

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
TOPIC_NOTIFACATION = os.getenv("TOPIC_NOTIFACATION")

app = FastAPI()

# Ініціалізація Kafka-консумера
consumer = KafkaConsumer(
    TOPIC_NOTIFACATION,
    bootstrap_servers='localhost:9092',
    group_id='consumer-group-id',
    auto_offset_reset='earliest',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

email_templates_env = Environment(loader=FileSystemLoader("notifications/templates"))





def consume_messages():

    for message in consumer:
        try:
            archive_todo = message.value
            if isinstance(archive_todo, dict) and 'title' in archive_todo:
                print(f"Send notifications: {archive_todo['title']}")
                email=archive_todo.get('user_email')
                title=archive_todo.get('title')
                description=archive_todo.get('description')
                priority=archive_todo.get('priority')


                template = email_templates_env.get_template("email_template.html")
                html_content = template.render(title=title, description=description, priority=priority)

                # Create email
                msg = EmailMessage()
                msg['Subject'] = "Todo notifications"
                msg['From'] = EMAIL_ADDRESS
                msg['To'] = email
                msg.set_content("This email requires an HTML-compatible email client.")  # Текстовий варіант
                msg.add_alternative(html_content, subtype="html")

                # Send email
                with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                    smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                    smtp.send_message(msg)

                print("Email send")
            else:
                print(f"Invalid message format: {message.value}")
        except Exception as e:
            print(f"Error processing message: {e}")


# Запуск споживача в окремому потоці
threading.Thread(target=consume_messages, daemon=True).start()