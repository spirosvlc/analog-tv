import json, shutil, subprocess
from pathlib import Path
class MediaProbe:
    def duration(self, path:Path)->float:
        exe=shutil.which('ffprobe')
        if not exe: return 0.0
        result=subprocess.run([exe,'-v','quiet','-print_format','json','-show_format',str(path)],capture_output=True,text=True,check=False)
        if result.returncode != 0: return 0.0
        try: return float(json.loads(result.stdout).get('format',{}).get('duration',0) or 0)
        except Exception: return 0.0
