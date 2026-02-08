"""
Module Worker Pool — Infrastructure for running modules as distributed workers.

Enables modules to run in separate processes or containers, communicating
via the EventBus instead of in-process queues. This is the foundation
for the microservices transition.
"""

import concurrent.futures
import logging
import multiprocessing
import os
import queue
import signal
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

log = logging.getLogger("spiderfoot.worker_pool")


class WorkerState(str, Enum):
    """Worker lifecycle states."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class PoolStrategy(str, Enum):
    """Worker pool execution strategies."""
    THREAD = "thread"        # ThreadPoolExecutor (default, backward compat)
    PROCESS = "process"      # ProcessPoolExecutor (CPU-bound modules)
    ASYNC = "async"          # asyncio tasks (I/O-bound modules)


@dataclass
class WorkerPoolConfig:
    """Configuration for the module worker pool.
    
    Attributes:
        strategy: Execution strategy
        max_workers: Maximum concurrent module workers
        queue_size: Max pending events per worker queue
        heartbeat_interval: Health check interval in seconds
        shutdown_timeout: Max wait time for graceful shutdown
        module_timeout: Max time per module event handling
    """
    strategy: PoolStrategy = PoolStrategy.THREAD
    max_workers: int = 0  # 0 = auto (cpu_count * 2)
    queue_size: int = 1000
    heartbeat_interval: float = 30.0
    shutdown_timeout: float = 30.0
    module_timeout: float = 300.0  # 5 min per event
    
    @classmethod
    def from_sf_config(cls, opts: Dict[str, Any]) -> "WorkerPoolConfig":
        """Create config from SpiderFoot options dict."""
        strategy_str = opts.get("_worker_strategy", "thread")
        try:
            strategy = PoolStrategy(strategy_str.lower())
        except ValueError:
            strategy = PoolStrategy.THREAD
        
        return cls(
            strategy=strategy,
            max_workers=int(opts.get("_worker_max", 0)),
            queue_size=int(opts.get("_worker_queue_size", 1000)),
            heartbeat_interval=float(opts.get("_worker_heartbeat", 30)),
            shutdown_timeout=float(opts.get("_worker_shutdown_timeout", 30)),
            module_timeout=float(opts.get("_worker_module_timeout", 300)),
        )
    
    @property
    def effective_max_workers(self) -> int:
        """Get effective max workers (auto-size if 0)."""
        if self.max_workers > 0:
            return self.max_workers
        cpu = os.cpu_count() or 4
        return min(cpu * 2, 32)


@dataclass
class WorkerInfo:
    """Runtime information about a module worker."""
    module_name: str
    state: WorkerState = WorkerState.IDLE
    events_processed: int = 0
    events_errored: int = 0
    last_activity: float = 0
    current_scan_id: Optional[str] = None
    started_at: float = 0
    
    @property
    def uptime(self) -> float:
        """Worker uptime in seconds."""
        if self.started_at == 0:
            return 0
        return time.time() - self.started_at
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_name": self.module_name,
            "state": self.state.value,
            "events_processed": self.events_processed,
            "events_errored": self.events_errored,
            "last_activity": self.last_activity,
            "current_scan_id": self.current_scan_id,
            "uptime": self.uptime,
        }


class ModuleWorker:
    """Wraps a SpiderFoot module for execution in the worker pool.
    
    Each ModuleWorker runs a single module instance and processes
    events from its input queue, producing results to its output queue
    or the EventBus.
    """
    
    def __init__(
        self,
        module_name: str,
        module_instance: Any,
        input_queue: Optional[queue.Queue] = None,
        output_callback: Optional[Callable] = None,
        config: Optional[WorkerPoolConfig] = None,
    ):
        self.module_name = module_name
        self.module = module_instance
        self.input_queue = input_queue or queue.Queue(maxsize=1000)
        self.output_callback = output_callback
        self.config = config or WorkerPoolConfig()
        self.info = WorkerInfo(module_name=module_name)
        self.log = logging.getLogger(f"spiderfoot.worker.{module_name}")
        self._stop_event = threading.Event()
    
    def start(self):
        """Start processing events."""
        self.info.state = WorkerState.RUNNING
        self.info.started_at = time.time()
        self.log.debug(f"Worker started: {self.module_name}")
    
    def stop(self):
        """Signal the worker to stop."""
        self.info.state = WorkerState.STOPPING
        self._stop_event.set()
    
    def process_event(self, event: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Process a single event through the module.
        
        Args:
            event: Event dict with 'type', 'data', 'scan_id', etc.
            
        Returns:
            List of output events produced, or None on error
        """
        if self.info.state != WorkerState.RUNNING:
            return None
        
        self.info.last_activity = time.time()
        
        try:
            # Handle the event through the module
            results = []
            
            if hasattr(self.module, "handleEvent"):
                self.module.handleEvent(event)
                self.info.events_processed += 1
            
            if self.output_callback:
                self.output_callback(results)
            
            return results
            
        except Exception as e:
            self.info.events_errored += 1
            self.log.error(f"Module {self.module_name} error: {e}")
            return None
    
    def run_loop(self):
        """Main processing loop — blocks until stopped."""
        self.start()
        
        while not self._stop_event.is_set():
            try:
                event = self.input_queue.get(timeout=1.0)
                
                if event is None:  # Poison pill
                    break
                
                self.process_event(event)
                self.input_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.log.error(f"Worker loop error: {e}")
                self.info.state = WorkerState.ERROR
                break
        
        self.info.state = WorkerState.STOPPED
        self.log.debug(f"Worker stopped: {self.module_name}")


class WorkerPool:
    """Manages a pool of module workers.
    
    Coordinates module lifecycle, distributes events, monitors health,
    and provides graceful shutdown.
    
    Usage:
        pool = WorkerPool(config)
        pool.register_module("sfp_dns", dns_module_instance)
        pool.register_module("sfp_whois", whois_module_instance)
        pool.start()
        
        pool.submit_event("sfp_dns", {"type": "DOMAIN_NAME", "data": "example.com"})
        
        pool.shutdown()
    """
    
    def __init__(self, config: Optional[WorkerPoolConfig] = None):
        self.config = config or WorkerPoolConfig()
        self.log = logging.getLogger("spiderfoot.worker_pool")
        self._workers: Dict[str, ModuleWorker] = {}
        self._executor: Optional[concurrent.futures.Executor] = None
        self._futures: Dict[str, concurrent.futures.Future] = {}
        self._lock = threading.RLock()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
    
    def register_module(
        self,
        module_name: str,
        module_instance: Any,
        output_callback: Optional[Callable] = None,
    ) -> ModuleWorker:
        """Register a module for pool execution.
        
        Args:
            module_name: Module identifier (e.g., 'sfp_dns')
            module_instance: Module instance
            output_callback: Callback for output events
            
        Returns:
            The created ModuleWorker
        """
        with self._lock:
            worker = ModuleWorker(
                module_name=module_name,
                module_instance=module_instance,
                output_callback=output_callback,
                config=self.config,
            )
            self._workers[module_name] = worker
            self.log.debug(f"Registered module worker: {module_name}")
            return worker
    
    def unregister_module(self, module_name: str) -> None:
        """Remove a module from the pool."""
        with self._lock:
            worker = self._workers.pop(module_name, None)
            if worker:
                worker.stop()
    
    def start(self) -> None:
        """Start the worker pool and all registered workers."""
        if self._running:
            return
        
        with self._lock:
            max_workers = self.config.effective_max_workers
            
            if self.config.strategy == PoolStrategy.THREAD:
                self._executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=max_workers,
                    thread_name_prefix="sf-module-worker",
                )
            elif self.config.strategy == PoolStrategy.PROCESS:
                self._executor = concurrent.futures.ProcessPoolExecutor(
                    max_workers=max_workers,
                )
            
            # Submit all workers to the executor
            for name, worker in self._workers.items():
                future = self._executor.submit(worker.run_loop)
                self._futures[name] = future
            
            self._running = True
            
            # Start health monitor
            self._monitor_thread = threading.Thread(
                target=self._health_monitor,
                daemon=True,
                name="sf-worker-monitor",
            )
            self._monitor_thread.start()
            
            self.log.info(
                f"Worker pool started: {len(self._workers)} workers, "
                f"strategy={self.config.strategy.value}, "
                f"max_workers={max_workers}"
            )
    
    def submit_event(self, module_name: str, event: Dict[str, Any]) -> bool:
        """Submit an event to a specific module worker.
        
        Args:
            module_name: Target module name
            event: Event dict
            
        Returns:
            True if submitted successfully
        """
        with self._lock:
            worker = self._workers.get(module_name)
            if not worker:
                self.log.warning(f"No worker for module: {module_name}")
                return False
            
            try:
                worker.input_queue.put(event, timeout=5.0)
                return True
            except queue.Full:
                self.log.warning(f"Queue full for {module_name}, event dropped")
                return False
    
    def broadcast_event(self, event: Dict[str, Any]) -> int:
        """Broadcast an event to all workers.
        
        Args:
            event: Event dict
            
        Returns:
            Number of workers that received the event
        """
        count = 0
        with self._lock:
            for name, worker in self._workers.items():
                if worker.info.state == WorkerState.RUNNING:
                    try:
                        worker.input_queue.put_nowait(event)
                        count += 1
                    except queue.Full:
                        self.log.warning(f"Queue full for {name}, skipping")
        return count
    
    def shutdown(self, wait: bool = True) -> None:
        """Gracefully shutdown all workers.
        
        Args:
            wait: Wait for workers to finish
        """
        if not self._running:
            return
        
        self.log.info("Shutting down worker pool...")
        
        with self._lock:
            # Signal all workers to stop
            for name, worker in self._workers.items():
                worker.stop()
                # Send poison pill
                try:
                    worker.input_queue.put(None, timeout=1.0)
                except queue.Full:
                    pass
            
            self._running = False
        
        # Wait for executor to finish
        if self._executor:
            self._executor.shutdown(wait=wait)
        
        self.log.info("Worker pool shutdown complete")
    
    def _health_monitor(self):
        """Background thread monitoring worker health."""
        while self._running:
            time.sleep(self.config.heartbeat_interval)
            
            if not self._running:
                break
            
            with self._lock:
                for name, worker in self._workers.items():
                    # Check for stalled workers
                    if (worker.info.state == WorkerState.RUNNING and
                            worker.info.last_activity > 0):
                        idle_time = time.time() - worker.info.last_activity
                        if idle_time > self.config.module_timeout:
                            self.log.warning(
                                f"Worker {name} stalled ({idle_time:.0f}s idle)"
                            )
                    
                    # Check for crashed futures
                    future = self._futures.get(name)
                    if future and future.done():
                        exc = future.exception()
                        if exc:
                            self.log.error(f"Worker {name} crashed: {exc}")
                            worker.info.state = WorkerState.ERROR
    
    def get_worker_info(self, module_name: str) -> Optional[Dict[str, Any]]:
        """Get info about a specific worker."""
        worker = self._workers.get(module_name)
        if worker:
            return worker.info.to_dict()
        return None
    
    def stats(self) -> Dict[str, Any]:
        """Get pool-wide statistics."""
        with self._lock:
            workers_info = {}
            total_processed = 0
            total_errors = 0
            
            for name, worker in self._workers.items():
                workers_info[name] = worker.info.to_dict()
                total_processed += worker.info.events_processed
                total_errors += worker.info.events_errored
            
            return {
                "running": self._running,
                "strategy": self.config.strategy.value,
                "max_workers": self.config.effective_max_workers,
                "registered_workers": len(self._workers),
                "total_events_processed": total_processed,
                "total_errors": total_errors,
                "workers": workers_info,
            }
