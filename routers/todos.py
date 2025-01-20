from typing import Annotated
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException,Path,APIRouter, Request
from models import Todos
from database import engine, SessionLocal
from starlette import status
from pydantic import BaseModel, Field
from .auth import get_current_user
from starlette.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="./templates")

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
    description: str = Field(min_length=3, max_length=100)
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
  todo_model= Todos(**todo_request.model_dump(),owner_id=user.get('id'))

  db.add(todo_model)
  db.commit()


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



from kafka import KafkaProducer
import json

producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

@router.post('/send_todo_to_archive/{todo_id}')
def send_todo_to_archive(todo_id: int, db: Session = Depends(get_db)):
    # Знайти завдання за id
    todo = db.query(Todos).filter(Todos.id == todo_id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    
    # Сформувати повідомлення
    todo_data = {
        "id": todo.id,
        "title": todo.title,
        "description": todo.description,
        "priority": todo.priority,
        "complete": todo.complete
    }
    
    # Відправити повідомлення в Kafka
    producer.send('todo_topic', todo_data)
    producer.flush()  # Переконатися, що повідомлення відправлено
    
    return {"message": f"Todo with id {todo_id} sent to archive"}