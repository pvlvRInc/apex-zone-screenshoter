# screenshot_collector_gdrive.py
import os
import time
import json
from datetime import datetime
from pathlib import Path
from pynput import keyboard
from PIL import ImageGrab
import psutil
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

class GoogleDriveScreenshotCollector:
    """
    Screenshot Collector с загрузкой на Google Drive
    Поддержка разных пользователей через папки
    """
    
    SCOPES = ['https://www.googleapis.com/auth/drive']
    APEX_PROCESS_NAMES = ['r5apex.exe', 'apex legends.exe', 'EALauncher.exe']
    
    def __init__(self, username='player1', output_dir='apex_dataset/local_cache'):
        self.username = username
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.screenshot_count = 0
        self.skipped_count = 0
        self.is_running = True
        self.listener = None
        
        self.log_file = self.output_dir / f'{username}_log.txt'
        self.credentials_file = 'credentials.json'
        self.token_file = f'token_{username}.pickle'
        
        # Инициализируем Google Drive сервис
        self.drive_service = self.authenticate_google_drive()
        
        # Создаем или получаем ID папки пользователя
        self.user_folder_id = self.get_or_create_user_folder()
        
        self.log(f"Запуск для пользователя: {username}")
        self.log(f"Google Drive папка ID: {self.user_folder_id}")
    
    def authenticate_google_drive(self):
        """Аутентификация в Google Drive"""
        try:
            import pickle
            
            creds = None
            
            # Проверяем есть ли сохраненный токен
            if os.path.exists(self.token_file):
                with open(self.token_file, 'rb') as token:
                    creds = pickle.load(token)
            
            # Если нет токена или он истек
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, self.SCOPES)
                    creds = flow.run_local_server(port=0)
                
                # Сохраняем токен для следующего раза
                with open(self.token_file, 'wb') as token:
                    pickle.dump(creds, token)
            
            service = build('drive', 'v3', credentials=creds)
            print(f"✓ Подключение к Google Drive успешно")
            return service
            
        except Exception as e:
            print(f"❌ Ошибка подключения к Google Drive: {e}")
            self.log(f"❌ Ошибка подключения: {e}")
            sys.exit(1)
    
    def get_or_create_user_folder(self):
        """
        Получает ID папки пользователя или создает новую
        Структура: ApexDataset/{username}/
        """
        try:
            # Ищем корневую папку ApexDataset
            results = self.drive_service.files().list(
                q="name='ApexDataset' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces='drive',
                pageSize=1,
                fields='files(id, name)'
            ).execute()
            
            files = results.get('files', [])
            
            if files:
                root_folder_id = files[0]['id']
            else:
                # Создаем корневую папку если не существует
                file_metadata = {
                    'name': 'ApexDataset',
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                root_folder = self.drive_service.files().create(
                    body=file_metadata,
                    fields='id'
                ).execute()
                root_folder_id = root_folder.get('id')
                print(f"✓ Создана папка ApexDataset: {root_folder_id}")
            
            # Ищем папку пользователя
            results = self.drive_service.files().list(
                q=f"name='{self.username}' and mimeType='application/vnd.google-apps.folder' and '{root_folder_id}' in parents and trashed=false",
                spaces='drive',
                pageSize=1,
                fields='files(id, name)'
            ).execute()
            
            files = results.get('files', [])
            
            if files:
                user_folder_id = files[0]['id']
                print(f"✓ Найдена папка пользователя {self.username}")
            else:
                # Создаем папку пользователя
                file_metadata = {
                    'name': self.username,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [root_folder_id]
                }
                user_folder = self.drive_service.files().create(
                    body=file_metadata,
                    fields='id'
                ).execute()
                user_folder_id = user_folder.get('id')
                print(f"✓ Создана папка пользователя: {self.username}")
            
            return user_folder_id
            
        except Exception as e:
            print(f"❌ Ошибка при работе с папками: {e}")
            self.log(f"❌ Ошибка папок: {e}")
            return None
    
    def upload_to_gdrive(self, local_filepath, filename):
        """
        Загружает файл на Google Drive в папку пользователя
        """
        try:
            file_metadata = {
                'name': filename,
                'parents': [self.user_folder_id]
            }
            
            media = MediaFileUpload(
                local_filepath,
                mimetype='image/png',
                resumable=True
            )
            
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            
            return file.get('id'), file.get('webViewLink')
            
        except Exception as e:
            print(f"❌ Ошибка загрузки на Google Drive: {e}")
            self.log(f"❌ Ошибка загрузки: {e}")
            return None, None
    
    def is_apex_running(self):
        return True, "test"
        """Проверяет, запущен ли Apex"""
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    process_name = proc.info['name'].lower()
                    for apex_name in self.APEX_PROCESS_NAMES:
                        if apex_name.lower() in process_name:
                            return True, proc.info['name']
                    if 'apex' in process_name:
                        return True, proc.info['name']
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        except Exception as e:
            self.log(f"⚠️ Ошибка проверки процесса: {e}")
        
        return False, None
    
    def take_screenshot(self):
        """Снимает скриншот и загружает на Google Drive"""
        apex_running, apex_name = self.is_apex_running()
        
        if not apex_running:
            self.skipped_count += 1
            msg = f"⚠️ Apex не запущен (пропущено: {self.skipped_count})"
            print(msg)
            self.log(msg)
            return False
        
        try:
            # Берем скриншот локально
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
            filename = f'apex_map_{timestamp}.png'
            local_path = self.output_dir / filename
            
            screenshot = ImageGrab.grab()
            screenshot.save(local_path, 'PNG')
            
            # Загружаем на Google Drive
            print(f"📤 Загрузка на Google Drive: {filename}...", end='')
            drive_id, drive_link = self.upload_to_gdrive(str(local_path), filename)
            
            if drive_id:
                self.screenshot_count += 1
                msg = f'✓ #{self.screenshot_count} [{apex_name}]: {filename} -> Google Drive'
                print(f" ✓")
                self.log(msg)
                return True
            else:
                print(f" ❌")
                self.log(f"❌ Ошибка загрузки {filename}")
                return False
            
        except Exception as e:
            print(f'❌ {str(e)}')
            self.log(f'❌ {str(e)}')
            return False
    
    def log(self, message):
        """Логирует сообщение"""
        with open(self.log_file, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f'[{timestamp}] {message}\n')
    
    def start_listener(self):
        """Запускает слушатель горячих клавиш"""
        hotkeys = {
            '<ctrl>+<alt>+s': self.take_screenshot,
            '<ctrl>+<alt>+q': self.stop_listener,
        }
        
        self.listener = keyboard.GlobalHotKeys(hotkeys)
        self.listener.start()
        
        print(f"\n{'='*60}")
        print(f"🎮 Screenshot Collector (Пользователь: {self.username})")
        print(f"{'='*60}")
        print(f"📸 Ctrl+Alt+S - Скриншот (на Google Drive)")
        print(f"🚪 Ctrl+Alt+Q - Выход")
        print(f"{'='*60}\n")
    
    def stop_listener(self):
        """Завершает работу"""
        print(f"\n🛑 Завершение...")
        self.is_running = False
        if self.listener:
            self.listener.stop()
        
        msg = f"Завершена работа. Скриншотов: {self.screenshot_count}, пропущено: {self.skipped_count}"
        print(msg)
        self.log(msg)
        
        sys.exit(0)
    
    def run(self):
        """Основной цикл"""
        self.start_listener()
        
        try:
            while self.is_running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.stop_listener()

if __name__ == '__main__':
    import sys
    
    # Можешь указать имя пользователя через аргумент
    username = sys.argv[1] if len(sys.argv) > 1 else 'player1'
    
    collector = GoogleDriveScreenshotCollector(username=username)
    collector.run()
