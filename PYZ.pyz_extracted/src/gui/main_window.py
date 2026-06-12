# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'src\\gui\\main_window.py'
# Bytecode version: 3.12.0rc2 (3531)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

import sys
import os
import threading
from PySide6.QtCore import Qt, QSize, Signal, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QPainter, QColor, QFont, QPixmap
from PySide6.QtWidgets import QApplication
from qfluentwidgets import FluentIcon, FluentWindow, NavigationItemPosition, qconfig, setTheme, Theme
try:
    from src._version import __version__
except ImportError:
    __version__ = 'DEV'
from src.gui.home_interface import HomeInterface
from src.gui.records_interface import RecordsInterface
from src.gui.profit_interface import ProfitInterface
from src.gui.statistics_interface import StatisticsInterface
from src.gui.milestone_interface import MilestoneInterface
from src.gui.settings_interface import SettingsInterface
from src.gui.pokedex_interface import PokedexInterface
from src.gui.overlay_window import OverlayWindow
from src.gui.update_dialog import UpdateDialog
from src.gui.shutdown import shutdown_main_window_services
from src.workers import FishingWorker, PopupWorker
from src.inputs import InputController
from src.managers.signal_manager import SignalManager
from src.managers.cycle_reset_manager import CycleResetManager
from src.managers.audio_manager import AudioManager
from src.managers.sales_limit_manager import SalesLimitManager
from src.services.update_service import UpdateCheckThread
from src.services.language_service import language_service, L
from src.weather_refresh_worker import WeatherRefreshWorker, handle_weather_refresh_finished, trigger_weather_refresh
class MainWindow(FluentWindow):
    preset_should_change = Signal(str)
    DEFAULT_WINDOW_SIZE = QSize(1320, 800)
    def nativeEvent(self, event_type, message):
        """\n        Override the native event handler to gracefully handle KeyboardInterrupts\n        that might be raised by underlying libraries (like pynput) interacting\n        with the Qt event loop.\n        """
        try:
            return super().nativeEvent(event_type, message)
        except KeyboardInterrupt:
            print('DEBUG: Caught and ignored KeyboardInterrupt in nativeEvent.')
            return (True, 0)
    def __init__(self):
        super().__init__()
        print('Initializing MainWindow UI...')
        self.setObjectName('MainWindow')
        self.setWindowTitle('钓鱼软件九尾特供版')
        from src.config import cfg
        icon_path = cfg._get_base_path() / 'resources' / 'favicon.ico'
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        else:
            self.setWindowIcon(FluentIcon.GAME.icon())
        self.resize(self.DEFAULT_WINDOW_SIZE)
        print('Instantiating interfaces...')
        self.home_interface = HomeInterface(self)
        self.records_interface = RecordsInterface(self)
        self.profit_interface = ProfitInterface(self)
        self.statistics_interface = StatisticsInterface(self)
        self.milestone_interface = MilestoneInterface(self)
        self.pokedex_interface = PokedexInterface(self)
        self.settings_interface = SettingsInterface(self)
        self.overlay = OverlayWindow()
        print('Instantiating worker and input controller...')
        self.worker = FishingWorker()
        self.popup_worker = PopupWorker()
        self.weather_refresh_worker = WeatherRefreshWorker()
        self.input_controller = InputController()
        self.home_interface.attach_worker(self.worker)
        self.audio_manager = AudioManager(self)
        self.signal_manager = SignalManager(self)
        self.cycle_reset_manager = CycleResetManager(self)
        self.sales_limit_manager = SalesLimitManager(self)
        print('Setting up navigation...')
        self.navigationInterface.setExpandWidth(150)
        self.addSubInterface(self.home_interface, FluentIcon.HOME, L('主页'))
        self.addSubInterface(self.records_interface, FluentIcon.HISTORY, L('记录'))
        self.addSubInterface(self.milestone_interface, FluentIcon.FLAG, L('里程'))
        self.addSubInterface(self.profit_interface, FluentIcon.SHOPPING_CART, L('收益'))
        self.addSubInterface(self.statistics_interface, FluentIcon.PIE_SINGLE, L('统计'))
        self.addSubInterface(self.pokedex_interface, FluentIcon.LIBRARY, L('图鉴'))
        self.addSubInterface(self.settings_interface, FluentIcon.SETTING, L('设置'), NavigationItemPosition.BOTTOM)
        self._init_navigation_language_toggle()
        self._init_navigation_theme_toggle()
        self._init_navigation_update_check()
        print('Connecting signals...')
        self.signal_manager.connect_all()
        self.settings_interface.release_mode_changed_signal.connect(self.home_interface.update_release_mode_segment)
        self.worker.start()
        self.popup_worker.start()
        self.weather_refresh_worker.start()
        self.input_controller.start_listening()
        self._update_overlay_limit()
        self._restore_overlay_state()
        self._connect_uno_signals()
        self.cycle_reset_manager.start()
        self._watermark_cache = None
        self._watermark_cache_size = QSize(0, 0)
        self._theme_listeners = []
        self._theme_class_listeners = []
        self._language_listeners = []
        self._language_class_listeners = []
        self._register_theme_listeners()
        self._register_language_listeners()
        self._cleanup_legacy_hidden_info_settings()
        self._manual_update_check = False
        self._update_check_thread = None
    def _cleanup_legacy_hidden_info_settings(self):
        from src.config import cfg
        removed = False
        missing = object()
        for key in ['external_ip', 'external_ip_updated_at']:
            if cfg.pop_global_setting(key, missing) is not missing:
                removed = True
        if removed:
            cfg.save()
    def _start_update_check(self, manual=False):
        if self._update_check_thread is not None and self._update_check_thread.isRunning():
            return
        else:
            self._manual_update_check = manual
            self._update_check_thread = UpdateCheckThread(__version__, parent=self)
            self._update_check_thread.update_available.connect(self._show_update_dialog)
            self._update_check_thread.no_update.connect(self._on_no_update)
            self._update_check_thread.check_failed.connect(self._on_update_check_failed)
            self._update_check_thread.finished.connect(self._cleanup_update_check_thread)
            self._update_check_thread.start()
    def _cleanup_update_check_thread(self):
        thread = self._update_check_thread
        self._update_check_thread = None
        if thread is not None:
            thread.deleteLater()
    def _on_no_update(self):
        if getattr(self, '_manual_update_check', False):
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.success(L('检查更新'), L('当前已是最新版本'), duration=3000, parent=self, position=InfoBarPosition.BOTTOM_RIGHT)
    def _on_update_check_failed(self, error_message: str):
        print(f'Update check skipped: {error_message}')
        if getattr(self, '_manual_update_check', False):
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.warning(L('检查更新'), L('检查更新失败，请稍后重试'), duration=3000, parent=self, position=InfoBarPosition.BOTTOM_RIGHT)
    def _show_update_dialog(self, update_info: dict):
        download_url = str(update_info.get('download_url', '')).strip()
        if not download_url:
            return
        else:
            latest_version = str(update_info.get('version', '')).strip() or L('未知版本')
            self.append_log(f'检测到新版本：{latest_version}')
            dialog = UpdateDialog(__version__, update_info, self)
            if dialog.exec():
                QDesktopServices.openUrl(QUrl(download_url))
    def _init_navigation_language_toggle(self):
        self.lang_toggle_item = self.navigationInterface.insertItem(0, 'langToggle', FluentIcon.LANGUAGE, L('语言'), onClick=self.toggle_language, selectable=False, position=NavigationItemPosition.BOTTOM)
        self._update_language_toggle_button()
        self.navigationInterface.widget('homeInterface').setText(L('主页'))
        self.navigationInterface.widget('recordsInterface').setText(L('记录'))
        self.navigationInterface.widget('milestoneInterface').setText(L('里程'))
        self.navigationInterface.widget('profitInterface').setText(L('收益'))
        self.navigationInterface.widget('statisticsInterface').setText(L('统计'))
        self.navigationInterface.widget('pokedexInterface').setText(L('图鉴'))
        self.navigationInterface.widget('settingsInterface').setText(L('设置'))
        self._update_language_toggle_button()
    def _update_language_toggle_button(self):
        if language_service.is_traditional():
            current_label = L('繁体')
            target_label = L('简体')
        else:
            current_label = L('简体')
            target_label = L('繁体')
        lang_widget = self.navigationInterface.widget('langToggle')
        lang_widget.setIcon(FluentIcon.LANGUAGE)
        lang_widget.setText(current_label)
        lang_widget.setToolTip(f"{L('当前')}{current_label}{L('模式')}，{L('点击切换到')}{target_label}")
    def toggle_language(self):
        from src.config import cfg
        if language_service.is_traditional():
            next_lang = 'simplified'
        else:
            next_lang = 'traditional'
        language_service.set_language(next_lang)
        cfg.set_global_setting('language', next_lang)
        cfg.save()
        self._update_language_toggle_button()
        self._update_theme_toggle_button()
        self._on_language_changed()
    def _on_language_changed(self):
        self._notify_language_listeners()
        nav_items = [('homeInterface', '主页'), ('recordsInterface', '记录'), ('milestoneInterface', '里程'), ('profitInterface', '收益'), ('statisticsInterface', '统计'), ('pokedexInterface', '图鉴'), ('settingsInterface', '设置')]
        for widget_id, text in nav_items:
            self.navigationInterface.widget(widget_id).setText(L(text))
        self._update_language_toggle_button()
        self._update_theme_toggle_button()
        self._watermark_cache = None
        self.update()
    def _init_navigation_theme_toggle(self):
        self.theme_toggle_item = self.navigationInterface.insertItem(0, 'themeToggle', FluentIcon.PALETTE, L('主题'), onClick=self.toggle_theme_mode, selectable=False, position=NavigationItemPosition.BOTTOM)
        self._update_theme_toggle_button()
    def _init_navigation_update_check(self):
        self.navigationInterface.insertItem(0, 'updateCheck', FluentIcon.SYNC, L('检查更新'), onClick=self._on_manual_update_check, selectable=False, position=NavigationItemPosition.BOTTOM)
        self.navigationInterface.widget('updateCheck').setToolTip(L('检查更新'))
    def _on_manual_update_check(self):
        if __version__ == 'DEV':
            return
        else:
            self._start_update_check(manual=True)
    def _get_current_theme_name(self) -> str:
        theme_value = qconfig.theme.value
        if hasattr(theme_value, 'name'):
            return 'Dark' if str(theme_value.name).upper() == 'DARK' else 'Light'
        else:
            return 'Dark' if str(theme_value).lower() == 'dark' else 'Light'
    def _update_theme_toggle_button(self):
        current_theme = self._get_current_theme_name()
        target_theme = 'Dark' if current_theme == 'Light' else 'Light'
        theme_icon = FluentIcon.QUIET_HOURS if target_theme == 'Dark' else FluentIcon.BRIGHTNESS
        current_label = L('亮色') if current_theme == 'Light' else L('暗黑')
        target_label = L('暗黑') if target_theme == 'Dark' else L('亮色')
        theme_widget = self.navigationInterface.widget('themeToggle')
        theme_widget.setIcon(theme_icon)
        theme_widget.setText(L('主题'))
        theme_widget.setToolTip(f"{L('当前')}{current_label}{L('主题')}，{L('点击切换到')}{target_label}")
    def toggle_theme_mode(self):
        current_theme = self._get_current_theme_name()
        next_theme = 'Dark' if current_theme == 'Light' else 'Light'
        self._on_theme_changed(next_theme)
    def _update_overlay_limit(self, _=None):
        """更新悬浮窗和首页的销售额度显示"""
        self.sales_limit_manager.update_overlay_limit(_)
    def set_overlay_mode(self, mode: str):
        """设置悬浮窗模式：off/on"""
        from src.config import cfg
        if mode == 'hidden':
            mode = 'on'
        else:
            if mode not in ['off', 'on']:
                mode = 'off'
        cfg.set_global_setting('overlay_mode', mode)
        cfg.save()
        if mode == 'off':
            self.overlay.hide()
        else:
            self.overlay.show()
            self.overlay.set_exclude_from_capture(False)
    def _restore_overlay_state(self):
        """恢复悬浮窗的上次状态和位置"""
        from src.config import cfg
        pos = cfg.get_global_setting('overlay_position', None)
        if pos and isinstance(pos, list) and (len(pos) == 2):
                    self.overlay.move(pos[0], pos[1])
        overlay_mode = cfg.get_global_setting('overlay_mode', None)
        if overlay_mode == 'hidden':
            overlay_mode = 'on'
            cfg.set_global_setting('overlay_mode', overlay_mode)
            cfg.save()
        else:
            if overlay_mode not in ['off', 'on']:
                overlay_visible = cfg.get_global_setting('overlay_visible', False)
                overlay_mode = 'on' if overlay_visible else 'off'
                cfg.set_global_setting('overlay_mode', overlay_mode)
                cfg.save()
        if overlay_mode!= 'off':
            self.overlay.show()
            self.overlay.set_exclude_from_capture(False)
        self.home_interface.banner_widget.overlay_segment.blockSignals(True)
        self.home_interface.banner_widget.overlay_segment.setCurrentItem(overlay_mode)
        self.home_interface.banner_widget.overlay_segment.blockSignals(False)
    def _save_overlay_state(self):
        """保存悬浮窗的当前状态和位置"""
        from src.config import cfg
        overlay_mode = 'on' if self.overlay.isVisible() else 'off'
        cfg.set_global_setting('overlay_mode', overlay_mode)
        pos = self.overlay.pos()
        cfg.set_global_setting('overlay_position', [pos.x(), pos.y()])
        cfg.save()
    def _on_account_changed(self, account_name: str):
        """账号切换时刷新各界面数据"""
        self.append_log(f'已切换到账号: {account_name}')
        self.records_interface.request_reload()
        self.milestone_interface.request_reload()
        if hasattr(self.profit_interface, 'refresh_server_region'):
            self.profit_interface.refresh_server_region()
        else:
            self.profit_interface.request_reload(delay_ms=0)
        if hasattr(self.statistics_interface, 'reload_data'):
            self.statistics_interface.reload_data()
        self.pokedex_interface.request_reload()
        self.settings_interface.refresh_account_ui()
        self._update_overlay_limit()
        self.overlay.update_fish_preview()
        self.cycle_reset_manager.schedule_next_reset()
    def _on_theme_changed(self, theme: str):
        from src.config import cfg
        if theme == 'Light':
            setTheme(Theme.LIGHT)
        else:
            setTheme(Theme.DARK)
        if cfg.get_global_setting('theme', 'Light')!= theme:
            cfg.set_global_setting('theme', theme)
            cfg.save()
        self._update_theme_toggle_button()
        self._watermark_cache = None
        self.update()
        self._notify_theme_listeners()
    def register_theme_listener(self, callback):
        """注册主题刷新回调"""
        if callback not in self._theme_listeners:
            self._theme_listeners.append(callback)
    def register_theme_class(self, cls, method_name='refresh_theme', top_level=True):
        """注册需要主题刷新的弹窗类\n\n        Args:\n            cls: 组件/弹窗类\n            method_name: 刷新方法名，默认 refresh_theme\n            top_level: True 表示遍历顶层窗口，False 表示使用 findChildren\n        """
        self._theme_class_listeners.append((cls, method_name, top_level))
    def register_language_listener(self, callback):
        """注册语言刷新回调"""
        if callback not in self._language_listeners:
            self._language_listeners.append(callback)
    def register_language_class(self, cls, method_name='refresh_language', top_level=True):
        """注册需要语言刷新的组件或弹窗"""
        self._language_class_listeners.append((cls, method_name, top_level))
    def _register_theme_listeners(self):
        """集中注册所有界面和弹窗的主题监听器"""
        self.register_theme_listener(self.home_interface.refresh_theme)
        self.register_theme_listener(self.records_interface.refresh_theme)
        self.register_theme_listener(self.settings_interface.refresh_theme)
        self.register_theme_listener(self.profit_interface.refresh_theme)
        self.register_theme_listener(self.statistics_interface.refresh_theme)
        self.register_theme_listener(self.pokedex_interface.refresh_theme)
        self.register_theme_listener(self.milestone_interface.refresh_theme)
        self.register_theme_listener(self.overlay.refresh_theme)
        from src.gui.fish_detail_dialog import FishDetailDialog
        from src.gui.sell_confirmation_dialog import SellConfirmationDialog
        from src.gui.pokedex_interface import TransparentDialog
        from src.gui.single_instance import TransparentDialog as SITransparentDialog
        from src.gui.components.filter_drawer import FilterDrawer
        self.register_theme_class(FishDetailDialog)
        self.register_theme_class(SellConfirmationDialog)
        self.register_theme_class(TransparentDialog)
        self.register_theme_class(SITransparentDialog)
        self.register_theme_class(FilterDrawer, top_level=False)
    def _register_language_listeners(self):
        """集中注册界面和弹窗的语言刷新监听器"""
        self.register_language_listener(self.home_interface.refresh_language)
        self.register_language_listener(self.records_interface.refresh_language)
        self.register_language_listener(self.settings_interface.refresh_language)
        self.register_language_listener(self.profit_interface.refresh_language)
        self.register_language_listener(self.statistics_interface.refresh_language)
        self.register_language_listener(self.pokedex_interface.refresh_language)
        self.register_language_listener(self.milestone_interface.refresh_language)
        self.register_language_listener(self.overlay.refresh_language)
        from src.gui.components.date_range_picker import DateRangeDialog
        from src.gui.components.filter_drawer import FilterDrawer
        from src.gui.fish_detail_dialog import FishDetailDialog
        from src.gui.sell_confirmation_dialog import SellConfirmationDialog
        from src.gui.settings_interface import PresetNameDialog, ServerRegionDialog
        self.register_language_class(FishDetailDialog)
        self.register_language_class(SellConfirmationDialog)
        self.register_language_class(UpdateDialog)
        self.register_language_class(DateRangeDialog)
        self.register_language_class(ServerRegionDialog)
        self.register_language_class(PresetNameDialog)
        self.register_language_class(FilterDrawer, top_level=False)
    def _notify_theme_listeners(self):
        """通知所有注册的监听器刷新主题"""
        for callback in self._theme_listeners:
            try:
                callback()
            except Exception as e:
                print(f'[Theme] 主题刷新回调失败: {e}')
                pass
        for cls, method_name, top_level in self._theme_class_listeners:
            try:
                widgets = QApplication.topLevelWidgets() if top_level else self.findChildren(cls)
                for widget in widgets:
                    if isinstance(widget, cls):
                        method = getattr(widget, method_name, None)
                        if method:
                            method()
            except Exception as e:
                print(f'[Theme] 弹窗主题刷新失败 ({cls.__name__}): {e}')
    def _notify_language_listeners(self):
        """通知所有注册的监听器刷新语言"""
        for callback in self._language_listeners:
            try:
                callback()
            except Exception as e:
                print(f'[Language] 语言刷新回调失败: {e}')
                pass
        for cls, method_name, top_level in self._language_class_listeners:
            try:
                widgets = QApplication.topLevelWidgets() if top_level else self.findChildren(cls)
                for widget in widgets:
                    if isinstance(widget, cls):
                        method = getattr(widget, method_name, None)
                        if method:
                            method()
            except Exception as e:
                print(f'[Language] 弹窗语言刷新失败 ({cls.__name__}): {e}')
    def append_log(self, message):
        """在日志窗口追加日志"""
        self.home_interface.update_log(message)
    def update_status(self, status):
        """更新状态标签"""
        self.home_interface.update_status(status)
    def _resume_worker_from_hotkey(self):
        if self.weather_refresh_worker.is_refreshing():
            self.weather_refresh_worker.cancel_refresh('脚本恢复运行')
        self.worker.resume()
        self.audio_manager.play_control_sound('start')
    def _pause_worker_from_hotkey(self):
        self.worker.pause()
        self.audio_manager.play_control_sound('pause')
    def toggle_script(self):
        """切换脚本的运行/暂停状态"""
        if self.home_interface.get_current_fishing_mode() == 'record_only':
            self.home_interface.apply_fishing_mode('auto', emit_log=True)
            if self.worker.paused:
                self._resume_worker_from_hotkey()
            return None
        else:
            if self.worker.paused:
                if self.weather_refresh_worker.is_refreshing():
                    self.weather_refresh_worker.cancel_refresh('脚本恢复运行')
                self.worker.resume()
                self.audio_manager.play_control_sound('start')
            else:
                self.worker.pause()
                self.audio_manager.play_control_sound('pause')
    def toggle_manual_mode_script(self):
        """切换到只记录模式，并在该模式下执行暂停/继续。"""
        current_mode = self.home_interface.get_current_fishing_mode()
        if current_mode!= 'record_only':
            self.home_interface.apply_fishing_mode('record_only', emit_log=True)
            if self.worker.paused:
                self._resume_worker_from_hotkey()
            return None
        else:
            if self.worker.paused:
                self._resume_worker_from_hotkey()
            else:
                self._pause_worker_from_hotkey()
    def _on_weather_refresh_hotkey(self):
        from src.config import cfg
        trigger_weather_refresh(config=cfg, worker=self.weather_refresh_worker, fishing_paused=self.worker.paused, append_log=self.append_log, update_status=self.update_status)
    def _on_weather_refresh_finished(self, success: bool, weather: str, cycles: int):
        # ***<module>.MainWindow._on_weather_refresh_finished: Failure: Different bytecode
        from src.config import cfg
    def _connect_uno_signals(self):
        """连接UNO管理器的信号到UI更新"""
        from src.uno import uno_manager
        uno_manager.cards_updated.connect(lambda current, maximum: self.overlay.update_uno_cards(current, maximum, True))
        uno_manager.log_message.connect(self.append_log)
        uno_manager.status_changed.connect(self._on_uno_status_changed)
        uno_manager.countdown_updated.connect(self.overlay.update_uno_countdown)
    def _on_uno_status_changed(self, status: str):
        """处理UNO状态变化"""
        from src.config import cfg
        if status == '已停止' or status == '已完成':
            self.overlay.update_uno_cards(0, cfg.get_global_setting('uno_max_cards', 35), False)
    def toggle_uno(self):
        """切换UNO功能的启动/停止状态"""
        from src.uno import uno_manager
        if uno_manager.running:
            uno_manager.stop()
        else:
            uno_manager.start()
    def take_debug_screenshot(self):
        """Taking debug screenshot and opening it"""
        print('Taking debug screenshot via hotkey...')
        try:
            from src.debug_overlay import generate_debug_screenshot
            filepath = generate_debug_screenshot(show_image=True)
            self.append_log(f'调试截图已保存: {filepath}')
            self.update_status('调试截图已生成')
        except Exception as e:
            print(f'Failed to take debug screenshot: {e}')
            self.append_log(f'截图失败: {e}')
            return None
    def on_preset_changed(self, preset_name: str):
        """\n        当UI中的预设改变时，通过信号安全地通知工作线程。\n        """
        self._apply_preset_change(preset_name, source='UI')
    def _apply_preset_change(self, preset_name: str, source: str):
        from src.config import cfg
        display_label = cfg.get_preset_display_label(preset_name)
        self.append_log(f'{source}请求更改预设为: {display_label}')
        self.preset_should_change.emit(preset_name)
        if not self.worker.paused:
            self.worker.pause()
        self.update_status(f'预设已切换为 \'{display_label}\'，脚本已暂停。')
        self.append_log('请检查配置，然后按快捷键继续。')
    def _on_preset_hotkey_triggered(self, preset_name: str):
        from src.config import cfg
        if preset_name not in cfg.presets:
            return
        else:
            self.home_interface.banner_widget.set_current_preset(preset_name)
            self.settings_interface.set_current_preset(preset_name)
            if cfg.current_preset_name == preset_name:
                return
            else:
                cfg.load_preset(preset_name)
                cfg.save()
                self._apply_preset_change(preset_name, source='快捷键')
    def paintEvent(self, event):
        """绘制可见水印"""
        # ***<module>.MainWindow.paintEvent: Failure: Different control flow
        super().paintEvent(event)
        current_size = self.size()
        if self._watermark_cache is not None and self._watermark_cache_size!= current_size:
            self._watermark_cache_size = QSize(current_size)
            cache = QPixmap(current_size)
            cache.fill(Qt.transparent)
            cache_painter = QPainter(cache)
            is_dark = qconfig.theme.value == 'Dark'
            watermark_alpha = 24 if is_dark else 60
            cache_painter.setPen(QColor(128, 128, 128, watermark_alpha))
            cache_painter.setFont(QFont('Microsoft YaHei', 20))
            cache_painter.rotate((-30))
            text = L('九尾修改版')
            for x in range((-500), self.width() + 500, 300):
                for y in range(0, self.height() + 500, 150):
                    cache_painter.drawText(x, y, text)
            cache_painter.end()
            self._watermark_cache = cache
        if self._watermark_cache is not None:
            painter = QPainter(self)
            painter.drawPixmap(0, 0, self._watermark_cache)
    def _wait_for_thread_shutdown(self, thread, thread_name: str, timeout_ms: int=5000):
        if thread.wait(timeout_ms):
            return True
        else:
            message = f'{thread_name}未能在 {timeout_ms / 1000:.1f} 秒内停止，尝试强制结束。'
            print(message)
            self.append_log(message)
            request_interruption = getattr(thread, 'requestInterruption', None)
            if callable(request_interruption):
                try:
                    request_interruption()
                except Exception:
                    pass
            quit_thread = getattr(thread, 'quit', None)
            if callable(quit_thread):
                try:
                    quit_thread()
                except Exception:
                    pass
            if thread.wait(2000):
                self.append_log(f'{thread_name}已在额外等待后停止。')
                return True
            else:
                terminate_thread = getattr(thread, 'terminate', None)
                if callable(terminate_thread) and thread.isRunning():
                    try:
                        terminate_thread()
                    except Exception:
                        pass
                    if thread.wait(1000):
                        self.append_log(f'{thread_name}已强制停止。')
                        return True
                message = f'{thread_name}强制结束失败，已取消关闭。'
                print(message)
                self.append_log(message)
                self.update_status('关闭已取消：后台线程仍在运行')
                return False
    @staticmethod
    def _terminate_thread_immediately(thread):
        if thread is None or not thread.isRunning():
            return None
        else:
            request_interruption = getattr(thread, 'requestInterruption', None)
            if callable(request_interruption):
                try:
                    request_interruption()
                except Exception:
                    pass
            quit_thread = getattr(thread, 'quit', None)
            if callable(quit_thread):
                try:
                    quit_thread()
                except Exception:
                    pass
            terminate_thread = getattr(thread, 'terminate', None)
            if callable(terminate_thread):
                try:
                    terminate_thread()
                except Exception:
                    return None
    @staticmethod
    def _schedule_force_process_exit(delay_seconds: float=0.25):
        timer = threading.Timer(delay_seconds, os._exit, args=(0,))
        timer.daemon = True
        timer.start()
    def closeEvent(self, event):
        """关闭窗口事件。"""
        print('Closing application immediately...')
        from src.uno import uno_manager
        shutdown_main_window_services(self, uno_manager, immediate=True)
        self.worker.stop('应用正在关闭', wait_for_async=False)
        self.popup_worker.stop()
        log_widget = getattr(getattr(self, 'home_interface', None), 'log_widget', None)
        save_latest_log_snapshot = getattr(log_widget, 'save_latest_log_snapshot', None)
        if callable(save_latest_log_snapshot):
            save_latest_log_snapshot()
        self._terminate_thread_immediately(self.worker)
        self._terminate_thread_immediately(self.popup_worker)
        self._terminate_thread_immediately(self.weather_refresh_worker)
        self._terminate_thread_immediately(self._update_check_thread)
        app = QApplication.instance()
        if app is not None:
            QTimer.singleShot(0, app.quit)
        self._schedule_force_process_exit()
        print('Close requested. Force-exit fallback armed.')
        event.accept()
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())