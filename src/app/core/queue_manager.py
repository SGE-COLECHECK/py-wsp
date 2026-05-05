import json
import asyncio
import random
import redis.asyncio as redis
from app.utils.logger import logger
from app.core.message_sender import process_queue_item
from app.utils.config_manager import config_manager

class QueueManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(QueueManager, cls).__new__(cls)
            cls._instance.redis_clients = {}
            cls._instance.workers = {}
            cls._instance.paused_workers = set()
            cls._instance.batch_counters = {}
            cls._instance.main_loop = None
        return cls._instance

    def set_main_loop(self, loop):
        self.main_loop = loop

    async def connect(self):
        await self.get_redis()

    async def get_redis(self):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError: return None

        if loop not in self.redis_clients or self.redis_clients[loop] is None:
            host = config_manager.get_global("redis_host", "localhost")
            port = config_manager.get_global("redis_port", 6379)
            try:
                # Conexión más robusta con reintentos y más timeout
                client = redis.Redis(
                    host=host, port=port, db=0, 
                    decode_responses=True, 
                    socket_timeout=20, # Aumentado a 20s
                    socket_connect_timeout=15,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                await client.ping()
                self.redis_clients[loop] = client
            except Exception as e:
                return None
        return self.redis_clients[loop]

    @property
    def is_connected(self):
        return len(self.redis_clients) > 0

    async def start_worker(self, account: str):
        if self.main_loop:
            if account not in self.workers or self.workers[account].done():
                self.workers[account] = asyncio.run_coroutine_threadsafe(self._worker(account), self.main_loop)

    async def get_all_queues(self):
        r = await self.get_redis()
        if not r: return []
        try:
            # En lugar de buscar llaves en Redis (que desaparecen si la cola está en 0),
            # iteramos sobre las sesiones existentes para mostrar siempre la cola.
            sessions = config_manager.get_client_list()
            queues = []
            for name in sessions:
                size = await r.llen(f"queue:{name}")
                queues.append((name, size))
            return sorted(queues)
        except: return []

    async def get_queue_size(self, account: str) -> int:
        r = await self.get_redis()
        if not r: return 0
        try: return await r.llen(f"queue:{account}")
        except: return 0

    def toggle_pause(self, account: str):
        if account in self.paused_workers: self.paused_workers.remove(account)
        else: self.paused_workers.add(account)

    async def enqueue(self, account: str, data: dict):
        r = await self.get_redis()
        if not r: return
        await r.rpush(f"queue:{account}", json.dumps(data))
        await self.start_worker(account)

    async def _worker(self, account: str):
        queue_name = f"queue:{account}"
        self.batch_counters[account] = 0
        
        while True:
            r = await self.get_redis()
            if not r: 
                await asyncio.sleep(2)
                continue
            try:
                if account in self.paused_workers:
                    await asyncio.sleep(2)
                    continue

                result = await r.blpop(queue_name, timeout=5)
                if result:
                    _, data_json = result
                    await process_queue_item(account, json.loads(data_json))
                    
                    self.batch_counters[account] += 1
                    batch_size = config_manager.get_global("batch_size", 20)
                    if self.batch_counters[account] >= batch_size:
                        pause_time = config_manager.get_global("batch_pause", 60)
                        logger.warn(f"[{account}] Pausa de lote: {pause_time}s")
                        self.batch_counters[account] = 0
                        await asyncio.sleep(pause_time)
                    else:
                        min_d = config_manager.get_global("min_delay", 2)
                        max_d = config_manager.get_global("max_delay", 5)
                        await asyncio.sleep(random.randint(min_d, max_d))
                else:
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error Redis Worker: {e}")
                await asyncio.sleep(5)

queue_manager = QueueManager()
