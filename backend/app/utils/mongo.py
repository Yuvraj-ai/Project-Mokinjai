from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import get_settings

class MongoManager:
    client: AsyncIOMotorClient | None = None

    @classmethod
    def get_client(cls) -> AsyncIOMotorClient:
        if cls.client is None:
            settings = get_settings()
            url = settings.MONGO_URL or "mongodb://localhost:27017"
            cls.client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=5000)
        return cls.client

    @classmethod
    def get_db(cls) -> AsyncIOMotorDatabase:
        return cls.get_client()[get_settings().MONGO_DB_NAME]

    @classmethod
    def close(cls) -> None:
        if cls.client is not None:
            cls.client.close()
            cls.client = None

    @classmethod
    async def ping(cls) -> None:
        await cls.get_client().admin.command("ping")

def get_mongo_db() -> AsyncIOMotorDatabase:
    return MongoManager.get_db()
