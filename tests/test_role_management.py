import pytest
from app.db.models import UserRole
from app.keyboards.inline import main_menu_keyboard


def test_user_role_enum_values():
    assert UserRole.CLIENT.value == "client"
    assert UserRole.MASTER.value == "master"
    assert UserRole.COMMANDER.value == "commander"
    assert UserRole.ADMIN.value == "admin"


def test_client_main_menu_does_not_contain_master_or_admin_actions():
    kb = main_menu_keyboard(role=UserRole.CLIENT)
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]

    assert "menu:new_ticket" in callbacks
    assert "menu:my_orders" in callbacks
    assert "admin:users" not in callbacks
    assert "commander:all_tickets" not in callbacks


def test_master_main_menu_does_not_contain_new_ticket():
    kb = main_menu_keyboard(role=UserRole.MASTER)
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]

    assert "menu:new_ticket" not in callbacks
    assert "menu:my_jobs" in callbacks
    assert "master:my_schedule" in callbacks


def test_commander_main_menu():
    kb = main_menu_keyboard(role=UserRole.COMMANDER)
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]

    assert "commander:all_tickets" in callbacks
    assert "commander:assign_masters" in callbacks
    assert "menu:new_ticket" not in callbacks


def test_admin_main_menu_contains_user_management():
    kb = main_menu_keyboard(role=UserRole.ADMIN)
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]

    assert "admin:users" in callbacks
    assert "commander:all_tickets" in callbacks
    assert "menu:new_ticket" not in callbacks
