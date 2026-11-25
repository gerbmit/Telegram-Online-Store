from aiogram.fsm.state import State, StatesGroup

class OrderState(StatesGroup):
    """FSM для процесса оформления заказа."""
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_city = State()
    waiting_for_address = State()
    waiting_for_comment = State()
    confirm_order = State()

class SupportState(StatesGroup):
    """FSM для обращения в поддержку."""
    waiting_for_question = State()
    waiting_for_answer = State()

class AdminProductState(StatesGroup):
    """FSM для добавления/редактирования товара админом."""
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_photo = State()
    waiting_for_stock = State()
    waiting_for_category = State()

class AdminCategoryState(StatesGroup):
    """FSM для добавления новой категории."""
    waiting_for_category_name = State()

class AdminBroadcastState(StatesGroup):
    """FSM для рассылки сообщений."""
    waiting_for_message = State()