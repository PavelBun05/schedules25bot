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
            # Формат: "123456789,987654321"
            config['ADMIN_IDS'] = [int(id.strip()) for id in admin_ids_env.split(',') if id.strip()]
            logger.info(f"✅ ID администраторов из переменных окружения: {len(config['ADMIN_IDS'])}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось распарсить ADMIN_IDS: {e}")
    
    # ПРИОРИТЕТ 2: Файл config.py (только если в окружении нет токена)
    if not config['TELEGRAM_BOT_TOKEN']:
        try:
            # Проверяем наличие config.py
            if os.path.exists('config.py'):
                from config import TELEGRAM_BOT_TOKEN, ADMIN_IDS
                config['TELEGRAM_BOT_TOKEN'] = TELEGRAM_BOT_TOKEN
                # Объединяем ID из файла с ID из окружения
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
        return False, f"❌ Ошибка: {str(e)}"

def create_main_keyboard():
    """Создает основную клавиатуру с кнопками"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    buttons = [
        "📋 Найти класс",
        "👨‍🏫 Найти учителя",
        "🔄 Обновить",
        "❓ Помощь",
        "ℹ️ О боте"
    ]
    
    for button in buttons:
        keyboard.add(types.KeyboardButton(button))
    
    return keyboard

def create_classes_keyboard():
    """Создает клавиатуру для поиска класса"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("⬅️ Назад"))
    return keyboard

def create_teachers_keyboard():
    """Создает клавиатуру для поиска учителя"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("⬅️ Назад"))
    return keyboard

def create_back_keyboard():
    """Создает клавиатуру только с кнопкой Назад"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("⬅️ Назад"))
    return keyboard

# ====== ОБРАБОТЧИКИ КОМАНД ======

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Обработчик команд /start и /help"""
    welcome_text = (
        "👋 *Добро пожаловать в школьный бот расписания!*\n\n"
        "Я помогу вам быстро найти расписание уроков.\n\n"
        "🎯 *Основные возможности:*\n"
        "• Поиск расписания по классу\n"
        "• Поиск расписания по учителю\n"
        "• Автоматическое обновление данных\n\n"
        "📱 *Используйте кнопки ниже для навигации*\n\n"
        "💡 *Совет:* Начните с кнопки 'Найти класс' или 'Найти учителя'"
    )
    
    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

@bot.message_handler(commands=['update'])
def update_command(message):
    """Обновление расписания"""
    if ADMIN_IDS and message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Эта команда доступна только администраторам.")
        return
    
    bot.send_message(
        message.chat.id,
        "🔄 Обновляю расписание с сайта...",
        reply_markup=create_back_keyboard()
    )
    
    success, msg = update_schedule_file()
    
    if success:
        bot.send_message(message.chat.id, msg)
    else:
        bot.send_message(message.chat.id, msg)

@bot.message_handler(commands=['schedule', 'class'])
def schedule_command(message):
    """Запрос расписания класса"""
    bot.send_message(
        message.chat.id,
        "📋 *Введите номер класса:*\n\n"
        "Например: 5А, 10Е, 8 Б\n\n"
        "💡 Просто отправьте номер класса",
        parse_mode='Markdown',
        reply_markup=create_classes_keyboard()
    )

@bot.message_handler(commands=['classes'])
def classes_command(message):
    """Список всех классов"""
    if not LOCAL_MODULES:
        bot.send_message(message.chat.id, "❌ Модули не загружены")
        return
    
    try:
        classes = modules['schedule_parser'].get_available_classes()
        if classes:
            # Разделяем классы по параллелям
            classes_by_grade = {}
            for cls in classes:
                match = re.search(r'(\d+)([А-Я])', cls)
                if match:
                    grade = match.group(1)
                    if grade not in classes_by_grade:
                        classes_by_grade[grade] = []
                    classes_by_grade[grade].append(cls)
            
            # Формируем сообщение
            text = "📋 *Все доступные классы:*\n\n"
            for grade in sorted(classes_by_grade.keys(), key=int):
                text += f"*{grade} класс:* {', '.join(sorted(classes_by_grade[grade]))}\n"
            
            text += f"\n📊 Всего: {len(classes)} классов"
            
            bot.send_message(message.chat.id, text, parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, 
                           "❌ Классы не найдены. Используйте /update", 
                           parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Ошибка получения классов: {e}")
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}", parse_mode='Markdown')

@bot.message_handler(commands=['teacher'])
def teacher_command(message):
    """Поиск расписания по учителю"""
    args = message.text.split()
    if len(args) < 2:
        bot.send_message(
            message.chat.id,
            "👨‍🏫 *Поиск расписания учителя:*\n\n"
            "✏️ *Введите фамилию учителя:*\n"
            "Например: Протасова\n\n"
            "🔍 *Совет:* Можно ввести первые буквы фамилии\n"
            "Например: про\n\n"
            "✏️ Введите фамилию учителя или первые буквы фамилии",
            parse_mode='Markdown',
            reply_markup=create_teachers_keyboard()
        )
        return
    
    teacher_name = ' '.join(args[1:])
    search_teacher_schedule(message, teacher_name)

@bot.message_handler(commands=['teachers'])
def search_teachers_command(message):
    """Поиск учителей по части фамилии"""
    args = message.text.split()
    if len(args) < 2:
        bot.send_message(
            message.chat.id,
            "🔍 *Поиск учителей:*\n\n"
            "✏️ *Введите часть фамилии:*\n"
            "Например: про\n\n"
            "📝 *Найдет:* Протасова, Прокопьев и т.д.\n\n"
            "⚠️ *Важно:* В оригинальном расписании могут быть опечатки, "
            "поэтому лучше искать по первым символам фамилии.",
            parse_mode='Markdown',
            reply_markup=create_back_keyboard()
        )
        return
    
    search_query = args[1]
    search_teacher_by_partial(message, search_query)

@bot.message_handler(commands=['about', 'info'])
def about_command(message):
    """Информация о боте"""
    about_text = (
        "ℹ️ *Информация о боте:*\n\n"
        "🤖 *Школьный бот расписания*\n"
        "Версия: 2.0\n\n"
        "📊 *Функционал:*\n"
        "• Поиск расписания по классам\n"
        "• Поиск расписания по учителям\n"
        "• Автоматическое обновление данных\n"
        "• Удобный интерфейс с кнопками\n\n"
        "⚠️ *Важная информация:*\n"
        "1. Данные берутся с официального сайта школы\n"
        "2. В расписании могут быть опечатки\n"
        "3. Рекомендуем искать учителей по первым символам фамилии\n"
        "4. Бот не несёт ответственности за неточности в расписании\n\n"
        "🎓 *Бот создан для образовательных целей*\n"
        "Тестирование показало хорошие результаты работы\n\n"
        "🔧 *Техническая информация:*\n"
        "• Данные обновляются командой /update\n"
        "• Работает на платформе Railway\n"
        "• Исходный код: закрытый\n\n"
        "📞 *Поддержка:*\n"
        "По вопросам работы бота обращайтесь к администратору."
    )
    
    bot.send_message(
        message.chat.id,
        about_text,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

@bot.message_handler(commands=['stats'])
def stats_command(message):
    """Статистика бота"""
    if not LOCAL_MODULES:
        bot.send_message(message.chat.id, "❌ Модули не загружены")
        return
    
    try:
        # Получаем статистику
        classes = modules['schedule_parser'].get_available_classes()
        teacher_index = modules['schedule_parser'].get_cached_teacher_index()
        
        # Проверяем файл расписания
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
            f"🔄 *Последнее обновление:* {time.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"✅ *Статус:* {'Работает нормально' if file_exists else 'Требуется обновление'}\n\n"
            f"💡 Используйте /update для обновления данных"
        )
        
        bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}", parse_mode='Markdown')

# ====== ОБРАБОТЧИКИ КНОПОК ======

@bot.message_handler(func=lambda message: message.text == "📋 Найти класс")
def handle_find_class_button(message):
    """Обработка кнопки 'Найти класс'"""
    schedule_command(message)

@bot.message_handler(func=lambda message: message.text == "👨‍🏫 Найти учителя")
def handle_find_teacher_button(message):
    """Обработка кнопки 'Найти учителя'"""
    teacher_command(message)

@bot.message_handler(func=lambda message: message.text == "🔄 Обновить")
def handle_update_button(message):
    """Обработка кнопки 'Обновить'"""
    update_command(message)

@bot.message_handler(func=lambda message: message.text == "❓ Помощь")
def handle_help_button(message):
    """Обработка кнопки 'Помощь'"""
    help_text = (
        "❓ *Помощь по использованию бота:*\n\n"
        
        "🎯 *Как найти расписание класса:*\n"
        "1. Нажмите кнопку '📋 Найти класс'\n"
        "2. Введите номер класса\n"
        "3. Например: 5А, 10Е, 8 Б\n\n"
        
        "👨‍🏫 *Как найти расписание учителя:*\n"
        "1. Нажмите кнопку '👨‍🏫 Найти учителя'\n"
        "2. Введите фамилию учителя или первые буквы\n"
        "3. *Важно:* В расписании могут быть опечатки\n"
        "4. *Совет:* Ищите по первым символам фамилии\n"
        "   Например: 'про' для Протасова\n\n"
        
        "🔍 *Поиск учителя по части фамилии:*\n"
        "• Отправьте команду /teachers <часть>\n"
        "• Например: /teachers про\n"
        "• Бот покажет всех учителей с такой частью фамилии\n\n"
        
        "⚠️ *Важная информация:*\n"
        "• Данные автоматически обновляются\n"
        "• В расписании возможны опечатки\n"
        "• Бот не несёт ответственности за неточности\n"
        "• Проект создан для образовательных целей\n\n"
        
        "📞 *Если возникли проблемы:*\n"
        "1. Попробуйте обновить данные (/update)\n"
        "2. Проверьте написание класса/фамилии\n"
        "3. Используйте поиск по части фамилии\n"
        "4. Обратитесь к администратору\n\n"
        
        "💡 *Быстрые команды:*\n"
        "/start - главное меню\n"
        "/help - эта справка\n"
        "/about - информация о боте\n"
        "/stats - статистика\n"
        "/classes - все классы\n"
        "/teacher <фамилия> - найти учителя\n"
        "/teachers <часть> - поиск учителей"
    )
    
    bot.send_message(
        message.chat.id,
        help_text,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == "ℹ️ О боте")
def handle_about_button(message):
    """Обработка кнопки 'О боте'"""
    about_command(message)

@bot.message_handler(func=lambda message: message.text == "⬅️ Назад")
def handle_back_button(message):
    """Обработка кнопки 'Назад'"""
    bot.send_message(
        message.chat.id,
        "🔙 Возвращаюсь в главное меню...",
        reply_markup=create_main_keyboard()
    )

# ====== ОБРАБОТЧИКИ ТЕКСТА ======

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    """Обработка текстовых сообщений"""
    user_input = message.text.strip()
    
    if not LOCAL_MODULES:
        bot.send_message(message.chat.id, "❌ Модули не загружены")
        return
    
    if not modules['schedule_parser'].has_schedule_file():
        bot.send_message(
            message.chat.id,
            "❌ *Файл расписания не найден!*\n\n"
            "📥 Используйте команду /update чтобы скачать актуальное расписание.",
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        return
    
    try:
        # Проверяем, является ли ввод классом (цифра + буква)
        if re.match(r'^\d+\s*[А-Яа-яA-Za-z]$', user_input, re.IGNORECASE):
            # Это класс
            search_class_schedule(message, user_input)
        else:
            # Пробуем найти как учителя
            search_teacher_schedule(message, user_input)
            
    except Exception as e:
        logger.error(f"Ошибка обработки запроса '{user_input}': {e}")
        bot.send_message(
            message.chat.id,
            f"❌ *Ошибка при обработке запроса:* {str(e)}\n\n"
            "💡 *Попробуйте:*\n"
            "1. Проверить написание\n"
            "2. Обновить расписание /update\n"
            "3. Обратиться к администратору",
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )

# ====== ФУНКЦИИ ПОИСКА ======

def search_class_schedule(message, class_name):
    """Поиск расписания для класса"""
    try:
        groups = modules['schedule_parser'].get_schedule_for_class_all_positions(class_name)
        
        if groups is None or not groups:
            bot.send_message(
                message.chat.id,
                f"❌ Класс {class_name} не найден.\n\n"
                "Попробуйте:\n"
                "• Другой формат (5А, 5 А, 5а)\n"
                "• Команду /classes для списка всех классов",
                reply_markup=create_classes_keyboard()
            )
            return
        
        message_text = modules['schedule_parser'].format_class_schedule_groups(class_name, groups)
        
        # Минимальное предупреждение
        message_text += "\n\nРасписание может содержать изменения."
        
        bot.send_message(
            message.chat.id,
            message_text,
            reply_markup=create_classes_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка поиска класса {class_name}: {e}")
        bot.send_message(
            message.chat.id,
            f"❌ Ошибка при поиске класса: {str(e)}",
            reply_markup=create_main_keyboard()
        )

def search_teacher_schedule(message, teacher_name):
    """Поиск расписания для учителя"""
    try:
        teacher_info = modules['schedule_parser'].get_schedule_by_teacher(teacher_name)
        
        if not teacher_info:
            bot.send_message(
                message.chat.id,
                f"❌ Учитель {teacher_name} не найден.\n\n"
                "Попробуйте:\n"
                "• Поиск по первым буквам\n"
                "• Команду /teachers {первые_буквы}",
                reply_markup=create_teachers_keyboard()
            )
            return
        
        response_text = modules['schedule_parser'].format_teacher_schedule(teacher_info)
        
        bot.send_message(
            message.chat.id,
            response_text,
            reply_markup=create_teachers_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка поиска учителя {teacher_name}: {e}")
        bot.send_message(
            message.chat.id,
            f"❌ Ошибка при поиске учителя: {str(e)}",
            reply_markup=create_main_keyboard()
        )

def search_teacher_by_partial(message, search_query):
    """Поиск учителей по части фамилии"""
    try:
        matches = modules['schedule_parser'].search_teachers_by_substring(search_query)
        response_text = modules['schedule_parser'].format_teachers_search_results(matches, search_query)
        
        bot.send_message(
            message.chat.id,
            response_text,
            parse_mode='Markdown',
            reply_markup=create_teachers_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка поиска учителей {search_query}: {e}")
        bot.send_message(
            message.chat.id,
            f"❌ Ошибка: {str(e)}",
            reply_markup=create_main_keyboard()
        )

# ====== ЗАПУСК БОТА ======

def main():
    """Основная функция"""
    logger.info("=" * 60)
    logger.info("🤖 ШКОЛЬНЫЙ БОТ ЗАПУСКАЕТСЯ")
    logger.info("=" * 60)
    
    # Проверяем файл расписания
    if LOCAL_MODULES:
        if os.path.exists('school_schedule.csv'):
            logger.info("✅ Файл расписания найден")
            
            # Инициализируем кэш учителей при запуске
            try:
                teacher_index = modules['schedule_parser'].get_cached_teacher_index()
                logger.info(f"✅ Индекс учителей создан: {len(teacher_index)} учителей")
            except Exception as e:
                logger.error(f"⚠️ Ошибка создания индекса учителей: {e}")
        else:
            logger.info("📭 Файл расписания не найден")
            logger.info("ℹ️  Используйте /update в боте для загрузки")
    
    # Запускаем бота с перезапуском при ошибках
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