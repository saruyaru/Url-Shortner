from sqlalchemy import Column, Integer , String , Boolean ,DateTime, func , Text
from database import Base
from datetime import datetime
from datetime import timezone
from datetime import UTC

class urlmodel(Base):
    __tablename__ = "short_urls"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    long_url = Column(Text, nullable=False)  
    short_code = Column(String(10), unique=True, nullable=False, index=True)
    created_at = Column(DateTime,default=lambda: datetime.now(timezone.utc), server_default=func.now())
    # With lambda - calls function each time (CORRECT)
    #gets the current UTC time when a new record is created
    click_count = Column(Integer, default=0)
    
    def __repr__(self):
        return f"<URLMapping(short_code='{self.short_code}', long_url='{self.long_url}')>"