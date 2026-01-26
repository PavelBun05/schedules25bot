import re

def escape_markdown(text):
    """Экранирует специальные символы MarkdownV2"""
    if not text:
        return ""
    
    # Список всех специальных символов в MarkdownV2
    # которые нужно экранировать
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

def read_schedule_file():
    """Читает файл расписания"""
    try:
        with open('school_schedule.csv', 'r', encoding='utf-8') as f:
            return f.readlines()
    except FileNotFoundError:
        return []

def normalize_name(name):
    """Нормализует имя (для класса или фамилии учителя)"""
    if not name:
        return ""
    return re.sub(r'\s+', '', name.strip().upper())

# ====== БАЗОВЫЕ ФУНКЦИИ ДЛЯ ПАРСИНГА ======

def split_by_slash(value):
    """Разбивает строку по слэшам"""
    if not value:
        return []
    parts = re.split(r'[\\\/]', value)
    return [part.strip() for part in parts if part.strip()]

def find_schedule_headers():
    """Находит все заголовки расписаний в файле"""
    lines = read_schedule_file()
    headers = []
    
    for line_num, line in enumerate(lines):
        line_upper = line.strip().upper()
        if 'РАСПИСАНИЕ НА' in line_upper:
            day_match = re.search(r'РАСПИСАНИЕ НА\s+(\w+)', line_upper)
            if day_match:
                day = day_match.group(1)
                headers.append({
                    'line_num': line_num,
                    'day': day,
                    'raw_line': line.strip()
                })
    
    headers.append({
        'line_num': len(lines),
        'day': 'КОНЕЦ_ФАЙЛА',
        'raw_line': ''
    })
    
    return headers

def get_day_for_line(line_num, headers):
    """Определяет день недели для строки"""
    for i in range(len(headers) - 1):
        if headers[i]['line_num'] <= line_num < headers[i+1]['line_num']:
            return headers[i]['day']
    return 'НЕИЗВЕСТНО'

# ====== ПОИСК КЛАССОВ ======

def find_class_positions(class_name):
    """Находит все позиции класса в файле"""
    normalized_target = normalize_name(class_name)
    lines = read_schedule_file()
    headers = find_schedule_headers()
    positions = []
    
    for line_num, line in enumerate(lines):
        cells = line.strip().split(',')
        for col_num, cell in enumerate(cells):
            cell_clean = cell.strip()
            if re.match(r'^\d+\s*[А-ЯA-Z](\s*[А-ЯA-Z])?$', cell_clean, re.IGNORECASE):
                if normalize_name(cell_clean) == normalized_target:
                    day = get_day_for_line(line_num, headers)
                    positions.append({
                        'line_num': line_num,
                        'col_num': col_num,
                        'class_name': cell_clean,
                        'day': day
                    })
    
    return positions

def get_lessons_for_position(position):
    """Получает уроки для класса в конкретной позиции"""
    lines = read_schedule_file()
    lessons = []
    
    line_num = position['line_num']
    col_num = position['col_num']
    headers = find_schedule_headers()
    base_day = position['day']
    
    i = line_num + 1
    
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        
        # Проверяем, не началось ли новое расписание
        current_day = get_day_for_line(i, headers)
        if current_day != base_day:
            break
        
        cells = line.split(',')
        
        # Проверяем, не началась ли новая таблица с классами
        has_new_classes = False
        for cell in cells:
            if re.match(r'^\d+\s*[А-ЯA-Z]', cell.strip(), re.IGNORECASE):
                has_new_classes = True
                break
        
        if has_new_classes:
            break
        
        # Проверяем строку со временем
        if len(cells) > 1:
            time_cell = cells[1].strip() if len(cells) > 1 else ""
            time_pattern = r'\d{1,2}\.\d{2}\s*[–\-]\s*\d{1,2}\.\d{2}'
            time_match = re.search(time_pattern, time_cell)
            
            if time_match:
                time_str = time_match.group(0)
                subject = ""
                teacher = ""
                classroom = ""
                
                # Предмет из строки выше
                if i - 1 >= 0:
                    prev_line = lines[i-1].strip()
                    prev_cells = prev_line.split(',')
                    if col_num < len(prev_cells):
                        subject = prev_cells[col_num].strip()
                
                # Учитель из текущей строки
                if col_num < len(cells):
                    teacher = cells[col_num].strip()
                
                # Кабинет из строки ниже
                if i + 1 < len(lines):
                    next_line = lines[i+1].strip()
                    next_cells = next_line.split(',')
                    if col_num < len(next_cells):
                        classroom = next_cells[col_num].strip()
                
                if subject or teacher or classroom:
                    lessons.append({
                        'time': time_str,
                        'subject': subject,
                        'teacher': teacher,
                        'classroom': classroom,
                        'class_name': position['class_name'],
                        'day': base_day
                    })
                
                i += 2
                continue
        
        i += 1
    
    return lessons

def get_schedule_for_class(class_name):
    """Получает все расписания для класса"""
    positions = find_class_positions(class_name)
    if not positions:
        return []
    
    all_schedules = []
    for pos in positions:
        lessons = get_lessons_for_position(pos)
        if lessons:
            all_schedules.append({
                'position_info': pos,
                'lessons': lessons
            })
    
    return all_schedules

def format_class_schedule(class_name, schedules):
    """Форматирует расписание класса для вывода"""
    if not schedules:
        escaped_class = escape_markdown(class_name)
        return f"Расписание для класса {escaped_class} не найдено\\."
    
    escaped_class = escape_markdown(class_name)
    result = f"📚 *Расписание для класса {escaped_class}:*\n\n"
    
    # Группируем по дням
    schedules_by_day = {}
    for schedule in schedules:
        day = schedule['position_info']['day']
        if day not in schedules_by_day:
            schedules_by_day[day] = []
        schedules_by_day[day].append(schedule)
    
    # Сортируем дни
    day_order = ['ПОНЕДЕЛЬНИК', 'ВТОРНИК', 'СРЕДА', 'ЧЕТВЕРГ', 'ПЯТНИЦА', 'СУББОТА']
    sorted_days = sorted(schedules_by_day.keys(), 
                        key=lambda x: day_order.index(x) if x in day_order else 999)
    
    for day in sorted_days:
        day_schedules = schedules_by_day[day]
        escaped_day = escape_markdown(day)
        result += f"*{escaped_day}:*\n"
        
        for i, schedule_info in enumerate(day_schedules):
            lessons = schedule_info['lessons']
            
            if len(day_schedules) > 1:
                result += f"_{escape_markdown(f'Вариант {i+1}')}_\n"
            
            for lesson in lessons:
                time_display = lesson['time'].replace('–', '-')
                escaped_time = escape_markdown(time_display)
                escaped_subject = escape_markdown(lesson['subject'])
                lesson_str = f"`{escaped_time}` \\- {escaped_subject}"
                
                if lesson['teacher']:
                    escaped_teacher = escape_markdown(lesson['teacher'])
                    lesson_str += f" \\({escaped_teacher}\\)"
                
                if lesson['classroom'] and lesson['classroom'].upper() not in ['', 'ДЕНЬ САМОПОДГОТОВКИ']:
                    escaped_classroom = escape_markdown(lesson['classroom'])
                    lesson_str += f" каб\\. {escaped_classroom}"
                
                result += lesson_str + "\n"
            
            result += "\n"
    
    return result

# ====== ПОИСК УЧИТЕЛЕЙ ======

def get_all_lessons():
    """Получает все уроки для всех классов"""
    lines = read_schedule_file()
    headers = find_schedule_headers()
    all_lessons = []
    
    # Сначала находим все классы
    class_positions = []
    for line_num, line in enumerate(lines):
        cells = line.strip().split(',')
        for col_num, cell in enumerate(cells):
            cell_clean = cell.strip()
            if re.match(r'^\d+\s*[А-ЯA-Z](\s*[А-ЯA-Z])?$', cell_clean, re.IGNORECASE):
                day = get_day_for_line(line_num, headers)
                class_positions.append({
                    'line_num': line_num,
                    'col_num': col_num,
                    'class_name': cell_clean,
                    'day': day
                })
    
    # Для каждого класса получаем уроки
    for pos in class_positions:
        lessons = get_lessons_for_position(pos)
        for lesson in lessons:
            all_lessons.append(lesson)
    
    return all_lessons

def get_teacher_schedule(teacher_name):
    """Получает расписание для учителя"""
    normalized_teacher = normalize_name(teacher_name)
    all_lessons = get_all_lessons()
    schedule_by_day = {}
    
    for lesson in all_lessons:
        teacher_field = lesson['teacher']
        if not teacher_field:
            continue
        
        teacher_parts = split_by_slash(teacher_field)
        teacher_index = -1
        
        # Ищем нашего учителя
        for idx, part in enumerate(teacher_parts):
            if normalize_name(part) == normalized_teacher:
                teacher_index = idx
                break
        
        if teacher_index >= 0:
            # Нашли учителя, определяем кабинет
            classroom_field = lesson['classroom']
            classroom_for_teacher = ""
            
            if classroom_field:
                classroom_parts = split_by_slash(classroom_field)
                if len(classroom_parts) == len(teacher_parts):
                    classroom_for_teacher = classroom_parts[teacher_index]
                elif len(classroom_parts) == 1:
                    classroom_for_teacher = classroom_parts[0]
                elif classroom_parts:
                    classroom_for_teacher = classroom_parts[0]
            
            # Создаем копию урока с правильным кабинетом
            lesson_copy = lesson.copy()
            lesson_copy['teacher'] = teacher_parts[teacher_index]
            lesson_copy['classroom'] = classroom_for_teacher
            
            day = lesson['day']
            if day not in schedule_by_day:
                schedule_by_day[day] = []
            schedule_by_day[day].append(lesson_copy)
    
    # Сортируем уроки внутри каждого дня по времени
    for day in schedule_by_day:
        schedule_by_day[day].sort(key=lambda x: parse_time(x['time']))
    
    return schedule_by_day

def parse_time(time_str):
    """Преобразует время в минуты для сортировки"""
    try:
        start_time = time_str.split('–')[0].strip().split('-')[0].strip()
        if '.' in start_time:
            hours, minutes = map(int, start_time.split('.'))
            return hours * 60 + minutes
        elif ':' in start_time:
            hours, minutes = map(int, start_time.split(':'))
            return hours * 60 + minutes
        else:
            return 0
    except:
        return 0

def format_teacher_schedule(teacher_name, schedule_by_day):
    """Форматирует расписание учителя"""
    if not schedule_by_day:
        return f"Учитель *{escape_markdown(teacher_name)}* не найден в расписании\\."
    
    result = f"👨‍🏫 *Расписание учителя {escape_markdown(teacher_name)}:*\n\n"
    
    total_lessons = sum(len(lessons) for lessons in schedule_by_day.values())
    result += f"📊 Всего уроков: {total_lessons}\n\n"
    
    # Сортируем дни
    day_order = ['ПОНЕДЕЛЬНИК', 'ВТОРНИК', 'СРЕДА', 'ЧЕТВЕРГ', 'ПЯТНИЦА', 'СУББОТА']
    sorted_days = sorted(schedule_by_day.keys(), 
                        key=lambda x: day_order.index(x) if x in day_order else 999)
    
    for day in sorted_days:
        lessons = schedule_by_day[day]
        escaped_day = escape_markdown(day)
        result += f"*{escaped_day}* \\({len(lessons)} уроков\\):\n"
        
        # Группируем уроки по времени
        lessons_by_time = {}
        for lesson in lessons:
            time = lesson['time']
            if time not in lessons_by_time:
                lessons_by_time[time] = []
            lessons_by_time[time].append(lesson)
        
        # Сортируем времена
        sorted_times = sorted(lessons_by_time.keys(), key=lambda x: parse_time(x))
        
        for time in sorted_times:
            time_lessons = lessons_by_time[time]
            time_display = time.replace('–', '-')
            escaped_time = escape_markdown(time_display)
            result += f"`{escaped_time}`:\n"
            
            for lesson in time_lessons:
                class_name = escape_markdown(lesson['class_name'])
                subject = escape_markdown(lesson['subject'])
                lesson_str = f"  \\- {class_name}: {subject}"
                
                if lesson['classroom'] and lesson['classroom'].upper() not in ['', 'ДЕНЬ САМОПОДГОТОВКИ']:
                    classroom = escape_markdown(lesson['classroom'])
                    lesson_str += f" \\(каб\\. {classroom}\\)"
                
                result += lesson_str + "\n"
            
            result += "\n"
        
        result += "\n"
    
    return result

def search_teachers_by_substring(substring):
    """Ищет учителей по части фамилии"""
    normalized_substring = normalize_name(substring)
    all_lessons = get_all_lessons()
    found_teachers = set()
    
    for lesson in all_lessons:
        teacher_field = lesson['teacher']
        if not teacher_field:
            continue
        
        teacher_parts = split_by_slash(teacher_field)
        for part in teacher_parts:
            if normalized_substring in normalize_name(part):
                found_teachers.add(part)
    
    return sorted(list(found_teachers))

# ====== ПОИСК ПО КАБИНЕТУ ======

def get_room_schedule(room_number):
    """Получает расписание для кабинета"""
    normalized_room = normalize_name(room_number)
    all_lessons = get_all_lessons()
    schedule_by_day = {}
    
    for lesson in all_lessons:
        classroom_field = lesson['classroom']
        if not classroom_field:
            continue
        
        # Проверяем все части кабинета (могут быть через слэш)
        classroom_parts = split_by_slash(classroom_field)
        classroom_found = False
        
        for part in classroom_parts:
            if normalize_name(part) == normalized_room:
                classroom_found = True
                break
        
        if classroom_found:
            day = lesson['day']
            if day not in schedule_by_day:
                schedule_by_day[day] = []
            
            # Создаем копию урока с информацией
            lesson_copy = lesson.copy()
            schedule_by_day[day].append(lesson_copy)
    
    # Сортируем уроки внутри каждого дня по времени
    for day in schedule_by_day:
        schedule_by_day[day].sort(key=lambda x: parse_time(x['time']))
    
    return schedule_by_day

def format_room_schedule(room_number, schedule_by_day):
    """Форматирует расписание кабинета"""
    if not schedule_by_day:
        return f"Кабинет *{escape_markdown(room_number)}* не найден в расписании\\."
    
    result = f"🏫 *Расписание кабинета {escape_markdown(room_number)}:*\n\n"
    
    total_lessons = sum(len(lessons) for lessons in schedule_by_day.values())
    result += f"📊 Всего уроков: {total_lessons}\n\n"
    
    # Сортируем дни
    day_order = ['ПОНЕДЕЛЬНИК', 'ВТОРНИК', 'СРЕДА', 'ЧЕТВЕРГ', 'ПЯТНИЦА', 'СУББОТА']
    sorted_days = sorted(schedule_by_day.keys(), 
                        key=lambda x: day_order.index(x) if x in day_order else 999)
    
    for day in sorted_days:
        lessons = schedule_by_day[day]
        escaped_day = escape_markdown(day)
        result += f"*{escaped_day}* \\({len(lessons)} уроков\\):\n"
        
        # Группируем уроки по времени
        lessons_by_time = {}
        for lesson in lessons:
            time = lesson['time']
            if time not in lessons_by_time:
                lessons_by_time[time] = []
            lessons_by_time[time].append(lesson)
        
        # Сортируем времена
        sorted_times = sorted(lessons_by_time.keys(), key=lambda x: parse_time(x))
        
        for time in sorted_times:
            time_lessons = lessons_by_time[time]
            time_display = time.replace('–', '-')
            escaped_time = escape_markdown(time_display)
            result += f"`{escaped_time}`:\n"
            
            for lesson in time_lessons:
                class_name = escape_markdown(lesson['class_name'])
                subject = escape_markdown(lesson['subject'])
                teacher = escape_markdown(lesson['teacher']) if lesson['teacher'] else ""
                classroom = escape_markdown(lesson['classroom']) if lesson['classroom'] else ""
                
                lesson_str = f"  \\- {class_name}: {subject}"
                
                if teacher:
                    lesson_str += f" \\({teacher}\\)"
                
                result += lesson_str + "\n"
            
            result += "\n"
        
        result += "\n"
    
    return result

# ====== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ======

def get_available_classes():
    """Получает список всех доступных классов"""
    lines = read_schedule_file()
    classes = set()
    
    for line in lines:
        cells = line.strip().split(',')
        for cell in cells:
            cell_clean = cell.strip()
            if re.match(r'^\d+\s*[А-ЯA-Z](\s*[А-ЯA-Z])?$', cell_clean, re.IGNORECASE):
                classes.add(cell_clean)
    
    return sorted(list(classes), key=lambda x: (
        int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 999,
        x
    ))

def has_schedule_file():
    """Проверяет наличие файла расписания"""
    try:
        with open('school_schedule.csv', 'r', encoding='utf-8'):
            return True
    except FileNotFoundError:
        return False

# ====== КОМПАТИБИЛЬНОСТЬ С СТАРЫМ КОДОМ ======

def get_schedule_for_class_all_positions(class_name):
    """Совместимость со старым кодом"""
    return get_schedule_for_class(class_name)

def format_class_schedule_groups(class_name, groups):
    """Совместимость со старым кодом"""
    return format_class_schedule(class_name, groups)

def get_schedule_by_teacher(teacher_name):
    """Совместимость со старым кодом"""
    schedule_by_day = get_teacher_schedule(teacher_name)
    if not schedule_by_day:
        return None
    
    total_lessons = sum(len(lessons) for lessons in schedule_by_day.values())
    groups = []
    
    for day, lessons in schedule_by_day.items():
        groups.append({
            'day': day,
            'shift': '1_смена',  # Заглушка
            'lessons': lessons,
            'total_lessons': len(lessons)
        })
    
    return {
        'teacher': teacher_name,
        'found_as': teacher_name,
        'match_type': 'exact',
        'groups': groups,
        'total_lessons': total_lessons
    }

def format_teacher_schedule_old(teacher_info):
    """Совместимость со старым кодом"""
    if not teacher_info:
        return "❌ Учитель не найден"
    
    teacher_name = teacher_info['teacher']
    schedule_by_day = {}
    
    for group in teacher_info['groups']:
        day = group['day']
        if day not in schedule_by_day:
            schedule_by_day[day] = []
        schedule_by_day[day].extend(group['lessons'])
    
    return format_teacher_schedule(teacher_name, schedule_by_day)

# ====== КЭШ ДЛЯ ПРОИЗВОДИТЕЛЬНОСТИ ======
_teacher_index_cache = None

def get_cached_teacher_index():
    """Совместимость со старым кодом"""
    global _teacher_index_cache
    if _teacher_index_cache is None:
        _teacher_index_cache = {}
        all_lessons = get_all_lessons()
        
        for lesson in all_lessons:
            teacher_field = lesson['teacher']
            if not teacher_field:
                continue
            
            teacher_parts = split_by_slash(teacher_field)
            for teacher in teacher_parts:
                if teacher not in _teacher_index_cache:
                    _teacher_index_cache[teacher] = []
                _teacher_index_cache[teacher].append(lesson)
    
    return _teacher_index_cache

def reload_schedule():
    """Перезагружает расписание"""
    global _teacher_index_cache
    _teacher_index_cache = None
    return True

# ====== ЭКСПОРТ ФУНКЦИЙ ======
__all__ = [
    'escape_markdown',
    'get_schedule_for_class',
    'get_schedule_for_class_all_positions',
    'format_class_schedule',
    'format_class_schedule_groups',
    'get_teacher_schedule',
    'get_schedule_by_teacher',
    'format_teacher_schedule',
    'format_teacher_schedule_old',
    'search_teachers_by_substring',
    'get_available_classes',
    'has_schedule_file',
    'get_cached_teacher_index',
    'reload_schedule',
    'get_room_schedule',
    'format_room_schedule'
]