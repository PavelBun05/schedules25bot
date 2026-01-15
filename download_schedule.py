import requests
from bs4 import BeautifulSoup
import csv
import logging

logger = logging.getLogger(__name__)

def download_schedule_from_site():
    """Простая версия скачивания - по одной ячейке"""
    
    base_url = "http://www.dnevnik25.ru/"
    schedule_url = base_url + "расписание.files/sheet001.htm"
    
    logger.info(f"🌐 Скачиваю расписание (простая версия): {schedule_url}")
    
    try:
        response = requests.get(schedule_url, timeout=30)
        response.encoding = 'windows-1251'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table')
        
        if not table:
            logger.error("❌ Таблица не найдена")
            return
        
        # Создаем CSV построчно
        with open('school_schedule.csv', 'w', encoding='utf-8', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            # Проходим по всем строкам таблицы
            for row in table.find_all('tr'):
                row_data = []
                
                # Проходим по всем ячейкам в строке
                for cell in row.find_all(['td', 'th']):
                    # Удаляем все теги внутри ячейки, сохраняя текст
                    for tag in cell.find_all():
                        if tag.name == 'br':
                            tag.replace_with(' ')  # Заменяем br на пробел
                    
                    # Получаем текст ячейки
                    text = cell.get_text(separator=' ', strip=True)
                    
                    # Очищаем от лишних пробелов и переносов
                    text = ' '.join(text.split())
                    text = text.replace('\n', ' ').replace('\r', ' ')
                    
                    row_data.append(text)
                
                # Записываем строку если есть данные
                if row_data:
                    writer.writerow(row_data)
        
        logger.info(f"✅ Расписание сохранено")
        
        # Создаем тестовый файл для проверки

        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")

        