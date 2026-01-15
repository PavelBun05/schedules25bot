import re
import time
from collections import defaultdict

def read_schedule_file():
    """Читает файл расписания"""
    try:
        with open('school_schedule.csv', 'r', encoding='utf-8') as f:
            return f.readlines()
    except FileNotFoundError:
        return []

lines = read_schedule_file()

# Кэши для производительности
_teacher_index_cache = None
_teacher_index_cache_time = None
_document_structure_cache = None
_document_structure_cache_time = None
CACHE_TIMEOUT = 300  # 5 минут

def normalize_class_name(class_name):
    """Нормализует название класса"""
    normalized = class_name.replace(" ", "")
    normalized = normalized.upper()
    return normalized

def parse_document_structure():
    """
    Простой и надежный анализ структуры документа
    """
    structure = []
    current_day = None
    current_sections = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        line_upper = line.upper()
        
        # Ищем день недели
        days = ['ПОНЕДЕЛЬНИК', 'ВТОРНИК', 'СРЕДА', 'ЧЕТВЕРГ', 'ПЯТНИЦА', 'СУББОТА']
        found_day = None
        for day in days:
            if day in line_upper:
                found_day = day
                break
        
        if found_day:
            # Сохраняем предыдущий день если есть
            if current_day and current_sections:
                structure.append({
                    'day': current_day,
                    'sections': current_sections.copy()
                })
            
            # Начинаем новый день
            current_day = found_day
            current_sections = []
            i += 1
            continue
        
        # Ищем начало таблицы с расписанием (строка с "ВРЕМЯ")
        if 'ВРЕМЯ' in line_upper and ',' in line:
            table_start = i
            
            # Определяем тип смены
            # Проверяем, есть ли "ВТОРАЯ СМЕНА" выше
            shift_type = '1_смена'
            for j in range(max(0, i-10), i):
                if 'ВТОРАЯ СМЕНА' in lines[j].upper():
                    shift_type = '2_смена'
                    break
            
            # Ищем конец таблицы
            table_end = i
            for j in range(i+1, min(i+100, len(lines))):
                next_line = lines[j].strip()
                next_upper = next_line.upper()
                
                # Таблица заканчивается если:
                # 1. Пустая строка после нескольких строк таблицы
                # 2. Начинается новый день
                # 3. Еще одно "ВРЕМЯ" (новая таблица)
                if not next_line:
                    # Проверяем, не начало ли это нового раздела
                    if j < len(lines) - 1:
                        next_next = lines[j+1].strip().upper()
                        if 'ВРЕМЯ' in next_next or any(day in next_next for day in days):
                            table_end = j - 1
                            break
                elif 'ВРЕМЯ' in next_upper and j > i + 5:
                    table_end = j - 1
                    break
                elif any(day in next_upper for day in days):
                    table_end = j - 1
                    break
                elif j == min(i+100, len(lines)) - 1:
                    table_end = j
            
            if table_end > table_start:
                current_sections.append({
                    'type': shift_type,
                    'start_line': table_start,
                    'end_line': table_end
                })
                
                i = table_end + 1
                continue
        
        i += 1
    
    # Сохраняем последний день
    if current_day and current_sections:
        structure.append({
            'day': current_day,
            'sections': current_sections
        })
    
    return structure

def get_cached_document_structure():
    """Получает закешированную структуру документа"""
    global _document_structure_cache, _document_structure_cache_time
    
    current_time = time.time()
    
    if (_document_structure_cache is None or 
        _document_structure_cache_time is None or 
        current_time - _document_structure_cache_time > CACHE_TIMEOUT):
        
        _document_structure_cache = parse_document_structure()
        _document_structure_cache_time = current_time
        
        print(f"✅ Создана структура документа: {len(_document_structure_cache)} дней")
        for day_struct in _document_structure_cache:
            print(f"  День: {day_struct['day']}, секций: {len(day_struct['sections'])}")
            for section in day_struct['sections']:
                print(f"    {section['type']}: строки {section['start_line']}-{section['end_line']}")
    
    return _document_structure_cache

def get_context_for_line(line_num):
    """
    Определяет контекст для строки: день и смена
    """
    structure = get_cached_document_structure()
    
    if not structure:
        return {'day': 'Неизвестно', 'shift': 'Неизвестно'}
    
    for day_struct in structure:
        for section in day_struct['sections']:
            if section['start_line'] <= line_num <= section['end_line']:
                return {
                    'day': day_struct['day'],
                    'shift': section['type']
                }
    
    return {'day': 'Неизвестно', 'shift': 'Неизвестно'}

def find_all_class_positions(class_name):
    """
    Находит ВСЕ позиции класса в файле
    """
    normalized_target = normalize_class_name(class_name)
    positions = []
    
    for line_num, line in enumerate(lines):
        cells = line.strip().split(',')
        for col_num, cell in enumerate(cells):
            cell_normalized = normalize_class_name(cell)
            if normalized_target == cell_normalized:
                context = get_context_for_line(line_num)
                positions.append({
                    'line_num': line_num,
                    'col_num': col_num,
                    'class_name': cell.strip(),
                    'context': context
                })
    
    return positions

def get_lessons_for_class_at_position(position):
    """
    Получает уроки для класса в конкретной позиции
    """
    line_num = position['line_num']
    col_num = position['col_num']
    context = position['context']
    lessons = []
    
    # Получаем границы текущей секции
    section_end = len(lines) - 1
    structure = get_cached_document_structure()
    for day_struct in structure:
        for section in day_struct['sections']:
            if section['start_line'] <= line_num <= section['end_line']:
                section_end = section['end_line']
                break
    
    # Ищем уроки ниже строки с классом
    for check_line_num in range(line_num + 1, min(line_num + 50, section_end + 1)):
        line = lines[check_line_num].strip()
        if not line:
            continue
        
        cells = line.split(',')
        
        # Проверяем, это строка с временем урока?
        if len(cells) > 1 and ('–' in cells[1] or '-' in cells[1]):
            time_str = cells[1].strip()
            
            # Собираем данные урока из этой строки и соседних
            data_parts = []
            
            for offset in range(-1, 2):
                check_line_num2 = check_line_num + offset
                if 0 <= check_line_num2 < len(lines):
                    check_line = lines[check_line_num2].strip()
                    if check_line:
                        check_cells = check_line.split(',')
                        if len(check_cells) > col_num:
                            data = check_cells[col_num].strip()
                            if data:
                                data_parts.append(data)
            
            if data_parts:
                lesson_info = {
                    'time': time_str,
                    'subject': data_parts[0] if len(data_parts) > 0 else '',
                    'teacher': data_parts[1] if len(data_parts) > 1 else '',
                    'classroom': data_parts[2] if len(data_parts) > 2 else '',
                    'raw_data': data_parts,
                    'context': context
                }
                lessons.append(lesson_info)
        
        # Если встречаем новую строку с классами - заканчиваем
        if len(cells) > 1:
            has_classes = False
            for cell in cells:
                if re.match(r'^\d+\s*[А-ЯA-Z]$', cell.strip(), re.IGNORECASE):
                    has_classes = True
                    break
            
            if has_classes and check_line_num > line_num + 2:
                break
    
    return lessons

def get_schedule_for_class_all_positions(class_name):
    """
    Получает расписание для класса из всех позиций
    """
    positions = find_all_class_positions(class_name)
    
    if not positions:
        return None
    
    # Группируем уроки по контексту
    grouped_lessons = defaultdict(list)
    
    for position in positions:
        lessons = get_lessons_for_class_at_position(position)
        
        for lesson in lessons:
            lesson['class_name'] = position['class_name']
        
        key = f"{position['context']['day']}_{position['context']['shift']}"
        grouped_lessons[key].extend(lessons)
    
    # Преобразуем в удобный формат
    result = []
    for context_key, lessons in grouped_lessons.items():
        parts = context_key.split('_')
        day = parts[0]
        shift = parts[1] if len(parts) > 1 else 'Неизвестно'
        
        # Сортируем уроки по времени
        sorted_lessons = sorted(lessons, key=lambda x: parse_time(x['time']))
        
        result.append({
            'day': day,
            'shift': shift,
            'lessons': sorted_lessons,
            'total_lessons': len(sorted_lessons)
        })
    
    # Сортируем: сначала 1 смена, потом 2 смена
    result.sort(key=lambda x: (0 if x['shift'] == '1_смена' else 1, x['day']))
    
    return result

def create_teacher_schedule_index():
    """
    Создает индекс расписания по учителям
    """
    teacher_index = defaultdict(list)
    
    # Сначала находим все строки с классами
    class_positions = []
    
    for line_num, line in enumerate(lines):
        cells = line.strip().split(',')
        
        for col_num, cell in enumerate(cells):
            cell_clean = cell.strip()
            if re.match(r'^\d+\s*[А-ЯA-Z]$', cell_clean, re.IGNORECASE):
                context = get_context_for_line(line_num)
                class_positions.append({
                    'line_num': line_num,
                    'col_num': col_num,
                    'class_name': cell_clean,
                    'context': context
                })
    
    # Для каждой позиции класса находим уроки
    for position in class_positions:
        lessons = get_lessons_for_class_at_position(position)
        
        for lesson in lessons:
            if lesson.get('teacher'):
                teacher_names_raw = lesson['teacher'].strip()
                
                # Обрабатываем нескольких учителей через слэш
                if '/' in teacher_names_raw or '\\' in teacher_names_raw:
                    teacher_names_clean = re.sub(r'[\\\/]+', '/', teacher_names_raw)
                    individual_teachers = [t.strip() for t in teacher_names_clean.split('/') if t.strip()]
                else:
                    individual_teachers = [teacher_names_raw]
                
                # Добавляем урок для каждого учителя
                for teacher_name in individual_teachers:
                    if not teacher_name:
                        continue
                    
                    lesson_info = {
                        'time': lesson['time'],
                        'subject': lesson.get('subject', ''),
                        'classroom': lesson.get('classroom', ''),
                        'class_name': position['class_name'],
                        'day': position['context']['day'],
                        'shift': position['context']['shift'],
                        'raw_data': lesson.get('raw_data', []),
                        'original_teacher_field': teacher_names_raw
                    }
                    
                    teacher_index[teacher_name].append(lesson_info)
    
    return dict(teacher_index)

def get_cached_teacher_index():
    """Получает закешированный индекс учителей"""
    global _teacher_index_cache, _teacher_index_cache_time
    
    current_time = time.time()
    
    if (_teacher_index_cache is None or 
        _teacher_index_cache_time is None or 
        current_time - _teacher_index_cache_time > CACHE_TIMEOUT):
        
        _teacher_index_cache = create_teacher_schedule_index()
        _teacher_index_cache_time = current_time
        print(f"✅ Создан индекс для {len(_teacher_index_cache)} учителей")
    
    return _teacher_index_cache

def parse_time(time_str):
    """Парсит время для сортировки"""
    try:
        # Извлекаем время начала
        start_time = time_str.split('–')[0].split('-')[0].strip()
        
        if ':' in start_time:
            hours, minutes = map(int, start_time.split(':'))
            return hours * 60 + minutes
        elif '.' in start_time:
            hours, minutes = map(int, start_time.split('.'))
            return hours * 60 + minutes
        else:
            lesson_number = int(start_time.split('.')[0])
            return lesson_number * 45
    except:
        return 0

def get_schedule_by_teacher(teacher_name):
    """Получает расписание для конкретного учителя"""
    teacher_index = get_cached_teacher_index()
    
    # Поиск учителя
    teacher_name_lower = teacher_name.lower()
    
    exact_matches = []
    partial_matches = []
    
    for teacher_key, lessons in teacher_index.items():
        if teacher_name_lower == teacher_key.lower():
            exact_matches.append({
                'teacher': teacher_key,
                'lessons': lessons,
                'match_type': 'exact'
            })
        elif teacher_name_lower in teacher_key.lower():
            partial_matches.append({
                'teacher': teacher_key,
                'lessons': lessons,
                'match_type': 'partial'
            })
    
    # Используем точные или частичные совпадения
    matches = exact_matches if exact_matches else partial_matches
    
    if not matches:
        return None
    
    # Объединяем уроки
    all_lessons = []
    for match in matches:
        all_lessons.extend(match['lessons'])
    
    # Удаляем дубликаты
    seen = set()
    unique_lessons = []
    for lesson in all_lessons:
        lesson_key = (
            lesson.get('time', ''),
            lesson.get('subject', ''),
            lesson.get('class_name', ''),
            lesson.get('classroom', ''),
            lesson.get('day', ''),
            lesson.get('shift', '')
        )
        
        if lesson_key not in seen:
            seen.add(lesson_key)
            unique_lessons.append(lesson)
    
    # Группируем уроки по дням и сменам
    grouped_lessons = defaultdict(list)
    for lesson in unique_lessons:
        key = f"{lesson['day']}_{lesson['shift']}"
        grouped_lessons[key].append(lesson)
    
    # Сортируем группы
    groups = []
    for key, lessons in grouped_lessons.items():
        parts = key.split('_')
        day = parts[0]
        shift = parts[1] if len(parts) > 1 else 'Неизвестно'
        
        # Сортируем уроки по времени
        sorted_lessons = sorted(lessons, key=lambda x: parse_time(x['time']))
        
        groups.append({
            'day': day,
            'shift': shift,
            'lessons': sorted_lessons,
            'total_lessons': len(sorted_lessons)
        })
    
    # Сортируем группы
    groups.sort(key=lambda x: (
        0 if x['shift'] == '1_смена' else 1,
        x['day']
    ))
    
    main_teacher_name = matches[0]['teacher'] if matches else teacher_name
    
    return {
        'teacher': teacher_name,
        'found_as': main_teacher_name,
        'match_type': 'exact' if exact_matches else 'partial',
        'groups': groups,
        'total_lessons': len(unique_lessons)
    }

def search_teachers_by_substring(substring):
    """Ищет учителей по подстроке в фамилии"""
    teacher_index = get_cached_teacher_index()
    substring_lower = substring.lower()
    
    matches = []
    for teacher_name, lessons in teacher_index.items():
        if substring_lower in teacher_name.lower() and lessons:
            # Проверяем, не является ли это составным учителем
            if '/' in teacher_name or '\\' in teacher_name:
                individual_teachers = re.split(r'[\\\/]+', teacher_name)
                main_teacher = individual_teachers[0].strip() if individual_teachers else teacher_name
            else:
                main_teacher = teacher_name
            
            # Если уже есть этот учитель в результатах, объединяем уроки
            existing_match = None
            for match in matches:
                if match['name'] == main_teacher:
                    existing_match = match
                    break
            
            if existing_match:
                existing_match['lesson_count'] += len(lessons)
            else:
                matches.append({
                    'name': main_teacher,
                    'full_name': teacher_name,
                    'lesson_count': len(lessons),
                    'sample_lesson': lessons[0] if lessons else None,
                    'is_combined': '/' in teacher_name or '\\' in teacher_name
                })
    
    # Сортируем по количеству уроков
    matches.sort(key=lambda x: x['lesson_count'], reverse=True)
    
    return matches

# ====== ФУНКЦИИ ФОРМАТИРОВАНИЯ ======

def escape_markdown(text):
    """Экранирует специальные символы Markdown"""
    if not text:
        return ""
    
    # Экранируем символы, которые могут сломать Markdown
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    result = text
    for char in special_chars:
        result = result.replace(char, '\\' + char)
    
    return result

# Замените функции форматирования на эти:

def format_class_schedule_groups(class_name, groups):
    """Форматирует расписание класса с несколькими группами"""
    if not groups:
        return f"📭 Нет уроков для класса {class_name}"
    
    message = f"📚 Расписание для класса {class_name}:\n\n"
    
    for group in groups:
        shift_text = "1 смена" if group['shift'] == '1_смена' else "2 смена"
        
        message += f"{group['day']}, {shift_text}:\n"
        
        if not group['lessons']:
            message += "  Нет уроков\n"
        else:
            for i, lesson in enumerate(group['lessons'], 1):
                time_display = lesson['time'].replace('–', '-')
                lesson_text = f"{i}. {time_display} - "
                
                if lesson['subject']:
                    lesson_text += f"{lesson['subject']}"
                
                if lesson['teacher']:
                    lesson_text += f" ({lesson['teacher']})"
                
                classroom = lesson.get('classroom', '')
                if classroom and classroom.upper() not in ['ДИСТАНТ', 'дистант', 'ДИСТАНЦИОННО']:
                    if '/' in classroom or '\\' in classroom:
                        classroom_display = classroom.replace('\\', '/')
                    else:
                        classroom_display = classroom
                    
                    lesson_text += f" каб. {classroom_display}"
                
                message += f"  {lesson_text}\n"
        
        message += "\n"
    
    message += f"📊 Всего групп расписания: {len(groups)}"
    
    return message

def format_teacher_schedule(teacher_info):
    """Форматирует расписание учителя"""
    if not teacher_info:
        return "❌ Учитель не найден"
    
    teacher_name = teacher_info['teacher']
    groups = teacher_info.get('groups', [])
    found_as = teacher_info.get('found_as', teacher_name)
    
    if not groups:
        return f"📭 У учителя {teacher_name} нет уроков в расписании"
    
    message = f"👨‍🏫 Расписание учителя {teacher_name}:\n"
    
    # Добавляем информацию о том, как найден учитель
    if teacher_info.get('match_type') == 'partial' and found_as != teacher_name:
        message += f"(найдено как: {found_as})\n"
    
    message += "\n"
    
    for group in groups:
        shift_text = "1 смена" if group['shift'] == '1_смена' else "2 смена"
        
        message += f"{group['day']}, {shift_text}:\n"
        
        if not group['lessons']:
            message += "  Нет уроков\n"
        else:
            for i, lesson in enumerate(group['lessons'], 1):
                time_display = lesson['time'].replace('–', '-')
                lesson_text = f"{i}. {time_display} - "
                
                if lesson['subject']:
                    lesson_text += f"{lesson['subject']}"
                
                if lesson['class_name']:
                    lesson_text += f" ({lesson['class_name']})"
                
                classroom = lesson.get('classroom', '')
                if classroom and classroom.upper() not in ['ДИСТАНТ', 'дистант', 'ДИСТАНЦИОННО']:
                    if '/' in classroom or '\\' in classroom:
                        classroom_display = classroom.replace('\\', '/')
                    else:
                        classroom_display = classroom
                    
                    lesson_text += f" каб. {classroom_display}"
                
                message += f"  {lesson_text}\n"
        
        message += "\n"
    
    message += f"📊 Всего уроков: {teacher_info['total_lessons']}"
    
    return message

def format_teachers_search_results(matches, search_query):
    """Форматирует результаты поиска учителей"""
    if not matches:
        return f"❌ Учителя с фамилией содержащей '{search_query}' не найдены."
    
    message = f"🔍 Найдено учителей ({len(matches)}):\n\n"
    
    for i, match in enumerate(matches[:15], 1):
        lesson_sample = match['sample_lesson']
        sample_info = ""
        
        if lesson_sample:
            if lesson_sample.get('subject'):
                subject = lesson_sample['subject'][:20] + ('...' if len(lesson_sample['subject']) > 20 else '')
                sample_info = f" - {subject}"
            if lesson_sample.get('class_name'):
                sample_info += f" ({lesson_sample['class_name']})"
        
        # Добавляем отметку о составном учителе
        teacher_display = match['name']
        if match.get('is_combined', False) and match['full_name'] != match['name']:
            teacher_display += f" ({match['full_name'].replace('/', '/')})"
        
        message += f"{i}. {teacher_display} - {match['lesson_count']} уроков{sample_info}\n"
    
    if len(matches) > 15:
        message += f"\n... и еще {len(matches) - 15}"
    
    message += "\n\n💡 Используйте /teacher <фамилия> для подробного расписания"
    
    return message

# ====== СТАРЫЕ ФУНКЦИИ (для обратной совместимости) ======

def find_class_position(class_name):
    """Находит позицию класса в файле (старая функция)"""
    normalized_target = normalize_class_name(class_name)
    
    for line_num, line in enumerate(lines):
        cells = line.strip().split(',')
        for i, cell in enumerate(cells):
            cell_normalized = normalize_class_name(cell)
            if normalized_target == cell_normalized:
                return i, line_num
    return -1, -1

def get_schedule_for_class(class_name):
    """Получает расписание для класса (старая функция)"""
    # Используем новую функцию и берем первую группу
    groups = get_schedule_for_class_all_positions(class_name)
    
    if not groups:
        return None
    
    # Преобразуем в старый формат
    old_format_lessons = []
    for lesson in groups[0]['lessons']:
        old_format_lessons.append({
            'time': lesson['time'],
            'data': lesson['raw_data']
        })
    
    return old_format_lessons

def format_schedule_for_telegram(class_name, lessons):
    """Форматирует расписание для Telegram (старый формат)"""
    if not lessons:
        return f"📭 Нет уроков для класса {escape_markdown(class_name)}"
    
    message = f"📚 *Расписание для класса {escape_markdown(class_name)}:*\n\n"
    
    for i, lesson in enumerate(lessons, 1):
        message += f"*{i}\\. {escape_markdown(lesson['time'])}*\n"
        
        # Первая строка: предмет (если есть)
        if len(lesson['data']) >= 1 and lesson['data'][0]:
            message += f"   📖 {escape_markdown(lesson['data'][0])}\n"
        
        # Вторая строка: учитель (если есть)
        if len(lesson['data']) >= 2 and lesson['data'][1]:
            message += f"   👨‍🏫 {escape_markdown(lesson['data'][1])}\n"
        
        # Третья строка: кабинет (если есть)
        if len(lesson['data']) >= 3 and lesson['data'][2]:
            message += f"   🏫 {escape_markdown(lesson['data'][2])}\n"
        
        message += "\n"
    
    return message

def format_schedule_for_console(class_name, lessons):
    """Форматирует расписание для консоли (старый формат)"""
    if not lessons:
        return f"📭 Нет уроков для класса {class_name}"
    
    message = f"\n{'='*60}\nРАСПИСАНИЕ ДЛЯ КЛАССА '{class_name}':\n{'='*60}\n"
    
    if lessons:
        message += f"\n📚 Найдено уроков: {len(lessons)}\n\n"
        for i, lesson in enumerate(lessons, 1):
            message += f"{i}. {lesson['time']}\n"
            if len(lesson['data']) >= 1 and lesson['data'][0]:
                message += f"   📖 {lesson['data'][0]}\n"
            if len(lesson['data']) >= 2 and lesson['data'][1]:
                message += f"   👨‍🏫 {lesson['data'][1]}\n"
            if len(lesson['data']) >= 3 and lesson['data'][2]:
                message += f"   🏫 {lesson['data'][2]}\n"
            message += "\n"
    else:
        message += "\n📭 Нет уроков на сегодня"
    
    return message

def get_available_classes():
    """Получает список доступных классов"""
    classes = set()
    
    for line in lines:
        cells = line.strip().split(',')
        for cell in cells:
            cell_clean = cell.strip()
            if re.match(r'^\d+\s*[А-ЯA-Z]$', cell_clean, re.IGNORECASE):
                classes.add(cell_clean)
    
    return sorted(list(classes), key=lambda x: (int(re.search(r'\d+', x).group()), x))

def reload_schedule():
    """Перезагружает расписание из файла"""
    global lines
    lines = read_schedule_file()
    
    # Сбрасываем кэш
    global _teacher_index_cache, _teacher_index_cache_time
    global _document_structure_cache, _document_structure_cache_time
    _teacher_index_cache = None
    _teacher_index_cache_time = None
    _document_structure_cache = None
    _document_structure_cache_time = None
    
    return lines

def has_schedule_file():
    """Проверяет наличие файла расписания"""
    try:
        with open('school_schedule.csv', 'r', encoding='utf-8'):
            return True
    except FileNotFoundError:
        return False