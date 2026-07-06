from pydantic import BaseModel


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
