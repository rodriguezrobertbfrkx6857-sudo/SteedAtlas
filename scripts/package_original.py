"""Package the original UI without rewriting its HTML, styles or compiled scripts."""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
original = root/'wangzhan/baiqipu.com-source-20260424-194149'
output = root/'frontend/dist'
backup = root/'runtime/ui-build-before-original-restore'
for p in (original, output, backup):
    if not p.resolve().is_relative_to(root.resolve()):
        raise ValueError('Workspace boundary')
if output.exists() and not backup.exists():
    shutil.copytree(output, backup)
shutil.copytree(original, output, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.vite', 'node_modules'))
print('Packaged original Baiqipu interface unchanged; redesign is not the default.')
