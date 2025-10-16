import os 
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL) #create a database engine


metadata=MetaData() #create a metadata object to hold the database schema information

Sessionlocal=sessionmaker(autocommit=False,autoflush=False,bind=engine) #create a session maker to handle database sessions

Base=declarative_base() #create a base class for our models


