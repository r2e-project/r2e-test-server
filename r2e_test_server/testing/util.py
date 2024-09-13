from pathlib import Path

def create_temp_file(content: str) -> str:
    raise NotImplementedError("creates a temp file with the given content and return the path")

def ensure(file: str|Path):
    Path(file).parent.mkdir(exist_ok=True, parents=True)
    return file
