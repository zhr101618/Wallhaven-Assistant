import sys
import os

# PyInstaller 修复 SSL 证书路径问题
if getattr(sys, 'frozen', False):
    import urllib3
    # 彻底禁用 SSL 验证警告
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    # 移除可能导致错误的证书路径环境变量
    if 'REQUESTS_CA_BUNDLE' in os.environ:
        del os.environ['REQUESTS_CA_BUNDLE']
    if 'SSL_CERT_FILE' in os.environ:
        del os.environ['SSL_CERT_FILE']

import requests
import ctypes
import time
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLineEdit, QPushButton, QComboBox, QScrollArea, QLabel, 
                             QGridLayout, QFileDialog, QMessageBox, QCheckBox, QFrame, QDialog,
                             QProgressBar, QMenu, QWidgetAction)
from PyQt6.QtGui import QPixmap, QImage, QKeyEvent, QIntValidator, QColor, QPainter
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, pyqtSlot, QMetaObject, Q_ARG
from io import BytesIO
from PIL import Image

# ================= 配置常量 =================
DEFAULT_PROXY = "socks5h://127.0.0.1:15235"
THUMBNAIL_SIZE = (250, 180) # 增大缩略图尺寸
# ===========================================

def get_verify_ssl():
    """获取是否验证 SSL 的标志"""
    return not getattr(sys, 'frozen', False)

def set_wallpaper(path):
    """设置 Windows 壁纸"""
    # SPI_SETDESKWALLPAPER = 20
    ctypes.windll.user32.SystemParametersInfoW(20, 0, path, 3)

class ClickableLabel(QLabel):
    """可点击的标签，用于触发预览"""
    clicked = pyqtSignal(int)

    def __init__(self, index, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.index = index
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)

class PreviewDialog(QDialog):
    """大图预览对话框，支持前后切换"""
    def __init__(self, images, index, parent=None):
        super().__init__(parent)
        self.images = images
        self.index = index
        self.parent = parent
        self.current_pixmap = None # 存储当前加载的大图 Pixmap
        self.setWindowTitle("大图预览")
        self.setMinimumSize(1200, 900)
        self.resize(1200, 900)
        self.init_ui()
        self.load_image()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 图片显示
        self.img_label = QLabel("加载中...")
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.img_label)

        # 控制按钮
        ctrl_layout = QHBoxLayout()
        self.prev_btn = QPushButton("◀ 上一张")
        self.prev_btn.clicked.connect(self.show_prev)
        self.next_btn = QPushButton("下一张 ▶")
        self.next_btn.clicked.connect(self.show_next)
        
        dl_btn = QPushButton("下载此图")
        dl_btn.clicked.connect(self.download_current)
        set_btn = QPushButton("设为壁纸")
        set_btn.clicked.connect(self.set_wallpaper_current)

        ctrl_layout.addWidget(self.prev_btn)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(dl_btn)
        ctrl_layout.addWidget(set_btn)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.next_btn)
        
        layout.addLayout(ctrl_layout)

    def load_image(self):
        data = self.images[self.index]
        self.img_label.setText(f"正在加载原图 (高清): {data['id']}...")
        self.current_pixmap = None
        
        def fetch():
            try:
                proxies = {"http": self.parent.proxy, "https": self.parent.proxy}
                verify_ssl = get_verify_ssl()
                # 直接拉取原图 path，确保极致清晰度
                r = requests.get(data['path'], proxies=proxies, timeout=30, verify=verify_ssl)
                qimg = QImage.fromData(r.content)
                self.current_pixmap = QPixmap.fromImage(qimg)
                # 使用 QMetaObject.invokeMethod 线程安全地更新 UI
                QMetaObject.invokeMethod(self, "update_image_display", Qt.ConnectionType.QueuedConnection)
            except Exception as e:
                # 如果原图加载失败，尝试回退到 large 预览图
                try:
                    r = requests.get(data['thumbs']['large'], proxies=proxies, timeout=15, verify=verify_ssl)
                    qimg = QImage.fromData(r.content)
                    self.current_pixmap = QPixmap.fromImage(qimg)
                    QMetaObject.invokeMethod(self, "update_image_display", Qt.ConnectionType.QueuedConnection)
                except Exception as inner_e:
                    # 使用 QMetaObject.invokeMethod 更新失败文本
                    QMetaObject.invokeMethod(self.img_label, "setText", 
                                           Qt.ConnectionType.QueuedConnection, 
                                           Q_ARG(str, f"加载失败: {inner_e}"))

        from threading import Thread
        Thread(target=fetch).start()
        
        # 更新按钮状态
        self.prev_btn.setEnabled(self.index > 0)
        self.next_btn.setEnabled(self.index < len(self.images) - 1)

    @pyqtSlot()
    def update_image_display(self):
        """根据当前窗口大小缩放并显示图片"""
        if self.current_pixmap:
            # 留出按钮区域的高度
            scaled_pixmap = self.current_pixmap.scaled(self.size() - QSize(40, 100), 
                                                     Qt.AspectRatioMode.KeepAspectRatio, 
                                                     Qt.TransformationMode.SmoothTransformation)
            self.img_label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        """窗口缩放时自动调整图片显示"""
        self.update_image_display()
        super().resizeEvent(event)

    def show_prev(self):
        if self.index > 0:
            self.index -= 1
            self.load_image()

    def show_next(self):
        if self.index < len(self.images) - 1:
            self.index += 1
            self.load_image()

    def download_current(self):
        data = self.images[self.index]
        self.parent.download_image(data['path'], data['id'])

    def set_wallpaper_current(self):
        data = self.images[self.index]
        self.parent.download_and_set_wallpaper(data['path'], data['id'])

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Left:
            self.show_prev()
        elif event.key() == Qt.Key.Key_Right:
            self.show_next()
        else:
            super().keyPressEvent(event)

class ImageLoaderThread(QThread):
    """异步加载图片列表的线程"""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, params, proxies):
        super().__init__()
        self.params = params
        self.proxies = proxies

    def run(self):
        try:
            # 这里的获取请求也改用 self.session
            verify_ssl = get_verify_ssl()
            resp = requests.get("https://wallhaven.cc/api/v1/search", 
                                params=self.params, 
                                proxies=self.proxies, 
                                timeout=30, 
                                verify=verify_ssl)
            data = resp.json()
            if resp.status_code == 200:
                self.finished.emit(data.get('data', []))
            else:
                self.error.emit(data.get('error', 'API 请求失败'))
        except Exception as e:
            self.error.emit(str(e))

class LoginDialog(QDialog):
    """登录对话框，用于输入 API Key"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("登录 Wallhaven")
        self.setFixedSize(400, 230) # 稍微增加高度以容纳更多提示
        self.api_key = ""
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(30, 25, 30, 25)

        title = QLabel("请输入您的 Wallhaven API Key")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("在此处粘贴 API Key (可选)...")
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.api_input)

        # 提示语优化
        tips_layout = QVBoxLayout()
        tips_layout.setSpacing(5)

        vpn_tip = QLabel("● 需全程科学上网，才能正常使用。")
        vpn_tip.setStyleSheet("font-size: 11px; color: #d32f2f; font-weight: bold;")
        
        nsfw_tip = QLabel("● 解锁 NSFW：需先在官网『Account Settings』中开启『18+』选项，并在此登录对应的 API Key。")
        nsfw_tip.setWordWrap(True)
        nsfw_tip.setStyleSheet("font-size: 11px; color: #555;")
        
        tips_layout.addWidget(vpn_tip)
        tips_layout.addWidget(nsfw_tip)
        layout.addLayout(tips_layout)

        tip_layout = QHBoxLayout()
        tip = QLabel("<a href='https://wallhaven.cc/settings/account'>如何获取 API Key?</a>")
        tip.setOpenExternalLinks(True)
        tip.setStyleSheet("font-size: 11px; color: #0066cc;")
        tip_layout.addWidget(tip)
        tip_layout.addStretch()
        layout.addLayout(tip_layout)

        btn_layout = QHBoxLayout()
        skip_btn = QPushButton("暂不登录")
        skip_btn.setFixedHeight(35)
        skip_btn.clicked.connect(self.reject)
        btn_layout.addWidget(skip_btn)

        login_btn = QPushButton("登录 / 验证")
        login_btn.setFixedHeight(35)
        login_btn.setStyleSheet("background-color: #333; color: white; font-weight: bold;")
        login_btn.clicked.connect(self.verify_and_accept)
        btn_layout.addWidget(login_btn)
        layout.addLayout(btn_layout)

    def verify_and_accept(self):
        key = self.api_input.text().strip()
        if not key:
            QMessageBox.warning(self, "错误", "请输入 API Key")
            return
        
        # 简单的验证逻辑：尝试请求设置
        try:
            params = {'apikey': key}
            # 同样修复这里的验证问题
            verify_ssl = get_verify_ssl()
            r = requests.get("https://wallhaven.cc/api/v1/settings", params=params, timeout=10, verify=verify_ssl)
            if r.status_code == 200:
                self.api_key = key
                self.accept()
            else:
                QMessageBox.critical(self, "验证失败", "无效的 API Key，请检查后重试")
        except Exception as e:
            QMessageBox.critical(self, "网络错误", f"无法连接到 Wallhaven: {e}")

class WallpaperApp(QMainWindow):
    status_signal = pyqtSignal(str, int) # 用于线程安全地更新状态栏 (text, timeout)
    progress_signal = pyqtSignal(int) # 用于更新进度条

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wallhaven 桌面助手")
        self.setMinimumSize(1000, 950) # 增大高度以完整显示三行
        self.resize(1000, 950)
        
        self.api_key = ""
        self.proxy = DEFAULT_PROXY
        
        # 加载配置
        self.config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        self.load_config()
        
        # 移除启动时的强制登录弹窗，直接以现有配置（或游客模式）启动
        
        self.page = 1
        self.current_images = [] # 存储当前页的所有图片数据
        self.cards = [] # 存储当前页的所有卡片 Widget
        self.selected_images = {} # 存储全局选中的图片 {img_id: img_path}
        self.checkboxes = {} # 存储当前显示的复选框 {img_id: checkbox_widget}
        self.selected_color = None # 存储选中的颜色
        self.is_loading = False # 正在加载标志
        
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

        self.init_ui()
        self.status_signal.connect(self.show_status)
        self.progress_signal.connect(self.progress_bar.setValue)
        # 确保信号连接完成后再进行初始搜索，以防 network 线程在连接前发出信号
        self.new_search()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # ---- 顶部工具栏 (分两行显示) ----
        top_bar_layout = QVBoxLayout()
        top_bar_layout.setSpacing(10)
        
        # 第一行: 搜索、排序、范围、分辨率、比例 + 用户信息
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索关键词...")
        self.search_input.setFixedWidth(200)
        row1.addWidget(QLabel("搜索:"))
        row1.addWidget(self.search_input)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Date Added", "Relevance", "Random", "Views", "Favorites", "Toplist", "Hot"])
        row1.addWidget(QLabel("排序:"))
        row1.addWidget(self.sort_combo)

        self.range_label = QLabel("范围:")
        self.range_combo = QComboBox()
        self.range_combo.addItems(["1d", "1w", "1M", "3M", "6M", "1y"])
        self.range_combo.setCurrentText("1M")
        row1.addWidget(self.range_label)
        row1.addWidget(self.range_combo)
        
        # 分辨率
        row1.addWidget(QLabel("分辨率:"))
        self.res_combo = QComboBox()
        self.res_combo.addItems(["Any", "1920x1080", "2560x1440", "3840x2160", "4096x2304", "5120x2880"])
        row1.addWidget(self.res_combo)

        # 比例
        row1.addWidget(QLabel("比例:"))
        self.ratio_combo = QComboBox()
        self.ratio_combo.addItems(["Any", "16x9", "16x10", "4x3", "21x9", "9x16", "10x16"])
        row1.addWidget(self.ratio_combo)

        search_btn = QPushButton("搜索/刷新")
        search_btn.setFixedWidth(100)
        search_btn.clicked.connect(self.new_search)
        row1.addWidget(search_btn)
        
        row1.addStretch(1)

        # 右上角用户栏 (仅保留一个暗色调的可点击人头图标)
        self.user_btn = QPushButton("👤" if self.api_key else "🔑")
        self.user_btn.setFixedSize(28, 28)
        self.user_btn.setToolTip("点击退出登录" if self.api_key else "点击登录")
        self.user_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.user_btn.setStyleSheet("""
            QPushButton {
                background-color: #333; 
                color: #888; 
                border: 1px solid #444; 
                border-radius: 14px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #444;
                color: #eee;
                border: 1px solid #666;
            }
        """)
        self.user_btn.clicked.connect(self.logout)
        row1.addWidget(self.user_btn)
        
        top_bar_layout.addLayout(row1)

        # 第二行: 分类、纯净度
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        
        # 分类
        row2.addWidget(QLabel("分类:"))
        self.cat_general = QCheckBox("General")
        self.cat_general.setChecked(True)
        self.cat_anime = QCheckBox("Anime")
        self.cat_anime.setChecked(True)
        self.cat_people = QCheckBox("People")
        self.cat_people.setChecked(True)
        row2.addWidget(self.cat_general)
        row2.addWidget(self.cat_anime)
        row2.addWidget(self.cat_people)
        
        row2.addSpacing(30)

        # 纯净度
        row2.addWidget(QLabel("纯净度:"))
        self.purity_sfw = QCheckBox("SFW")
        self.purity_sfw.setChecked(True)
        self.purity_sketchy = QCheckBox("Sketchy")
        self.purity_sketchy.setChecked(True)
        self.purity_nsfw = QCheckBox("NSFW")
        self.purity_nsfw.setChecked(True if self.api_key else False) # 有 API 时默认勾选，没有则不勾选
        if not self.api_key:
            self.purity_nsfw.setEnabled(False)
            self.purity_nsfw.setToolTip("登录后即可解锁 NSFW 内容")
        
        row2.addWidget(self.purity_sfw)
        row2.addWidget(self.purity_sketchy)
        row2.addWidget(self.purity_nsfw)

        row2.addSpacing(30)

        # 颜色筛选
        row2.addWidget(QLabel("颜色:"))
        self.color_btn = QPushButton("全部")
        self.color_btn.setFixedWidth(80)
        self.color_btn.clicked.connect(self.show_color_menu)
        row2.addWidget(self.color_btn)

        row2.addStretch(1) # 关键：让所有控件向左靠拢
        top_bar_layout.addLayout(row2)
        main_layout.addLayout(top_bar_layout)

        # 初始可见性逻辑（必须在所有 UI 控件初始化完成后调用）
        self.sort_combo.currentTextChanged.connect(self.on_sort_changed)
        self.sort_combo.setCurrentText("Toplist") 
        self.on_sort_changed(self.sort_combo.currentText())

        # ---- 图片展示区域 ----
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.scroll_area.setWidget(self.grid_widget)
        main_layout.addWidget(self.scroll_area)

        # ---- 底部状态栏/翻页 ----
        bottom_bar = QHBoxLayout()
        
        # 左侧功能区
        left_ctrl = QHBoxLayout()
        dir_btn = QPushButton("更改保存目录")
        dir_btn.clicked.connect(self.change_dir)
        left_ctrl.addWidget(dir_btn)

        open_dir_btn = QPushButton("打开下载目录")
        open_dir_btn.clicked.connect(self.open_save_dir)
        left_ctrl.addWidget(open_dir_btn)

        self.select_all_btn = QPushButton("全选本页")
        self.select_all_btn.clicked.connect(self.select_all_current)
        left_ctrl.addWidget(self.select_all_btn)

        self.batch_dl_btn = QPushButton("批量下载 (0)")
        self.batch_dl_btn.clicked.connect(self.batch_download_selected)
        left_ctrl.addWidget(self.batch_dl_btn)
        
        bottom_bar.addLayout(left_ctrl)

        # 中间状态提示
        bottom_bar.addStretch(1)
        
        status_container = QVBoxLayout()
        self.status_label = QLabel("准备就绪")
        self.status_label.setStyleSheet("color: #666; font-size: 11px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide() # 初始隐藏
        
        status_container.addWidget(self.status_label)
        status_container.addWidget(self.progress_bar)
        bottom_bar.addLayout(status_container)
        
        bottom_bar.addStretch(1)

        # 右侧翻页区
        right_ctrl = QHBoxLayout()
        self.prev_btn_ctrl = QPushButton("上一页")
        self.prev_btn_ctrl.clicked.connect(self.prev_page)
        self.next_btn_ctrl = QPushButton("下一页")
        self.next_btn_ctrl.clicked.connect(self.next_page)
        
        right_ctrl.addWidget(self.prev_btn_ctrl)
        
        # 将 QLabel 改为 QLineEdit 以支持输入跳转
        right_ctrl.addWidget(QLabel("第"))
        self.page_input = QLineEdit(str(self.page))
        self.page_input.setFixedWidth(40)
        self.page_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_input.setValidator(QIntValidator(1, 9999))
        self.page_input.returnPressed.connect(self.jump_to_page)
        right_ctrl.addWidget(self.page_input)
        right_ctrl.addWidget(QLabel("页"))
        
        right_ctrl.addWidget(self.next_btn_ctrl)
        
        bottom_bar.addLayout(right_ctrl)

        main_layout.addLayout(bottom_bar)

    def on_sort_changed(self, text):
        """当排序方式改变时，控制范围选择框的显示/隐藏"""
        is_toplist = text == "Toplist"
        self.range_label.setVisible(is_toplist)
        self.range_combo.setVisible(is_toplist)

    def show_color_menu(self):
        """显示仿官网的颜色选择面板"""
        menu = QMenu(self)
        container = QWidget()
        layout = QGridLayout(container)
        layout.setSpacing(2)
        layout.setContentsMargins(5, 5, 5, 5)

        # Wallhaven 官方支持的颜色列表
        colors = [
            "660000", "990000", "cc0000", "cc3333", "ea4c88", "993399", "663399", "333399",
            "0066cc", "0099cc", "66cccc", "77cc33", "669900", "336600", "666600", "999900",
            "cccc33", "ffff00", "ffc125", "ff9900", "ff6600", "ff4500", "d46f31", "aa6633",
            "996633", "663300", "000000", "424153", "999999", "cccccc", "ffffff", "adadad"
        ]

        row, col = 0, 0
        for color_hex in colors:
            btn = QPushButton()
            btn.setFixedSize(25, 15)
            btn.setStyleSheet(f"background-color: #{color_hex}; border: 1px solid #444;")
            btn.clicked.connect(lambda checked, c=color_hex: self.select_color(c, menu))
            layout.addWidget(btn, row, col)
            col += 1
            if col >= 8:
                col = 0
                row += 1
        
        # 添加一个“重置”按钮
        reset_btn = QPushButton("清除选择")
        reset_btn.clicked.connect(lambda: self.select_color(None, menu))
        layout.addWidget(reset_btn, row, 0, 1, 8)

        action = QWidgetAction(menu)
        action.setDefaultWidget(container)
        menu.addAction(action)
        
        # 在按钮下方弹出
        menu.exec(self.color_btn.mapToGlobal(self.color_btn.rect().bottomLeft()))

    def select_color(self, color_hex, menu):
        """选中颜色并关闭菜单"""
        self.selected_color = color_hex
        if color_hex:
            self.color_btn.setText("")
            self.color_btn.setStyleSheet(f"background-color: #{color_hex}; border: 1px solid #888;")
        else:
            self.color_btn.setText("全部")
            self.color_btn.setStyleSheet("")
        menu.close()
        self.new_search()

    def new_search(self):
        """全新的搜索/刷新逻辑，回到第一页"""
        self.page = 1
        self.refresh_images()

    def refresh_images(self, append=False):
        if self.is_loading: return
        self.is_loading = True
        
        # 如果不是追加模式，清空网格
        if not append:
            # 不在这里重置 self.page，而是在触发搜索的地方显式重置
            for i in reversed(range(self.grid_layout.count())): 
                item = self.grid_layout.itemAt(i)
                if item and item.widget():
                    item.widget().setParent(None)
            self.current_images = []
            self.cards = []
            self.checkboxes = {} # 清空当前页的复选框引用
            self.page_input.setText(str(self.page))

        purity = ""
        purity += "1" if self.purity_sfw.isChecked() else "0"
        purity += "1" if self.purity_sketchy.isChecked() else "0"
        purity += "1" if self.purity_nsfw.isChecked() else "0"

        categories = ""
        categories += "1" if self.cat_general.isChecked() else "0"
        categories += "1" if self.cat_anime.isChecked() else "0"
        categories += "1" if self.cat_people.isChecked() else "0"

        # 映射显示名称到 API 字段
        sort_map = {
            "Date Added": "date_added",
            "Relevance": "relevance",
            "Random": "random",
            "Views": "views",
            "Favorites": "favorites",
            "Toplist": "toplist",
            "Hot": "hot"
        }
        sorting = sort_map.get(self.sort_combo.currentText(), "date_added")

        params = {
            'apikey': self.api_key,
            'q': self.search_input.text(),
            'sorting': sorting,
            'purity': purity,
            'categories': categories,
            'page': self.page,
        }
        
        # 只有 toplist 模式下才需要 topRange
        if sorting == "toplist":
            params['topRange'] = self.range_combo.currentText()
        
        # 添加分辨率筛选
        if self.res_combo.currentText() != "Any":
            params['resolutions'] = self.res_combo.currentText()
        
        # 添加比例筛选
        if self.ratio_combo.currentText() != "Any":
            params['ratios'] = self.ratio_combo.currentText()
        
        # 添加颜色筛选
        if self.selected_color:
            params['colors'] = self.selected_color
        
        proxies = {"http": self.proxy, "https": self.proxy}
        
        self.loader = ImageLoaderThread(params, proxies)
        self.loader.finished.connect(lambda imgs: self.on_images_loaded(imgs, append))
        self.loader.error.connect(self.on_load_error)
        self.loader.start()

    def on_images_loaded(self, images, append):
        self.is_loading = False
        if not images:
            if not append: QMessageBox.information(self, "提示", "未找到图片")
            return

        start_index = len(self.current_images)
        self.current_images.extend(images)
        
        for i, img_data in enumerate(images):
            card = self.create_image_card(img_data, start_index + i)
            self.cards.append(card)
        
        self.relayout()
        # 更新批量下载按钮数量
        self.batch_dl_btn.setText(f"批量下载 ({len(self.selected_images)})")
    
    def on_load_error(self, err_msg):
        self.is_loading = False
        QMessageBox.critical(self, "错误", f"获取图片失败: {err_msg}")

    def relayout(self):
        """重新排列网格中的卡片，以适应当前窗口宽度"""
        # 清空网格布局（但不销毁部件）
        for i in reversed(range(self.grid_layout.count())): 
            item = self.grid_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)

        if not self.cards:
            return

        # 计算列数: 窗口宽度 / (卡片宽度 + 间距)
        # 卡片宽度约为 THUMBNAIL_SIZE[0] + 布局边距
        available_width = self.scroll_area.width() - 40
        card_width = THUMBNAIL_SIZE[0] + 20
        cols = max(1, available_width // card_width)
        
        row, col = 0, 0
        for card in self.cards:
            self.grid_layout.addWidget(card, row, col)
            col += 1
            if col >= cols:
                col = 0
                row += 1
    
    def resizeEvent(self, event):
        """主窗口缩放时重新排列布局"""
        self.relayout()
        super().resizeEvent(event)
    
    def show_status(self, text, timeout=2000):
        self.status_label.setText(text)
        if timeout > 0:
            from PyQt6.QtCore import QTimer
            # 不再恢复为“就绪”，而是保留最后一条有意义的状态信息
            # QTimer.singleShot(timeout, lambda: self.status_label.setText("就绪"))
            pass

    def create_image_card(self, data, index):
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setFixedWidth(THUMBNAIL_SIZE[0] + 20)
        layout = QVBoxLayout(card)

        # 复选框和 ID 栏
        top_info = QHBoxLayout()
        cb = QCheckBox()
        img_id = data['id']
        cb.setChecked(img_id in self.selected_images)
        cb.stateChanged.connect(lambda state: self.on_checkbox_changed(state, data))
        self.checkboxes[img_id] = cb # 记录当前页显示的复选框
        
        id_label = QLabel(f"ID: {img_id}")
        id_label.setStyleSheet("color: #888; font-size: 10px;")
        
        top_info.addWidget(cb)
        top_info.addWidget(id_label)
        top_info.addStretch()
        layout.addLayout(top_info)

        # 预览图 (使用可点击的 ClickableLabel)
        img_label = ClickableLabel(index, "加载中...")
        img_label.setFixedSize(QSize(*THUMBNAIL_SIZE))
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.clicked.connect(self.open_preview)
        layout.addWidget(img_label)

        # 异步加载缩略图
        def load_thumb():
            try:
                proxies = {"http": self.proxy, "https": self.proxy}
                verify_ssl = get_verify_ssl()
                # 使用 large 预览图替代 small，解决模糊问题
                r = requests.get(data['thumbs']['large'], proxies=proxies, timeout=10, verify=verify_ssl)
                qimg = QImage.fromData(r.content)
                pixmap = QPixmap.fromImage(qimg).scaled(QSize(*THUMBNAIL_SIZE), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                # 线程安全更新 Pixmap
                QMetaObject.invokeMethod(img_label, "setPixmap", 
                                       Qt.ConnectionType.QueuedConnection, 
                                       Q_ARG(QPixmap, pixmap))
            except Exception as e:
                # 线程安全更新文本
                QMetaObject.invokeMethod(img_label, "setText", 
                                       Qt.ConnectionType.QueuedConnection, 
                                       Q_ARG(str, "预览失败"))
        
        # 按钮
        btn_layout = QHBoxLayout()
        dl_btn = QPushButton("下载")
        dl_btn.clicked.connect(lambda: self.start_single_download(data['path'], data['id']))
        set_btn = QPushButton("壁纸")
        set_btn.clicked.connect(lambda: self.download_and_set_wallpaper(data['path'], data['id']))
        
        btn_layout.addWidget(dl_btn)
        btn_layout.addWidget(set_btn)
        layout.addLayout(btn_layout)

        # 启动缩略图加载
        from threading import Thread
        Thread(target=load_thumb).start()

        return card

    def on_checkbox_changed(self, state, data):
        """当单个复选框状态改变时，更新全局选中字典"""
        img_id = data['id']
        if state == 2: # Checked
            self.selected_images[img_id] = data['path']
        else: # Unchecked
            if img_id in self.selected_images:
                del self.selected_images[img_id]
        
        self.batch_dl_btn.setText(f"批量下载 ({len(self.selected_images)})")

    def select_all_current(self):
        """全选/取消全选当前页的所有图片"""
        # 简单逻辑：如果当前页有没有选中的，就全选；否则全部取消
        all_checked = True
        for cb in self.checkboxes.values():
            if not cb.isChecked():
                all_checked = False
                break
        
        new_state = not all_checked
        for cb in self.checkboxes.values():
            cb.setChecked(new_state)

    def batch_download_selected(self):
        """批量下载所有选中的图片"""
        if not self.selected_images:
            QMessageBox.information(self, "提示", "请先勾选要下载的图片")
            return

        count = len(self.selected_images)
        
        # 移除确认弹窗，直接执行
        # 确保保存目录存在
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
        
        # 初始化进度条
        self.progress_bar.setMaximum(count)
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        
        # 使用多线程下载，防止阻塞 UI
        from concurrent.futures import ThreadPoolExecutor
        def do_batch():
            self.status_signal.emit(f"准备下载 {count} 张图片...", 0)
            completed = 0
            with ThreadPoolExecutor(max_workers=5) as executor:
                # 提交所有任务
                futures = []
                for img_id, img_url in list(self.selected_images.items()):
                    futures.append(executor.submit(self.download_image, img_url, img_id))
                
                # 等待并更新进度
                for _ in futures:
                    _.result() # 等待单个完成
                    completed += 1
                    self.progress_signal.emit(completed)
                    self.status_signal.emit(f"正在下载: {completed}/{count}", 0)
            
            self.status_signal.emit(f"已完成 {count} 张下载", 3000)
            
            # 下载完成后清除选中状态
            # 注意：这里修改 UI 也要小心，但由于 self.checkboxes 是 UI 控件，最好通过 QMetaObject 或者让主线程来做
            from PyQt6.QtCore import QMetaObject, Q_ARG
            QMetaObject.invokeMethod(self, "clear_selections", Qt.ConnectionType.QueuedConnection)

            from PyQt6.QtCore import QTimer
            QTimer.singleShot(3000, self.progress_bar.hide) # 延时隐藏进度条

        from threading import Thread
        Thread(target=do_batch).start()

    def start_single_download(self, url, img_id):
        """异步开始单张下载，避免界面卡顿"""
        from threading import Thread
        Thread(target=self.download_image, args=(url, img_id)).start()

    def open_preview(self, index):
        """打开大图预览窗口"""
        dialog = PreviewDialog(self.current_images, index, self)
        dialog.exec()

    def download_image(self, url, img_id, quiet=False):
        try:
            # 确保保存目录存在
            if not os.path.exists(self.save_dir):
                os.makedirs(self.save_dir)

            proxies = {"http": self.proxy, "https": self.proxy}
            ext = url.split('.')[-1]
            path = os.path.join(self.save_dir, f"{img_id}.{ext}")
            
            if os.path.exists(path):
                self.status_signal.emit(f"ID: {img_id} 已存在", 2000)
                return path

            # 单个下载时显示进度条
            is_single = not self.progress_bar.isVisible()
            if is_single:
                self.progress_bar.setMaximum(0) # 忙碌模式
                self.progress_bar.setValue(0)
                # 由于 progress_bar.show() 会修改 UI，这里也要小心
                from PyQt6.QtCore import QMetaObject, Q_ARG
                QMetaObject.invokeMethod(self.progress_bar, "show", Qt.ConnectionType.QueuedConnection)

            self.status_signal.emit(f"正在下载: {img_id}...", 0)
            verify_ssl = get_verify_ssl()
            r = requests.get(url, proxies=proxies, timeout=60, verify=verify_ssl)
            if r.status_code == 200:
                with open(path, 'wb') as f:
                    f.write(r.content)
                self.status_signal.emit(f"ID: {img_id} 完成", 1000)
                if is_single:
                    QMetaObject.invokeMethod(self.progress_bar, "hide", Qt.ConnectionType.QueuedConnection)
                return path
            else:
                self.status_signal.emit(f"下载失败: {r.status_code}", 2000)
                if is_single:
                    QMetaObject.invokeMethod(self.progress_bar, "hide", Qt.ConnectionType.QueuedConnection)
                return None
        except Exception as e:
            self.status_signal.emit("下载异常", 2000)
            print(f"下载错误: {e}")
            if 'is_single' in locals() and is_single:
                QMetaObject.invokeMethod(self.progress_bar, "hide", Qt.ConnectionType.QueuedConnection)
            return None

    def download_and_set_wallpaper(self, url, img_id):
        def do_set():
            path = self.download_image(url, img_id, quiet=True)
            if path:
                try:
                    set_wallpaper(os.path.abspath(path))
                    self.status_signal.emit("壁纸设置成功", 2000)
                except Exception as e:
                    self.status_signal.emit(f"设置壁纸失败: {e}", 2000)
        
        from threading import Thread
        Thread(target=do_set).start()

    def next_page(self):
        self.page += 1
        self.page_input.setText(str(self.page))
        self.refresh_images()

    def prev_page(self):
        if self.page > 1:
            self.page -= 1
            self.page_input.setText(str(self.page))
            self.refresh_images()

    @pyqtSlot()
    def clear_selections(self):
        """主线程调用的清除选中状态方法"""
        self.selected_images.clear()
        for cb in self.checkboxes.values():
            cb.setChecked(False)
        self.batch_dl_btn.setText(f"批量下载 (0)")

    def jump_to_page(self):
        """跳转到输入的页码"""
        try:
            new_page = int(self.page_input.text())
            if new_page >= 1:
                self.page = new_page
                self.refresh_images()
            else:
                self.page_input.setText(str(self.page))
        except ValueError:
            self.page_input.setText(str(self.page))

    def logout(self):
        """退出登录或进入登录流程"""
        if not self.api_key:
            # 游客模式点击图标，弹出登录框
            login = LoginDialog(self)
            if login.exec() == QDialog.DialogCode.Accepted:
                self.api_key = login.api_key
                self.save_config()
                self.update_user_ui()
                self.new_search()
            return

        reply = QMessageBox.question(self, "确认", "确定要退出登录吗？退出后将清除已保存的 API Key 并回到游客模式。", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.api_key = ""
            self.save_config()
            self.update_user_ui()
            self.new_search()

    def update_user_ui(self):
        """更新与用户登录状态相关的 UI 元素"""
        self.user_btn.setText("👤" if self.api_key else "🔑")
        self.user_btn.setToolTip("点击退出登录" if self.api_key else "点击登录")
        
        # 更新 NSFW 复选框
        self.purity_nsfw.setEnabled(bool(self.api_key))
        if not self.api_key:
            self.purity_nsfw.setChecked(False)
            self.purity_nsfw.setToolTip("登录后即可解锁 NSFW 内容")
        else:
            self.purity_nsfw.setChecked(True)
            self.purity_nsfw.setToolTip("")

    def change_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "选择保存目录", self.save_dir)
        if directory:
            self.save_dir = directory
            self.save_config()
            self.status_signal.emit(f"保存目录已更改: {self.save_dir}", 3000)

    def open_save_dir(self):
        """打开下载目录文件夹"""
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
        os.startfile(self.save_dir)

    def load_config(self):
        """加载配置文件"""
        default_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Wallhaven_Downloads")
        self.save_dir = default_dir
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.save_dir = config.get("save_dir", default_dir)
                    self.api_key = config.get("api_key", "") # 加载 API Key
            except Exception as e:
                print(f"加载配置失败: {e}")
        
        # 确保目录存在
        if not os.path.exists(self.save_dir):
            try:
                os.makedirs(self.save_dir)
            except:
                pass

    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "save_dir": self.save_dir,
                    "api_key": self.api_key # 保存 API Key
                }, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存配置失败: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WallpaperApp()
    window.show()
    sys.exit(app.exec())
