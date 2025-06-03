from django.test import TestCase
from .models import HostnameGenerator

class HostnameGeneratorTests(TestCase):
    def test_generate_hostname(self):
        generator = HostnameGenerator()
        hostname = generator.generate()  # Assuming generate() is a method in your model
        self.assertIsInstance(hostname, str)
        self.assertGreater(len(hostname), 0)

    def test_hostname_format(self):
        generator = HostnameGenerator()
        hostname = generator.generate()
        self.assertRegex(hostname, r'^[a-z0-9-]+\.example\.com$')  # Adjust regex as per your hostname format

    def test_multiple_hostnames(self):
        generator = HostnameGenerator()
        hostnames = [generator.generate() for _ in range(10)]
        self.assertEqual(len(hostnames), len(set(hostnames)))  # Ensure all generated hostnames are unique