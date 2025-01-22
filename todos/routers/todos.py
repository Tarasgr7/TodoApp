from typing import Annotated
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException,Path,APIRouter, Request
from todos.models import Todos,Users
from todos.database import engine, SessionLocal
from starlette import status
from pydantic import BaseModel, Field
from .auth import get_current_user
from starlette.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi import FastAPI
from kafka import KafkaProducer
import json
import os
from dotenv import load_dotenv

load_dotenv()

TOPIC_ARCHIVE = os.getenv("TOPIC_ARCHIVE")
TOPIC_NOTIFACATION = os.getenv("TOPIC_NOTIFACATION")



producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)




templates = Jinja2Templates(directory="todos/templates")

router=APIRouter(
  prefix='/todos',
  tags=['todo']
)


def get_db():
  db=SessionLocal()
  try:
    yield db
  finally:
    db.close()

db_dependency=Annotated[Session,Depends(get_db)]
user_dependency=Annotated[dict,Depends(get_current_user)]

class TodoRequest(BaseModel):
    title: str = Field(min_length=3)
    description: str = Field(min_length=3, max_length=500)
    priority: int = Field(gt=0, lt=6)
    complete: bool


def redirect_to_login():
    redirect_response = RedirectResponse(url="/auth/login-page", status_code=status.HTTP_302_FOUND)
    redirect_response.delete_cookie(key="access_token")
    return redirect_response


@router.get("/todo-page")
async def render_todo_page(request: Request, db: db_dependency):
    try:
        user = await get_current_user(request.cookies.get('access_token'))

        if user is None:
            return redirect_to_login()

        todos = db.query(Todos).filter(Todos.owner_id == user.get("id")).all()

        return templates.TemplateResponse("todo.html", {"request": request, "todos": todos, "user": user})

    except:
        return redirect_to_login()

@router.get('/add-todo-page')
async def render_todo_page(request: Request):
    try:
        user = await get_current_user(request.cookies.get('access_token'))

        if user is None:
            return redirect_to_login()

        return templates.TemplateResponse("add-todo.html", {"request": request, "user": user})

    except:
        return redirect_to_login()


@router.get("/edit-todo-page/{todo_id}")
async def render_edit_todo_page(request: Request, todo_id: int, db: db_dependency):
    try:
        user = await get_current_user(request.cookies.get('access_token'))

        if user is None:
            return redirect_to_login()

        todo = db.query(Todos).filter(Todos.id == todo_id).first()

        return templates.TemplateResponse("edit-todo.html", {"request": request, "todo": todo, "user": user})

    except:
        return redirect_to_login()


@router.get('/',status_code=status.HTTP_200_OK)
async def read_all(user:user_dependency,db: db_dependency):
  return db.query(Todos).filter(Todos.owner_id==user.get('id')).all()

@router.get('/todo/{todo_id}',status_code=status.HTTP_200_OK)
async def read_todo(user:user_dependency, db: db_dependency ,todo_id: int=Path(gt=0) ):
  if user is None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail='User is not authorized')
  todo_model=db.query(Todos).filter(Todos.id == todo_id).filter(Todos.owner_id==user.get('id')).first()
  if todo_model is not None:
    return todo_model
  raise HTTPException(status_code=404,detail="Todo not found.")



@router.post('/todo',status_code=status.HTTP_201_CREATED)
async def create_todo(user: user_dependency, db: db_dependency, todo_request: TodoRequest):

  if user is None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail='User is not authorized')
  print(todo_request)
  todo_model= Todos(**todo_request.model_dump(),owner_id=user.get('id'))
  users=db.query(Users).filter(Users.id==user.get('id')).first()
  print(user.get('id'))
  db.add(todo_model)
  db.commit()
  if users.email:
    json_message={
      "user_email":users.email,
      "title":todo_request.title,
      "description":todo_request.description,
      "priority":todo_request.priority,
    }
    producer.send(TOPIC_NOTIFACATION, json_message)
    producer.flush()
    print(json_message)
    return {"status": "Message sent", "topic": TOPIC_NOTIFACATION, "message": json_message}



@router.put('/todo/{todo_id}',status_code=status.HTTP_204_NO_CONTENT)
async def update_todo(user: user_dependency,db:db_dependency, todo_request: TodoRequest ,todo_id:int=Path(gt=0)):
  if user is None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail='User is not authorized')
  todo_model=db.query(Todos).filter(Todos.id == todo_id).filter(Todos.owner_id==user.get("id")).first()
  if todo_model is None:
    raise HTTPException(status_code=404,detail="Todo not found.")
  todo_model.title=todo_request.title
  todo_model.description=todo_request.description
  todo_model.priority=todo_request.priority
  todo_model.complete=todo_request.complete
  db.add(todo_model)
  db.commit()

@router.delete('/todo/{todo_id}',status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(user: user_dependency,db: db_dependency ,todo_id: int=Path(gt=0)):
  if user is None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail='User is not authorized')
  todo_model=db.query(Todos).filter(Todos.id == todo_id).filter(Todos.owner_id==user.get("id")).first()
  if todo_model is None:
    raise HTTPException(status_code=404,detail="Todo not found.")
  db.query(Todos).filter(Todos.id == todo_id).filter(Todos.owner_id==user.get("id")).delete()
  db.commit()

@router.post("/archive_todos/{todo_id}",status_code=status.HTTP_202_ACCEPTED)
async def archive_todo(todo_id: int, db: db_dependency):
    """
    Архівування завдання з БД та повідомленням в Kafka
    """
    todos=db.query(Todos).filter(Todos.id==todo_id).first()
    if todos is None:
        raise HTTPException(status_code=404, detail="Todo not found.")
    todos_json={
       "title":todos.title,
       "description":todos.description,
       "priority":todos.priority,
       "complete":todos.complete,
       "owner_id":todos.owner_id,
    }
    if todos.complete:
      producer.send(TOPIC_ARCHIVE, todos_json)
      producer.flush()
      print("Todo was archived")
      return {"status": "Message sent", "topic": TOPIC_ARCHIVE, "message": todos_json}
    else:
      raise HTTPException(status_code=400, detail="Todo is not completed.")

