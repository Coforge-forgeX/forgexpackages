from mcp.server.fastmcp import FastMCP
import redis
from .base_cache import BaseCache
from .config import CacheConfig


class AzureRedisCache(BaseCache):
    """
    Azure Redis cache implementation for storing and retrieving data.
    """

    def __init__(self, prefix: str):
        super().__init__(prefix)
        config = CacheConfig()
        azure_config = config.get_azure_config()
        
        self.r = redis.Redis(
            host=azure_config["host"],
            port=azure_config["port"],
            password=azure_config["password"],
            ssl=azure_config["ssl"]
        )
        self.expiry_seconds = azure_config["expiry_seconds"]
    
    async def append_to_key(self,data: dict)->dict:
        """
        Append data to a Redis key.

        Args:
            data (dict): A dictionary containing the key and value to append.

        Returns:
            dict: Confirmation of the append operation.
        """
        try:
            for key, value in data.items():
                self.r.append(self.prefix+key, value)
            return {"status": "success", "message": f"Data appended successfully to keys: {list(data.keys())}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def store_data(self,data : dict) -> dict:
        """
        Store data in Redis cache.Expiry time set to 15mins.

        Args:
            key (str): The key under which the value will be stored.
            value (str): The value to be stored.

        Returns:
            dict: Confirmation of storage.
        """
        try:
            prefix_data = {}
            for k , v in data.items():
                prefix_data[self.prefix+k] = v
                
            self.r.mset(prefix_data)
            
            # Set expiration for each key to 15 minutes (900 seconds)
            for k in prefix_data.keys():
                self.r.expire(k, self.expiry_seconds)
            
            return {"status": "success", "message": f"Data stored successfully under keys: {list(data.keys())},expiry set for 15minutes"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def retrieve_data(self,key: str| list[str]) -> dict:
        """
        Retrieve data from Redis cache.

        Args:
            key (str | list[str]): The key or list of keys to retrieve values for.

        Returns:
            dict: The value stored under the key, or an error message if not found.
        """
        response = {}
        try:
            if(type(key) is str):
                val = self.r.get(self.prefix+key)
                return {"status":"success","data":{f"{key}":val.decode()} if val else {}}
            
            prefix_key = []
            for k in key:
                prefix_key.append(self.prefix + k)
            values = self.r.mget(prefix_key)
            
            for k,v in zip(key,values):
                if v:
                    response[k] = v.decode() 
            
            return {"status": "success","data": response}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def get_all(self,uuid: str | None = None)->dict:
        """
        Retrieve all keys or keys for uuid and their values from Redis cache .
        args:
            uuid (str | None): Optional UUID to filter keys. If provided, only keys starting with the UUID will be returned.
        Returns:
            dict: A dictionary containing all keys and their corresponding values.
        """
        try:
            cursor = '0'
            get_keys = []
            pattern = self.prefix+f'{uuid}*' if uuid else self.prefix +'*'
            while cursor != 0:
                cursor, keys = self.r.scan(cursor=cursor, match=pattern, count=100)
                get_keys.extend(keys)
                
            response = {}
            
            for key in get_keys:
                value = self.r.get(key)
                response[key.decode()] = value.decode() if value else None
                # response[key.decode().replace(self.prefix,"")] = value.decode() if value else None
            
            return {"status": "success", "data": response}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def flush_all(self,uuid: str|None = None) -> dict:
        """
        Flush all data from Redis cache or data relevant to provided uuid.

        Returns:
            dict: Confirmation of the flush operation.
        """
           
        try:
            if uuid:
                cursor = '0'
                flush_keys = []
                pattern = self.prefix+(f'{uuid}*' if uuid else "*")
                while cursor != 0:
                    cursor, keys = self.r.scan(cursor=cursor, match=pattern, count=100)
                    flush_keys.extend(keys)
                print(flush_keys)
                if len(flush_keys) > 0:
                    self.r.delete(*flush_keys)
                
            else:
                self.r.flushall(asynchronous=True)
                
             
            return {"status": "success", "message": "All data flushed successfully."}
        except Exception as e:
            return {"status": "error", "message": str(e)}
 


# import asyncio
# print(asyncio.run(store_data({"test_key": "test_value"})))
# print(asyncio.run(retrieve_data(["test_key","foo","name"])))

# r = RedisCache("test_prefix")

# print(asyncio.run(r.flush_all()))
# print(asyncio.run(r.store_data({"name": "Ashish", "age": "22"})))
# print(asyncio.run(r.get_all()))


# mcp.run(transport = "streamable-http")

