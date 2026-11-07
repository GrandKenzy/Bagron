from __future__ import annotations

import os
from pathlib import Path

CLAUSES: list[str] = ['Arch',
                      'System',
                      'Boot',
                      'ABI',
                      'Privacy',
                      'StackLimit',
                      'Optimizations',
]

BASEDIR: Path = Path('./')

BAGRON_ROOT: Path = (
    Path(os.environ['BAGRON_ROOT']).resolve()
    if os.environ.get('BAGRON_ROOT')
    else Path(__file__).resolve().parent.parent
)
