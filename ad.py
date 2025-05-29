import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.enums import ParseMode

# Конфигурация
API_TOKEN = "8010104498:AAFu41LIYHrPWWl-kvT1pQ0GZrxE8AL0wZE"
ADMIN_USERNAME = "Dashappe"

# Инициализация
bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# Функция создания клавиатуры
def create_main_keyboard():
    builder = ReplyKeyboardBuilder()
    # Первый ряд
    builder.add(types.KeyboardButton(text="📝 Создать задачу"))
    builder.add(types.KeyboardButton(text="📋 Мои задачи"))
    # Второй ряд
    builder.add(types.KeyboardButton(text="👥 Управление ролями"))
    builder.add(types.KeyboardButton(text="ℹ️ Помощь"))
    # Третий ряд (только для админа)
    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True, input_field_placeholder="Выберите действие...")

# Обработчики команд
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🔹 <b>Планировщик задач МУ им. С.Ю. Витте</b> 🔹\n"
        "Используйте кнопки ниже для навигации:",
        reply_markup=create_main_keyboard()
    )

@dp.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: types.Message):
    await message.answer(
        "📚 <b>Доступные действия:</b>\n\n"
        "📝 <b>Создать задачу</b> - Добавить новое задание\n"
        "📋 <b>Мои задачи</b> - Просмотр текущих задач\n"
        "👥 <b>Управление ролями</b> - Настройка прав доступа\n\n"
        "<i>Для администрирования используйте команды:\n"
        "/set_role - назначить роль\n"
        "/list_users - список пользователей</i>"
    )

@dp.message(F.text == "📝 Создать задачу")
async def create_task(message: types.Message):
    await message.answer("🛠️ <b>Создание задачи:</b>\n"
                       "1. Введите название задачи\n"
                       "2. Укажите срок выполнения\n"
                       "3. Выберите ответственного")

@dp.message(F.text == "📋 Мои задачи")
async def show_tasks(message: types.Message):
    await message.answer("📌 <b>Ваши текущие задачи:</b>\n"
                       "1. Подготовить отчет (до 05.06.2025)\n"
                       "2. Пройти тестирование (до 10.06.2025)")

@dp.message(F.text == "👥 Управление ролями")
async def manage_roles(message: types.Message):
    await message.answer("👨‍💼 <b>Управление ролями:</b>\n"
                       "Используйте команды:\n"
                       "/set_role - изменить роль пользователя\n"
                       "/list_roles - список всех пользователей")

# Запуск бота
async def main():
    print(f"Бот запущен. Администратор: @{ADMIN_USERNAME}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())