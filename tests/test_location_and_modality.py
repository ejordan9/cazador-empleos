from datetime import datetime
import unittest
from bs4 import BeautifulSoup
from src.models import Opportunity
from src.location_filter import is_location_allowed, normalize_text
from src.collectors.getonbrd import GetOnBrdCollector
from src.collectors.jobspy_source import LinkedInJobSpyCollector, _robust_linkedin_get_location
from src.notifier import _format_opportunity, _get_greeting, build_batches


class TestLocationFilter(unittest.TestCase):
    def setUp(self):
        self.allowed = ["bogota", "bogotá"]

    def test_remote_always_allowed(self):
        opp1 = Opportunity(fuente="test", empresa="Corp", rol="Data Analyst", url="u1", modalidad="remoto", ubicacion="Santiago, Chile")
        opp2 = Opportunity(fuente="test", empresa="Corp", rol="Data Analyst", url="u2", modalidad="remoto", ubicacion="Remote (4 locations)")
        opp3 = Opportunity(fuente="test", empresa="Corp", rol="Data Analyst", url="u3", modalidad="remoto", ubicacion="")
        self.assertTrue(is_location_allowed(opp1, self.allowed))
        self.assertTrue(is_location_allowed(opp2, self.allowed))
        self.assertTrue(is_location_allowed(opp3, self.allowed))

    def test_presencial_only_bogota(self):
        opp_bogota1 = Opportunity(fuente="test", empresa="Corp", rol="Analista", url="u1", modalidad="presencial", ubicacion="Bogotá")
        opp_bogota2 = Opportunity(fuente="test", empresa="Corp", rol="Analista", url="u2", modalidad="presencial", ubicacion="Bogota, D.C., Capital District, Colombia")
        opp_bogota3 = Opportunity(fuente="test", empresa="Corp", rol="Analista", url="u3", modalidad="presencial", ubicacion="BOGOTA, COLOMBIA")
        self.assertTrue(is_location_allowed(opp_bogota1, self.allowed))
        self.assertTrue(is_location_allowed(opp_bogota2, self.allowed))
        self.assertTrue(is_location_allowed(opp_bogota3, self.allowed))

        opp_santiago = Opportunity(fuente="test", empresa="Corp", rol="Analista", url="u4", modalidad="presencial", ubicacion="Santiago, Chile")
        opp_lima = Opportunity(fuente="test", empresa="Corp", rol="Analista", url="u5", modalidad="presencial", ubicacion="Lima, Perú")
        opp_medellin = Opportunity(fuente="test", empresa="Corp", rol="Analista", url="u6", modalidad="presencial", ubicacion="Medellín, Antioquia, Colombia")
        self.assertFalse(is_location_allowed(opp_santiago, self.allowed))
        self.assertFalse(is_location_allowed(opp_lima, self.allowed))
        self.assertFalse(is_location_allowed(opp_medellin, self.allowed))

    def test_hibrido_only_bogota(self):
        opp_bogota = Opportunity(fuente="test", empresa="Corp", rol="Analista", url="u1", modalidad="hibrido", ubicacion="Bogotá")
        opp_bogota_dc = Opportunity(fuente="test", empresa="Corp", rol="Analista", url="u2", modalidad="hibrido", ubicacion="Bogota, D.C.")
        self.assertTrue(is_location_allowed(opp_bogota, self.allowed))
        self.assertTrue(is_location_allowed(opp_bogota_dc, self.allowed))

        opp_santiago = Opportunity(fuente="test", empresa="Corp", rol="Analista", url="u3", modalidad="hibrido", ubicacion="Santiago")
        opp_buenos_aires = Opportunity(fuente="test", empresa="Corp", rol="Analista", url="u4", modalidad="hibrido", ubicacion="Buenos Aires, Argentina")
        self.assertFalse(is_location_allowed(opp_santiago, self.allowed))
        self.assertFalse(is_location_allowed(opp_buenos_aires, self.allowed))

    def test_unspecified_modality(self):
        # Physical location outside Bogota -> rejected
        opp_santiago = Opportunity(fuente="test", empresa="Corp", rol="Analista", url="u1", modalidad="", ubicacion="Santiago")
        self.assertFalse(is_location_allowed(opp_santiago, self.allowed))

        # Physical location in Bogota -> accepted
        opp_bogota = Opportunity(fuente="test", empresa="Corp", rol="Analista", url="u2", modalidad="", ubicacion="Bogotá, Colombia")
        self.assertTrue(is_location_allowed(opp_bogota, self.allowed))

        # No location but description mentions remote -> accepted
        opp_remote_desc = Opportunity(fuente="test", empresa="Corp", rol="Analista", url="u3", modalidad="", ubicacion="", descripcion="Puesto 100% remoto para LATAM")
        self.assertTrue(is_location_allowed(opp_remote_desc, self.allowed))


class TestGetOnBrdParsing(unittest.TestCase):
    def test_infer_modalidad(self):
        self.assertEqual(GetOnBrdCollector._infer_modalidad("Santiago (Hybrid)"), "hibrido")
        self.assertEqual(GetOnBrdCollector._infer_modalidad("Bogotá (Hybrid)"), "hibrido")
        self.assertEqual(GetOnBrdCollector._infer_modalidad("Santiago (In-office)"), "presencial")
        self.assertEqual(GetOnBrdCollector._infer_modalidad("Remote (Argentina)"), "remoto")
        self.assertEqual(GetOnBrdCollector._infer_modalidad("Remote"), "remoto")
        self.assertEqual(GetOnBrdCollector._infer_modalidad("Trabajo Híbrido en Oficina"), "hibrido")


class TestLinkedInJobSpyCollector(unittest.TestCase):
    def test_robust_location_parsing(self):
        self_dummy = type("obj", (), {"country": "usa"})
        
        # 4 parts (Bogota)
        soup4 = BeautifulSoup('<div class="base-search-card__metadata"><span class="job-search-card__location">Bogota, D.C., Capital District, Colombia</span></div>', 'html.parser')
        loc4 = _robust_linkedin_get_location(self_dummy, soup4.div)
        self.assertEqual(loc4.display_location(), "Bogota, D.C., Capital District, Colombia")

        # 3 parts (Santiago)
        soup3 = BeautifulSoup('<div class="base-search-card__metadata"><span class="job-search-card__location">Santiago, Región Metropolitana, Chile</span></div>', 'html.parser')
        loc3 = _robust_linkedin_get_location(self_dummy, soup3.div)
        self.assertEqual(loc3.display_location(), "Santiago, Región Metropolitana, Chile")

        # 1 part (Mexico City)
        soup1 = BeautifulSoup('<div class="base-search-card__metadata"><span class="job-search-card__location">Mexico City Metropolitan Area</span></div>', 'html.parser')
        loc1 = _robust_linkedin_get_location(self_dummy, soup1.div)
        self.assertEqual(loc1.display_location(), "Mexico City Metropolitan Area")


class TestNotifierFormatting(unittest.TestCase):
    def test_formatting(self):
        opp_remoto = Opportunity(fuente="getonbrd", empresa="Veltrix", rol="Growth Lead", url="https://job1", modalidad="remoto", ubicacion="Remote")
        opp_hibrido = Opportunity(fuente="getonbrd", empresa="Acme", rol="Analista BI", url="https://job2", modalidad="hibrido", ubicacion="Bogotá")
        opp_presencial = Opportunity(fuente="linkedin", empresa="Burson", rol="Social Listening", url="https://job3", modalidad="presencial", ubicacion="Bogota, D.C.")

        fmt_r = _format_opportunity(opp_remoto)
        fmt_h = _format_opportunity(opp_hibrido)
        fmt_p = _format_opportunity(opp_presencial)

        self.assertIn("✅", fmt_r)
        self.assertNotIn("(Remote)", fmt_r)
        self.assertIn("🔄", fmt_h)
        self.assertIn("(Bogotá)", fmt_h)
        self.assertIn("🏢", fmt_p)
        self.assertIn("(Bogota, D.C.)", fmt_p)

    def test_get_greeting(self):
        morning = datetime(2026, 9, 17, 9, 0)
        afternoon = datetime(2026, 9, 17, 15, 30)
        night = datetime(2026, 9, 17, 21, 0)

        self.assertEqual(_get_greeting(morning), "¡Hola! Buenos días ☀️")
        self.assertEqual(_get_greeting(afternoon), "¡Hola! Buenas tardes ⛅")
        self.assertEqual(_get_greeting(night), "¡Hola! Buenas noches 🌙")

    def test_build_batches_humanized(self):
        morning = datetime(2026, 9, 17, 8, 0)
        opp1 = Opportunity(fuente="torre", empresa="Labs", rol="Media Buyer", url="https://u1", modalidad="remoto", score=5)
        opp2 = Opportunity(fuente="getonbrd", empresa="Acme", rol="Data Analyst", url="https://u2", modalidad="hibrido", ubicacion="Bogotá", score=3)
        opp3 = Opportunity(fuente="computrabajo", empresa="Corp", rol="Trafficker", url="https://u3", modalidad="presencial", ubicacion="Bogotá", score=2)

        # Caso 1 oferta
        batches_single = build_batches([opp1], batch_size=10, now=morning)
        self.assertEqual(len(batches_single), 1)
        self.assertIn("¡Hola! Buenos días ☀️", batches_single[0])
        self.assertIn("la oferta destacada del día:", batches_single[0])
        self.assertIn("¡Mucho éxito en las postulaciones! 🚀", batches_single[0])

        # Caso varias ofertas en 1 lote
        batches_multi = build_batches([opp1, opp2, opp3], batch_size=10, now=morning)
        self.assertEqual(len(batches_multi), 1)
        self.assertIn("¡Hola! Buenos días ☀️", batches_multi[0])
        self.assertIn("las *3 ofertas destacadas* del día:", batches_multi[0])
        self.assertIn("Media Buyer", batches_multi[0])
        self.assertIn("¡Mucho éxito en las postulaciones! 🚀", batches_multi[0])

        # Caso paginado (batch_size=2)
        batches_paginated = build_batches([opp1, opp2, opp3], batch_size=2, now=morning)
        self.assertEqual(len(batches_paginated), 2)
        self.assertIn("parte 1 de 2", batches_paginated[0])
        self.assertIn("parte 2 de 2", batches_paginated[1])
        self.assertIn("¡Mucho éxito en las postulaciones! 🚀", batches_paginated[1])


if __name__ == "__main__":
    unittest.main()
