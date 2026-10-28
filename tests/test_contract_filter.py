import unittest
from src.models import Opportunity
from src.contract_filter import is_freelance_or_part_time, get_contract_badge
from src.notifier import _format_opportunity


class TestContractFilter(unittest.TestCase):
    def test_freelance_by_role(self):
        opp1 = Opportunity(fuente="test", empresa="Acme", rol="Media Buyer (Freelance)", url="u1")
        opp2 = Opportunity(fuente="test", empresa="Acme", rol="Consultor Freelancer Social Listening", url="u2")
        allowed1, cat1 = is_freelance_or_part_time(opp1)
        allowed2, cat2 = is_freelance_or_part_time(opp2)
        self.assertTrue(allowed1)
        self.assertEqual(cat1, "freelance")
        self.assertTrue(allowed2)
        self.assertEqual(cat2, "freelance")

    def test_freelance_by_tags(self):
        opp1 = Opportunity(fuente="linkedin", empresa="Acme", rol="Social Listening Lead", url="u1", tags=["contract"])
        opp2 = Opportunity(fuente="getonbrd", empresa="Acme", rol="Meta Ads Specialist", url="u2", tags=["Freelance"])
        allowed1, cat1 = is_freelance_or_part_time(opp1)
        allowed2, cat2 = is_freelance_or_part_time(opp2)
        self.assertTrue(allowed1)
        self.assertEqual(cat1, "freelance")
        self.assertTrue(allowed2)
        self.assertEqual(cat2, "freelance")

    def test_freelance_by_description(self):
        opp1 = Opportunity(
            fuente="test",
            empresa="Acme",
            rol="Especialista Brandwatch",
            url="u1",
            descripcion="Contrato por prestación de servicios profesionales para análisis de reputación.",
        )
        opp2 = Opportunity(
            fuente="test",
            empresa="Acme",
            rol="Data Storyteller",
            url="u2",
            descripcion="Pago por honorarios profesionales como contractor independiente.",
        )
        allowed1, cat1 = is_freelance_or_part_time(opp1)
        allowed2, cat2 = is_freelance_or_part_time(opp2)
        self.assertTrue(allowed1)
        self.assertEqual(cat1, "freelance")
        self.assertTrue(allowed2)
        self.assertEqual(cat2, "freelance")

    def test_part_time_detection(self):
        opp_title = Opportunity(fuente="test", empresa="Acme", rol="Trafficker Part-Time", url="u1")
        opp_tag = Opportunity(fuente="test", empresa="Acme", rol="Analista de Datos", url="u2", tags=["parttime"])
        opp_desc = Opportunity(
            fuente="test",
            empresa="Acme",
            rol="Analista BI",
            url="u3",
            descripcion="Buscamos apoyo medio tiempo o media jornada para métricas de campañas.",
        )
        self.assertEqual(is_freelance_or_part_time(opp_title), (True, "part-time"))
        self.assertEqual(is_freelance_or_part_time(opp_tag), (True, "part-time"))
        self.assertEqual(is_freelance_or_part_time(opp_desc), (True, "part-time"))

    def test_por_horas_detection(self):
        # Por presupuesto
        opp_budget1 = Opportunity(fuente="test", empresa="Acme", rol="Analista", url="u1", presupuesto="$30 USD/hora")
        opp_budget2 = Opportunity(fuente="test", empresa="Acme", rol="Analista", url="u2", presupuesto="25 USD/hr")
        opp_budget3 = Opportunity(fuente="test", empresa="Acme", rol="Analista", url="u3", presupuesto="20 USD/h")
        opp_budget4 = Opportunity(fuente="test", empresa="Acme", rol="Analista", url="u4", presupuesto="35 USD/hourly")
        self.assertEqual(is_freelance_or_part_time(opp_budget1), (True, "por_horas"))
        self.assertEqual(is_freelance_or_part_time(opp_budget2), (True, "por_horas"))
        self.assertEqual(is_freelance_or_part_time(opp_budget3), (True, "por_horas"))
        self.assertEqual(is_freelance_or_part_time(opp_budget4), (True, "por_horas"))

        # Por texto o banco de horas
        opp_desc1 = Opportunity(
            fuente="test",
            empresa="Acme",
            rol="Looker Studio Specialist",
            url="u5",
            descripcion="Pago por horas trabajadas, disponibilidad de 15 a 20 horas semanales.",
        )
        opp_desc2 = Opportunity(
            fuente="test",
            empresa="Acme",
            rol="Dashboard Developer",
            url="u6",
            descripcion="Manejo mediante bolsa de horas según requerimientos del cliente.",
        )
        self.assertEqual(is_freelance_or_part_time(opp_desc1), (True, "por_horas"))
        self.assertEqual(is_freelance_or_part_time(opp_desc2), (True, "por_horas"))

    def test_por_proyecto_detection(self):
        opp_title = Opportunity(fuente="test", empresa="Acme", rol="Media Buyer por Proyecto", url="u1")
        opp_tag = Opportunity(fuente="test", empresa="Acme", rol="Data Analyst", url="u2", tags=["project-based"])
        opp_desc = Opportunity(
            fuente="test",
            empresa="Acme",
            rol="Social Listening Specialist",
            url="u3",
            descripcion="Proyecto puntual por entregables con duración de 2 meses.",
        )
        self.assertEqual(is_freelance_or_part_time(opp_title), (True, "por_proyecto"))
        self.assertEqual(is_freelance_or_part_time(opp_tag), (True, "por_proyecto"))
        self.assertEqual(is_freelance_or_part_time(opp_desc), (True, "por_proyecto"))

    def test_full_time_rejection(self):
        opp_ft1 = Opportunity(
            fuente="computrabajo",
            empresa="Corp",
            rol="Analista de Marketing Digital",
            url="u1",
            descripcion="Contrato a término indefinido, tiempo completo 40 horas semanales con prestaciones de ley.",
        )
        opp_ft2 = Opportunity(
            fuente="linkedin",
            empresa="Corp",
            rol="Senior Social Listening Analyst",
            url="u2",
            tags=["full-time"],
            descripcion="Jornada completa, dedicación exclusiva.",
        )
        opp_ft3 = Opportunity(
            fuente="test",
            empresa="Corp",
            rol="Media Trafficker",
            url="u3",
            descripcion="Directo por nómina, 48 horas semanales de lunes a sábado.",
        )
        allowed1, cat1 = is_freelance_or_part_time(opp_ft1)
        allowed2, cat2 = is_freelance_or_part_time(opp_ft2)
        allowed3, cat3 = is_freelance_or_part_time(opp_ft3)
        self.assertFalse(allowed1)
        self.assertEqual(cat1, "full-time")
        self.assertFalse(allowed2)
        self.assertEqual(cat2, "full-time")
        self.assertFalse(allowed3)
        self.assertEqual(cat3, "full-time")

    def test_unspecified_rejection(self):
        opp = Opportunity(
            fuente="indeed",
            empresa="Agencia Creativa",
            rol="Analista de Datos y Social Listening",
            url="u1",
            descripcion="Buscamos analista proactivo con manejo de Meltwater y Looker Studio para cuentas regionales.",
        )
        allowed, reason = is_freelance_or_part_time(opp)
        self.assertFalse(allowed)
        self.assertEqual(reason, "unspecified")

    def test_freelance_negation_rejection(self):
        opp = Opportunity(
            fuente="test",
            empresa="Agencia",
            rol="Growth Specialist",
            url="u1",
            descripcion="Puesto tiempo completo, abstenerse freelancers. Buscamos vinculación fija en nómina.",
        )
        allowed, _ = is_freelance_or_part_time(opp)
        self.assertFalse(allowed)

    def test_experience_only_not_freelance(self):
        opp = Opportunity(
            fuente="test",
            empresa="Agencia",
            rol="Especialista en Meta Ads",
            url="u1",
            descripcion="Contrato a término indefinido tiempo completo. Requisitos: experiencia previa como freelance o en agencia de al menos 2 años.",
        )
        allowed, reason = is_freelance_or_part_time(opp)
        self.assertFalse(allowed)
        self.assertEqual(reason, "full-time")

    def test_alternative_full_time_or_freelance_accepted(self):
        opp = Opportunity(
            fuente="test",
            empresa="Startup",
            rol="Media Buyer",
            url="u1",
            descripcion="Disponibilidad: Tiempo completo o Freelance según disponibilidad del candidato.",
        )
        allowed, cat = is_freelance_or_part_time(opp)
        self.assertTrue(allowed)
        self.assertEqual(cat, "freelance")


class TestNotifierContractBadges(unittest.TestCase):
    def test_badges_in_formatted_opportunity(self):
        opp_fl = Opportunity(
            fuente="test", empresa="Global", rol="Social Listening", url="https://u1", modalidad="remoto", tipo="freelance"
        )
        opp_pt = Opportunity(
            fuente="test", empresa="Global", rol="Trafficker", url="https://u2", modalidad="remoto", tipo="part-time"
        )
        opp_hr = Opportunity(
            fuente="test", empresa="Global", rol="Looker Dev", url="https://u3", modalidad="remoto", tipo="por_horas", presupuesto="$25 USD/hora"
        )
        opp_proj = Opportunity(
            fuente="test", empresa="Global", rol="Auditor de Campañas", url="https://u4", modalidad="remoto", tipo="por_proyecto"
        )
        opp_emp = Opportunity(
            fuente="test", empresa="Global", rol="Analista", url="https://u5", modalidad="remoto", tipo="empleo"
        )

        fmt_fl = _format_opportunity(opp_fl)
        fmt_pt = _format_opportunity(opp_pt)
        fmt_hr = _format_opportunity(opp_hr)
        fmt_proj = _format_opportunity(opp_proj)
        fmt_emp = _format_opportunity(opp_emp)

        self.assertIn("💼 Freelance", fmt_fl)
        self.assertIn("⏱️ Part-time", fmt_pt)
        self.assertIn("⏳ Por horas", fmt_hr)
        self.assertIn("📁 Por proyecto", fmt_proj)
        self.assertNotIn("💼", fmt_emp)
        self.assertNotIn("⏱️", fmt_emp)


if __name__ == "__main__":
    unittest.main()
