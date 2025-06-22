"""Compatibility wrapper for legacy tests."""
import importlib.util
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir))

root_cfg = root_dir / 'project_config.py'
spec = importlib.util.spec_from_file_location('root_project_config', root_cfg)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

globals().update({name: getattr(module, name) for name in getattr(module, '__all__', [])})
__all__ = getattr(module, '__all__', [])
