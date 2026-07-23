import os
import unittest


class TestConfig(unittest.TestCase):
    def test_id_list_parser(self):
        os.environ["BOT_TOKEN"] = "123:abc"
        os.environ["MASTERS_CHAT_ID"] = "-1001"
        os.environ["AI_API_KEY"] = "key"
        os.environ["DATABASE_URL"] = "postgresql+asyncpg://u:p@localhost:5432/db"
        os.environ["MASTER_TELEGRAM_IDS"] = "1, 2,3"

        from app.config import Settings

        settings = Settings()
        self.assertEqual(settings.master_telegram_ids, [1, 2, 3])

