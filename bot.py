import telebot
from telebot import types
import os
import sys
import logging
import time
import re

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Добавляем путь для локальных модулей
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ====== СОСТОЯНИЯ ПОЛЬЗОВАТЕЛЯ ======
user_states = {}  # Словарь для хранения состояний пользователей

# ====== БЕЗОПАСНАЯ ЗАГРУЗКА КОНФИГУРАЦИИ ======
def load_config():
    """Безопасная загрузка конфигурации"""
    config = {
        'TELEGRAM_BOT_TOKEN': None,
        'ADMIN_IDS': []
    }
    
    # ПРИОРИТЕТ 1: Переменные окружения Railway
    token_from_env = os.getenv('TELEGRAM_BOT_TOKEN')
    if token_from_env:
        config['TELEGRAM_BOT_TOKEN'] = token_from_env
        logger.info("✅ Токен загружен из переменных окружения Railway")
    
    # ID администраторов из переменных окружения
    admin_ids_env = os.getenv('ADMIN_IDS')
    if admin_ids_env:
        try:
            config['ADMIN_IDS'] = [int(id.strip()) for id in admin_ids_env.split(',') if id.strip()]
            logger.info(f"✅ ID администраторов из переменных окружения: {len(config['ADMIN_IDS'])}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось распарсить ADMIN_IDS: {e}")
    
    # ПРИОРИТЕТ 2: Файл config.py (только если в окружении нет токена)
    if not config['TELEGRAM_BOT_TOKEN']:
        try:
            if os.path.exists('config.py'):
                from config import TELEGRAM_BOT_TOKEN, ADMIN_IDS
                config['TELEGRAM_BOT_TOKEN'] = TELEGRAM_BOT_TOKEN
                if ADMIN_IDS:
                    config['ADMIN_IDS'].extend([id for id in ADMIN_IDS if id not in config['ADMIN_IDS']])
                logger.info("✅ Конфиг загружен из config.py")
            else:
                logger.warning("⚠️ Файл config.py не найден")
        except ImportError as e:
            logger.error(f"❌ Ошибка импорта config.py: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки config.py: {e}")
    
    return config

# Загружаем конфигурацию
config = load_config()
TELEGRAM_BOT_TOKEN = config['TELEGRAM_BOT_TOKEN']
ADMIN_IDS = config['ADMIN_IDS']

# Проверяем токен
if not TELEGRAM_BOT_TOKEN:
    logger.error("❌ Токен не найден!")
    logger.error("\n💡 СПОСОБЫ УКАЗАТЬ ТОКЕН:")
    logger.error("1. НА RAILWAY: Установите переменную окружения TELEGRAM_BOT_TOKEN")
    logger.error("2. ЛОКАЛЬНО: Создайте файл config.py с содержанием:")
    logger.error("   TELEGRAM_BOT_TOKEN = 'ваш_токен_бота'")
    logger.error("   ADMIN_IDS = [ваш_id_телеграм]")
    sys.exit(1)

logger.info(f"✅ Токен получен (первые 10 символов): {TELEGRAM_BOT_TOKEN[:10]}...")
if ADMIN_IDS:
    logger.info(f"✅ Администраторы: {len(ADMIN_IDS)} пользователей")
else:
    logger.warning("⚠️ ADMIN_IDS не установлены - команды администратора будут недоступны")

# Создаем бота
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# ====== БЕЗОПАСНАЯ ЗАГРУЗКА МОДУЛЕЙ ======
def safe_import_modules():
    """Безопасная загрузка модулей с обработкой ошибок"""
    modules = {
        'download_schedule': None,
        'schedule_parser': None
    }
    
    try:
        import download_schedule
        modules['download_schedule'] = download_schedule
        logger.info("✅ Модуль download_schedule загружен")
    except ImportError as e:
        logger.warning(f"⚠️ Модуль download_schedule не найден: {e}")
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки download_schedule: {e}")
    
    try:
        import schedule_parser
        modules['schedule_parser'] = schedule_parser
        logger.info("✅ Модуль schedule_parser загружен")
    except ImportError as e:
        logger.warning(f"⚠️ Модуль schedule_parser не найден: {e}")
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки schedule_parser: {e}")
    
    return modules

# Загружаем модули
modules = safe_import_modules()
LOCAL_MODULES = modules['download_schedule'] is not None and modules['schedule_parser'] is not None

if not LOCAL_MODULES:
    logger.warning("⚠️ Основные модули не загружены, некоторые функции будут недоступны")

# ====== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ======
def escape_markdown(text):
    """Экранирует специальные символы MarkdownV2"""
    if not text:
        return ""
    
    # Список всех специальных символов в MarkdownV2
    escape_chars = [
        '_', '*', '[', ']', '(', ')', '~', 
        '`', '>', '#', '+', '-', '=', '|', 
        '{', '}', '.', '!'
    ]
    
    result = str(text)
    
    # Экранируем каждый символ
    for char in escape_chars:
        result = result.replace(char, f'\\{char}')
    
    return result

def update_schedule_file():
    """Обновляет файл расписания с сайта"""
    if not LOCAL_MODULES:
        return False, "Модули расписания не загружены"
    
    try:
        logger.info("🔄 Начинаю обновление расписания с сайта...")
        modules['download_schedule'].download_schedule_from_site()
        
        import importlib
        importlib.reload(modules['schedule_parser'])
        
        if os.path.exists('school_schedule.csv'):
            file_size = os.path.getsize('school_schedule.csv')
            return True, f"✅ Расписание обновлено! Размер файла: {file_size} байт"
        else:
            return False, "❌ Файл расписания не был создан"
    except Exception as e:
        logger.error(f"Ошибка обновления расписания: {e}")
        return False, f"❌ Ошибка: {escape_markdown(str(e))}"

def create_main_keyboard():
    """Создает основную клавиатуру с кнопками"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    buttons = [
        "📋 Найти класс",
        "👨‍🏫 Найти учителя",
        "🔍 Поиск учителя (часть фамилии)",
        "🏫 Найти кабинет",
        "🔄 Обновить",
        "❓ Помощь",
        "ℹ️ О боте"
    ]
    
    # Разделяем на две колонки для лучшего вида
    row1 = buttons[:3]
    row2 = buttons[3:5]
    row3 = buttons[5:]
    
    keyboard.row(*row1)
    keyboard.row(*row2)
    keyboard.row(*row3)
    
    return keyboard

def create_search_keyboard(search_type):
    """Создает клавиатуру для режима поиска"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    keyboard.add(types.KeyboardButton("🔙 Назад к меню"))
    return keyboard

def set_user_state(user_id, state):
    """Устанавливает состояние пользователя"""
    user_states[user_id] = state
    logger.debug(f"Установлено состояние {state} для пользователя {user_id}")

def get_user_state(user_id):
    """Получает состояние пользователя"""
    return user_states.get(user_id)

def clear_user_state(user_id):
    """Очищает состояние пользователя"""
    if user_id in user_states:
        del user_states[user_id]
        logger.debug(f"Очищено состояние для пользователя {user_id}")

# ====== ОБРАБОТЧИКИ КОМАНД ======
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Обработчик команд /start и /help"""
    clear_user_state(message.chat.id)
    
    welcome_text = (
        "👋 *Добро пожаловать в школьный бот расписания\\!*\n\n"
        "Я помогу вам быстро найти расписание уроков\\.\n\n"
        "🎯 *Основные возможности:*\n"
        "• Поиск расписания по классу\n"
        "• Поиск расписания по учителю \\(полная фамилия\\)\n"
        "• Поиск учителей по части фамилии \\(с расписанием\\)\n"
        "• Поиск расписания по кабинету \\(полный номер\\)\n"
        "• Автоматическое обновление данных\n\n"
        "📱 *Используйте кнопки ниже для навигации*\n\n"
        "💡 *Совет:* Начните с кнопки 'Найти класс' или 'Найти учителя'"
    )
    
    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode='MarkdownV2',
        reply_markup=create_main_keyboard()
    )

@bot.message_handler(commands=['update'])
def update_command(message):
    """Обновление расписания"""
    if ADMIN_IDS and message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Эта команда доступна только администраторам\\.")
        return
    
    clear_user_state(message.chat.id)
    
    bot.send_message(
        message.chat.id,
        "🔄 Обновляю расписание с сайта\\.\\.\\.",
        parse_mode='MarkdownV2'
    )
    
    success, msg = update_schedule_file()
    
    if success:
        bot.send_message(message.chat.id, msg, reply_markup=create_main_keyboard())
    else:
        bot.send_message(message.chat.id, msg, reply_markup=create_main_keyboard())

@bot.message_handler(commands=['schedule', 'class'])
def schedule_command(message):
    """Запрос расписания класса"""
    set_user_state(message.chat.id, 'waiting_for_class')
    
    bot.send_message(
        message.chat.id,
        "📋 *Режим поиска класса*\n\n"
        "✏️ *Введите номер класса:*\n"
        "Например: 5А, 10Е, 8 Б\n\n"
        "💡 *Совет:* Можно вводить в любом формате \\(5А, 5 А, 5а\\)\n\n"
        "⚠️ *Внимание:* Теперь любой ваш текст будет восприниматься как поиск класса\n"
        "Для выхода из режима поиска нажмите кнопку '🔙 Назад к меню'",
        parse_mode='MarkdownV2',
        reply_markup=create_search_keyboard('class')
    )

@bot.message_handler(commands=['classes'])
def classes_command(message):
    """Список всех классов"""
    if not LOCAL_MODULES:
        bot.send_message(message.chat.id, "❌ Модули не загружены", reply_markup=create_main_keyboard())
        return
    
    clear_user_state(message.chat.id)
    
    try:
        classes = modules['schedule_parser'].get_available_classes()
        if classes:
            classes_by_grade = {}
            for cls in classes:
                match = re.search(r'(\d+)([А\\-Я])', cls)
                if match:
                    grade = match.group(1)
                    if grade not in classes_by_grade:
                        classes_by_grade[grade] = []
                    classes_by_grade[grade].append(cls)
            
            text = "📋 *Все доступные классы:*\n\n"
            for grade in sorted(classes_by_grade.keys(), key=int):
                text += f"*{grade} класс:* {', '.join(sorted(classes_by_grade[grade]))}\n"
            
            text += f"\n📊 Всего: {len(classes)} классов"
            
            bot.send_message(message.chat.id, text, parse_mode='MarkdownV2', reply_markup=create_main_keyboard())
        else:
            bot.send_message(message.chat.id, 
                           "❌ Классы не найдены\\. Используйте /update", 
                           parse_mode='MarkdownV2',
                           reply_markup=create_main_keyboard())
    except Exception as e:
        logger.error(f"Ошибка получения классов: {e}")
        error_msg = escape_markdown(str(e))
        bot.send_message(message.chat.id, f"❌ Ошибка: {error_msg}", parse_mode='MarkdownV2', reply_markup=create_main_keyboard())

@bot.message_handler(commands=['teacher'])
def teacher_command(message):
    """Поиск расписания по учителю"""
    args = message.text.split()
    if len(args) < 2:
        set_user_state(message.chat.id, 'waiting_for_teacher_full')
        
        bot.send_message(
            message.chat.id,
            "👨‍🏫 *Режим поиска учителя \\(полная фамилия\\)*\n\n"
            "✏️ *Введите полную фамилию учителя:*\n"
            "Например: Протасова, ИНКИНА\n\n"
            "Используйте команду /teachers или кнопку '🔍 Поиск учителя \\(часть фамилии\\)' если не знаете полную фамилию\\.",
            parse_mode='MarkdownV2',
            reply_markup=create_search_keyboard('teacher')
        )
        return
    
    teacher_name = ' '.join(args[1:])
    search_teacher_full(message, teacher_name)

@bot.message_handler(commands=['teachers'])
def search_teachers_command(message):
    """Поиск учителей по части фамилии"""
    args = message.text.split()
    if len(args) < 2:
        clear_user_state(message.chat.id)
        
        bot.send_message(
            message.chat.id,
            "🔍 *Поиск учителей по части фамилии:*\n\n"
            "✏️ *Введите часть фамилии:*\n"
            "Например: про, инк, шум\n\n"
            "ℹ️ *Теперь бот покажет расписание для каждого найденного учителя\\!*",
            parse_mode='MarkdownV2',
            reply_markup=create_main_keyboard()
        )
        return
    
    search_query = args[1]
    search_teacher_partial(message, search_query)
    
@bot.message_handler(commands=['room', 'cabinet', 'кабинет'])
def room_command(message):
    """Поиск расписания по кабинету"""
    args = message.text.split()
    if len(args) < 2:
        set_user_state(message.chat.id, 'waiting_for_room_full')
        
        bot.send_message(
            message.chat.id,
            "🏫 *Режим поиска кабинета \\(полный номер\\)*\n\n"
            "✏️ *Введите полный номер кабинета:*\n"
            "Например: 164, 243, 1 ГРУППА 456\n\n"
            "ℹ️ *Поиск по части номера кабинета больше не доступен\\.*\n"
            "Вводите только полный номер кабинета\\.",
            parse_mode='MarkdownV2',
            reply_markup=create_search_keyboard('room')
        )
        return
    
    room_number = ' '.join(args[1:])
    search_room_full(message, room_number)

@bot.message_handler(commands=['about', 'info'])
def about_command(message):
    """Информация о боте"""
    clear_user_state(message.chat.id)
    
    about_text = (
        "ℹ️ *Информация о боте:*\n\n"
        "🤖 *Школьный бот расписания*\n"
        "Версия: 4\\.0 \\(с улучшенным поиском учителей\\)\n\n"
        "📊 *Функционал:*\n"
        "• Поиск расписания по классам\n"
        "• Поиск расписания по учителям \\(полная фамилия\\)\n"
        "• Поиск учителей по части фамилии \\(с выводом расписания\\)\n"
        "• Поиск расписания по кабинетам \\(полный номер\\)\n"
        "• Автоматическое обновление данных\n"
        "• Удобный интерфейс с кнопками\n\n"
        "⚠️ *Важная информация:*\n"
        "1\\. Данные берутся с официального сайта школы\n"
        "2\\. В расписании могут быть опечатки\n"
        "3\\. Рекомендуем искать по первым символам фамилии/номера\n"
        "4\\. Бот не несёт ответственности за неточности в расписании\n\n"
        "🎓 *Бот создан для образовательных целей*\n"
        "Тестирование показало хорошие результаты работы\n\n"
        "🔧 *Техническая информация:*\n"
        "• Данные обновляются командой /update\n"
        "• Работает на платформе Railway\n"
        "• Исходный код: закрытый\n\n"
        "📞 *Поддержка:*\n"
        "По вопросам работы бота обращайтесь к администратору\\."
    )
    
    bot.send_message(
        message.chat.id,
        about_text,
        parse_mode='MarkdownV2',
        reply_markup=create_main_keyboard()
    )

@bot.message_handler(commands=['stats'])
def stats_command(message):
    """Статистика бота"""
    if not LOCAL_MODULES:
        bot.send_message(message.chat.id, "❌ Модули не загружены", reply_markup=create_main_keyboard())
        return
    
    clear_user_state(message.chat.id)
    
    try:
        classes = modules['schedule_parser'].get_available_classes()
        teacher_index = modules['schedule_parser'].get_cached_teacher_index()
        
        file_exists = modules['schedule_parser'].has_schedule_file()
        file_info = ""
        
        if file_exists and os.path.exists('school_schedule.csv'):
            file_size = os.path.getsize('school_schedule.csv')
            file_info = f"Размер файла: {file_size} байт\n"
        
        stats_text = (
            f"📊 *Статистика бота:*\n\n"
            f"📋 *Классы:* {len(classes) if classes else 0}\n"
            f"👨‍🏫 *Учителя:* {len(teacher_index) if teacher_index else 0}\n"
            f"{file_info}"
            f"🔄 *Последнее обновление:* {time.strftime('%d\\.%m\\.%Y %H:%M')}\n\n"
            f"✅ *Статус:* {'Работает нормально' if file_exists else 'Требуется обновление'}\n\n"
            f"💡 Используйте /update для обновления данных"
        )
        
        bot.send_message(message.chat.id, stats_text, parse_mode='MarkdownV2', reply_markup=create_main_keyboard())
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        error_msg = escape_markdown(str(e))
        bot.send_message(message.chat.id, f"❌ Ошибка: {error_msg}", parse_mode='MarkdownV2', reply_markup=create_main_keyboard())

# ====== ОБРАБОТЧИКИ КНОПОК ======
@bot.message_handler(func=lambda message: message.text == "📋 Найти класс")
def handle_find_class_button(message):
    """Обработка кнопки 'Найти класс'"""
    schedule_command(message)

@bot.message_handler(func=lambda message: message.text == "👨‍🏫 Найти учителя")
def handle_find_teacher_button(message):
    """Обработка кнопки 'Найти учителя' (полная фамилия)"""
    set_user_state(message.chat.id, 'waiting_for_teacher_full')
    
    bot.send_message(
        message.chat.id,
        "👨‍🏫 *Режим поиска учителя \\(полная фамилия\\)*\n\n"
        "✏️ *Введите полную фамилию учителя:*\n"
        "Например: Протасова, ИНКИНА\n\n"
        "🔍 *Особенности:*\n"
        "• Ищет точное совпадение фамилии\n"
        "• Учитывает составных учителей \\(ИНКИНА/ЛАТЫШЕВА\\)\n"
        "• Правильно распределяет кабинеты\n\n"
        "⚠️ *Внимание:* Теперь любой ваш текст будет восприниматься как поиск учителя\n"
        "Для выхода из режима поиска нажмите кнопку '🔙 Назад к меню'",
        parse_mode='MarkdownV2',
        reply_markup=create_search_keyboard('teacher')
    )

@bot.message_handler(func=lambda message: message.text == "🔍 Поиск учителя (часть фамилии)")
def handle_search_teacher_partial_button(message):
    """Обработка кнопки 'Поиск учителя (часть фамилии)'"""
    set_user_state(message.chat.id, 'waiting_for_teacher_partial')
    
    bot.send_message(
        message.chat.id,
        "🔍 *Режим поиска учителя \\(часть фамилии\\)*\n\n"
        "✏️ *Введите часть фамилии учителя:*\n"
        "Например: про, инк, шум\n\n"
        "ℹ️ *Новая функция\\!* Бот покажет расписание для каждого найденного учителя\\!\n\n"
        "⚠️ *Внимание:* Теперь любой ваш текст будет восприниматься как поиск учителя\n"
        "Для выхода из режима поиска нажмите кнопку '🔙 Назад к меню'",
        parse_mode='MarkdownV2',
        reply_markup=create_search_keyboard('teacher')
    )

@bot.message_handler(func=lambda message: message.text == "🏫 Найти кабинет")
def handle_find_room_button(message):
    """Обработка кнопки 'Найти кабинет' (полный номер)"""
    set_user_state(message.chat.id, 'waiting_for_room_full')
    
    bot.send_message(
        message.chat.id,
        "🏫 *Режим поиска кабинета \\(полный номер\\)*\n\n"
        "✏️ *Введите полный номер кабинета:*\n"
        "Например: 164, 243, 1 ГРУППА 456\n\n"
        "ℹ️ *Поиск по части номера больше не доступен\\. Вводите только полный номер\\!*\n\n"
        "⚠️ *Внимание:* Теперь любой ваш текст будет восприниматься как поиск кабинета\n"
        "Для выхода из режима поиска нажмите кнопку '🔙 Назад к меню'",
        parse_mode='MarkdownV2',
        reply_markup=create_search_keyboard('room')
    )

@bot.message_handler(func=lambda message: message.text == "🔄 Обновить")
def handle_update_button(message):
    """Обработка кнопки 'Обновить'"""
    update_command(message)

@bot.message_handler(func=lambda message: message.text == "❓ Помощь")
def handle_help_button(message):
    """Обработка кнопки 'Помощь'"""
    clear_user_state(message.chat.id)
    
    help_text = (
        "❓ *Помощь по использованию бота:*\n\n"
        
        "🎯 *Как найти расписание класса:*\n"
        "1\\. Нажмите кнопку '📋 Найти класс'\n"
        "2\\. Введите номер класса\n"
        "3\\. Например: 5А, 10Е, 8 Б\n\n"
        
        "👨‍🏫 *Как найти расписание учителя \\(полная фамилия\\):*\n"
        "1\\. Нажмите кнопку '👨‍🏫 Найти учителя'\n"
        "2\\. Введите полную фамилию учителя\n"
        "3\\. *Важно:* В расписании могут быть опечатки\n"
        "4\\. *Совет:* Используйте поиск по части фамилии если не знаете точное написание\n\n"
        
        "🔍 *Поиск учителя по части фамилии \\(НОВАЯ ФУНКЦИЯ\\):*\n"
        "1\\. Нажмите кнопку '🔍 Поиск учителя \\(часть фамилии\\)'\n"
        "2\\. Введите часть фамилии\n"
        "3\\. Например: про, инк, шум\n"
        "4\\. *Бот покажет расписание для каждого найденного учителя\\!*\n\n"
        
        "🏫 *Как найти расписание кабинета \\(полный номер\\):*\n"
        "1\\. Нажмите кнопку '🏫 Найти кабинет'\n"
        "2\\. Введите полный номер кабинета\n"
        "3\\. Например: 164, 243, 1 ГРУППА 456\n"
        "4\\. *Важно:* Учитывайте составные кабинеты \\(453\\\\241\\)\n"
        "5\\. *Поиск по части номера больше не доступен\\!*\n\n"
        
        "🔄 *Как обновить расписание:*\n"
        "\\- Нажмите кнопку '🔄 Обновить'\n"
        "\\- Или отправьте команду /update\n\n"
        
        "🔙 *Как выйти из режима поиска:*\n"
        "\\- В режиме поиска нажмите кнопку '🔙 Назад к меню'\n\n"
        
        "⚠️ *Важная информация:*\n"
        "• Данные автоматически обновляются\n"
        "• В расписании возможны опечатки\n"
        "• Бот не несёт ответственности за неточности\n"
        "• Проект создан для образовательных целей\n\n"
        
        "📞 *Если возникли проблемы:*\n"
        "1\\. Попробуйте обновить данные \\(/update\\)\n"
        "2\\. Проверьте написание класса/фамилии/номера\n"
        "3\\. Используйте поиск по части фамилии для учителей\n"
        "4\\. Обратитесь к администратору\n\n"
        
        "💡 *Быстрые команды:*\n"
        "/start \\- главное меню\n"
        "/help \\- эта справка\n"
        "/about \\- информация о боте\n"
        "/stats \\- статистика\n"
        "/classes \\- все классы\n"
        "/teacher \\<фамилия\\> \\- найти учителя\n"
        "/teachers \\<часть\\> \\- поиск учителей \\(с расписанием\\)\n"
        "/room \\<номер\\> \\- найти кабинет"
    )
    
    bot.send_message(
        message.chat.id,
        help_text,
        parse_mode='MarkdownV2',
        reply_markup=create_main_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == "ℹ️ О боте")
def handle_about_button(message):
    """Обработка кнопки 'О боте'"""
    about_command(message)

@bot.message_handler(func=lambda message: message.text == "🔙 Назад к меню")
def handle_back_button(message):
    """Обработка кнопки 'Назад к меню'"""
    clear_user_state(message.chat.id)
    
    bot.send_message(
        message.chat.id,
        "✅ Вы вернулись в главное меню\n\n"
        "Выберите действие с помощью кнопок ниже:",
        reply_markup=create_main_keyboard()
    )

# ====== ОБРАБОТЧИКИ ТЕКСТА С УЧЕТОМ СОСТОЯНИЙ ======
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    """Обработка текстовых сообщений с учетом состояний"""
    user_input = message.text.strip()
    user_id = message.chat.id
    current_state = get_user_state(user_id)
    
    # Проверяем, если это не обычный текст (уже обработанные кнопки)
    main_buttons = [
        "📋 Найти класс", "👨‍🏫 Найти учителя", "🔍 Поиск учителя (часть фамилии)",
        "🏫 Найти кабинет", "🔄 Обновить", "❓ Помощь", "ℹ️ О боте", "🔙 Назад к меню"
    ]
    if user_input in main_buttons:
        return
    
    if not LOCAL_MODULES:
        bot.send_message(message.chat.id, "❌ Модули не загружены", reply_markup=create_main_keyboard())
        return
    
    if not modules['schedule_parser'].has_schedule_file():
        bot.send_message(
            message.chat.id,
            "❌ *Файл расписания не найден\\!*\n\n"
            "📥 Используйте команду /update чтобы скачать актуальное расписание\\.",
            parse_mode='MarkdownV2',
            reply_markup=create_main_keyboard()
        )
        return
    
    try:
        # Обработка в зависимости от состояния
        if current_state == 'waiting_for_class':
            search_class_schedule(message, user_input)
            
        elif current_state == 'waiting_for_teacher_full':
            search_teacher_full(message, user_input)
            
        elif current_state == 'waiting_for_teacher_partial':
            search_teacher_partial(message, user_input)
            
        elif current_state == 'waiting_for_room_full':
            search_room_full(message, user_input)
            
        else:
            # Обычный режим - пытаемся определить, что хочет пользователь
            if re.match(r'^\d+\s*[А-Яа-яA-Za-z]$', user_input, re.IGNORECASE):
                # Это класс
                set_user_state(user_id, 'waiting_for_class')
                bot.send_message(
                    user_id,
                    f"🔍 Ищу расписание для класса {escape_markdown(user_input)}\\.\\.\\.\n"
                    f"⚠️ Теперь вы в режиме поиска класса\\. Для выхода нажмите '🔙 Назад к меню'",
                    parse_mode='MarkdownV2',
                    reply_markup=create_search_keyboard('class')
                )
                search_class_schedule(message, user_input)
            elif re.match(r'^\d+$', user_input):
                # Это номер кабинета (только цифры) - пробуем как кабинет
                set_user_state(user_id, 'waiting_for_room_full')
                bot.send_message(
                    user_id,
                    f"🔍 Ищу расписание для кабинета {escape_markdown(user_input)}\\.\\.\\.\n"
                    f"⚠️ Теперь вы в режиме поиска кабинета\\. Для выхода нажмите '🔙 Назад к меню'",
                    parse_mode='MarkdownV2',
                    reply_markup=create_search_keyboard('room')
                )
                search_room_full(message, user_input)
            else:
                # Пробуем как поиск учителя по части фамилии
                set_user_state(user_id, 'waiting_for_teacher_partial')
                bot.send_message(
                    user_id,
                    f"🔍 Ищу учителей по запросу '{escape_markdown(user_input)}'\\.\\.\\.\n"
                    f"⚠️ Теперь вы в режиме поиска учителя\\. Для выхода нажмите '🔙 Назад к меню'",
                    parse_mode='MarkdownV2',
                    reply_markup=create_search_keyboard('teacher')
                )
                search_teacher_partial(message, user_input)
            
    except Exception as e:
        logger.error(f"Ошибка обработки запроса '{user_input}': {e}")
        error_msg = escape_markdown(str(e)) if str(e) else "Неизвестная ошибка"
        bot.send_message(
            message.chat.id,
            f"❌ *Ошибка при обработке запроса:* {error_msg}\n\n"
            "💡 *Попробуйте:*\n"
            "1\\. Проверить написание\n"
            "2\\. Обновить расписание /update\n"
            "3\\. Обратиться к администратору",
            parse_mode='MarkdownV2',
            reply_markup=create_main_keyboard()
        )

def search_room_full(message, room_number):
    """Поиск кабинета по полному номеру"""
    try:
        schedule_by_day = modules['schedule_parser'].get_room_schedule(room_number)
        
        if not schedule_by_day:
            escaped_room = escape_markdown(room_number)
            bot.send_message(
                message.chat.id,
                f"❌ Кабинет *{escaped_room}* не найден\\.\n\n"
                "Возможные причины:\n"
                "• Опечатка в номере кабинета\n"
                "• Кабинет не используется в расписании\n"
                "• Номер написан по\\-другому \\(например, 1 ГРУППА 456\\)\n\n"
                "💡 *Важно:* Поиск по части номера больше не доступен\\!",
                parse_mode='MarkdownV2',
                reply_markup=create_search_keyboard('room')
            )
            return
        
        response_text = modules['schedule_parser'].format_room_schedule(room_number, schedule_by_day)
        
        bot.send_message(
            message.chat.id,
            response_text,
            parse_mode='MarkdownV2',
            reply_markup=create_search_keyboard('room')
        )
        
    except Exception as e:
        logger.error(f"Ошибка поиска кабинета {room_number}: {e}")
        error_msg = escape_markdown(str(e)) if str(e) else "Неизвестная ошибка"
        bot.send_message(
            message.chat.id,
            f"❌ Ошибка при поиске кабинета: {error_msg}",
            parse_mode='MarkdownV2',
            reply_markup=create_search_keyboard('room')
        )

# ====== ФУНКЦИИ ПОИСКА ======
def search_class_schedule(message, class_name):
    """Поиск расписания для класса"""
    try:
        schedules = modules['schedule_parser'].get_schedule_for_class(class_name)
        
        if not schedules:
            escaped_class = escape_markdown(class_name)
            bot.send_message(
                message.chat.id,
                f"❌ Класс *{escaped_class}* не найден\\.\n\n"
                "Попробуйте:\n"
                "• Другой формат \\(5А, 5 А, 5а\\)\n"
                "• Команду /classes для списка всех классов",
                parse_mode='MarkdownV2',
                reply_markup=create_search_keyboard('class')
            )
            return
        
        message_text = modules['schedule_parser'].format_class_schedule(class_name, schedules)
        
        bot.send_message(
            message.chat.id,
            message_text,
            parse_mode='MarkdownV2',
            reply_markup=create_search_keyboard('class')
        )
        
    except Exception as e:
        logger.error(f"Ошибка поиска класса {class_name}: {e}")
        error_msg = escape_markdown(str(e)) if str(e) else "Неизвестная ошибка"
        bot.send_message(
            message.chat.id,
            f"❌ Ошибка при поиске класса: {error_msg}",
            parse_mode='MarkdownV2',
            reply_markup=create_search_keyboard('class')
        )

def search_teacher_full(message, teacher_name):
    """Поиск учителя по полной фамилии"""
    try:
        schedule_by_day = modules['schedule_parser'].get_teacher_schedule(teacher_name)
        
        if not schedule_by_day:
            escaped_teacher = escape_markdown(teacher_name)
            bot.send_message(
                message.chat.id,
                f"❌ Учитель *{escaped_teacher}* не найден\\.\n\n"
                "Попробуйте:\n"
                "• Проверить написание фамилии\n"
                "• Использовать поиск по части фамилии \\(кнопка '🔍 Поиск учителя'\\)\n"
                "• Искать по первым буквам фамилии",
                parse_mode='MarkdownV2',
                reply_markup=create_search_keyboard('teacher')
            )
            return
        
        response_text = modules['schedule_parser'].format_teacher_schedule(teacher_name, schedule_by_day)
        
        bot.send_message(
            message.chat.id,
            response_text,
            parse_mode='MarkdownV2',
            reply_markup=create_search_keyboard('teacher')
        )
        
    except Exception as e:
        logger.error(f"Ошибка поиска учителя {teacher_name}: {e}")
        error_msg = escape_markdown(str(e)) if str(e) else "Неизвестная ошибка"
        bot.send_message(
            message.chat.id,
            f"❌ Ошибка при поиске учителя: {error_msg}",
            parse_mode='MarkdownV2',
            reply_markup=create_search_keyboard('teacher')
        )

def search_teacher_partial(message, search_query):
    """Поиск учителей по части фамилии с выводом расписания"""
    try:
        matches = modules['schedule_parser'].search_teachers_by_substring(search_query)
        
        if not matches:
            escaped_query = escape_markdown(search_query)
            bot.send_message(
                message.chat.id,
                f"🔍 *По запросу '{escaped_query}' учителей не найдено\\.*\n\n"
                "Возможные причины:\n"
                "• Опечатка в запросе\n"
                "• Учитель не ведет уроки в расписании\n"
                "• Фамилия написана по\\-другому\n\n"
                "💡 *Совет:* Попробуйте:\n"
                "• Первые 2\\-3 буквы фамилии\n"
                "• Поиск по полной фамилии \\(кнопка '👨‍🏫 Найти учителя'\\)",
                parse_mode='MarkdownV2',
                reply_markup=create_search_keyboard('teacher')
            )
            return
        
        escaped_query = escape_markdown(search_query)
        bot.send_message(
            message.chat.id,
            f"🔍 *Найдено учителей \\({len(matches)}\\) по запросу '{escaped_query}':*\n\n"
            f"*Список учителей:* {', '.join([escape_markdown(t) for t in matches])}\n\n"
            f"*Теперь показываю расписание для каждого учителя:*\n"
            f"〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️",
            parse_mode='MarkdownV2',
            reply_markup=create_search_keyboard('teacher')
        )
        
        # Показываем расписание для каждого найденного учителя
        for teacher in matches:
            try:
                schedule_by_day = modules['schedule_parser'].get_teacher_schedule(teacher)
                if schedule_by_day:
                    response_text = modules['schedule_parser'].format_teacher_schedule(teacher, schedule_by_day)
                    bot.send_message(
                        message.chat.id,
                        response_text,
                        parse_mode='MarkdownV2',
                        reply_markup=create_search_keyboard('teacher')
                    )
                    # Небольшая задержка между сообщениями
                    time.sleep(0.5)
            except Exception as e:
                logger.error(f"Ошибка при получении расписания для {teacher}: {e}")
                continue
        
        bot.send_message(
            message.chat.id,
            f"✅ *Готово\\! Показано расписание для {len(matches)} учителей\\.*\n\n"
            f"💡 *Для поиска другого учителя:*\n"
            f"• Введите другую часть фамилии\n"
            f"• Или нажмите '🔙 Назад к меню'",
            parse_mode='MarkdownV2',
            reply_markup=create_search_keyboard('teacher')
        )
        
    except Exception as e:
        logger.error(f"Ошибка поиска учителей {search_query}: {e}")
        error_msg = escape_markdown(str(e)) if str(e) else "Неизвестная ошибка"
        bot.send_message(
            message.chat.id,
            f"❌ Ошибка при поиске: {error_msg}",
            parse_mode='MarkdownV2',
            reply_markup=create_search_keyboard('teacher')
        )

# ====== ЗАПУСК БОТА ======
def main():
    """Основная функция"""
    logger.info("=" * 60)
    logger.info("🤖 ШКОЛЬНЫЙ БОТ ЗАПУСКАЕТСЯ")
    logger.info("=" * 60)
    
    global user_states
    user_states = {}
    logger.info("✅ Система состояний инициализирована")
    
    if LOCAL_MODULES:
        if os.path.exists('school_schedule.csv'):
            logger.info("✅ Файл расписания найден")
            
            try:
                teacher_index = modules['schedule_parser'].get_cached_teacher_index()
                logger.info(f"✅ Индекс учителей создан: {len(teacher_index)} учителей")
            except Exception as e:
                logger.error(f"⚠️ Ошибка создания индекса учителей: {e}")
        else:
            logger.info("📭 Файл расписания не найден")
            logger.info("ℹ️  Используйте /update в боте для загрузки")
    
    while True:
        try:
            logger.info("🔄 Запуск polling...")
            bot.polling(none_stop=True, interval=2, timeout=30)
        except Exception as e:
            logger.error(f"❌ Ошибка polling: {e}")
            logger.info("⏳ Перезапуск через 10 секунд...")
            time.sleep(10)

if __name__ == '__main__':
    main()