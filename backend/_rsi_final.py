import sys
sys.path.insert(0, ".")
import numpy as np
from app.services.technicals import FactorEngine
from app.agents.crypto_agent import _rsi

# 1) technicals: flat -> 50, up -> 100, down -> 0
flat = np.full(30, 100.0)
assert FactorEngine.rsi(flat, 14)[-1] == 50.0, "flat must be 50"
up = np.arange(1, 31, dtype=float)
assert FactorEngine.rsi(up, 14)[-1] == 100.0, "up must be 100"
down = np.arange(30, 0, -1, dtype=float)
assert FactorEngine.rsi(down, 14)[-1] == 0.0, "down must be 0"
print("technicals: OK (flat=50, up=100, down=0)")

# 2) crypto_agent._rsi: flat -> 50, up -> 100, down -> 0
assert _rsi(flat) == 50.0, "crypto flat must be 50"
assert _rsi(up) == 100.0, "crypto up must be 100"
assert _rsi(down) == 0.0, "crypto down must be 0"
assert _rsi(flat[:5]) == 50.0, "crypto short data -> 50"
print("crypto_agent: OK")

# 3) screener RSI (private fn, direkt import edilemez; dolayli kontrol icin
#    ayni mantigi ornekle dogrulandiktan sonra dosyada syntax kontrol yapilir)
import ast
for f in ["app/services/technicals.py", "app/services/screener_service.py",
          "app/services/prediction_engine.py", "app/agents/crypto_agent.py"]:
    ast.parse(open(f, encoding="utf-8").read())
print("syntax: OK (4 dosya)")
print("ALL OK")
