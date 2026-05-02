from typing import List

from app.contracts import DatasetMetadata
from app.metadata_registry import MetadataRegistry


def list_datasets_tool() -> List[DatasetMetadata]:
    return MetadataRegistry().list()
