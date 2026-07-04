from dataclasses import dataclass

from fastapi import FastAPI
from config.settings import Settings

@dataclass
class Dependencies:
    settings: Settings


async def build_dependencies(app: FastAPI) -> Dependencies:
    settings = Settings()

    return Dependencies(
        settings =settings,
    )
app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}
