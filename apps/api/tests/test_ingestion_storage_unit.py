from app.ingestion.service import IngestionService
from app.ingestion.storage import ObjectStorage, get_object_storage


def test_ingestion_service_has_object_storage() -> None:
  storage = get_object_storage()
  assert storage.put_bytes("test/ping.txt", b"ok", content_type="text/plain") == "test/ping.txt"
  assert storage.get_bytes("test/ping.txt") == b"ok"
  assert ObjectStorage.sha256(b"ok") == storage.sha256(b"ok")
