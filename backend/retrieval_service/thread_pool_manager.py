"""
Thread Pool Manager for parallel initialization processing.
Manages global and per-user thread limits to prevent resource exhaustion.
"""
import threading
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Any, List
from dotenv import load_dotenv

load_dotenv()

# Global configuration
MAX_WORKERS_PER_USER = int(os.getenv("MAX_WORKERS_PER_USER", "5"))
MAX_TOTAL_WORKERS = int(os.getenv("MAX_TOTAL_WORKERS", "20"))


class GlobalThreadPoolManager:
    """
    Manages thread pools across all users with global and per-user limits.
    Thread-safe singleton pattern.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._active_workers = 0
        self._user_workers = {}  # user_id -> worker_count
        self._global_lock = threading.Lock()
        self._user_locks = {}  # user_id -> lock
    
    def _get_user_lock(self, user_id: str) -> threading.Lock:
        """Get or create lock for specific user"""
        with self._global_lock:
            if user_id not in self._user_locks:
                self._user_locks[user_id] = threading.Lock()
            return self._user_locks[user_id]
    
    def can_acquire_worker(self, user_id: str) -> bool:
        """
        Check if we can acquire a worker for the given user.
        
        Args:
            user_id: User UUID
        
        Returns:
            bool: True if worker can be acquired
        """
        with self._global_lock:
            user_workers = self._user_workers.get(user_id, 0)
            
            # Check global limit
            if self._active_workers >= MAX_TOTAL_WORKERS:
                return False
            
            # Check per-user limit
            if user_workers >= MAX_WORKERS_PER_USER:
                return False
            
            return True
    
    def acquire_worker(self, user_id: str) -> bool:
        """
        Try to acquire a worker slot for the given user.
        
        Args:
            user_id: User UUID
        
        Returns:
            bool: True if worker was acquired
        """
        with self._global_lock:
            if not self.can_acquire_worker(user_id):
                return False
            
            self._active_workers += 1
            self._user_workers[user_id] = self._user_workers.get(user_id, 0) + 1
            return True
    
    def release_worker(self, user_id: str):
        """
        Release a worker slot for the given user.
        
        Args:
            user_id: User UUID
        """
        with self._global_lock:
            self._active_workers = max(0, self._active_workers - 1)
            if user_id in self._user_workers:
                self._user_workers[user_id] = max(0, self._user_workers[user_id] - 1)
                if self._user_workers[user_id] == 0:
                    del self._user_workers[user_id]
    
    def get_stats(self) -> dict:
        """Get current worker statistics"""
        with self._global_lock:
            return {
                "active_workers": self._active_workers,
                "max_total_workers": MAX_TOTAL_WORKERS,
                "user_workers": dict(self._user_workers),
                "max_workers_per_user": MAX_WORKERS_PER_USER
            }
    
    def process_parallel(
        self,
        user_id: str,
        items: List[Any],
        process_func: Callable,
        max_workers: int = None
    ) -> List[Any]:
        """
        Process items in parallel with automatic worker management.
        
        Args:
            user_id: User UUID
            items: List of items to process
            process_func: Function to process each item (func(item) -> result)
            max_workers: Max workers for this batch (defaults to MAX_WORKERS_PER_USER)
        
        Returns:
            List of results (same order as input items)
        """
        if not items:
            return []
        
        if max_workers is None:
            max_workers = MAX_WORKERS_PER_USER
        
        # Limit to available workers
        max_workers = min(max_workers, MAX_WORKERS_PER_USER)
        
        results = [None] * len(items)
        
        def worker_wrapper(idx: int, item: Any):
            """Wrapper that processes item and handles errors"""
            try:
                result = process_func(item)
                return idx, result
            except Exception as e:
                print(f"Error processing item {idx}: {e}")
                import traceback
                traceback.print_exc()
                return idx, None
        
        # Use ThreadPoolExecutor for parallel processing
        # The executor itself manages the concurrency
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(worker_wrapper, idx, item): idx
                for idx, item in enumerate(items)
            }
            
            for future in as_completed(futures):
                try:
                    idx, result = future.result()
                    results[idx] = result
                except Exception as e:
                    print(f"Error in future: {e}")
                    import traceback
                    traceback.print_exc()
        
        return results


# Global instance
_thread_pool_manager = GlobalThreadPoolManager()


def get_thread_pool_manager() -> GlobalThreadPoolManager:
    """Get the global thread pool manager instance"""
    return _thread_pool_manager
