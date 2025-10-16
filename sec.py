from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware  # Import CORS Middleware
from pydantic import BaseModel, HttpUrl
import os
import pymysql
import secrets
from model import urlmodel as URLMODEL
from database import Sessionlocal, engine, Base
import string

from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# --- CORS Configuration ---
# This allows your frontend to communicate with your backend.
origins = [
    "*",  # In production, you should restrict this to your frontend's domain
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --- End CORS Configuration ---


class URLResponse(BaseModel):
    url: str
    short_code: str
    short_url: str


class URLItem(BaseModel):
    url: HttpUrl


def getdb():
    db = Sessionlocal()
    try:
        yield db
    finally:
        db.close()

DATABASE_URL = os.getenv("DATABASE_URL")

# This check prevents trying to create tables if the database connection fails
try:
    URLMODEL.metadata.create_all(bind=engine)  # create the tables in the database
except Exception as e:
    print(f"Error connecting to database or creating tables: {e}")

BASE62_ALPHABET = string.ascii_letters + string.digits
SHORT_CODE_SIZE = 7  # 7 characters allows for 62^7 ≈ 3.5 trillion unique codes
MAX_COLLISION_RETRIES = 5  # Maximum attempts to generate a unique short code

def generate_random_short_code(size: int = SHORT_CODE_SIZE) -> str:
    """Generates a cryptographically secure random short code using the Base62 alphabet."""
    code_chars = []
    for _ in range(size):
        char = secrets.choice(BASE62_ALPHABET)
        code_chars.append(char)
    return "".join(code_chars)


def create_url_mapping(long_url_user: str, db: Sessionlocal):
    """
    Inserts a new URL mapping into the database, handling potential short code collisions.
    
    Returns the successfully created short code.
    """
    for attempt in range(MAX_COLLISION_RETRIES):
        short_code = generate_random_short_code()
        new_url = URLMODEL(long_url=str(long_url_user), short_code=short_code)
        try:
            db.add(new_url)
            db.commit()
            db.refresh(new_url)
            return short_code
        except Exception as e:
            # Collision occurred, rollback and retry
            print(f"Database error on attempt {attempt + 1}: {e}")
            db.rollback()
            if attempt == MAX_COLLISION_RETRIES - 1:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to generate unique short code after multiple attempts"
                )
            continue
    
    raise HTTPException(
        status_code=500,
        detail="Failed to create URL mapping"
    )


@app.get("/")
async def read_root():
    return "WELCOME TO URL SHORTENER APP :)"

@app.post("/shorten/", response_model=URLResponse) # Corrected response_model
async def shorten_url(item: URLItem, db: Sessionlocal = Depends(getdb)): # Corrected variable name
    long_url_user = str(item.url).strip()
    if not long_url_user.startswith(('http://', 'https://')):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")
    
    existing_url = db.query(URLMODEL).filter(URLMODEL.long_url == long_url_user).first()
    
    if existing_url:
        # URL exists! Return the existing short code
        base_url = os.getenv("BASE_URL", "http://localhost:8000")
        short_url = f"{base_url}/{existing_url.short_code}"
        
        return URLResponse(
            url=existing_url.long_url,  # This is from database
            short_code=existing_url.short_code,
            short_url=short_url
        )
    
    short_code = create_url_mapping(long_url_user, db)
    
    # Step 4: Build the complete short URL and return it
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    short_url = f"{base_url}/{short_code}"
    
    return URLResponse(
        url=long_url_user,
        short_code=short_code,
        short_url=short_url
    )

@app.get("/{short_code}")
async def redirect_url(short_code: str, db: Sessionlocal = Depends(getdb)):
    """
    Redirect to the original long URL based on short code
    """
    # Query the database for the short code
    url_mapping = db.query(URLMODEL).filter(
        URLMODEL.short_code == short_code
    ).first()
    
    if not url_mapping:
        raise HTTPException(
            status_code=404,
            detail=f"Short URL '{short_code}' not found"
        )
    
    # Increment click count (if you have this field)
    if hasattr(url_mapping, 'click_count'):
        url_mapping.click_count += 1
        db.commit()
    
    # Redirect to the long URL
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=url_mapping.long_url, status_code=301)

@app.get("/api/stats/{short_code}")
async def get_stats(short_code: str, db: Sessionlocal = Depends(getdb)):
    """
    Get statistics for a shortened URL
    """
    url_mapping = db.query(URLMODEL).filter(
        URLMODEL.short_code == short_code
    ).first()
    
    if not url_mapping:
        raise HTTPException(
            status_code=404,
            detail=f"Short URL '{short_code}' not found"
        )
    
    return {
        "short_code": url_mapping.short_code,
        "long_url": url_mapping.long_url,
        "created_at": url_mapping.created_at if hasattr(url_mapping, 'created_at') else None,
        "click_count": url_mapping.click_count if hasattr(url_mapping, 'click_count') else 0
    }

@app.delete("/api/delete/{short_code}")
async def delete_url(short_code: str, db: Sessionlocal = Depends(getdb)):
    """
    Delete a shortened URL
    """
    url_mapping = db.query(URLMODEL).filter(
        URLMODEL.short_code == short_code
    ).first()
    
    if not url_mapping:
        raise HTTPException(
            status_code=404,
            detail=f"Short URL '{short_code}' not found"
        )
    
    db.delete(url_mapping)
    db.commit()
    
    return {"message": f"Short URL '{short_code}' deleted successfully"}
