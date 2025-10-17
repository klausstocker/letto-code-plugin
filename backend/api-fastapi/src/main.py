import os
import sys
from fastapi import FastAPI, Response
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

api = FastAPI()

@api.get("/")
async def test():
    return {"message": f"API running {datetime.now()}"}

