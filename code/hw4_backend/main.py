from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import crud, models
from .database import Base, engine, get_db
from .schemas import (
    ListingCreate,
    ListingOut,
    ListingUpdate,
    LoginRequest,
    OwnerCreate,
    OwnerOut,
    OwnerUpdate,
    UserCreate,
    UserOut,
)
from .security import TokenError, create_access_token, decode_access_token, verify_password

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Rental Housing Listings HW4 API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
bearer_scheme = HTTPBearer(auto_error=False)


def require_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, object]:
    """Require a valid signed JWT; the HW7 routes do not read cookie sessions."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer token required")
    try:
        return decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def require_roles(*roles: str):
    def dependency(identity: dict[str, object] = Depends(require_identity)) -> dict[str, object]:
        if identity["role"] not in roles:
            raise HTTPException(status_code=403, detail=f"Requires one of: {', '.join(roles)}")
        return identity

    return dependency


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/register")
def register(payload: UserCreate, db: Session = Depends(get_db)):
    try:
        user = crud.create_user(db, payload.username, payload.password)
        return UserOut(id=user.id, username=user.username, role=user.role)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists")


@app.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.username == payload.username))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(user.id, user.username, user.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": UserOut(id=user.id, username=user.username, role=user.role),
    }


@app.post("/auth/logout")
def logout(_: dict[str, object] = Depends(require_identity)):
    """JWTs are stateless; clients remove their local bearer token on logout."""
    return {"logged_out": True}


@app.get("/auth/me", response_model=UserOut)
def me(identity: dict[str, object] = Depends(require_identity)):
    return UserOut(
        id=int(str(identity["sub"])), username=str(identity["username"]), role=str(identity["role"])
    )


@app.post("/listings", response_model=ListingOut, status_code=status.HTTP_201_CREATED)
def add_listing(
    payload: ListingCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("writer", "moderator")),
):
    try:
        return crud.create_listing(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Listing code must be unique")


@app.get("/listings", response_model=list[ListingOut])
def list_listings(
    db: Session = Depends(get_db),
    _=Depends(require_identity),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return crud.list_listings(db, skip, limit)


@app.post("/owners", response_model=OwnerOut, status_code=status.HTTP_201_CREATED)
def add_owner(
    payload: OwnerCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("writer", "moderator")),
):
    try:
        return crud.create_owner(db, payload)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Owner email must be unique")


@app.get("/owners", response_model=list[OwnerOut])
def get_owners(
    db: Session = Depends(get_db),
    _=Depends(require_identity),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return crud.list_owners(db, skip, limit)


@app.get("/owners/{owner_id}", response_model=OwnerOut)
def get_owner(owner_id: int, db: Session = Depends(get_db), _=Depends(require_identity)):
    row = crud.get_owner(db, owner_id)
    if not row:
        raise HTTPException(status_code=404, detail="Owner not found")
    return row


@app.put("/owners/{owner_id}", response_model=OwnerOut)
def edit_owner(
    owner_id: int,
    payload: OwnerUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("writer", "moderator")),
):
    try:
        row = crud.update_owner(db, owner_id, payload)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Owner email must be unique")
    if not row:
        raise HTTPException(status_code=404, detail="Owner not found")
    return row


@app.delete("/owners/{owner_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_owner(
    owner_id: int, db: Session = Depends(get_db), _=Depends(require_roles("moderator"))
):
    try:
        row = crud.delete_owner(db, owner_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not row:
        raise HTTPException(status_code=404, detail="Owner not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/owners/{owner_id}/listings", response_model=list[ListingOut])
def get_owner_listings(owner_id: int, db: Session = Depends(get_db), _=Depends(require_identity)):
    try:
        return crud.listings_by_owner(db, owner_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/listings/{listing_id}", response_model=ListingOut)
def read_listing(listing_id: int, db: Session = Depends(get_db), _=Depends(require_identity)):
    row = crud.get_listing(db, listing_id)
    if not row:
        raise HTTPException(status_code=404, detail="Listing not found")
    return row


@app.put("/listings/{listing_id}", response_model=ListingOut)
def edit_listing(
    listing_id: int,
    payload: ListingUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("writer", "moderator")),
):
    try:
        row = crud.update_listing(db, listing_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Listing code must be unique")
    if not row:
        raise HTTPException(status_code=404, detail="Listing not found")
    return row


@app.delete("/listings/{listing_id}", response_model=ListingOut)
def remove_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("moderator")),
):
    row = crud.delete_listing(db, listing_id)
    if not row:
        raise HTTPException(status_code=404, detail="Listing not found")
    return row


@app.get("/measure/listings/{version}", response_model=list[ListingOut])
def measured_listings(
    version: str,
    response: Response,
    page_size: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db),
    _=Depends(require_identity),
):
    if version not in {"naive", "fixed"} or page_size not in {10, 50, 200}:
        raise HTTPException(status_code=400, detail="invalid version or page_size")
    connection = db.connection()
    connection.info["hw4_sql_count"] = 0
    if version == "naive":
        rows = crud.list_naive(db, offset, page_size)
    else:
        rows = crud.list_fixed(db, offset, page_size)
    response.headers["X-SQL-Count"] = str(connection.info.get("hw4_sql_count", 0))
    return rows
