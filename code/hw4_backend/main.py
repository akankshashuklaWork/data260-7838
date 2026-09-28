from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from . import crud, models
from .database import Base, engine, get_db
from .schemas import ListingCreate, ListingOut, ListingUpdate, LoginRequest, UserCreate
from .security import verify_password
from .session_crud import create_session, delete_session, get_session

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Rental Housing Listings HW4 API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def require_session(request: Request, db: Session = Depends(get_db)):
    session = get_session(db, request.cookies.get("session_id"))
    if not session: raise HTTPException(status_code=401, detail="Login required")
    return session

@app.get("/health")
def health(): return {"status": "ok"}

@app.post("/auth/register")
def register(payload: UserCreate, db: Session = Depends(get_db)):
    try:
        user = crud.create_user(db, payload.name, payload.email, payload.password)
        return {"id": user.id, "email": user.email}
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail="Email already exists")

@app.post("/auth/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash): raise HTTPException(status_code=401, detail="Invalid email or password")
    session = create_session(db, user.id)
    response.set_cookie("session_id", session.id, httponly=True, samesite="lax", max_age=1800)
    return {"logged_in": True, "user_id": user.id, "email": user.email}

@app.post("/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    delete_session(db, request.cookies.get("session_id")); response.delete_cookie("session_id"); return {"logged_in": False}

@app.get("/auth/me")
def me(session=Depends(require_session), db: Session = Depends(get_db)):
    user = db.get(models.User, session.user_id); return {"logged_in": True, "user_id": user.id, "email": user.email}

@app.post("/listings", response_model=ListingOut)
def add_listing(payload: ListingCreate, db: Session = Depends(get_db), _=Depends(require_session)): return crud.create_listing(db, payload)

@app.get("/listings", response_model=list[ListingOut])
def list_listings(db: Session = Depends(get_db), _=Depends(require_session)): return crud.list_fixed(db, 0, 200)

@app.get("/listings/{listing_id}", response_model=ListingOut)
def read_listing(listing_id: int, db: Session = Depends(get_db), _=Depends(require_session)):
    row = crud.get_listing(db, listing_id)
    if not row: raise HTTPException(status_code=404, detail="Listing not found")
    return row

@app.put("/listings/{listing_id}", response_model=ListingOut)
def edit_listing(listing_id: int, payload: ListingUpdate, db: Session = Depends(get_db), _=Depends(require_session)):
    row = crud.update_listing(db, listing_id, payload)
    if not row: raise HTTPException(status_code=404, detail="Listing not found")
    return row

@app.delete("/listings/{listing_id}", response_model=ListingOut)
def remove_listing(listing_id: int, db: Session = Depends(get_db), _=Depends(require_session)):
    row = crud.delete_listing(db, listing_id)
    if not row: raise HTTPException(status_code=404, detail="Listing not found")
    return row

@app.get("/measure/listings/{version}", response_model=list[ListingOut])
def measured_listings(version: str, response: Response, page_size: int = 10, offset: int = 0, db: Session = Depends(get_db), _=Depends(require_session)):
    if version not in {"naive", "fixed"} or page_size not in {10, 50, 200}: raise HTTPException(status_code=400, detail="invalid version or page_size")
    connection = db.connection()
    connection.info["hw4_sql_count"] = 0
    rows = crud.list_naive(db, offset, page_size) if version == "naive" else crud.list_fixed(db, offset, page_size)
    response.headers["X-SQL-Count"] = str(connection.info.get("hw4_sql_count", 0))
    return rows
