# -*- coding: utf-8 -*-
"""Coloca `scripts/` no sys.path para que `import vitrine_core` funcione.

O pacote nao e instalado com pip: ele mora em `scripts/` e e importado tanto
pela CLI quanto pelo painel, que ajustam o sys.path do mesmo jeito.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))
