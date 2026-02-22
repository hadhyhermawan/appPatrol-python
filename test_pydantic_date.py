from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class M(BaseModel):
    d: Optional[datetime] = None

print("Str with space:", repr(M(d='2026-02-21 15:30:00').d))
print("Str with T:", repr(M(d='2026-02-21T15:30:00').d))
print("ISO with Z:", repr(M(d='2026-02-21T15:30:00.000Z').d))
