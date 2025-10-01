# workflow_cache.py

class WorkflowCache:
    """Manages caching of PNG workflow data with LRU eviction"""
    
    def __init__(self, max_size=50):
        self.cache = {}  # file_path -> parsed_workflow_json
        self.access_order = []  # Track usage for LRU
        self.max_size = max_size
    
    def get(self, file_path, parser_func=None):
        """Get workflow data, parse if not cached"""
        if file_path in self.cache:
            # Move to front (most recently used)
            self.access_order.remove(file_path)
            self.access_order.append(file_path)
            return self.cache[file_path]
        
        # Parse if parser provided and not in cache
        if parser_func:
            workflow_data = parser_func(file_path)
            self.put(file_path, workflow_data)
            return workflow_data
        
        return None
    
    def put(self, file_path, workflow_data):
        """Cache workflow data with LRU eviction"""
        # If cache full, remove least recently used
        if len(self.cache) >= self.max_size:
            lru_file = self.access_order.pop(0)
            del self.cache[lru_file]
        
        # Add new entry
        self.cache[file_path] = workflow_data
        self.access_order.append(file_path)
    
    def preload_batch(self, file_paths, parser_func, max_preload=10):
        """Preload workflows for multiple files"""
        for file_path in file_paths[:max_preload]:
            if file_path not in self.cache:
                try:
                    workflow_data = parser_func(file_path)
                    self.put(file_path, workflow_data)
                except Exception as e:
                    print(f"Failed to preload workflow for {file_path}: {e}")
    
    def clear(self):
        """Clear the cache"""
        self.cache.clear()
        self.access_order.clear()
    
    def stats(self):
        """Get cache statistics"""
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'usage_ratio': len(self.cache) / self.max_size
        }

