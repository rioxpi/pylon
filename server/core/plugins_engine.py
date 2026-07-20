from .net_protocol import NetProtocol
import os
import importlib.util
import sys

class PluginsEngine:
    def __init__(self, conn,plugin_dir="plugins") -> None:
        self.net_protocol = NetProtocol(conn)
        self.plugin_dir = plugin_dir
        self.loaded_plugins = []
    
    def load_plugins(self):
        if not os.path.exists(self.plugin_dir):
            return
        
        for filename in os.listdir(self.plugin_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                plugin_name = filename[:-3]
                filepath = os.path.join(self.plugin_dir, filename)
                
                try:
                    spec = importlib.util.spec_from_file_location(self.plugin_dir, filepath)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[plugin_name] = module
                    spec.loader.exec_module(module)
                    
                    if hasattr(module, "METADATA") and hasattr(module, "execute"):
                        module.initialize(self.net_protocol)
                        self.loaded_plugins.append(module)
                except Exception as e:
                    print(f"Error-loading: {e}")
    
    def execute_plugins(self, word: str) -> str: 
        try:
            for p in self.loaded_plugins:
                if p.METADATA['trigger'] == word:
                    return p.execute()
        except Exception as e:
            print(f"Error-plugins: {e}")
        return ""