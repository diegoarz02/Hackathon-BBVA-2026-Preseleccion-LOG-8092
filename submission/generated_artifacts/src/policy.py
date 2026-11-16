"""Estrategia de despacho LOG-8092: politica parametrizable (solo biblioteca estandar).

Marco: el problema es un MDP de despacho online (estado = envios pendientes + flota + hora;
accion = que grupo sale ahora y con que transportista; recompensa = -(coste + penalizacion por
tiempo/riesgo)). Se resuelve por APROXIMACION DE POLITICA (regla parametrica), no por programacion
dinamica exacta: los parametros de ``PARAMS`` se afinan offline sobre el simulador.

Componentes
  1. Grupos (cluster, zona, intento, capacidades): unico agrupamiento que el motor admite en un lote.
  2. Retencion deliberada <= 45 min SOLO para agrupar clusters multi-tarjeta (cuyo patron de
     identificador se aprende en linea: P(cluster con >1 tarjeta | forma del id)). Nunca supera el
     tick de auditoria de retencion: 0 infracciones por construccion.
  3. Prioridad EDD (earliest due date): primero el grupo con plazo SLA mas cercano.
  4. Seleccion de carrier por VALOR ESPERADO en centavos:
         J = precio exacto + w_time * ETA + w_fail * P(fallo atribuible al carrier) * F(intento, zona)
             + coste sombra de la unidad ocupada
     con las probabilidades de fallo tomadas del contexto (no hay nada que inferir).
  5. Mejoras mensuales solo ante cola persistente (disparador por backlog).
  6. Asignacion por tick: greedy por prioridad o Hungarian (variante), segun PARAMS["assign"].

Estado minimo: solo grupos pendientes (los envios despachados se olvidan).
"""

from __future__ import annotations

import heapq
from collections import deque

from interfaces import BaseDispatcherStrategy, FleetUpgradeDecision

PARAMS = {
    # valor del tiempo y del riesgo, en centavos
    "w_time": 6.0,          # centavos por minuto de ETA y por tarjeta
    "w_vip": 3.0,           # multiplicador del valor del tiempo para VIP_BLACK
    "w_fail": 1.0,          # escala del coste esperado de fallo
    "vip_fail_extra": 500.0,  # coste extra de que falle un VIP (incumple SLA seguro)
    "terminal_extra": 3000.0,  # coste extra de devolver una tarjeta a custodia
    "w_unit": 0.0,          # centavos por minuto de unidad ocupada (coste sombra de flota)
    "unit_util_gamma": 1.0,  # el coste sombra crece con la utilizacion del carrier
    # retencion para agrupar clusters
    "hold_on": 1,
    "hold_p_min": 0.5,      # retener si P(cluster multi) >= umbral
    "hold_prior": 0.15,
    "hold_prior_n": 6.0,
    "hold_second": 1,       # retener al segundo miembro (cluster seguro multi)
    "hold_full_release": 1,  # liberar al alcanzar el tamano maximo de cluster observado
    "hold_cap_min": 45.0,   # tope de la retencion desde la 1a tarjeta del cluster (<= 45 por regla)
    # despacho
    "dispatch_on_arrival": 1,
    "assign": 0,            # 0 = greedy por prioridad, 1 = Hungarian por tick
    "assign_k": 24,
    # mejoras mensuales
    "up_on": 0,
    "up_wait_thr": 5.0,     # envios en cola (media por tick) para pedir mejora
    "up_units": 1,
}

_DIGITS = {ord(c): None for c in "0123456789"}
_ZONE_DIST = {"URBANA": 12, "SUBURBANA": 35, "RURAL": 80, "REMOTA": 150}
_RETRY_WAIT_MIN = 1440.0
_BIG = 1e9


class _Rec:
    """Tarjeta pendiente: solo lo imprescindible (sin el objeto Shipment)."""
    __slots__ = ("sid", "dl", "vip", "metal")

    def __init__(self, sid, dl, vip, metal):
        self.sid, self.dl, self.vip, self.metal = sid, dl, vip, metal


class _Grp:
    """Tarjetas que pueden viajar juntas. state: 0 = retenido (en ``_hold``), 1 = listo."""
    __slots__ = ("key", "zone", "attempt", "caps", "members", "release", "dl", "state")

    def __init__(self, key, zone, attempt, caps, release):
        self.key, self.zone, self.attempt, self.caps = key, zone, attempt, caps
        self.members = []
        self.release = release
        self.dl = 1 << 60
        self.state = 0


class _Car:
    """Vista persistente de un carrier: parte estatica + estado dinamico que mantenemos entre ticks.

    La flota se modela localmente (cada unidad que enviamos vuelve en ``now + pickup + 2*ida``,
    igual que el motor), asi se puede despachar al llegar una tarjeta sin pedir otro snapshot.
    """
    __slots__ = ("cid", "key", "free", "total", "cap", "base", "zp", "tm", "op0", "op", "hard",
                 "zones", "caps", "eta", "occ", "operates", "ret")


class CandidateStrategy(BaseDispatcherStrategy):
    def __init__(self, carrier_service) -> None:
        super().__init__(carrier_service)
        self.p = dict(PARAMS)
        self._anchor = 0           # instante del primer tick (los ticks caen en anchor + k*tick)
        self._policy_ready = False
        self._holidays = frozenset()
        self._groups = {}          # clave -> grupo pendiente (retenido o listo)
        self._hold = []            # heap (release, seq, clave) de grupos retenidos / reintentos futuros
        self._ready = {}           # clase (zona, caps) -> heap (dl, seq, grupo)
        self._seq = 0
        self._ready_n = 0          # tarjetas en grupos listos
        self._wait_acc = 0.0
        self._wait_ticks = 0
        self._cl = {}              # cluster -> [primer_ts, tarjetas vistas, forma del id]
        self._cl_q = deque()
        self._shape = {}           # forma del id -> [clusters cerrados, de ellos multi]
        self._max_size = 0
        self._ftab = {}
        self._snap = None          # ultimo snapshot recibido (en un tick o en la planificacion)
        self._snap_now = None
        self._stale = True
        self._cars = []
        self._car_by_id = {}
        self._resync = False
        self._now_dt = None
        self._now_ts = 0
        self._set_defaults()

    # ------------------------------------------------------------------ politica publica
    def _set_defaults(self) -> None:
        self._abs = {1: 0.07, 2: 0.035, 3: 0.015}
        self._zmod = {"URBANA": 0.0, "SUBURBANA": 0.005, "RURAL": 0.015, "REMOTA": 0.03}
        self._inacc = {"URBANA": 0.0, "SUBURBANA": 0.0, "RURAL": 0.04, "REMOTA": 0.12}
        self._sun, self._hol, self._max_att = 0.01, 0.02, 3
        self._dist, self._att = dict(_ZONE_DIST), [1.0, 0.5, 1.0]
        self._pen, self._add, self._metal, self._hold_s, self._tick_s = 2000, 120, 450, 2700, 900

    def _init_policy(self, ctx) -> None:
        """Toma del contexto las constantes del escenario (una sola vez)."""
        if self._policy_ready:
            return
        fp, dp = ctx.failure_policy, ctx.decision_policy
        self._holidays = frozenset(ctx.calendar.holidays)
        self._abs = {a.attempt_number: a.customer_absence_bps / 1e4 for a in fp.attempts}
        self._zmod = {z.zone: z.absence_modifier_bps / 1e4 for z in fp.zones}
        self._inacc = {z.zone: z.inaccessible_route_bps / 1e4 for z in fp.zones}
        self._sun, self._hol = fp.sunday_operation_modifier_bps / 1e4, fp.holiday_operation_modifier_bps / 1e4
        self._max_att = len(fp.attempts)
        if dp is not None:
            self._dist = {d.zone: d.distance_km for d in dp.distances}
            self._att = [x / 1e4 for x in dp.pricing.attempt_multipliers_bps]
            self._pen = dp.pricing.terminal_penalty_cents
            self._add, self._metal = dp.pricing.additional_card_cents, dp.pricing.metal_security_cents
            self._hold_s = dp.pricing.max_voluntary_hold_minutes * 60
            self._tick_s = dp.pricing.dispatch_tick_minutes * 60
        self._policy_ready = True

    def _build_ftab(self, cars) -> None:
        """F[(intento, zona)]: coste esperado, en centavos, de que ese intento falle."""
        p = self.p
        for z in self._dist:
            lines = [c.base + c.zp[z] for c in cars if z in c.zp]
            line = sum(lines) / len(lines) if lines else 600.0
            nxt = self._pen + p["terminal_extra"]
            self._ftab[(self._max_att, z)] = nxt
            for a in range(self._max_att - 1, 0, -1):
                pf_next = min(1.0, self._abs.get(a + 1, 0.0) + self._zmod.get(z, 0.0) + 0.015)
                nxt = self._att[a] * line + p["w_time"] * (_RETRY_WAIT_MIN + 100.0) + pf_next * nxt
                self._ftab[(a, z)] = nxt

    # ------------------------------------------------------------------ vistas de flota
    def _note_snapshot(self, snap, now) -> None:
        self._snap, self._snap_now, self._stale = snap, now, True

    def _cars_at(self, now_ts):
        """Carriers con su estado al instante ``now_ts`` (snapshot del ultimo tick + modelo local)."""
        if self._snap is None:
            self._note_snapshot(self.carrier_service.snapshot(), self._now_dt)
        if self._stale:
            self._sync()
        for c in self._cars:
            ret = c.ret
            while ret and ret[0] <= now_ts:
                heapq.heappop(ret)
                c.free += 1
        return self._cars

    def _sync(self) -> None:
        now = self._snap_now
        snap_ts = int(now.timestamp())
        sun = now.isoweekday() == 7
        hol = now.date() in self._holidays
        cars = []
        for s in self._snap:
            c = self._car_by_id.get(s.carrier_id)
            key = (s.speed_multiplier_bps, s.speed_kmh, s.pickup_minutes)
            if c is None:
                c = self._car_by_id[s.carrier_id] = _Car()
                c.cid, c.ret, c.key = s.carrier_id, [], None
            if c.key != key:
                c.key = key
                c.base = s.base_fee_cents
                c.zp = {z.zone: z.surcharge_cents for z in s.zone_prices}
                c.zones = frozenset(c.zp)
                c.caps = frozenset(s.capabilities)
                c.hard = "HARD_ACCESS" in c.caps
                c.op0 = s.operational_failure_bps / 1e4
                den = s.speed_kmh * s.speed_multiplier_bps
                c.eta, c.occ = {}, {}
                for z in c.zp:
                    ida = -(-self._dist.get(z, 150) * 600000 // den)
                    c.eta[z] = s.pickup_minutes + ida
                    c.occ[z] = s.pickup_minutes + 2 * ida
            c.free, c.total, c.cap = s.available_units, s.total_units, s.batch_capacity
            c.tm, c.operates = s.current_time_multiplier_bps / 1e4, s.operates_now
            c.op = min(1.0, c.op0 + (self._sun if sun else 0.0) + (self._hol if hol else 0.0))
            ret = c.ret
            while ret and ret[0] <= snap_ts:   # esos retornos ya estan reflejados en el snapshot
                heapq.heappop(ret)
            cars.append(c)
        self._cars = cars
        self._stale = False

    # ------------------------------------------------------------------ clusters
    def _audit_ts(self, ready_ts):
        """Primer tick >= ready + 45 min: instante en que el motor audita la retencion."""
        a, t = self._anchor, self._tick_s
        return a + t * (-(-(ready_ts + self._hold_s - a) // t))

    def _tick_up(self, ts):
        """Primer tick >= ts."""
        a, t = self._anchor, self._tick_s
        return a + t * (-(-(int(ts) - a) // t))

    def _p_multi(self, shape):
        n, m = self._shape.get(shape, (0, 0))
        n0 = self.p["hold_prior_n"]
        return (m + self.p["hold_prior"] * n0) / (n + n0)

    def _note_cluster(self, cid, ts):
        """Registra una tarjeta de primer intento; devuelve (vistas antes, forma, primer_ts)."""
        info = self._cl.get(cid)
        if info is None:
            shape = cid.translate(_DIGITS)
            self._cl[cid] = [ts, 1, shape]
            self._cl_q.append((ts, cid))
            return 0, shape, ts
        prev = info[1]
        info[1] += 1
        return prev, info[2], info[0]

    def _expire_clusters(self, now_ts):
        """Un cluster queda cerrado 45 min despues de su primera tarjeta: ahi se conoce su tamano."""
        q, horizon = self._cl_q, self._hold_s + self._tick_s
        while q and q[0][0] + horizon <= now_ts:
            _, cid = q.popleft()
            info = self._cl.pop(cid, None)
            if info is None:
                continue
            st = self._shape.setdefault(info[2], [0, 0])
            st[0] += 1
            if info[1] > 1:
                st[1] += 1
            if info[1] > self._max_size:
                self._max_size = info[1]

    # ------------------------------------------------------------------ grupos
    def _add_member(self, cid, zone, attempt, caps, rec, ts, now_ts, retry_ready=0):
        """Inserta una tarjeta en su grupo; decide la retencion al crearse el grupo."""
        key = (cid, zone, attempt, caps, retry_ready)
        g = self._groups.get(key)
        p = self.p
        if g is None:
            release = retry_ready if attempt > 1 else now_ts
            if attempt == 1 and p["hold_on"]:
                seen, shape, first_ts = self._note_cluster(cid, ts)
                full = self._max_size and seen + 1 >= self._max_size
                if not full and ((seen >= 1 and p["hold_second"])
                                 or (seen == 0 and self._p_multi(shape) >= p["hold_p_min"])):
                    release = max(now_ts, min(self._audit_ts(first_ts),
                                              self._tick_up(first_ts + p["hold_cap_min"] * 60)))
            g = _Grp(key, zone, attempt, caps, release)
            self._groups[key] = g
            g.members.append(rec)
            g.dl = rec.dl
            if release <= now_ts:
                self._to_ready(g)
            else:
                self._seq += 1
                heapq.heappush(self._hold, (release, self._seq, key))
            return
        if attempt == 1 and p["hold_on"]:
            self._note_cluster(cid, ts)
        g.members.append(rec)
        if rec.dl < g.dl:
            g.dl = rec.dl
        if g.state == 1:
            self._ready_n += 1
        elif p["hold_full_release"] and self._max_size and len(g.members) >= self._max_size:
            self._to_ready(g)  # cluster completo: no tiene sentido seguir esperando

    def _to_ready(self, g):
        g.state = 1
        self._ready_n += len(g.members)
        self._heap_push(g)

    def _heap_push(self, g):
        cls = (g.zone, g.caps)
        h = self._ready.get(cls)
        if h is None:
            h = self._ready[cls] = []
        self._seq += 1
        heapq.heappush(h, (g.dl, self._seq, g))

    def _release_due(self, now_ts):
        hold, groups = self._hold, self._groups
        while hold and hold[0][0] <= now_ts:
            _, _, key = heapq.heappop(hold)
            g = groups.get(key)
            if g is not None and g.state == 0:
                self._to_ready(g)

    # ------------------------------------------------------------------ hooks
    def on_shipments_available(self, now, shipments) -> None:
        self._now_dt = now
        now_ts = int(now.timestamp())
        for s in shipments:
            self._add_member(
                s.delivery_cluster_id, s.zone, s.attempt_number, tuple(s.required_capabilities),
                _Rec(s.shipment_id, int(s.sla_deadline.timestamp()), s.product == "VIP_BLACK", s.is_metal),
                int(s.ready_at.timestamp()), now_ts)
        if self.p["dispatch_on_arrival"]:
            self._release_due(now_ts)
            if self._ready_n:
                self._dispatch(now_ts)

    def on_dispatch_tick(self, context) -> None:
        self._init_policy(context)
        now = self._now_dt = context.now
        now_ts = int(now.timestamp())
        self._note_snapshot(context.carriers, now)
        self._expire_clusters(now_ts)
        self._release_due(now_ts)
        if self._ready_n:
            self._dispatch(now_ts)
        self._wait_acc += self._ready_n
        self._wait_ticks += 1

    def on_delivery_succeeded(self, result) -> None:
        return None

    def on_delivery_failed(self, result) -> None:
        if result.terminal:
            return
        s = result.shipment
        rts = int(s.ready_at.timestamp())
        self._add_member(
            s.delivery_cluster_id, s.zone, s.attempt_number, tuple(s.required_capabilities),
            _Rec(s.shipment_id, int(s.sla_deadline.timestamp()), s.product == "VIP_BLACK", s.is_metal),
            rts, int(result.occurred_at.timestamp()), retry_ready=rts)

    def on_monthly_planning(self, context):
        self._init_policy(context)
        self._now_dt = context.now
        if context.period_index == 0:
            self._anchor = int(context.now.timestamp())
        self._note_snapshot(context.carriers, context.now)
        if not self._ftab:
            self._build_ftab(self._cars_at(self._anchor))
        decisions = ()
        if self.p["up_on"] and context.upgrades_enabled and context.period_index > 0 and self._wait_ticks:
            decisions = self._plan_upgrades(context)
        self._wait_acc, self._wait_ticks = 0.0, 0
        return decisions

    # ------------------------------------------------------------------ mejoras
    def _plan_upgrades(self, ctx):
        """Pide una unidad extra solo si la cola media del periodo supera el umbral."""
        if self._wait_acc / self._wait_ticks < self.p["up_wait_thr"]:
            return ()
        load = {}
        for g in self._groups.values():
            if g.state == 1:
                load[g.zone] = load.get(g.zone, 0) + len(g.members)
        if not load:
            return ()
        zone = max(load, key=load.get)
        best = None
        for s in ctx.carriers:
            zp = {z.zone: z.surcharge_cents for z in s.zone_prices}
            if "EXTRA_UNIT" in s.supported_upgrades and zone in zp:
                key = s.base_fee_cents + zp[zone]
                if best is None or key < best[0]:
                    best = (key, s.carrier_id)
        if best is None:
            return ()
        return (FleetUpgradeDecision(best[1], "EXTRA_UNIT", int(self.p["up_units"])),)

    # ------------------------------------------------------------------ nucleo de despacho
    def _score(self, g, chunk, c):
        """J en centavos de enviar ``chunk`` (del grupo g) con el carrier c."""
        p, zone = self.p, g.zone
        metals = wsum = fsum = 0.0
        f1 = self._ftab.get((g.attempt, zone), 0.0)
        for r in chunk:
            metals += r.metal
            if r.vip:
                wsum += p["w_vip"]
                fsum += f1 + p["vip_fail_extra"]
            else:
                wsum += 1.0
                fsum += f1
        att = self._att[min(g.attempt, len(self._att)) - 1]
        price = (c.base + c.zp[zone]) * att * c.tm + self._add * (len(chunk) - 1) + self._metal * metals
        p_inacc = 0.0 if c.hard else self._inacc.get(zone, 0.0)
        pf = (1.0 - (1.0 - p_inacc) * (1.0 - c.op)) * (1.0 - self._abs.get(g.attempt, 0.0) - self._zmod.get(zone, 0.0))
        j = price + p["w_time"] * wsum * c.eta[zone] + p["w_fail"] * pf * fsum
        if p["w_unit"]:
            util = 1.0 - c.free / c.total if c.total else 1.0
            j += p["w_unit"] * c.occ[zone] * (1.0 + p["unit_util_gamma"] * util)
        return j

    def _dispatch(self, now_ts) -> None:
        self._now_ts = now_ts
        usable = [c for c in self._cars_at(now_ts) if c.free > 0 and c.operates]
        if usable:
            try:
                if self.p["assign"] == 1:
                    self._dispatch_hungarian(usable)
                else:
                    self._dispatch_greedy(usable)
            finally:
                if self._resync:   # el modelo local discrepo del motor: se pide la verdad una vez
                    self._resync = False
                    self._note_snapshot(self.carrier_service.snapshot(), self._now_dt)

    @staticmethod
    def _feasible(g, usable):
        need = g.caps
        return [c for c in usable if c.free > 0 and g.zone in c.zones and (not need or c.caps.issuperset(need))]

    def _pop_next(self, usable):
        """Cabeza de mayor prioridad (EDD) entre las clases con algun carrier libre y factible."""
        best_cls, best = None, None
        for cls, h in self._ready.items():
            while h and (h[0][2].state != 1 or not h[0][2].members):
                heapq.heappop(h)
            if not h:
                continue
            zone, need = cls
            if not any(c.free > 0 and zone in c.zones and (not need or c.caps.issuperset(need)) for c in usable):
                continue
            if best is None or h[0] < best:
                best, best_cls = h[0], cls
        return heapq.heappop(self._ready[best_cls])[2] if best_cls is not None else None

    def _send(self, g, ranked):
        """Envia el grupo (en trozos de la capacidad) al primer carrier que lo acepte."""
        for _, c in ranked:
            chunk = g.members[:c.cap]
            rcpt = self.carrier_service.dispatch_batch(c.cid, [r.sid for r in chunk])
            if rcpt.accepted:
                c.free -= 1
                heapq.heappush(c.ret, self._now_ts + c.occ[g.zone] * 60)
                del g.members[:len(chunk)]
                self._ready_n -= len(chunk)
                return True
            if rcpt.rejection_reason in ("NO_AVAILABLE_UNIT", "OUTSIDE_OPERATING_WINDOW"):
                c.free = 0
                self._resync = True
        return False

    def _settle(self, g, sent):
        """Tras un intento de envio: olvida el grupo vaciado o lo devuelve a la cola."""
        if not g.members:
            self._groups.pop(g.key, None)
            g.state = 2
            return
        if sent:
            g.dl = min(r.dl for r in g.members)
        self._heap_push(g)

    def _dispatch_greedy(self, usable) -> None:
        blocked = []
        while self._ready_n:
            g = self._pop_next(usable)
            if g is None:
                break
            ranked = sorted(((self._score(g, g.members[:c.cap], c), c) for c in self._feasible(g, usable)),
                            key=lambda t: t[0])
            if self._send(g, ranked):
                self._settle(g, True)
            else:
                blocked.append(g)
        for g in blocked:
            self._settle(g, False)

    def _dispatch_hungarian(self, usable) -> None:
        k = int(self.p["assign_k"])
        while self._ready_n:
            cand = []
            while len(cand) < k:
                g = self._pop_next(usable)
                if g is None:
                    break
                cand.append(g)
            if not cand:
                break
            slots = [c for c in usable for _ in range(min(c.free, len(cand)))]
            cost = [[self._score(g, g.members[:c.cap], c)
                     if g.zone in c.zones and (not g.caps or c.caps.issuperset(g.caps)) else _BIG
                     for c in slots] for g in cand]
            match = _hungarian(cost) if slots else [None] * len(cand)
            sent_any = False
            for gi in sorted(range(len(cand)), key=lambda i: cand[i].dl):
                g, si = cand[gi], match[gi]
                sent = False
                if si is not None and cost[gi][si] < _BIG and slots[si].free > 0:
                    sent = self._send(g, [(cost[gi][si], slots[si])])
                sent_any = sent_any or sent
                self._settle(g, sent)
            if not sent_any:
                break


def _hungarian(cost):
    """Asignacion de coste minimo (algoritmo hungaro O(n^2 m)). Devuelve, por fila, su columna o None."""
    n, m = len(cost), len(cost[0])
    transposed = n > m
    if transposed:
        cost = [list(r) for r in zip(*cost)]
        n, m = m, n
    inf = float("inf")
    u, v, pm, way = [0.0] * (n + 1), [0.0] * (m + 1), [0] * (m + 1), [0] * (m + 1)
    for i in range(1, n + 1):
        pm[0] = i
        j0 = 0
        minv = [inf] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = pm[j0], inf, 0
            for j in range(1, m + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(m + 1):
                if used[j]:
                    u[pm[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if pm[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            pm[j0] = pm[j1]
            j0 = j1
    res = [None] * (m if transposed else n)
    for j in range(1, m + 1):
        if pm[j]:
            if transposed:
                res[j - 1] = pm[j] - 1
            else:
                res[pm[j] - 1] = j - 1
    return res
