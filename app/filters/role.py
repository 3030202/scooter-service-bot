from aiogram.filters import Filter
from aiogram.types import TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User, UserRole


class RoleFilter(Filter):
    def __init__(self, *roles: UserRole | str):
        self.roles = {r.value if isinstance(r, UserRole) else str(r).lower() for r in roles}

    async def __call__(self, event: TelegramObject, session: AsyncSession) -> bool | dict[str, User]:
        from_user = getattr(event, "from_user", None)
        if not from_user:
            return False

        telegram_id = from_user.id

        # Hardcoded admins in settings always pass ADMIN role checks
        if telegram_id in settings.admin_telegram_ids:
            if UserRole.ADMIN.value in self.roles or UserRole.COMMANDER.value in self.roles:
                user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
                return {"db_user": user} if user else True

        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
        if not user:
            return False

        user_role_val = user.role.value if isinstance(user.role, UserRole) else str(user.role).lower()
        if user_role_val in self.roles:
            return {"db_user": user}

        return False
