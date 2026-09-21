# Route layer: thin. Parse request -> call service -> return. No business logic here.

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.models import Item, ItemCreate, ItemUpdate
from app.service import ItemService
from app.deps import get_service

app = FastAPI(title="Interview App")

# Wide-open CORS for a same-session demo (frontend on a different port).
# Say out loud this would be scoped to the real frontend origin in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/items", response_model=list[Item])
def list_items(svc: ItemService = Depends(get_service)):
    return svc.list_items()


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: str, svc: ItemService = Depends(get_service)):
    return svc.get_item(item_id)


@app.post("/items", response_model=Item, status_code=201)
def create_item(data: ItemCreate, svc: ItemService = Depends(get_service)):
    return svc.create_item(data)


@app.patch("/items/{item_id}", response_model=Item)
def update_item(item_id: str, data: ItemUpdate, svc: ItemService = Depends(get_service)):
    return svc.update_item(item_id, data)


@app.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: str, svc: ItemService = Depends(get_service)):
    svc.delete_item(item_id)
