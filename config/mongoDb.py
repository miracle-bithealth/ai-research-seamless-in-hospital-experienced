from motor.motor_asyncio import AsyncIOMotorClient as AsyncMongoClient
from pymongo.errors import ConnectionFailure
from config.setting import env
from pymongo.server_api import ServerApi

class MongoDb:
    def __init__(
        self, 
        database: str = env.MONGODB_DB_NAME,
        collection: str = env.MONGO_COLLECTION_NAME
    ):
        try:
            uri = f"mongodb+srv://{env.MONGODB_ATLAS_USERNAME}:{env.MONGODB_ATLAS_PASSWORD}@{env.MONGODB_ATLAS_HOST}/?retryWrites=true&w=majority&appName=${env.MONGODB_ATLAS_APP_NAME}"

            self.client = AsyncMongoClient(uri, server_api=ServerApi('1')) if env.MONGODB_TYPE == "ATLAS" else AsyncMongoClient(
                host=env.MONGODB_HOST, 
                port=env.MONGODB_PORT,
                username=env.MONGODB_USERNAME,
                password=env.MONGODB_PASSWORD,
            )
            
            self.db = self.client[database]
            self.collection = self.db[collection] if collection else self.collection if collection else None

        except ConnectionFailure as e:
            raise Exception(f"Could not connect to MongoDB: {e}")
            
    async def close_connection(self):
        if self.client:
            self.client.close()

    def _get_collection(self, name=None):
        """Helper to resolve collection name"""
        return self.db[name] if name else self.collection

    async def find_one(self, filter: dict, sort: list = None, collection: str = None):
        """Get a single document, optionally sorted"""
        coll = self._get_collection(collection)
        cursor = coll.find(filter)
        if sort:
            cursor = cursor.sort(sort)
        
        results = await cursor.to_list(length=1)
        return results[0] if results else None

    def get_cursor(self, filter: dict, sort: list = None, limit: int = None, collection: str = None):
        """
        Returns an Async Iterator (Cursor) instead of a list. 
        Critical for 'alist' to stream results efficiently without loading all into memory.
        """
        coll = self._get_collection(collection)
        cursor = coll.find(filter)
        if sort:
            cursor = cursor.sort(sort)
        if limit:
            cursor = cursor.limit(limit)
        return cursor

    async def bulk_write(self, operations: list, collection: str = None):
        """Execute bulk write operations"""
        if not operations: return
        coll = self._get_collection(collection)
        await coll.bulk_write(operations)

    async def update_upsert(self, filter: dict, data: dict, collection: str = None):
        """Specific helper for upserting checkpoints"""
        coll = self._get_collection(collection)
        await coll.update_one(filter, {"$set": data}, upsert=True)

    async def delete_many_data(self, filter: dict, collection: str = None):
        """Delete multiple documents"""
        coll = self._get_collection(collection)
        await coll.delete_many(filter)
        
db = MongoDb()