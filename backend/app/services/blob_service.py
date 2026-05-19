from typing import Any, Optional
from bson import ObjectId
from bson.errors import InvalidId
from app.utils.mongo import get_mongo_db

class BlobService:
    """Service for managing large JSON blobs in MongoDB."""

    collection_name: str = "blobs"

    @classmethod
    async def save_blob(cls, data: Any) -> str:
        """Saves a JSON blob to MongoDB and returns the ObjectId as a string."""
        db = get_mongo_db()  # Not async, motor client handles it
        result = await db[cls.collection_name].insert_one({"data": data})
        return str(result.inserted_id)

    @classmethod
    async def get_blob(cls, blob_id: str) -> Optional[Any]:
        """Retrieves a JSON blob from MongoDB by its ID."""
        if not blob_id:
            return None
        try:
            oid = ObjectId(blob_id)
        except InvalidId:
            return None
        db = get_mongo_db()
        doc = await db[cls.collection_name].find_one({"_id": oid})
        return doc["data"] if doc else None

    @classmethod
    async def update_blob(cls, blob_id: str, data: Any) -> bool:
        """Updates an existing JSON blob in MongoDB."""
        if not blob_id:
            return False
        try:
            oid = ObjectId(blob_id)
        except InvalidId:
            return False
        db = get_mongo_db()
        result = await db[cls.collection_name].replace_one(
            {"_id": oid},
            {"data": data}
        )
        return result.modified_count > 0

    @classmethod
    async def delete_blob(cls, blob_id: str) -> bool:
        """Deletes a JSON blob from MongoDB."""
        if not blob_id:
            return False
        try:
            oid = ObjectId(blob_id)
        except InvalidId:
            return False
        db = get_mongo_db()
        result = await db[cls.collection_name].delete_one({"_id": oid})
        return result.deleted_count > 0
