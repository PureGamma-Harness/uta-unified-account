"""Extract only regular files/directories within a fresh destination."""
from pathlib import Path,PurePosixPath
import sys,tarfile
source,destination=map(Path,sys.argv[1:])
assert destination.is_dir() and not list(destination.iterdir())
with tarfile.open(source) as archive:
 members=archive.getmembers()
 assert len({m.name for m in members})==len(members)
 for member in members:
  name=PurePosixPath(member.name)
  assert not name.is_absolute() and ".." not in name.parts
  assert member.isfile() or member.isdir()
 archive.extractall(destination,filter="data")
print("safe extraction",source,destination,len(members),"members")
