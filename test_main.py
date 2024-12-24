import unittest
from unittest.mock import patch, MagicMock
from aiogram import types
from asyncio import Future

import main  

class TestCurrencyBot(unittest.TestCase):
    def setUp(self):
        self.bot_patcher = patch('main.bot', autospec=True)
        self.mock_bot = self.bot_patcher.start()

    def tearDown(self):
        self.bot_patcher.stop()

    @patch('main.requests.get')
    @patch('main.sqlite3.connect')
    def test_fetch_and_store_exchange_rates(self, mock_connect, mock_get):
        mock_response = MagicMock()
        mock_response.content = b'<ValCurs Date="23/12/2024"><Valute ID="R01235"><CharCode>USD</CharCode><Nominal>1</Nominal><Value>75.84</Value></Valute></ValCurs>'
        mock_get.return_value = mock_response

        mock_conn = mock_connect.return_value
        mock_cursor = mock_conn.cursor.return_value

        # Выполнение функции
        main.fetch_and_store_exchange_rates()

        # Проверка, что запрос к API был сделан
        mock_get.assert_called()
        # Проверка, что данные записались в базу данных
        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()

    @patch('main.sqlite3.connect')
    async def test_show_rate(self, mock_connect):
        mock_conn = mock_connect.return_value
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchone.return_value = (75.84, 0.5, 76.09)

        message = types.Message(message_id=1, chat=types.Chat(id=123, type='private'), date=None, text='/check_rate USD-RUB',
                                from_user=types.User(id=123, is_bot=False, first_name="Test User"))

        with patch('main.types.Message.answer') as mock_answer:
            await main.show_rate(message, 'USD', 'RUB')
            mock_answer.assert_called_with("Курс биржи: 75.84, Спред: 0.5%, Итоговый курс: 76.09")

    @patch('main.sqlite3.connect')
    @patch('aiogram.types.Message.answer', new_callable=MagicMock)
    async def test_change_spread(self, mock_answer, mock_connect):
        # Мок настройки базы данных
        mock_conn = mock_connect.return_value
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchone.return_value = 75.84, 0.7, 77.1  # Предполагаемые новые значения после обновления спреда

        # Запуск тестируемой функции
        await main.change_spread(self.message)

        # Проверки, что ответ был отправлен
        mock_answer.assert_called_with("Спред успешно изменен.")

        # Проверка, что база данных была обновлена верно
        script_calls = [
            ('UPDATE exchange_rates SET spread=? WHERE currency_from=? AND currency_to=?', (0.7, 'USD', 'RUB')),
            ('UPDATE exchange_rates SET final_rate=rate + rate * (spread / 100.0) WHERE currency_from=? AND currency_to=?', ('USD', 'RUB'))
        ]

        mock_cursor.execute.assert_has_calls(script_calls, any_order=True)
        self.assertEqual(mock_cursor.execute.call_count, 2)

if __name__ == '__main__':
    unittest.main()
