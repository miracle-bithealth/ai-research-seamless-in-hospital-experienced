import base64
import ast
import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional, Sequence, Tuple

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP, BaseCheckpointSaver, ChannelVersions, Checkpoint, 
    CheckpointMetadata, CheckpointTuple, get_checkpoint_id
)
from pymongo import UpdateOne
from config.mongoDb import MongoDb

class AsyncMongoDBSaver(BaseCheckpointSaver):
    mongo: MongoDb

    def __init__(
        self,
        mongo_db_instance: MongoDb,
        cache_manager=None,
        checkpoint_collection_name: str = "checkpoints",
        writes_collection_name: str = "checkpoint_writes",
    ) -> None:
        super().__init__()
        self.mongo = mongo_db_instance
        self.cache = cache_manager
        self.cp_col = checkpoint_collection_name
        self.wr_col = writes_collection_name

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        cp_ns = config["configurable"].get("checkpoint_ns", "")
        cp_id = get_checkpoint_id(config)

        # 1. Cache Lookup
        if self.cache:
            try:
                cached = await self.cache.get_checkpoint(thread_id, cp_ns, cp_id)
                if cached: return await self._parse_cached_data(cached, thread_id, cp_ns)
            except Exception as e:
                raise Exception(f"Cache read failed: {e}")

        # 2. Mongo Lookup (Refactored to use MongoDb class)
        query = {"thread_id": thread_id, "checkpoint_ns": cp_ns}
        if cp_id: query["checkpoint_id"] = cp_id
        
        # Use new find_one method
        doc = await self.mongo.find_one(query, sort=[("checkpoint_id", -1)], collection=self.cp_col)

        if not doc: return None

        return await self._process_mongo_doc(doc, thread_id, cp_ns)

    async def aput(
        self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: ChannelVersions
    ) -> RunnableConfig:
        thread_id = config["configurable"]["thread_id"]
        cp_ns = config["configurable"]["checkpoint_ns"]
        cp_id = checkpoint["id"]
        
        type_, serialized_cp = self.serde.dumps_typed(checkpoint)
        
        doc = {
            "parent_checkpoint_id": config["configurable"].get("checkpoint_id"),
            "type": type_,
            "checkpoint": serialized_cp,
            "metadata": self._dumps_metadata(metadata),
            "checkpoint_id": cp_id,
            "thread_id": thread_id,
            "checkpoint_ns": cp_ns,
        }

        # 1. Write to Mongo (Refactored)
        await self.mongo.update_upsert(
            filter={"thread_id": thread_id, "checkpoint_ns": cp_ns, "checkpoint_id": cp_id},
            data=doc,
            collection=self.cp_col
        )
        
        # 2. Write to Redis
        if self.cache:
            await self.cache.set_checkpoint(thread_id, cp_ns, cp_id, doc)

        return {"configurable": {"thread_id": thread_id, "checkpoint_ns": cp_ns, "checkpoint_id": cp_id}}

    async def aput_writes(
        self, config: RunnableConfig, writes: Sequence[Tuple[str, Any]], task_id: str, task_path: str = ""
    ) -> None:
        thread_id = config["configurable"]["thread_id"]
        cp_ns = config["configurable"]["checkpoint_ns"]
        cp_id = config["configurable"]["checkpoint_id"]
        
        ops = []
        writes_data = []
        set_method = "$set" if all(w[0] in WRITES_IDX_MAP for w in writes) else "$setOnInsert"

        for idx, (channel, value) in enumerate(writes):
            query = {
                "thread_id": thread_id, "checkpoint_ns": cp_ns, "checkpoint_id": cp_id,
                "task_id": task_id, "idx": WRITES_IDX_MAP.get(channel, idx),
            }
            type_, ser_val = self.serde.dumps_typed(value)
            write_doc = {"channel": channel, "type": type_, "value": ser_val, "task_id": task_id, "task_path": task_path}
            
            ops.append(UpdateOne(query, {set_method: write_doc}, upsert=True))
            writes_data.append({**query, **write_doc})

        # 1. Bulk Write (Refactored)
        await self.mongo.bulk_write(ops, collection=self.wr_col)

        # 2. Cache Write
        if self.cache and writes_data:
            await self.cache.set_checkpoint(thread_id, cp_ns, cp_id, {}, writes_data=writes_data)

    async def alist(self, config: Optional[RunnableConfig], *, filter: Optional[Dict[str, Any]] = None, before: Optional[RunnableConfig] = None, limit: Optional[int] = None) -> AsyncIterator[CheckpointTuple]:
        # Try Cache for simple queries
        if config and not filter and not before and self.cache:
            thread_id = config["configurable"]["thread_id"]
            cp_ns = config["configurable"].get("checkpoint_ns", "")
            cached_list = await self.cache.list_checkpoints(thread_id, cp_ns, limit)
            if cached_list:
                for d in cached_list: yield await self._parse_cached_data(d, d["thread_id"], d["checkpoint_ns"])
                return

        # Mongo Query
        query = {}
        if config: query = {"thread_id": config["configurable"]["thread_id"], "checkpoint_ns": config["configurable"].get("checkpoint_ns", "")}
        if filter: 
            for k, v in filter.items(): query[f"metadata.{k}"] = self._dumps_metadata(v)
        if before: query["checkpoint_id"] = {"$lt": before["configurable"]["checkpoint_id"]}

        # Use new get_cursor method
        cursor = self.mongo.get_cursor(query, sort=[("checkpoint_id", -1)], limit=limit, collection=self.cp_col)
        
        async for doc in cursor:
            yield await self._process_mongo_doc(doc, doc["thread_id"], doc["checkpoint_ns"])

    async def adelete_thread(self, thread_id: str) -> None:
        await self.mongo.delete_many_data({"thread_id": thread_id}, collection=self.cp_col)
        await self.mongo.delete_many_data({"thread_id": thread_id}, collection=self.wr_col)
        if self.cache: await self.cache.invalidate_checkpoint(thread_id, clear_all=True)

    # --- Helpers ---

    async def _process_mongo_doc(self, doc, thread_id, cp_ns):
        """Helper to process a mongo document into a CheckpointTuple and warm cache"""
        w_cursor = self.mongo.get_cursor(
            {"thread_id": thread_id, "checkpoint_ns": cp_ns, "checkpoint_id": doc["checkpoint_id"]},
            collection=self.wr_col
        )
        
        pending_writes = []
        writes_raw = []
        async for w in w_cursor:
            pending_writes.append((w["task_id"], w["channel"], self.serde.loads_typed((w["type"], w["value"]))))
            writes_raw.append(w)

        if self.cache:
            await self.cache.populate_from_mongodb(thread_id, cp_ns, doc["checkpoint_id"], doc, writes_raw)

        checkpoint = self.serde.loads_typed((doc["type"], doc["checkpoint"]))
        parent_cfg = {"configurable": {"thread_id": thread_id, "checkpoint_ns": cp_ns, "checkpoint_id": doc["parent_checkpoint_id"]}} if doc.get("parent_checkpoint_id") else None

        return CheckpointTuple(
            config={"configurable": {"thread_id": thread_id, "checkpoint_ns": cp_ns, "checkpoint_id": doc["checkpoint_id"]}},
            checkpoint=checkpoint,
            metadata=self._loads_metadata(doc["metadata"]),
            parent_config=parent_cfg,
            pending_writes=pending_writes
        )

    def _dumps_metadata(self, metadata: CheckpointMetadata) -> str:
        return json.dumps(metadata)

    def _loads_metadata(self, metadata_str: str) -> CheckpointMetadata:
        try: return json.loads(metadata_str)
        except: return {}

    def _convert_bytes(self, data: Any) -> bytes:
        if isinstance(data, bytes): return data
        if isinstance(data, list): return bytes(data)
        if isinstance(data, str):
            if data.startswith('b"') or data.startswith("b'"): return ast.literal_eval(data)
            try: return base64.b64decode(data)
            except: return data.encode('utf-8')
        return data

    async def _parse_cached_data(self, cached_data: dict, thread_id: str, checkpoint_ns: str) -> CheckpointTuple:
        checkpoint_bytes = self._convert_bytes(cached_data["checkpoint"])
        checkpoint = self.serde.loads_typed((cached_data["type"], checkpoint_bytes))
        
        pending_writes = []
        if self.cache:
            cached_writes = await self.cache.get_checkpoint_writes(thread_id, checkpoint_ns, cached_data["checkpoint_id"])
            if cached_writes:
                for w in cached_writes:
                    val_bytes = self._convert_bytes(w["value"])
                    pending_writes.append((w["task_id"], w["channel"], self.serde.loads_typed((w["type"], val_bytes))))
        
        parent_config = None
        if cached_data.get("parent_checkpoint_id"):
             parent_config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": cached_data["parent_checkpoint_id"]}}

        return CheckpointTuple(
            config={"configurable": {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": cached_data["checkpoint_id"]}},
            checkpoint=checkpoint,
            metadata=self._loads_metadata(cached_data["metadata"]),
            parent_config=parent_config,
            pending_writes=pending_writes
        )