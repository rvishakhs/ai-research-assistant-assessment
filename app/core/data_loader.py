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
    tittle : str
    status : str
    principal_investigator : str
    organisation : str
    datasets : list[str]

class Researcher(BaseModel):
    username : str
    display_name :  str
    role: str
    projects: list[str]


MOCK_DATA_DIR = Path(__file__).parent.parent.parent / "mock_data"

class DataStore:
    def __init__(self):
        self.datasets = self._load_json("datasets.json", Dataset, "id")
        self.projects = self._load_json("projects.json", Project, "id")
        self.researchers = self._load_json("researchers.json", Researcher, "username")

    def _read_json(self, filename: str):
        with (MOCK_DATA_DIR /filename).open("r", encoding="utf-8") as f:
            return json.load(f)

    def _load_json(self, filename: str, model, key: str):
        data = self._read_json(filename)
        return{
            item[key] : model(**item) for item in data
        }

datastore = DataStore()