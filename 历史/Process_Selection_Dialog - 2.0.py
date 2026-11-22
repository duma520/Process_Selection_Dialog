import sys
import os
import numpy as np
import cv2
import json
import time
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, 
                           QVBoxLayout, QPushButton, QLabel, QListWidget, 
                           QDialog, QHBoxLayout, QFileDialog, QComboBox,
                           QSpinBox, QDoubleSpinBox, QCheckBox, QSlider,
                           QGroupBox, QMessageBox, QInputDialog, QAction,
                           QMenu, QToolBar, QStatusBar, QSplitter,QFormLayout,
                           QLineEdit,QListWidgetItem)
from PyQt5.QtCore import Qt, QTimer, QSize, QRect, QPoint
from PyQt5.QtGui import (QImage, QPixmap, QPainter, QPen, QColor, QIcon, 
                        QFont, QCursor, QBrush)
import dxcam
from skimage import measure


class ProcessSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择目标进程")
        self.setWindowModality(Qt.ApplicationModal)
        self.resize(500, 400)
        
        self.layout = QVBoxLayout()
        
        # 筛选区域
        self.filter_group = QGroupBox("进程筛选")
        self.filter_layout = QHBoxLayout()
        
        self.filter_label = QLabel("筛选条件:")
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["所有进程", "图形窗口", "高CPU占用", "高内存占用"])
        self.filter_text = QLineEdit()
        self.filter_text.setPlaceholderText("输入进程名...")
        self.refresh_btn = QPushButton("刷新")
        
        self.filter_layout.addWidget(self.filter_label)
        self.filter_layout.addWidget(self.filter_combo)
        self.filter_layout.addWidget(self.filter_text)
        self.filter_layout.addWidget(self.refresh_btn)
        self.filter_group.setLayout(self.filter_layout)
        
        # 进程列表
        self.process_list = QListWidget()
        self.process_list.setIconSize(QSize(32, 32))
        
        # 详情区域
        self.detail_group = QGroupBox("进程详情")
        self.detail_layout = QVBoxLayout()
        self.detail_label = QLabel("选择进程查看详情")
        self.detail_label.setWordWrap(True)
        self.detail_layout.addWidget(self.detail_label)
        self.detail_group.setLayout(self.detail_layout)
        
        # 按钮区域
        self.button_layout = QHBoxLayout()
        self.ok_button = QPushButton("确定")
        self.cancel_button = QPushButton("取消")
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.ok_button)
        self.button_layout.addWidget(self.cancel_button)
        
        # 主布局
        self.layout.addWidget(self.filter_group)
        
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.process_list)
        splitter.addWidget(self.detail_group)
        self.layout.addWidget(splitter)
        self.layout.addLayout(self.button_layout)
        
        self.setLayout(self.layout)
        
        # 模拟进程数据
        self.simulate_processes = [
            {"name": "explorer.exe", "title": "文件资源管理器", "cpu": 2.5, "memory": 120, "icon": "folder"},
            {"name": "chrome.exe", "title": "Google Chrome", "cpu": 15.8, "memory": 450, "icon": "browser"},
            {"name": "notepad.exe", "title": "记事本", "cpu": 0.5, "memory": 25, "icon": "text"},
            {"name": "python.exe", "title": "Python 解释器", "cpu": 3.2, "memory": 80, "icon": "code"},
            {"name": "dwm.exe", "title": "桌面窗口管理器", "cpu": 1.8, "memory": 65, "icon": "window"},
            {"name": "photoshop.exe", "title": "Adobe Photoshop", "cpu": 8.7, "memory": 320, "icon": "image"},
            {"name": "spotify.exe", "title": "Spotify", "cpu": 4.1, "memory": 180, "icon": "music"}
        ]
        
        # 连接信号
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self.refresh_btn.clicked.connect(self.refresh_processes)
        self.process_list.itemSelectionChanged.connect(self.show_process_details)
        self.filter_combo.currentIndexChanged.connect(self.refresh_processes)
        self.filter_text.textChanged.connect(self.refresh_processes)
        
        self.refresh_processes()
    
    def refresh_processes(self):
        self.process_list.clear()
        
        filter_type = self.filter_combo.currentText()
        filter_text = self.filter_text.text().lower()
        
        for proc in self.simulate_processes:
            # 应用筛选条件
            if filter_text and filter_text not in proc["name"].lower() and filter_text not in proc["title"].lower():
                continue
                
            if filter_type == "高CPU占用" and proc["cpu"] < 5:
                continue
                
            if filter_type == "高内存占用" and proc["memory"] < 100:
                continue
                
            # 创建列表项
            item = QListWidgetItem()
            item.setText(f"{proc['name']} - {proc['title']} (CPU: {proc['cpu']}%, 内存: {proc['memory']}MB")
            
            # 设置图标 (实际应用中应该获取真实进程图标)
            icon_name = proc["icon"]
            if icon_name == "folder":
                item.setIcon(QIcon.fromTheme("folder"))
            elif icon_name == "browser":
                item.setIcon(QIcon.fromTheme("web-browser"))
            elif icon_name == "text":
                item.setIcon(QIcon.fromTheme("text-plain"))
            elif icon_name == "code":
                item.setIcon(QIcon.fromTheme("text-x-python"))
            elif icon_name == "window":
                item.setIcon(QIcon.fromTheme("window"))
            elif icon_name == "image":
                item.setIcon(QIcon.fromTheme("image-x-generic"))
            elif icon_name == "music":
                item.setIcon(QIcon.fromTheme("audio-x-generic"))
            
            item.setData(Qt.UserRole, proc)
            self.process_list.addItem(item)
    
    def show_process_details(self):
        selected = self.process_list.selectedItems()
        if not selected:
            return
            
        proc = selected[0].data(Qt.UserRole)
        details = f"""
        <b>进程名称:</b> {proc['name']}<br>
        <b>窗口标题:</b> {proc['title']}<br>
        <b>CPU占用:</b> {proc['cpu']}%<br>
        <b>内存占用:</b> {proc['memory']} MB<br>
        <b>进程ID:</b> {hash(proc['name']) % 10000} (模拟)<br>
        """
        self.detail_label.setText(details)


class TrajectoryWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.trajectory_points = []  # 存储所有轨迹点
        self.current_frame = None    # 当前帧图像
        self.trajectory_colors = []  # 不同轨迹的颜色
        self.active_trajectory = 0   # 当前活动轨迹索引
        self.show_trajectory = True  # 是否显示轨迹
        self.show_points = True      # 是否显示轨迹点
        self.show_info = True        # 是否显示信息
        self.grid_size = 50          # 网格大小
        self.show_grid = False       # 是否显示网格
        self.measure_points = []     # 测量点
        self.measure_mode = False    # 是否处于测量模式
        self.setMouseTracking(True)
        self.setMinimumSize(640, 480)
        
        # 初始化默认颜色
        self.trajectory_colors = [
            QColor(255, 0, 0),     # 红色
            QColor(0, 255, 0),      # 绿色
            QColor(0, 0, 255),      # 蓝色
            QColor(255, 255, 0),    # 黄色
            QColor(255, 0, 255),    # 紫色
            QColor(0, 255, 255),    # 青色
        ]
        
    def set_frame(self, frame):
        """设置当前帧图像"""
        self.current_frame = frame
        self.update()
        
    def add_point(self, point, trajectory_idx=0):
        """添加轨迹点"""
        while len(self.trajectory_points) <= trajectory_idx:
            self.trajectory_points.append([])
            
        self.trajectory_points[trajectory_idx].append(point)
        self.update()
        
    def clear_trajectory(self, trajectory_idx=None):
        """清除轨迹"""
        if trajectory_idx is None:
            self.trajectory_points = []
        else:
            if trajectory_idx < len(self.trajectory_points):
                self.trajectory_points[trajectory_idx] = []
        self.update()
        
    def start_measure(self):
        """开始测量"""
        self.measure_mode = True
        self.measure_points = []
        self.setCursor(Qt.CrossCursor)
        
    def end_measure(self):
        """结束测量"""
        self.measure_mode = False
        self.measure_points = []
        self.unsetCursor()
        self.update()
        
    def mousePressEvent(self, event):
        if self.measure_mode and event.button() == Qt.LeftButton:
            pos = event.pos()
            # 转换为图像坐标
            img_pos = self._window_to_image(pos)
            if img_pos:
                self.measure_points.append(img_pos)
                self.update()
                
    def mouseMoveEvent(self, event):
        if self.measure_mode:
            self.update()
            
    def paintEvent(self, event):
        painter = QPainter(self)
        
        # 绘制背景
        painter.fillRect(self.rect(), QBrush(QColor(50, 50, 50)))
        
        # 绘制当前帧
        if self.current_frame is not None:
            height, width, channel = self.current_frame.shape
            bytes_per_line = 3 * width
            q_img = QImage(self.current_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
            
            # 计算缩放后的尺寸，保持宽高比
            img_ratio = width / height
            widget_ratio = self.width() / self.height()
            
            if img_ratio > widget_ratio:
                # 以宽度为准
                display_width = self.width()
                display_height = int(display_width / img_ratio)
            else:
                # 以高度为准
                display_height = self.height()
                display_width = int(display_height * img_ratio)
                
            # 居中显示
            x_offset = (self.width() - display_width) // 2
            y_offset = (self.height() - display_height) // 2
            
            self.display_rect = QRect(x_offset, y_offset, display_width, display_height)
            painter.drawPixmap(self.display_rect, QPixmap.fromImage(q_img))
            
            # 绘制网格
            if self.show_grid and self.display_rect.width() > 0:
                pen = QPen(QColor(255, 255, 255, 50), 1, Qt.DotLine)
                painter.setPen(pen)
                
                # 计算网格线数量
                x_lines = int(display_width / self.grid_size) + 1
                y_lines = int(display_height / self.grid_size) + 1
                
                # 绘制垂直线
                for i in range(x_lines):
                    x = x_offset + i * self.grid_size
                    painter.drawLine(x, y_offset, x, y_offset + display_height)
                
                # 绘制水平线
                for i in range(y_lines):
                    y = y_offset + i * self.grid_size
                    painter.drawLine(x_offset, y, x_offset + display_width, y)
        
        # 绘制轨迹
        if self.show_trajectory:
            for traj_idx, trajectory in enumerate(self.trajectory_points):
                if len(trajectory) > 1:
                    color = self.trajectory_colors[traj_idx % len(self.trajectory_colors)]
                    pen = QPen(color, 3)
                    painter.setPen(pen)
                    
                    # 绘制轨迹线
                    for i in range(1, len(trajectory)):
                        prev_point = self._image_to_window(trajectory[i-1])
                        curr_point = self._image_to_window(trajectory[i])
                        if prev_point and curr_point:
                            painter.drawLine(prev_point, curr_point)
                    
                    # 绘制轨迹点
                    if self.show_points:
                        point_pen = QPen(color, 1)
                        painter.setPen(point_pen)
                        brush = QBrush(color)
                        painter.setBrush(brush)
                        
                        for point in trajectory:
                            win_point = self._image_to_window(point)
                            if win_point:
                                painter.drawEllipse(win_point, 3, 3)
        
        # 绘制测量线和距离
        if len(self.measure_points) >= 1:
            pen = QPen(QColor(0, 255, 255), 2, Qt.DashLine)
            painter.setPen(pen)
            
            # 绘制已确定的点
            for i, point in enumerate(self.measure_points):
                win_point = self._image_to_window(point)
                if win_point:
                    painter.drawEllipse(win_point, 5, 5)
                    if i > 0:
                        prev_point = self._image_to_window(self.measure_points[i-1])
                        painter.drawLine(prev_point, win_point)
                        
                        # 计算并显示距离
                        dx = point[0] - self.measure_points[i-1][0]
                        dy = point[1] - self.measure_points[i-1][1]
                        distance = np.sqrt(dx*dx + dy*dy)
                        mid_x = (prev_point.x() + win_point.x()) / 2
                        mid_y = (prev_point.y() + win_point.y()) / 2
                        painter.drawText(int(mid_x), int(mid_y), f"{distance:.1f}px")
            
            # 绘制当前鼠标位置到最后一个点的线
            if self.measure_mode and len(self.measure_points) > 0:
                mouse_pos = self.mapFromGlobal(QCursor.pos())
                img_pos = self._window_to_image(mouse_pos)
                if img_pos:
                    last_point = self._image_to_window(self.measure_points[-1])
                    curr_point = self._image_to_window(img_pos)
                    if last_point and curr_point:
                        painter.drawLine(last_point, curr_point)
                        
                        # 计算并显示距离
                        dx = img_pos[0] - self.measure_points[-1][0]
                        dy = img_pos[1] - self.measure_points[-1][1]
                        distance = np.sqrt(dx*dx + dy*dy)
                        mid_x = (last_point.x() + curr_point.x()) / 2
                        mid_y = (last_point.y() + curr_point.y()) / 2
                        painter.drawText(int(mid_x), int(mid_y), f"{distance:.1f}px")
        
        # 绘制信息
        if self.show_info and self.current_frame is not None:
            info_text = f"帧尺寸: {self.current_frame.shape[1]}x{self.current_frame.shape[0]}\n"
            info_text += f"轨迹数: {len(self.trajectory_points)}\n"
            for i, traj in enumerate(self.trajectory_points):
                info_text += f"轨迹{i+1}点数: {len(traj)}\n"
            
            pen = QPen(QColor(255, 255, 255))
            painter.setPen(pen)
            painter.drawText(10, 20, info_text)
        
        painter.end()
    
    def _window_to_image(self, window_point):
        """将窗口坐标转换为图像坐标"""
        if not hasattr(self, 'display_rect') or not self.display_rect or self.current_frame is None:
            return None
            
        # 检查点是否在图像区域内
        if not self.display_rect.contains(window_point):
            return None
            
        # 计算相对于图像的位置
        rel_x = window_point.x() - self.display_rect.x()
        rel_y = window_point.y() - self.display_rect.y()
        
        # 转换为图像坐标
        img_x = int(rel_x * self.current_frame.shape[1] / self.display_rect.width())
        img_y = int(rel_y * self.current_frame.shape[0] / self.display_rect.height())
        
        return (img_x, img_y)
    
    def _image_to_window(self, image_point):
        """将图像坐标转换为窗口坐标"""
        if not hasattr(self, 'display_rect') or not self.display_rect or self.current_frame is None:
            return None
            
        # 检查点是否在图像范围内
        if (image_point[0] < 0 or image_point[0] >= self.current_frame.shape[1] or
            image_point[1] < 0 or image_point[1] >= self.current_frame.shape[0]):
            return None
            
        # 转换为窗口坐标
        win_x = int(image_point[0] * self.display_rect.width() / self.current_frame.shape[1]) + self.display_rect.x()
        win_y = int(image_point[1] * self.display_rect.height() / self.current_frame.shape[0]) + self.display_rect.y()
        
        return QPoint(win_x, win_y)


class MotionDetector:
    def __init__(self):
        self.prev_frame = None
        self.min_contour_area = 100
        self.threshold = 25
        self.detection_roi = None  # (x, y, w, h)
        
    def set_roi(self, roi):
        """设置检测区域"""
        self.detection_roi = roi
        
    def detect(self, frame):
        """检测运动物体"""
        if frame is None:
            return []
            
        # 转换为灰度图
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        
        # 应用ROI
        if self.detection_roi:
            x, y, w, h = self.detection_roi
            gray = gray[y:y+h, x:x+w]
        
        # 初始化前一帧
        if self.prev_frame is None:
            self.prev_frame = gray
            return []
            
        # 计算帧差
        frame_diff = cv2.absdiff(gray, self.prev_frame)
        self.prev_frame = gray
        
        # 二值化
        _, threshold = cv2.threshold(frame_diff, self.threshold, 255, cv2.THRESH_BINARY)
        
        # 膨胀处理
        kernel = np.ones((5, 5), np.uint8)
        threshold = cv2.dilate(threshold, kernel, iterations=1)
        
        # 查找轮廓
        contours, _ = cv2.findContours(threshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 过滤小轮廓
        motion_centers = []
        for cnt in contours:
            if cv2.contourArea(cnt) > self.min_contour_area:
                # 计算轮廓中心
                M = cv2.moments(cnt)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    
                    # 如果有ROI，调整坐标
                    if self.detection_roi:
                        cx += self.detection_roi[0]
                        cy += self.detection_roi[1]
                        
                    motion_centers.append((cx, cy))
        
        return motion_centers


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("高级进程画面轨迹记录工具")
        self.resize(1200, 800)
        
        # 初始化UI
        self.init_ui()
        
        # 初始化捕获相关
        self.camera = None
        self.capture_region = None  # (x, y, w, h)
        self.capture_fps = 30
        self.is_capturing = False
        
        # 初始化轨迹记录相关
        self.is_recording = False
        self.record_start_time = 0
        self.trajectory_count = 1
        
        # 初始化运动检测
        self.motion_detector = MotionDetector()
        self.detect_motion = False
        
        # 初始化视频录制
        self.video_writer = None
        self.record_video = False
        self.video_filename = ""
        
        # 初始化定时器
        self.capture_timer = QTimer()
        self.capture_timer.timeout.connect(self.capture_frame)
        
        # 状态栏
        self.statusBar().showMessage("就绪")
        
        # 加载样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #333;
            }
            QTabWidget::pane {
                border: 1px solid #444;
                background: #444;
            }
            QTabBar::tab {
                background: #555;
                color: white;
                padding: 8px;
                border: 1px solid #444;
            }
            QTabBar::tab:selected {
                background: #666;
            }
            QGroupBox {
                border: 1px solid #555;
                border-radius: 3px;
                margin-top: 10px;
                padding-top: 15px;
                color: white;
            }
            QLabel {
                color: white;
            }
            QPushButton {
                background-color: #555;
                color: white;
                border: 1px solid #444;
                padding: 5px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #666;
            }
            QPushButton:pressed {
                background-color: #777;
            }
            QListWidget {
                background-color: #444;
                color: white;
                border: 1px solid #333;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #444;
                color: white;
                border: 1px solid #333;
                padding: 3px;
            }
        """)
    
    def init_ui(self):
        # 创建菜单栏
        self.create_menus()
        
        # 创建工具栏
        self.create_toolbar()
        
        # 主标签页
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # 创建标签页
        self.tab_capture = QWidget()
        self.tab_trajectory = QWidget()
        self.tab_settings = QWidget()
        
        self.tabs.addTab(self.tab_capture, "画面捕获")
        self.tabs.addTab(self.tab_trajectory, "轨迹分析")
        self.tabs.addTab(self.tab_settings, "设置")
        
        # 初始化各标签页
        self.init_capture_tab()
        self.init_trajectory_tab()
        self.init_settings_tab()
    
    def create_menus(self):
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        
        new_action = QAction("新建项目", self)
        open_action = QAction("打开项目", self)
        save_action = QAction("保存项目", self)
        exit_action = QAction("退出", self)
        
        file_menu.addAction(new_action)
        file_menu.addAction(open_action)
        file_menu.addAction(save_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)
        
        # 编辑菜单
        edit_menu = menubar.addMenu("编辑")
        
        pref_action = QAction("首选项", self)
        edit_menu.addAction(pref_action)
        
        # 视图菜单
        view_menu = menubar.addMenu("视图")
        
        fullscreen_action = QAction("全屏", self, checkable=True)
        view_menu.addAction(fullscreen_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        
        about_action = QAction("关于", self)
        help_menu.addAction(about_action)
        
        # 连接信号
        exit_action.triggered.connect(self.close)
        about_action.triggered.connect(self.show_about)
    
    def create_toolbar(self):
        toolbar = QToolBar("主工具栏")
        self.addToolBar(toolbar)
        
        # 添加工具按钮
        select_process_act = QAction(QIcon.fromTheme("document-open"), "选择进程", self)
        start_capture_act = QAction(QIcon.fromTheme("media-playback-start"), "开始捕获", self)
        stop_capture_act = QAction(QIcon.fromTheme("media-playback-stop"), "停止捕获", self)
        screenshot_act = QAction(QIcon.fromTheme("camera-photo"), "截图", self)
        
        toolbar.addAction(select_process_act)
        toolbar.addAction(start_capture_act)
        toolbar.addAction(stop_capture_act)
        toolbar.addSeparator()
        toolbar.addAction(screenshot_act)
        
        # 连接信号
        select_process_act.triggered.connect(self.select_process)
        start_capture_act.triggered.connect(self.start_capture)
        stop_capture_act.triggered.connect(self.stop_capture)
        screenshot_act.triggered.connect(self.take_screenshot)
    
    def init_capture_tab(self):
        layout = QVBoxLayout()
        
        # 控制区域
        control_group = QGroupBox("捕获控制")
        control_layout = QHBoxLayout()
        
        self.select_process_btn = QPushButton("选择目标进程")
        self.start_capture_btn = QPushButton("开始捕获")
        self.stop_capture_btn = QPushButton("停止捕获")
        self.screenshot_btn = QPushButton("截图")
        self.record_video_chk = QCheckBox("录制视频")
        
        control_layout.addWidget(self.select_process_btn)
        control_layout.addWidget(self.start_capture_btn)
        control_layout.addWidget(self.stop_capture_btn)
        control_layout.addWidget(self.screenshot_btn)
        control_layout.addWidget(self.record_video_chk)
        control_layout.addStretch()
        
        control_group.setLayout(control_layout)
        
        # 预览区域
        self.preview_label = QLabel("画面预览区域")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background-color: black; color: white;")
        
        # 信息区域
        info_group = QGroupBox("捕获信息")
        info_layout = QHBoxLayout()
        
        self.fps_label = QLabel("帧率: 0")
        self.resolution_label = QLabel("分辨率: 0x0")
        self.time_label = QLabel("时间: 00:00:00")
        
        info_layout.addWidget(self.fps_label)
        info_layout.addWidget(self.resolution_label)
        info_layout.addWidget(self.time_label)
        info_layout.addStretch()
        
        info_group.setLayout(info_layout)
        
        # 主布局
        layout.addWidget(control_group)
        layout.addWidget(self.preview_label, 1)
        layout.addWidget(info_group)
        
        self.tab_capture.setLayout(layout)
        
        # 连接信号
        self.select_process_btn.clicked.connect(self.select_process)
        self.start_capture_btn.clicked.connect(self.start_capture)
        self.stop_capture_btn.clicked.connect(self.stop_capture)
        self.screenshot_btn.clicked.connect(self.take_screenshot)
        self.record_video_chk.stateChanged.connect(self.toggle_video_recording)
    
    def init_trajectory_tab(self):
        layout = QVBoxLayout()
        
        # 轨迹控制区域
        control_group = QGroupBox("轨迹控制")
        control_layout = QHBoxLayout()
        
        self.start_trajectory_btn = QPushButton("开始记录")
        self.stop_trajectory_btn = QPushButton("停止记录")
        self.clear_trajectory_btn = QPushButton("清除轨迹")
        self.save_trajectory_btn = QPushButton("保存轨迹")
        self.detect_motion_chk = QCheckBox("运动检测")
        self.new_trajectory_btn = QPushButton("新轨迹")
        
        control_layout.addWidget(self.start_trajectory_btn)
        control_layout.addWidget(self.stop_trajectory_btn)
        control_layout.addWidget(self.clear_trajectory_btn)
        control_layout.addWidget(self.save_trajectory_btn)
        control_layout.addWidget(self.detect_motion_chk)
        control_layout.addWidget(self.new_trajectory_btn)
        control_layout.addStretch()
        
        control_group.setLayout(control_layout)
        
        # 轨迹显示区域
        self.trajectory_widget = TrajectoryWidget()
        
        # 分析区域
        analysis_group = QGroupBox("轨迹分析")
        analysis_layout = QVBoxLayout()
        
        self.trajectory_info = QLabel("轨迹信息将显示在这里")
        self.trajectory_info.setWordWrap(True)
        
        self.measure_btn = QPushButton("测量工具")
        self.export_btn = QPushButton("导出数据")
        
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.measure_btn)
        btn_layout.addWidget(self.export_btn)
        btn_layout.addStretch()
        
        analysis_layout.addWidget(self.trajectory_info)
        analysis_layout.addLayout(btn_layout)
        
        analysis_group.setLayout(analysis_layout)
        
        # 主布局
        layout.addWidget(control_group)
        layout.addWidget(self.trajectory_widget, 1)
        layout.addWidget(analysis_group)
        
        self.tab_trajectory.setLayout(layout)
        
        # 连接信号
        self.start_trajectory_btn.clicked.connect(self.start_trajectory)
        self.stop_trajectory_btn.clicked.connect(self.stop_trajectory)
        self.clear_trajectory_btn.clicked.connect(self.clear_trajectory)
        self.save_trajectory_btn.clicked.connect(self.save_trajectory)
        self.detect_motion_chk.stateChanged.connect(self.toggle_motion_detection)
        self.new_trajectory_btn.clicked.connect(self.new_trajectory)
        self.measure_btn.clicked.connect(self.toggle_measure_tool)
        self.export_btn.clicked.connect(self.export_trajectory_data)
    
    def init_settings_tab(self):
        layout = QVBoxLayout()
        
        # 捕获设置
        capture_group = QGroupBox("捕获设置")
        capture_layout = QFormLayout()
        
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 120)
        self.fps_spin.setValue(30)
        
        self.region_combo = QComboBox()
        self.region_combo.addItems(["全屏", "窗口", "自定义区域"])
        
        capture_layout.addRow("帧率 (FPS):", self.fps_spin)
        capture_layout.addRow("捕获区域:", self.region_combo)
        
        capture_group.setLayout(capture_layout)
        
        # 轨迹设置
        trajectory_group = QGroupBox("轨迹设置")
        trajectory_layout = QFormLayout()
        
        self.traj_width_spin = QSpinBox()
        self.traj_width_spin.setRange(1, 10)
        self.traj_width_spin.setValue(3)
        
        self.traj_show_points = QCheckBox()
        self.traj_show_points.setChecked(True)
        
        self.traj_show_info = QCheckBox()
        self.traj_show_info.setChecked(True)
        
        trajectory_layout.addRow("轨迹宽度:", self.traj_width_spin)
        trajectory_layout.addRow("显示轨迹点:", self.traj_show_points)
        trajectory_layout.addRow("显示信息:", self.traj_show_info)
        
        trajectory_group.setLayout(trajectory_layout)
        
        # 运动检测设置
        motion_group = QGroupBox("运动检测设置")
        motion_layout = QFormLayout()
        
        self.motion_threshold = QSlider(Qt.Horizontal)
        self.motion_threshold.setRange(5, 50)
        self.motion_threshold.setValue(25)
        
        self.min_area_spin = QSpinBox()
        self.min_area_spin.setRange(10, 1000)
        self.min_area_spin.setValue(100)
        
        motion_layout.addRow("检测阈值:", self.motion_threshold)
        motion_layout.addRow("最小区域:", self.min_area_spin)
        
        motion_group.setLayout(motion_layout)
        
        # 主布局
        layout.addWidget(capture_group)
        layout.addWidget(trajectory_group)
        layout.addWidget(motion_group)
        layout.addStretch()
        
        self.tab_settings.setLayout(layout)
        
        # 连接信号
        self.fps_spin.valueChanged.connect(self.update_capture_fps)
        self.traj_width_spin.valueChanged.connect(self.update_trajectory_width)
        self.traj_show_points.stateChanged.connect(self.toggle_show_points)
        self.traj_show_info.stateChanged.connect(self.toggle_show_info)
        self.motion_threshold.valueChanged.connect(self.update_motion_threshold)
        self.min_area_spin.valueChanged.connect(self.update_min_area)
    
    def select_process(self):
        dialog = ProcessSelectionDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            selected_items = dialog.process_list.selectedItems()
            if selected_items:
                selected_process = selected_items[0].text()
                self.statusBar().showMessage(f"已选择进程: {selected_process}", 3000)
                
                # 这里应该实现真正的进程选择和捕获初始化
                try:
                    self.camera = dxcam.create()
                    self.statusBar().showMessage("DirectX Surface Sharing初始化成功", 3000)
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"初始化失败: {e}")
    
    def start_capture(self):
        if self.camera is None:
            QMessageBox.warning(self, "警告", "请先选择目标进程")
            return
            
        self.capture_fps = self.fps_spin.value()
        interval = int(1000 / self.capture_fps)
        self.capture_timer.setInterval(interval)
        self.capture_timer.start()
        self.is_capturing = True
        self.record_start_time = time.time()
        
        # 初始化视频录制
        if self.record_video_chk.isChecked():
            self.start_video_recording()
        
        self.statusBar().showMessage(f"画面捕获已开始 ({self.capture_fps}FPS)", 3000)
    
    def stop_capture(self):
        self.capture_timer.stop()
        self.is_capturing = False
        
        # 停止视频录制
        if self.video_writer is not None:
            self.stop_video_recording()
        
        self.statusBar().showMessage("画面捕获已停止", 3000)
    
    def capture_frame(self):
        if self.camera is None:
            return
            
        frame = self.camera.grab()
        if frame is not None:
            # 转换为RGB格式
            frame_rgb = frame[:, :, [2, 1, 0]]  # BGR to RGB
            
            # 更新预览
            height, width, channel = frame_rgb.shape
            bytes_per_line = 3 * width
            q_img = QImage(frame_rgb.data, width, height, bytes_per_line, QImage.Format_RGB888)
            self.preview_label.setPixmap(QPixmap.fromImage(q_img).scaled(
                self.preview_label.width(), self.preview_label.height(), Qt.KeepAspectRatio))
            
            # 更新信息
            elapsed = time.time() - self.record_start_time
            self.fps_label.setText(f"帧率: {self.capture_fps}")
            self.resolution_label.setText(f"分辨率: {width}x{height}")
            self.time_label.setText(f"时间: {datetime.utcfromtimestamp(elapsed).strftime('%H:%M:%S')}")
            
            # 更新轨迹页面的当前帧
            self.trajectory_widget.set_frame(frame_rgb)
            
            # 运动检测
            if self.detect_motion:
                motion_centers = self.motion_detector.detect(frame_rgb)
                for center in motion_centers:
                    self.trajectory_widget.add_point(center, self.trajectory_widget.active_trajectory)
            
            # 录制视频
            if self.video_writer is not None:
                # 需要转换回BGR格式
                frame_bgr = frame_rgb[:, :, [2, 1, 0]]
                self.video_writer.write(frame_bgr)
    
    def start_video_recording(self):
        if self.camera is None:
            return
            
        # 获取视频文件名
        filename, _ = QFileDialog.getSaveFileName(
            self, "保存视频文件", "", "MP4 文件 (*.mp4);;AVI 文件 (*.avi)")
            
        if not filename:
            self.record_video_chk.setChecked(False)
            return
            
        self.video_filename = filename
        
        # 获取帧尺寸
        frame = self.camera.grab()
        if frame is None:
            self.record_video_chk.setChecked(False)
            return
            
        height, width = frame.shape[:2]
        
        # 创建VideoWriter
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.video_writer = cv2.VideoWriter(
            filename, fourcc, self.capture_fps, (width, height))
            
        if not self.video_writer.isOpened():
            QMessageBox.critical(self, "错误", "无法创建视频文件")
            self.video_writer = None
            self.record_video_chk.setChecked(False)
    
    def stop_video_recording(self):
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None
            self.statusBar().showMessage(f"视频已保存到: {self.video_filename}", 5000)
    
    def toggle_video_recording(self, state):
        if state == Qt.Checked and self.is_capturing:
            self.start_video_recording()
        elif self.video_writer is not None:
            self.stop_video_recording()
    
    def take_screenshot(self):
        if self.camera is None or not self.is_capturing:
            QMessageBox.warning(self, "警告", "没有可捕获的画面")
            return
            
        frame = self.camera.grab()
        if frame is not None:
            # 转换为RGB格式
            frame_rgb = frame[:, :, [2, 1, 0]]
            
            # 获取保存路径
            filename, _ = QFileDialog.getSaveFileName(
                self, "保存截图", "", "PNG 图像 (*.png);;JPEG 图像 (*.jpg *.jpeg)")
                
            if filename:
                # 保存图像
                cv2.imwrite(filename, frame_rgb)
                self.statusBar().showMessage(f"截图已保存到: {filename}", 5000)
    
    def start_trajectory(self):
        if not self.is_capturing:
            QMessageBox.warning(self, "警告", "请先开始画面捕获")
            return
            
        self.is_recording = True
        self.statusBar().showMessage("轨迹记录已开始", 3000)
    
    def stop_trajectory(self):
        self.is_recording = False
        self.statusBar().showMessage("轨迹记录已停止", 3000)
    
    def clear_trajectory(self):
        self.trajectory_widget.clear_trajectory()
        self.statusBar().showMessage("轨迹已清除", 3000)
    
    def save_trajectory(self):
        if not self.trajectory_widget.trajectory_points:
            QMessageBox.warning(self, "警告", "没有轨迹数据可保存")
            return
            
        # 获取保存路径
        filename, _ = QFileDialog.getSaveFileName(
            self, "保存轨迹数据", "", "JSON 文件 (*.json);;CSV 文件 (*.csv)")
            
        if filename:
            # 准备轨迹数据
            traj_data = {
                "timestamp": datetime.now().isoformat(),
                "frame_size": {
                    "width": self.trajectory_widget.current_frame.shape[1],
                    "height": self.trajectory_widget.current_frame.shape[0]
                },
                "trajectories": []
            }
            
            for i, traj in enumerate(self.trajectory_widget.trajectory_points):
                traj_data["trajectories"].append({
                    "id": i,
                    "color": self.trajectory_widget.trajectory_colors[i % len(self.trajectory_widget.trajectory_colors)].name(),
                    "points": traj
                })
            
            # 保存为JSON
            if filename.endswith('.json'):
                with open(filename, 'w') as f:
                    json.dump(traj_data, f, indent=2)
            # 保存为CSV
            elif filename.endswith('.csv'):
                with open(filename, 'w') as f:
                    f.write("trajectory_id,x,y\n")
                    for i, traj in enumerate(self.trajectory_widget.trajectory_points):
                        for point in traj:
                            f.write(f"{i},{point[0]},{point[1]}\n")
            
            self.statusBar().showMessage(f"轨迹数据已保存到: {filename}", 5000)
    
    def toggle_motion_detection(self, state):
        self.detect_motion = state == Qt.Checked
        if self.detect_motion:
            self.statusBar().showMessage("运动检测已启用", 3000)
        else:
            self.statusBar().showMessage("运动检测已禁用", 3000)
    
    def new_trajectory(self):
        self.trajectory_widget.active_trajectory = self.trajectory_count
        self.trajectory_count += 1
        self.statusBar().showMessage(f"新建轨迹 {self.trajectory_widget.active_trajectory + 1}", 3000)
    
    def toggle_measure_tool(self):
        if self.trajectory_widget.measure_mode:
            self.trajectory_widget.end_measure()
            self.measure_btn.setText("测量工具")
            self.statusBar().showMessage("测量工具已关闭", 3000)
        else:
            self.trajectory_widget.start_measure()
            self.measure_btn.setText("结束测量")
            self.statusBar().showMessage("测量工具已启用 - 点击画面添加测量点", 3000)
    
    def export_trajectory_data(self):
        # 这里可以添加更复杂的数据导出功能
        self.save_trajectory()
    
    def update_capture_fps(self, fps):
        self.capture_fps = fps
        if self.is_capturing:
            self.capture_timer.setInterval(int(1000 / fps))
            self.statusBar().showMessage(f"帧率已更新: {fps}FPS", 2000)
    
    def update_trajectory_width(self, width):
        # 这里可以更新轨迹宽度设置
        pass
    
    def toggle_show_points(self, state):
        self.trajectory_widget.show_points = state == Qt.Checked
        self.trajectory_widget.update()
    
    def toggle_show_info(self, state):
        self.trajectory_widget.show_info = state == Qt.Checked
        self.trajectory_widget.update()
    
    def update_motion_threshold(self, value):
        self.motion_detector.threshold = value
    
    def update_min_area(self, value):
        self.motion_detector.min_contour_area = value
    
    def show_about(self):
        QMessageBox.about(self, "关于", 
            "<h2>高级进程画面轨迹记录工具</h2>"
            "<p>版本 1.0</p>"
            "<p>使用Python和PyQt5开发</p>"
            "<p>功能：</p>"
            "<ul>"
            "<li>进程画面捕获</li>"
            "<li>运动轨迹记录</li>"
            "<li>视频和截图保存</li>"
            "<li>轨迹数据分析</li>"
            "</ul>")
    
    def closeEvent(self, event):
        # 停止所有活动
        if self.is_capturing:
            self.stop_capture()
        
        if self.video_writer is not None:
            self.stop_video_recording()
        
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置中文显示
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())