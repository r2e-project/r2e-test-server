from pathlib import Path

def ensure(file: str|Path):
    Path(file).parent.mkdir(exist_ok=True, parents=True)
    return file
