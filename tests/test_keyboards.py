import unittest

try:
    import pytest
    pytest.importorskip("aiogram")
except ImportError:
    pass

from app.keyboards.inline import admin_assign_keyboard, admin_queue_keyboard, client_confirmation_keyboard, client_final_offer_keyboard, main_menu_keyboard, master_ticket_keyboard


class TestKeyboards(unittest.TestCase):
    def test_client_confirmation_keyboard_callback_data(self):
        keyboard = client_confirmation_keyboard(42)
        callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
        self.assertIn("client:confirm:42", callbacks)
        self.assertIn("client:cancel:42", callbacks)
        self.assertIn("menu:home", callbacks)

    def test_client_final_offer_keyboard_callback_data(self):
        keyboard = client_final_offer_keyboard(42)
        callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
        self.assertIn("client:approve_price:42", callbacks)
        self.assertIn("client:cancel:42", callbacks)

    def test_master_keyboard_callback_data(self):
        keyboard = master_ticket_keyboard(42, is_admin=True)
        callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
        self.assertIn("ticket:assign:42", callbacks)
        self.assertIn("ticket:offer_ai:42", callbacks)
        self.assertIn("ticket:edit_offer:42", callbacks)
        self.assertIn("ticket:start_work:42", callbacks)
        self.assertIn("ticket:done:42", callbacks)
        self.assertIn("admin:queue:all", callbacks)

    def test_main_menu_staff_buttons(self):
        keyboard = main_menu_keyboard(is_master=True, is_admin=True)
        callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
        self.assertNotIn("menu:new_ticket", callbacks)
        self.assertIn("admin:users", callbacks)
        self.assertIn("admin:queue:all", callbacks)

    def test_admin_queue_filters(self):
        keyboard = admin_queue_keyboard([1, 2], "all")
        callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
        self.assertIn("admin:view:1", callbacks)
        self.assertIn("admin:queue:new", callbacks)
        self.assertIn("admin:queue:price", callbacks)
        self.assertIn("admin:queue:approved", callbacks)
        self.assertIn("admin:queue:work", callbacks)

    def test_admin_assign_keyboard(self):
        keyboard = admin_assign_keyboard(42, [1001, 1002])
        callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
        self.assertIn("admin:assign:42:1001", callbacks)
        self.assertIn("admin:assign:42:1002", callbacks)

