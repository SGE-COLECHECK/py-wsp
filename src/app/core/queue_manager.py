import json
import asyncio
import random
import time
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
            cls._instance.worker_locks = {}
            cls._instance.last_activity = {}
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
                client = redis.Redis(
                    host=host, port=port, db=0,
                    decode_responses=True,
                    socket_timeout=20,
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
        if not self.main_loop:
            logger.error(f"No se puede arrancar worker para {account}: main_loop no seteado")
            return
        if account not in self.worker_locks:
            self.worker_locks[account] = asyncio.Lock()
        # Si el worker está vivo, no hacer nada. Si murió, reiniciar.
        existing = self.workers.get(account)
        if existing is not None and not existing.done():
            return
        if existing is not None and existing.done():
            try:
                exc = existing.exception()
                if exc:
                    logger.error(f"Worker de {account} murió: {exc}. Reiniciando...")
            except: pass
        self.workers[account] = asyncio.run_coroutine_threadsafe(self._worker(account), self.main_loop)
        logger.info(f"Worker arrancado para {account}")

    async def restart_all_workers(self):
        """Fuerza el reinicio de TODOS los workers, incluso los que están vivos."""
        if not self.main_loop:
            return
        accounts = list(self.workers.keys())
        if not accounts:
            # Si no hay workers en el dict, intenta con todas las sesiones configuradas
            accounts = config_manager.get_client_list()
        for acc in accounts:
            existing = self.workers.get(acc)
            if existing is not None and not existing.done():
                logger.info(f"Cancelando worker vivo de {acc} para reiniciar")
                existing.cancel()
            self.batch_counters[acc] = 0
            self.workers[acc] = asyncio.run_coroutine_threadsafe(self._worker(acc), self.main_loop)
            logger.success(f"Worker de {acc} reiniciado")

    async def get_all_queues(self):
        r = await self.get_redis()
        if not r: return []
        try:
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

    async def pause_worker(self, account: str):
        self.paused_workers.add(account)

    async def resume_worker(self, account: str):
        self.paused_workers.discard(account)

    async def save_failed(self, account: str, data: dict, error: str, screenshot: str = ""):
        r = await self.get_redis()
        if not r: return
        entry = {
            "phone": data.get("phone", ""),
            "label": data.get("label", "MENSAJE"),
            "message": data.get("message", ""),
            "error": error[:300],
            "screenshot": screenshot,
            "timestamp": time.time(),
        }
        await r.lpush(f"failed:{account}", json.dumps(entry))
        await r.ltrim(f"failed:{account}", 0, 999)

    async def get_failed_count(self, account: str = "") -> int:
        r = await self.get_redis()
        if not r: return 0
        if account:
            return await r.llen(f"failed:{account}")
        total = 0
        for acc in config_manager.get_client_list():
            total += await r.llen(f"failed:{acc}")
        return total

    async def enqueue(self, account: str, data: dict):
        r = await self.get_redis()
        if not r: return
        await r.rpush(f"queue:{account}", json.dumps(data))
        # Solo intentar arrancar si el worker no está vivo
        existing = self.workers.get(account)
        if existing is None or existing.done():
            await self.start_worker(account)

    async def _worker(self, account: str):
        queue_name = f"queue:{account}"
        self.batch_counters[account] = 0
        worker_start = time.time()
        consecutive_errors = 0

        while True:
            r = await self.get_redis()
            if not r:
                await asyncio.sleep(2)
                continue
            try:
                if account in self.paused_workers:
                    await asyncio.sleep(2)
                    continue

                result = await r.blpop(queue_name, timeout=2)
                if result:
                    _, data_json = result
                    item_start = time.time()
                    try:
                        await process_queue_item(account, json.loads(data_json))
                        elapsed = time.time() - item_start
                        self.last_activity[account] = time.time()
                        if elapsed > 30:
                            logger.warn(f"[{account}] Mensaje lento: {elapsed:.1f}s", account=account)
                    except Exception as e:
                        logger.error(f"[{account}] Error procesando item: {e}", account=account)
                    finally:
                        # SIEMPRE incrementa el counter, no importa si el item tuvo error
                        self.batch_counters[account] = (self.batch_counters.get(account, 0) or 0) + 1

                    batch_size = config_manager.get_client_delay(account, "batch_size", 20)
                    if self.batch_counters[account] >= batch_size:
                        pause_time = config_manager.get_client_delay(account, "batch_pause", 60)
                        logger.warn(f"[{account}] Pausa de lote: {pause_time}s")
                        self.batch_counters[account] = 0
                        await asyncio.sleep(pause_time)
                    else:
                        min_d = config_manager.get_client_delay(account, "min_delay", 2)
                        max_d = config_manager.get_client_delay(account, "max_delay", 5)
                        await asyncio.sleep(random.randint(min_d, max_d))
                    consecutive_errors = 0
                else:
                    await asyncio.sleep(1)
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error Redis Worker [{account}] (#{consecutive_errors}): {e}")
                if consecutive_errors > 10:
                    logger.error(f"Worker [{account}] abortando tras {consecutive_errors} errores consecutivos")
                    break
                await asyncio.sleep(5)

queue_manager = QueueManager()
