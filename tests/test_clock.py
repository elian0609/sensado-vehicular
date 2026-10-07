"""Pruebas de core/clock.py: corrección de la hora con el gateway.

  python3 -m unittest tests.test_clock -v
"""
import json
import unittest
from datetime import datetime, timedelta, timezone

from core.clock import ClockSync

NODE_NOW = datetime(2026, 10, 6, 23, 0, 0, tzinfo=timezone.utc)


def _msg(dt: datetime) -> bytes:
    return json.dumps({"utc": dt.isoformat().replace("+00:00", "Z")}).encode()


class ClockSyncTest(unittest.TestCase):
    def setUp(self):
        self.ntp = False
        self.mono = 1000.0
        self.set_calls, self.rtc_calls = [], []
        self.clock = ClockSync(ntp_synced=lambda: self.ntp, now=lambda: NODE_NOW,
                               set_clock=self.set_calls.append,
                               write_rtc=self.rtc_calls.append,
                               monotonic=lambda: self.mono)

    def test_corrige_reloj_y_rtc_si_el_nodo_va_atrasado(self):
        phone = NODE_NOW + timedelta(seconds=12)
        self.assertEqual(self.clock.on_gateway_time(_msg(phone)), "corregida")
        self.assertEqual(self.set_calls, [phone])
        self.assertEqual(self.rtc_calls, [phone])
        self.assertEqual(self.clock.source(), "gateway")

    def test_no_toca_el_reloj_con_desfase_menor_a_1s(self):
        phone = NODE_NOW + timedelta(milliseconds=400)
        self.assertEqual(self.clock.on_gateway_time(_msg(phone)), "en_hora")
        self.assertEqual(self.set_calls, [])
        self.assertEqual(self.clock.source(), "gateway")   # hora confirmada

    def test_admite_retrocesos_pequenos(self):
        phone = NODE_NOW - timedelta(seconds=5)             # RTC adelantado
        self.assertEqual(self.clock.on_gateway_time(_msg(phone)), "corregida")

    def test_rechaza_retrocesos_grandes(self):
        phone = NODE_NOW - timedelta(minutes=5)
        self.assertEqual(self.clock.on_gateway_time(_msg(phone)), "rechazada_atras")
        self.assertEqual(self.set_calls, [])

    def test_con_ntp_ignora_al_gateway(self):
        self.ntp = True
        phone = NODE_NOW + timedelta(seconds=30)
        self.assertEqual(self.clock.on_gateway_time(_msg(phone)), "ignorada_ntp")
        self.assertEqual(self.set_calls, [])
        self.assertEqual(self.clock.source(), "ntp")

    def test_mensajes_invalidos(self):
        self.assertEqual(self.clock.on_gateway_time(b"no es json"), "invalida")
        self.assertEqual(self.clock.on_gateway_time(b'{"utc": "2026-10-06T23:00:00"}'),
                         "invalida")                        # sin zona horaria
        self.assertEqual(self.clock.on_gateway_time(_msg(datetime(2020, 1, 1,
                                                    tzinfo=timezone.utc))), "invalida")

    def test_la_correccion_del_gateway_caduca(self):
        self.clock.on_gateway_time(_msg(NODE_NOW + timedelta(seconds=3)))
        self.mono += 7 * 3600                                # más de 6 h después
        self.assertEqual(self.clock.source(), "rtc")


if __name__ == "__main__":
    unittest.main()
