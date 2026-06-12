# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'main.py'
# Bytecode version: 3.12.0rc2 (3531)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

# irreducible cflow, using cdg fallback
# ***<module>: Failure: Compilation Error
import sys
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme
from src.config import cfg
from src.gui.dpi_scale import init_scale
from src.gui.main_window import MainWindow
from src.gui.single_instance import SingleInstance
from src.gui.startup_splash import create_startup_splash
from src.services.language_service import language_service
if getattr(sys, 'frozen', False):
    resources_path = Path(sys._MEIPASS)
    application_path = Path(sys.executable).parent
else:
    resources_path = Path(__file__).parent
    application_path = Path(__file__).parent
if __name__ == '__main__':
    pass
cfg.set_base_path(resources_path, application_path)
single_instance = SingleInstance('钓鱼软件九尾特供版')
if single_instance.is_running():
    print('[单例检测] 检测到 钓鱼软件九尾特供版 已在运行，阻止双开')
    single_instance.show_running_message()
    sys.exit(0)
app = QApplication(sys.argv)
init_scale(app)
if not single_instance.start_server():
    print('警告: 无法启动单例服务')
theme_name = cfg.get_global_setting('theme', 'Light')
if theme_name == 'Light':
    setTheme(Theme.LIGHT)
else:
    setTheme(Theme.DARK)
saved_lang = cfg.get_global_setting('language', 'simplified')
language_service.set_language(saved_lang)
ui_font = cfg.get_ui_font()
app.setFont(QFont(ui_font, 9))
print(f'界面语言: {saved_lang}')
print(f'界面字体: {ui_font}')
font = app.font()
print(f'当前字体: {font.family()}, 大小: {font.pointSize()}')
icon_path = cfg._get_base_path() / 'resources' / 'favicon.ico'
splash = create_startup_splash(theme_name, icon_path)
splash.show()
app.processEvents()
w = MainWindow()
def show_main_window():
    w.show()
    app.processEvents()
    splash.finish(w)
QTimer.singleShot(0, show_main_window)
sys.exit(app.exec())
    except Exception as e:
            print(f'CRITICAL ERROR: {e}')
            import traceback
            traceback.print_exc()
            if not getattr(sys, 'frozen', False):
                input('Press Enter to exit...')
                    e = None