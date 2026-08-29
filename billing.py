import datetime
import uuid

# Имитация БД пользователей и подписок (на практике заменяется на SQLite/PostgreSQL)
USERS_DB = {}

SUBSCRIPTION_FEE_KZT = 1000  # 2$ по курсу в тенге
TRIAL_DAYS = 30

class BillingManager:
    @staticmethod
    def get_or_create_user(user_id: str) -> dict:
        """Получение или создание профиля с бесплатным периодом на 30 дней"""
        if user_id not in USERS_DB:
            now = datetime.datetime.now()
            trial_end = now + datetime.timedelta(days=TRIAL_DAYS)
            USERS_DB[user_id] = {
                "user_id": user_id,
                "created_at": now.isoformat(),
                "trial_ends_at": trial_end.isoformat(),
                "subscription_active_until": trial_end.isoformat(),
                "status": "trial"
            }
        return USERS_DB[user_id]

    @staticmethod
    def is_subscription_active(user_id: str) -> bool:
        """Проверка активности подписки или пробного периода"""
        user = BillingManager.get_or_create_user(user_id)
        active_until = datetime.datetime.fromisoformat(user["subscription_active_until"])
        return datetime.datetime.now() <= active_until

    @staticmethod
    def create_kaspi_payment_link(user_id: str) -> dict:
        """
        Генерация QR / Ссылки на оплату через Kaspi Pay API
        """
        payment_id = str(uuid.uuid4())
        
        # Ссылка на оплату через Kaspi (формат Kaspi Pay API / Deeplink)
        # Пример интеграционной ссылки Kaspi Pay
        kaspi_pay_url = f"https://kaspi.kz/pay/GovAccountingAI?service_id=10893&account={user_id}&amount={SUBSCRIPTION_FEE_KZT}"
        
        return {
            "payment_id": payment_id,
            "amount": SUBSCRIPTION_FEE_KZT,
            "currency": "KZT",
            "kaspi_url": kaspi_pay_url,
            "qr_data": kaspi_pay_url
        }

    @staticmethod
    def process_kaspi_webhook(user_id: str, payment_status: str) -> bool:
        """Обработка успешной оплаты от Kaspi Webhook"""
        if payment_status == "SUCCESS":
            user = USERS_DB.get(user_id)
            if user:
                current_expiry = datetime.datetime.fromisoformat(user["subscription_active_until"])
                now = datetime.datetime.now()
                # Если подписка истекла — продлеваем от текущей даты, если активна — добавляем к остатку
                start_date = max(current_expiry, now)
                new_expiry = start_date + datetime.timedelta(days=30)
                
                user["subscription_active_until"] = new_expiry.isoformat()
                user["status"] = "paid"
                return True
        return False