from typing import Dict, Any, Optional, Union, List, Tuple
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import MetaData
from config.setting import env
import clickhouse_connect

metadata = MetaData()
Base = declarative_base(metadata=metadata)
SYNC_DB_URL = (
    f"clickhouse://{env.CLICKHOUSE_USER}:{env.CLICKHOUSE_PASSWORD}@"
    f"{env.CLICKHOUSE_HOST}:{env.CLICKHOUSE_HTTP_PORT}/{env.CLICKHOUSE_DATABASE}"
)

class ClickhouseDb:
    def __init__(self):
        self.client = None
        
    async def _ensure_client_initialized(self):
        """
        An internal method to create the async client if it doesn't exist.
        This is called before every query.
        """
        if self.client is None:
            try:
                self.client = await clickhouse_connect.create_async_client(
                    host=env.CLICKHOUSE_HOST,
                    port=env.CLICKHOUSE_HTTP_PORT,
                    username=env.CLICKHOUSE_USER,
                    password=env.CLICKHOUSE_PASSWORD,
                    database=env.CLICKHOUSE_DATABASE
                )
            except Exception as e:
                raise e
        
    async def aexecute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        retrieve_header: bool = False
    ) -> Optional[Union[List[tuple], Tuple[List[str], List[tuple]]]]:
        """
        Asynchronously executes a SQL query with parameters and optional headers.

        Args:
            query: The SQL query string with named parameters (e.g., %(my_param)s).
            params: A dictionary of parameters to bind to the query.
            retrieve_header: If True, returns a tuple of (headers, rows).
                               Otherwise, returns only the rows.

        Returns:
            The query results, or None if an error occurs.
        """
        try:
            await self._ensure_client_initialized()

            result = await self.client.query(query, parameters=params)
            
            if retrieve_header:
                headers = result.column_names
                rows = result.result_rows
                return headers, rows
            
            return result.result_rows
            
        except Exception as e:
            return e

db = ClickhouseDb()
