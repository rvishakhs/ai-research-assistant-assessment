from pathlib import Path
from pydantic import BaseModel
import json

class Dataset(BaseModel):
    id : str
    name : str
    description : str
    records : int
    restricted : bool
    fields: list[str]

class Project(BaseModel):
    id : str
    title : str
    status : str
    principal_investigator : str
    organisation : str
    datasets : list[str]

class Researcher(BaseModel):
    username : str
    display_name :  str
    role: str
    projects: list[str]


MOCK_DATA_DIR = Path(__file__).parent.parent.parent / "mock-data"

class DataStore:
    _instance: "DataStore | None" = None

    def __new__(cls) -> "DataStore":
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._load()
            cls._instance = instance
        return cls._instance

    def _load(self) -> None:
        self.datasets: dict[str, Dataset] = {
            entry["id"]: Dataset(**entry)
            for entry in json.loads((MOCK_DATA_DIR / "datasets.json").read_text())
        }
        self.projects: dict[str, Project] = {
            entry["id"]: Project(**entry)
            for entry in json.loads((MOCK_DATA_DIR / "projects.json").read_text())
        }
        self.researchers: dict[str, Researcher] = {
            entry["username"]: Researcher(**entry)
            for entry in json.loads((MOCK_DATA_DIR / "researchers.json").read_text())
        }
        self.query_results: dict[str, dict] = json.loads(
            (MOCK_DATA_DIR / "sample_query_results.json").read_text()
        )

datastore = DataStore()