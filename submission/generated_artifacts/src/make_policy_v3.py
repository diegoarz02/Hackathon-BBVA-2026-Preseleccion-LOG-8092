"""Genera policy_v3.py (investigacion) a partir de candidate_strategy.py: regla de espera POR POSTERIOR.

En lugar de esperar siempre hasta el tick de auditoria, en cada ronda se compara
  ganancia esperada de esperar un tick  = F * P(llegue al menos otro miembro en el proximo tick | k vistos, e minutos)
  coste de esperar un tick               = w_time * (valor del tiempo de los miembros retenidos) * minutos_del_tick
La posterior sobre el tamano del cluster usa: tamanos aprendidos en linea, desfases uniformes en (0, ventana) y P(multi | forma del id).
hold_rule = 0 reproduce exactamente la regla anterior."""
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "candidate_strategy.py"
OUT = Path(__file__).with_name("policy_v3.py")
t = SRC.read_text(encoding="utf-8")


def rep(old, new, count=1):
    global t
    assert old in t, old[:90]
    t = t.replace(old, new, count)


rep('    "hold_cap_min": 45.0,     # tope (min) de la retencion desde la 1a tarjeta del cluster (<= 45 por regla)',
    '    "hold_cap_min": 45.0,     # tope (min) de la retencion desde la 1a tarjeta del cluster (<= 45 por regla)\n'
    '    "hold_rule": 1,           # 1 = espera por posterior (ganancia vs coste por tick); 0 = regla anterior (hasta la auditoria)\n'
    '    "hold_gain": 400.0,       # centavos que vale evitar un lote adicional (ganancia de que llegue otro miembro)')
rep("import heapq\nfrom collections import deque", "import heapq\nfrom collections import deque\nfrom math import comb")
rep('    __slots__ = ("key", "zone", "attempt", "caps", "members", "release", "dl", "state")',
    '    __slots__ = ("key", "zone", "attempt", "caps", "members", "release", "dl", "state", "rule")')
rep("        self.dl = 1 << 60\n        self.state = 0\n", "        self.dl = 1 << 60\n        self.state = 0\n        self.rule = False       # retenido por la regla de posterior (se reevalua cada tick)\n")
rep("        self._max_size = 0\n", "        self._max_size = 0\n        self._size_n = {2: 1.0, 3: 1.0, 4: 1.0}   # tamanos de cluster multi observados (pseudo-conteos)\n        self._held = {}            # grupos retenidos por la regla de posterior\n")
# aprendizaje de tamanos
rep("            if info[1] > self._max_size:\n                self._max_size = info[1]\n",
    "            if info[1] > self._max_size:\n                self._max_size = info[1]\n            if info[1] > 1:\n                self._size_n[info[1]] = self._size_n.get(info[1], 0.0) + 1.0\n")
# decision por posterior
rep("    def _note_cluster(self, cid, ts):",
    '''    def _worth_waiting(self, k, e_s, pm, wsum):
        """True si conviene esperar un tick mas. k = miembros vistos del cluster, e_s = segundos desde el primero,
        pm = P(cluster multi) a priori, wsum = valor del tiempo (suma de pesos) de las tarjetas retenidas."""
        p = self.p
        H = float(self._hold_s)
        e = min(float(e_s), H)
        if e >= H:
            return False
        dt = float(self._tick_s)
        q = e / H
        sizes = self._size_n
        tot = sum(sizes.values()) or 1.0
        num = {}
        if k == 1:
            num[1] = 1.0 - pm
        for n, c in sizes.items():
            if n >= k:
                num[n] = num.get(n, 0.0) + pm * (c / tot) * comb(n - 1, k - 1) * (q ** (k - 1)) * ((1.0 - q) ** (n - k))
        z = sum(num.values())
        if z <= 0.0:
            return False
        step = min(1.0, dt / (H - e))
        rem = 0.0
        for n, v in num.items():
            if n > k:
                rem += v * (1.0 - (1.0 - step) ** (n - k))
        rem /= z
        gain = p["hold_gain"] * rem
        cost = p["w_time"] * wsum * (dt / 60.0)
        return gain >= cost

    def _group_weight(self, g):
        w = self.p["w_vip"]
        return sum(w if r.vip else 1.0 for r in g.members[:8])

    def _reeval_held(self, now_ts):
        for key, g in list(self._held.items()):
            if g.state != 0:
                self._held.pop(key, None)
                continue
            info = self._cl.get(key[0])
            if info is None:
                self._to_ready(g)
                continue
            if not self._worth_waiting(info[1], now_ts - info[0], 1.0 if info[1] > 1 else self._p_multi(info[2]), self._group_weight(g)):
                self._to_ready(g)

    def _note_cluster(self, cid, ts):''')
# creacion del grupo
rep('''                full = self._max_size and seen + 1 >= self._max_size
                if not full and ((seen >= 1 and p["hold_second"])
                                 or (seen == 0 and self._p_multi(shape) >= p["hold_p_min"])):
                    release = max(now_ts, min(self._audit_ts(first_ts),
                                              self._tick_up(first_ts + p["hold_cap_min"] * 60)))
            g = _Grp(key, zone, attempt, caps, release)''',
    '''                full = self._max_size and seen + 1 >= self._max_size
                rule = False
                if p["hold_rule"]:
                    if not full:
                        pm = 1.0 if seen >= 1 else self._p_multi(shape)
                        w1 = p["w_vip"] if rec.vip else 1.0
                        if self._worth_waiting(seen + 1, now_ts - first_ts, pm, w1):
                            release = max(now_ts, min(self._audit_ts(first_ts),
                                                      self._tick_up(first_ts + p["hold_cap_min"] * 60)))
                            rule = release > now_ts
                elif not full and ((seen >= 1 and p["hold_second"])
                                   or (seen == 0 and self._p_multi(shape) >= p["hold_p_min"])):
                    release = max(now_ts, min(self._audit_ts(first_ts),
                                              self._tick_up(first_ts + p["hold_cap_min"] * 60)))
            g = _Grp(key, zone, attempt, caps, release)
            if attempt == 1 and p["hold_rule"] and rule:
                g.rule = True
                self._held[key] = g''')
rep('''        elif p["hold_full_release"] and self._max_size and len(g.members) >= self._max_size:
            self._to_ready(g)  # cluster completo: no tiene sentido seguir esperando''',
    '''        elif p["hold_full_release"] and self._max_size and len(g.members) >= self._max_size:
            self._to_ready(g)  # cluster completo: no tiene sentido seguir esperando
        elif g.rule:
            info = self._cl.get(cid)
            if info is not None and not self._worth_waiting(info[1], now_ts - info[0], 1.0, self._group_weight(g)):
                self._to_ready(g)''')
rep("    def _to_ready(self, g):\n        g.state = 1\n", "    def _to_ready(self, g):\n        g.state = 1\n        if g.rule:\n            self._held.pop(g.key, None)\n")
# reevaluacion en cada tick
rep("        self._expire_clusters(now_ts)\n        self._release_due(now_ts)\n        if self._ready_n:\n            self._dispatch(now_ts)\n        self._wait_acc += self._ready_n",
    "        self._expire_clusters(now_ts)\n        if self.p[\"hold_rule\"] and self._held:\n            self._reeval_held(now_ts)\n        self._release_due(now_ts)\n        if self._ready_n:\n            self._dispatch(now_ts)\n        self._wait_acc += self._ready_n")
OUT.write_text(t, encoding="utf-8")
print("policy_v3.py generado")
