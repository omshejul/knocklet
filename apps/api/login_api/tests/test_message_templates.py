from django.test import SimpleTestCase

from login_api.message_templates import render_template_body


class MessageTemplateRenderingTests(SimpleTestCase):
    def test_skips_leading_titles_and_professional_credentials(self):
        names = {
            "Dr. Ada Lovelace": "Ada",
            "Mr Alan Turing": "Alan",
            "Mrs. Grace Hopper": "Grace",
            "Ms Katherine Johnson": "Katherine",
            "Prof. Edsger Dijkstra": "Edsger",
            "Adv. Cornelia Sorabji": "Cornelia",
            "CA Akhil Kumar": "Akhil",
            "CMA Priya Shah": "Priya",
            "CPA Mary Harris": "Mary",
            "CS Aditi Gupta": "Aditi",
            "Dr. CA Akhil Kumar": "Akhil",
        }

        for full_name, expected_first_name in names.items():
            with self.subTest(full_name=full_name):
                assert render_template_body("Hi, {first_name}", full_name) == (
                    f"Hi, {expected_first_name}"
                )
