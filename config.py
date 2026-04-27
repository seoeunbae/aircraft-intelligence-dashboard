import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    project_id: str
    dataset_id: str
    table_id: str
    location: str
    db_type: str

    @property
    def full_table_ref(self) -> str:
        return f"`{self.project_id}.{self.dataset_id}.{self.table_id}`"


settings = Settings(
    project_id=os.getenv("GOOGLE_CLOUD_PROJECT", "cloud-cycle-pj"),
    dataset_id=os.getenv("BIGQUERY_DATASET", "mdas-dataset"),
    table_id=os.getenv("BIGQUERY_TABLE", "aircraft_dummy"),
    location=os.getenv(
        "BIGQUERY_REGION", os.getenv("GOOGLE_CLOUD_LOCATION", "asia-southeast1")
    ),
    db_type=os.getenv("DB_TYPE", "bigquery"),
)
