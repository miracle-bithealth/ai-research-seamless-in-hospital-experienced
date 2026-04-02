import redis.asyncio as redis
import valkey.asyncio as valkey
import json
import pickle
from typing import Literal

from typing import Any, Dict, List, Optional
from config.setting import env
from redis.asyncio.retry import Retry
from redis.backoff import ConstantBackoff
from redis.exceptions import ConnectionError, TimeoutError

class CacheManager:
    """
    Asynchronous Redis / Valkey Manager that handles connection pooling, serialization,
    and specific caching logic for LangGraph checkpoints.
    """

    def __init__(self, type: Literal['redis', 'valkey'] = 'redis'):
        """
        Initialize the Redis / Valkey connection with retry logic and connection pooling.
        
        Reads configuration from the `env` settings.
        """
        setting = {
            "host": env.CACHE_HOST,
            "port": env.CACHE_PORT,
            "db": env.CACHE_DB,
            "password": env.CACHE_PASSWORD,
            "username": env.CACHE_USERNAME,
            "decode_responses": True,
            "retry_on_error": [ConnectionError, TimeoutError],
            "retry": Retry(ConstantBackoff(backoff=1.0), 0)
        }
        match type:
            case 'redis':
                self.client = redis.Redis(**setting)
            case 'valkey':
                self.client = valkey.Valkey(**setting)
        
        self.checkpoint_ttl = env.CACHE_EXPIRES_SEC 
        self.prefix = getattr(env, 'REDIS_PREFIX_CHECKPOINT', 'checkpoint')

    def get_client(self) -> redis.Redis:
        """
        Get the underlying Redis client instance.

        Returns:
            redis.Redis: The raw Redis client.
        """
        return self.client
    
    async def ping(self) -> bool:
        """
        Check if the Redis connection is healthy.

        Returns:
            bool: True if connection is successful.

        Raises:
            Exception: If connection fails.
        """
        try:
            return await self.client.ping()
        except Exception as e:
            raise e 
    
    async def close(self):
        """
        Close the Redis connection pool.
        """
        await self.client.aclose()

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set a key-value pair with automatic serialization (JSON or Pickle).
        
        Args:
            key: Redis key.
            value: Value to store.
            ttl: Time to live in seconds.

        Returns:
            bool: True if successful.
        """
        serialized_value = self._serialize(value)
        return await self.client.set(key, serialized_value, ex=ttl)
    
    async def get(self, key: str, default: Any = None) -> Any:
        """
        Get value by key with automatic deserialization.
        
        Args:
            key: Redis key.
            default: Default value if key doesn't exist.

        Returns:
            Any: Deserialized value or default.
        """
        value = await self.client.get(key)
        if value is None:
            return default
        return self._deserialize(value)
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple keys at once.

        Args:
            keys: List of Redis keys.

        Returns:
            Dict[str, Any]: Dictionary mapping keys to deserialized values.
        """
        values = await self.client.mget(keys)
        result = {}
        for key, value in zip(keys, values):
            result[key] = self._deserialize(value) if value else None
        return result
    
    async def set_many(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        Set multiple key-value pairs at once using a pipeline.

        Args:
            mapping: Dictionary of key-value pairs.
            ttl: Time to live in seconds (applied to all keys).

        Returns:
            bool: True if all operations succeeded.
        """
        serialized_mapping = {k: self._serialize(v) for k, v in mapping.items()}
        
        pipe = self.client.pipeline()
        pipe.mset(serialized_mapping)
        
        if ttl:
            for key in mapping.keys():
                pipe.expire(key, ttl)
        
        results = await pipe.execute()
        return all(results)

    def _serialize(self, value: Any) -> str:
        """
        Internal method to serialize value for Redis storage.
        
        Uses JSON for basic types and Pickle for complex objects.
        """
        if isinstance(value, (str, int, float, bool)):
            return json.dumps(value)
        elif isinstance(value, (dict, list, tuple, set)):
            return json.dumps(value, default=str)
        else:
            return f"pickle:{pickle.dumps(value).hex()}"
    
    def _deserialize(self, value: str) -> Any:
        """
        Internal method to deserialize value from Redis.
        """
        if value.startswith("pickle:"):
            hex_data = value[7:] 
            return pickle.loads(bytes.fromhex(hex_data))
        else:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value

    async def get_set(self, prefix: str, key: str, cb, ttl: int = 300, is_cache: bool = True):
        """
        Tries to get a value from the Redis cache; if not found, it calls the 
        callback function 'cb' to compute the value, caches it, and returns it.

        Args:
            prefix: Key prefix.
            key: Unique key identifier.
            cb: Async callback function to retrieve data if cache miss.
            ttl: Time to live in seconds.
            is_cache: If False, bypasses cache read/write (passthrough).

        Returns:
            Any: The cached or computed value.
        """
        full_key = f"{prefix}:{key}"
        cached_value = await self.get(full_key)
        if cached_value is not None and is_cache:
            return cached_value
        value = await cb()
        await self.set(full_key, value, ttl)
        return value

    # ==========================================
    # LANGGRAPH CHECKPOINT METHODS
    # ==========================================

    def _make_checkpoint_key(self, thread_id: str, checkpoint_ns: str, checkpoint_id: str | None = None) -> str:
        """
        Generate a formatted Redis key for a checkpoint.
        Format: {prefix}:{thread}:{ns}:{id} OR {prefix}:{thread}:{ns}:latest
        """
        base = f"{self.prefix}:{thread_id}:{checkpoint_ns or 'default'}"
        return f"{base}:{checkpoint_id}" if checkpoint_id else f"{base}:latest"

    def _make_writes_key(self, thread_id: str, checkpoint_ns: str, checkpoint_id: str) -> str:
        """
        Generate a formatted Redis key for checkpoint writes.
        Format: {prefix}:writes:{thread}:{ns}:{id}
        """
        return f"{self.prefix}:writes:{thread_id}:{checkpoint_ns or 'default'}:{checkpoint_id}"

    async def get_checkpoint(self, thread_id: str, checkpoint_ns: str, checkpoint_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific checkpoint or the latest one if no ID is provided.

        Args:
            thread_id: The conversation thread ID.
            checkpoint_ns: The namespace.
            checkpoint_id: (Optional) Specific ID. If None, fetches 'latest'.

        Returns:
            Optional[Dict[str, Any]]: The checkpoint data or None if missing.
        """
        key = self._make_checkpoint_key(thread_id, checkpoint_ns, checkpoint_id)
        return await self.get(key)

    async def get_checkpoint_writes(self, thread_id: str, checkpoint_ns: str, checkpoint_id: str) -> Optional[List[Any]]:
        """
        Retrieve pending writes associated with a specific checkpoint.

        Args:
            thread_id: The conversation thread ID.
            checkpoint_ns: The namespace.
            checkpoint_id: The specific checkpoint ID.

        Returns:
            Optional[List[Any]]: List of write operations or None.
        """
        key = self._make_writes_key(thread_id, checkpoint_ns, checkpoint_id)
        return await self.get(key)

    async def set_checkpoint(
        self, 
        thread_id: str, 
        checkpoint_ns: str, 
        checkpoint_id: str, 
        checkpoint_data: Dict[str, Any], 
        writes_data: List[Any] = None
    ) -> bool:
        """
        Atomically save a checkpoint and its associated writes to Redis using a pipeline.
        
        This updates both the specific checkpoint key and the 'latest' pointer.

        Args:
            thread_id: The conversation thread ID.
            checkpoint_ns: The namespace.
            checkpoint_id: The checkpoint ID.
            checkpoint_data: The main checkpoint dictionary.
            writes_data: (Optional) List of associated pending writes.

        Returns:
            bool: True if all operations succeeded.
        """
        try:
            pipe = self.client.pipeline()
            
            if checkpoint_data:
                key = self._make_checkpoint_key(thread_id, checkpoint_ns, checkpoint_id)
                latest_key = self._make_checkpoint_key(thread_id, checkpoint_ns, None)
                serialized = self._serialize(checkpoint_data)
                
                pipe.set(key, serialized, ex=self.checkpoint_ttl)
                pipe.set(latest_key, serialized, ex=self.checkpoint_ttl)

            if writes_data:
                writes_key = self._make_writes_key(thread_id, checkpoint_ns, checkpoint_id)
                pipe.set(writes_key, self._serialize(writes_data), ex=self.checkpoint_ttl)

            results = await pipe.execute()
            return all(results)
        except Exception as e:
            raise e

    async def list_checkpoints(self, thread_id: str, checkpoint_ns: str, limit: int = None) -> Optional[List[Dict[str, Any]]]:
        """
        List all checkpoints for a specific thread, ordered by ID descending.

        Args:
            thread_id: The conversation thread ID.
            checkpoint_ns: The namespace.
            limit: (Optional) Maximum number of checkpoints to return.

        Returns:
            Optional[List[Dict[str, Any]]]: List of checkpoint dictionaries.
        """
        pattern = f"{self.prefix}:{thread_id}:{checkpoint_ns or 'default'}:*"
        
        try:
            keys = []
            cursor = 0
            while True:
                # Use SCAN for performance on large datasets
                cursor, batch = await self.client.scan(cursor, match=pattern, count=100)
                for k in batch:
                    # Filter out 'latest' pointer and 'writes' keys to get only actual checkpoint IDs
                    if not k.endswith(':latest') and ':writes:' not in k:
                        keys.append(k)
                if cursor == 0:
                    break
            
            if not keys:
                return None

            values_map = await self.get_many(keys)
            valid_checkpoints = [v for v in values_map.values() if v]

            # Sort by checkpoint_id in descending order (newest first)
            valid_checkpoints.sort(key=lambda x: x.get("checkpoint_id", ""), reverse=True)

            return valid_checkpoints[:limit] if limit else valid_checkpoints
        except Exception as e:
            raise e

    async def populate_from_mongodb(self, thread_id: str, checkpoint_ns: str, checkpoint_id: str, doc: dict, writes_data: List[Any] = None) -> bool:
        """
        Populate the Redis cache from MongoDB data (Cache Warming).

        Args:
            thread_id: The conversation thread ID.
            checkpoint_ns: The namespace.
            checkpoint_id: The checkpoint ID.
            doc: The checkpoint document from MongoDB.
            writes_data: Associated writes from MongoDB.

        Returns:
            bool: True if successful.
        """
        return await self.set_checkpoint(thread_id, checkpoint_ns, checkpoint_id, doc, writes_data)

    async def invalidate_checkpoint(self, thread_id: str, checkpoint_ns: str = "", checkpoint_id: str = None, clear_all: bool = False) -> bool:
        """
        Remove checkpoint data from Redis.

        Args:
            thread_id: The conversation thread ID.
            checkpoint_ns: The namespace.
            checkpoint_id: (Optional) Specific ID to remove.
            clear_all: (Optional) If True, deletes ALL data for the thread.

        Returns:
            bool: True if deletion command was sent.
        """
        try:
            keys_to_delete = []
            
            if clear_all:
                # Find all keys for this thread (checkpoints + writes)
                pattern = f"{self.prefix}:{thread_id}:*"
                writes_pattern = f"{self.prefix}:writes:{thread_id}:*"
                
                for pat in [pattern, writes_pattern]:
                    cursor = 0
                    while True:
                        cursor, batch = await self.client.scan(cursor, match=pat, count=100)
                        keys_to_delete.extend(batch)
                        if cursor == 0: break
            
            elif checkpoint_id:
                keys_to_delete = [
                    self._make_checkpoint_key(thread_id, checkpoint_ns, checkpoint_id),
                    self._make_writes_key(thread_id, checkpoint_ns, checkpoint_id)
                ]

            if keys_to_delete:
                await self.client.delete(*keys_to_delete)
            return True
        except Exception as e:
            raise e 

cache = CacheManager()