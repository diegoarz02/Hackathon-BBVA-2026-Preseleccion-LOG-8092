"""Politicas de REFERENCIA (offline): correctas y simples. Sirven para

  * normalizar la funcion objetivo (R = "mas barata inmediata"),
  * medir la escalera de mejora  starter -> arreglo minimo -> barata -> rapida -> policy final,
  * dar cohortes de rivales plausibles para el analisis por percentiles.

Despacho inmediato por grupo (cluster, zona, intento) en cada tick; sin retencion deliberada;
sin mejoras. ``MODE``: "price" (carrier mas barato), "eta" (carrier mas rapido), "mix" (precio + 5c/min).
"""

from __future__ import annotations

from interfaces import BaseDispatcherStrategy

PARAMS = {
    "mode": "price",
    "mix_cents_per_min": 5.0,
}


class CandidateStrategy(BaseDispatcherStrategy):
    def __init__(self, carrier_service):
        super().__init__(carrier_service)
        self.p = dict(PARAMS)
        self.pending = {}

    def on_shipments_available(self, now, shipments):
        for s in shipments:
            self.pending[s.shipment_id] = s

    def on_delivery_succeeded(self, result):
        pass

    def on_delivery_failed(self, result):
        if not result.terminal:
            self.pending[result.shipment.shipment_id] = result.shipment

    def on_monthly_planning(self, context):
        return ()

    @staticmethod
    def _ida(km, c):
        num = km * 60 * 10000
        den = c.speed_kmh * c.speed_multiplier_bps
        return -(-num // den)

    def on_dispatch_tick(self, context):
        now = context.now
        groups = {}
        for s in self.pending.values():
            if s.ready_at <= now:
                groups.setdefault((s.delivery_cluster_id, s.zone, s.attempt_number), []).append(s)
        if not groups:
            return
        dist = {z.zone: z.distance_km for z in context.decision_policy.distances}
        att = context.decision_policy.pricing.attempt_multipliers_bps
        free = {c.carrier_id: c.available_units for c in context.carriers}
        order = sorted(groups.values(), key=lambda g: min(x.sla_deadline for x in g))
        for g in order:
            g.sort(key=lambda x: x.shipment_id)
            zone, attempt = g[0].zone, g[0].attempt_number
            need = set()
            for x in g:
                need.update(x.required_capabilities)
            best = None
            for c in context.carriers:
                if free[c.carrier_id] <= 0 or not c.operates_now or zone not in c.allowed_zones:
                    continue
                if not need.issubset(c.capabilities):
                    continue
                zp = next(z.surcharge_cents for z in c.zone_prices if z.zone == zone)
                price = (c.base_fee_cents + zp) * att[attempt - 1] * c.current_time_multiplier_bps / 10000 ** 2
                ida = self._ida(dist[zone], c)
                eta = c.pickup_minutes + ida
                mode = self.p["mode"]
                key = price if mode == "price" else (eta if mode == "eta" else price + self.p["mix_cents_per_min"] * eta)
                if best is None or key < best[0]:
                    best = (key, c)
            if best is None:
                continue
            c = best[1]
            cap = c.batch_capacity
            for i in range(0, len(g), cap):
                chunk = g[i:i + cap]
                if free[c.carrier_id] <= 0:
                    break
                r = self.carrier_service.dispatch_batch(c.carrier_id, [x.shipment_id for x in chunk])
                if r.accepted:
                    free[c.carrier_id] -= 1
                    for x in chunk:
                        self.pending.pop(x.shipment_id, None)
