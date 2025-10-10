import os
from pymongo import MongoClient
import threading

_client = None
_db = None

def init(connection_string, db_name):
    global _client, _db

    if _client is not None:
        raise RuntimeError("MongoDB client is already initialized.")
    
    _client = MongoClient(connection_string)
    _db = _client[db_name]
    
    try:
        client = MongoClient(connection_string, 
                           serverSelectionTimeoutMS=5000,  # 5 second timeout
                           connectTimeoutMS=5000)
        
        # Test connection
        client.admin.command('ping')
        print("MongoDB connection successful")
        
        db = client['winton_bot']
    except Exception as e:    
        raise RuntimeError("Failed to connect to MongoDB", str(e))


def get_client():
    if _client is None:
        raise RuntimeError("MongoDB client is not initialized.")
    return _client

def get_db():
    if _db is None:
        raise RuntimeError("MongoDB database is not initialized.")
    return _db

def get_collection(name):
    return get_db()[name]

def close():
    global _client, _db

    if _client is not None:
        _client.close()
        _client = None
        _db = None

def is_intialized():
    return _client is not None 