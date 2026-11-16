"""Pruebas unitarias de la estrategia del candidato (stdlib unittest, sin motor).

Cubren las reglas que el motor hace cumplir: lotes homogeneos, capacidades persistentes tras
INACCESSIBLE_ROUTE, no despachar antes de ``ready_at``, tick de auditoria de retencion, asignacion
optima y contrato de ``on_monthly_planning``.
"""

from __future__ import annotations

import itertools
import random
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import candidate_strategy as cs
from candidate_strategy import CandidateStrategy
from interfaces import DispatchContext, DispatchReceipt, MonthlyPlanningContext, Shipment, ZonePrice
from test_candidate_strategy_smoke import (
    carrier_snapshot,
    failure_policy,
    rcp_policy,
    scenario_calendar,
)

LIMA = timezone(timedelta(hours=-5))
T0 = datetime(2026, 1, 5, 8, 0, tzinfo=LIMA)


class Service:
    """Servicio falso con varios carriers; acepta todo lo que sea coherente con su snapshot."""

    def __init__(self, now, carriers):
        self.now, self.carriers, self.calls, self.n = now, carriers, [], 0

    def snapshot(self):
        return self.carriers

    def dispatch_batch(self, carrier_id, shipment_ids):
        ids = tuple(sorted(shipment_ids))
        self.calls.append((carrier_id, ids))
        self.n += 1
        return DispatchReceipt(True, carrier_id, ids, self.now, 100, f"B-{self.n}", self.now + timedelta(minutes=30))


def car(now, cid, zones=("URBANA",), caps=(), base=500, units=2, capacity=4, **kw):
    s = carrier_snapshot(now)
    return replace(s, carrier_id=cid, allowed_zones=zones, capabilities=caps, base_fee_cents=base,
                   available_units=units, total_units=units, batch_capacity=capacity,
                   zone_prices=tuple(ZonePrice(z, 0) for z in zones), **kw)


def ship(sid, cluster, now=T0, zone="URBANA", attempt=1, caps=(), ready=None, product="STANDARD"):
    return Shipment(sid, now, ready or now, now + timedelta(days=3), product, zone, cluster, False,
                    "READY", attempt, tuple(caps))


def ctx(now, carriers):
    return DispatchContext(now=now, reference_budget_cents=10 ** 6, spent_cents=0,
                           contingency_threshold_cents=11 * 10 ** 5, carriers=carriers,
                           calendar=scenario_calendar(), failure_policy=failure_policy(), rcp_policy=rcp_policy())


class HungarianTest(unittest.TestCase):
    def test_matches_brute_force(self):
        rnd = random.Random(7)
        for n, m in [(3, 3), (3, 5), (4, 4), (5, 3)]:
            for _ in range(20):
                cost = [[rnd.randint(0, 50) for _ in range(m)] for _ in range(n)]
                match = cs._hungarian(cost)
                got = sum(cost[i][j] for i, j in enumerate(match) if j is not None)
                k = min(n, m)
                best = min(
                    sum(cost[i][j] for i, j in zip(rows, cols))
                    for rows in itertools.combinations(range(n), k)
                    for cols in itertools.permutations(range(m), k)
                )
                self.assertEqual(got, best)


class BatchingTest(unittest.TestCase):
    def setUp(self):
        self.svc = Service(T0, (car(T0, "A"),))
        self.st = CandidateStrategy(self.svc)

    def test_same_cluster_zone_attempt_share_a_batch(self):
        self.st.on_shipments_available(T0, (ship("S1", "C1"), ship("S2", "C1")))
        self.assertEqual(self.svc.calls, [("A", ("S1", "S2"))])

    def test_different_clusters_never_mix(self):
        self.st.on_shipments_available(T0, (ship("S1", "C1"), ship("S2", "C2")))
        self.assertEqual(sorted(c[1] for c in self.svc.calls), [("S1",), ("S2",)])

    def test_batch_capacity_is_respected(self):
        svc = Service(T0, (car(T0, "A", capacity=2, units=3),))
        st = CandidateStrategy(svc)
        st.on_shipments_available(T0, tuple(ship(f"S{i}", "C1") for i in range(5)))
        self.assertTrue(all(len(c[1]) <= 2 for c in svc.calls))
        self.assertEqual(sum(len(c[1]) for c in svc.calls), 5)

    def test_more_ready_groups_than_the_matching_window_are_all_dispatched(self):
        """Regresion: con mas grupos listos que ``assign_k`` y unidades de sobra, nada puede quedar pendiente tras la llamada."""
        svc = Service(T0, (car(T0, "A", units=100),))
        st = CandidateStrategy(svc)
        st.on_shipments_available(T0, tuple(ship(f"S{i:03d}", f"C{i:03d}") for i in range(3 * int(st.p["assign_k"]))))
        self.assertEqual(len(svc.calls), 3 * int(st.p["assign_k"]))
        self.assertFalse(st.pending)

    def test_pending_is_empty_after_dispatch(self):
        self.st.on_shipments_available(T0, (ship("S1", "C1"),))
        self.assertFalse(self.st.pending)


class RetryRulesTest(unittest.TestCase):
    def test_hard_access_requirement_picks_capable_carrier(self):
        cheap, strong = car(T0, "CHEAP", base=200), car(T0, "STRONG", caps=("HARD_ACCESS",), base=900)
        svc = Service(T0, (cheap, strong))
        st = CandidateStrategy(svc)
        st.on_shipments_available(T0, (ship("S1", "C1", attempt=2, caps=("HARD_ACCESS",)),))
        st.on_dispatch_tick(ctx(T0, svc.snapshot()))
        self.assertEqual(svc.calls, [("STRONG", ("S1",))])

    def test_never_dispatched_before_ready_at(self):
        svc = Service(T0, (car(T0, "A"),))
        st = CandidateStrategy(svc)
        later = T0 + timedelta(hours=24)
        retry = ship("S1", "C1", attempt=2, ready=later)
        from interfaces import DeliveryAttemptResult
        st.on_delivery_failed(DeliveryAttemptResult(retry, "A", "B-1", 1, T0, False, "CUSTOMER_ABSENT"))
        st.on_dispatch_tick(ctx(T0 + timedelta(hours=1), svc.snapshot()))
        self.assertEqual(svc.calls, [])
        st.on_dispatch_tick(ctx(later, svc.snapshot()))
        self.assertEqual(svc.calls, [("A", ("S1",))])

    def test_terminal_failure_is_forgotten(self):
        svc = Service(T0, (car(T0, "A"),))
        st = CandidateStrategy(svc)
        from interfaces import DeliveryAttemptResult
        st.on_delivery_failed(DeliveryAttemptResult(ship("S1", "C1", attempt=3), "A", "B-1", 3, T0, True, "CUSTOMER_ABSENT"))
        st.on_dispatch_tick(ctx(T0 + timedelta(days=2), svc.snapshot()))
        self.assertEqual(svc.calls, [])


class HoldTest(unittest.TestCase):
    def test_audit_tick_is_first_tick_at_or_after_45_minutes(self):
        st = CandidateStrategy(Service(T0, ()))
        t = int(T0.timestamp())
        st._anchor = t - t % 900
        self.assertEqual(st._audit_ts(t), t + 2700)
        self.assertEqual(st._audit_ts(t + 1), t + 3600)

    def _held(self, cap_min):
        svc = Service(T0, (car(T0, "A"),))
        st = CandidateStrategy(svc)
        st.p["hold_cap_min"] = cap_min
        st._anchor = int(T0.timestamp())
        st._shape["CLU-E"] = [10, 10]          # forma aprendida: casi todos son multi
        st.on_shipments_available(T0, (ship("S1", "CLU-E000001"),))
        return svc, st

    def test_holds_to_group_then_releases_at_the_hold_cap(self):
        """Con un tope menor que 45 min el grupo sale en el primer tick >= tope, antes de la auditoria."""
        svc, st = self._held(20.0)
        self.assertEqual(svc.calls, [])        # retenida para agrupar
        st.on_dispatch_tick(ctx(T0 + timedelta(minutes=15), svc.snapshot()))
        self.assertEqual(svc.calls, [])
        st.on_dispatch_tick(ctx(T0 + timedelta(minutes=30), svc.snapshot()))
        self.assertEqual(svc.calls, [("A", ("S1",))])

    def test_default_hold_cap_never_exceeds_the_allowed_wait(self):
        self.assertLessEqual(CandidateStrategy(Service(T0, ())).p["hold_cap_min"], 45.0)

    def test_never_holds_a_shipment_past_its_audit_tick(self):
        """Aunque el tope sea el maximo permitido (45 min), el grupo sale justo en el tick de auditoria."""
        svc, st = self._held(45.0)
        self.assertEqual(svc.calls, [])
        st.on_dispatch_tick(ctx(T0 + timedelta(minutes=30), svc.snapshot()))
        self.assertEqual(svc.calls, [])
        st.on_dispatch_tick(ctx(T0 + timedelta(minutes=45), svc.snapshot()))
        self.assertEqual(svc.calls, [("A", ("S1",))])   # sale justo en el tick de auditoria


class PlanningTest(unittest.TestCase):
    def test_returns_tuple_and_respects_disabled_upgrades(self):
        svc = Service(T0, (car(T0, "A"),))
        st = CandidateStrategy(svc)
        c = MonthlyPlanningContext(T0, 1, 10 ** 6, 0, 11 * 10 ** 5, svc.snapshot(), scenario_calendar(),
                                   failure_policy(), rcp_policy(), upgrades_enabled=False)
        self.assertEqual(st.on_monthly_planning(c), ())


if __name__ == "__main__":
    unittest.main()
