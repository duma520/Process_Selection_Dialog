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
                           QMenu, QToolBar, QStatusBar, QSplitter, QFormLayout,
                           QLineEdit, QListWidgetItem, QSizePolicy, QGraphicsView,
                           QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem,
                           QGraphicsEllipseItem, QGraphicsTextItem, QColorDialog,
                           QDockWidget, QTextEdit,QGraphicsPixmapItem)
from PyQt5.QtCore import Qt, QTimer, QSize, QRect, QPoint, QRectF, QEvent,QPointF, QLineF
from PyQt5.QtGui import (QImage, QPixmap, QPainter, QPen, QColor, QIcon, 
                        QFont, QCursor, QBrush, QPolygonF, QFontMetrics)
import dxcam
from skimage import measure
import psutil
import win32gui
import win32process
import win32con
from scipy.interpolate import splprep, splev
from scipy.ndimage import gaussian_filter1d
from collections import deque
from sklearn.cluster import KMeans
from sklearn.linear_model import LinearRegression
import math




class EnhancedGraphicsView(QGraphicsView):
    """增强的图形视图，支持缩放和平移"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._zoom = 0
        self._empty = True
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QBrush(QColor(30, 30, 30)))
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setRenderHint(QPainter.Antialiasing)
        
    def hasImage(self):
        return not self._empty
    
    def fitInView(self, scale=True):
        rect = QRectF(self._pixmap.rect())
        if not rect.isNull():
            self.setSceneRect(rect)
            if self.hasImage():
                unity = self.transform().mapRect(QRectF(0, 0, 1, 1))
                self.scale(1 / unity.width(), 1 / unity.height())
                viewrect = self.viewport().rect()
                scenerect = self.transform().mapRect(rect)
                factor = min(viewrect.width() / scenerect.width(),
                             viewrect.height() / scenerect.height())
                self.scale(factor, factor)
            self._zoom = 0

    def setImage(self, pixmap):
        self._zoom = 0
        if pixmap.isNull():
            self._empty = True
            return
        self._empty = False
        self._pixmap = pixmap
        self._scene.clear()
        self._scene.addPixmap(self._pixmap)
        self.fitInView()
        
    def wheelEvent(self, event):
        if self.hasImage():
            if event.angleDelta().y() > 0:
                factor = 1.25
                self._zoom += 1
            else:
                factor = 0.8
                self._zoom -= 1
            if self._zoom > 0:
                self.scale(factor, factor)
            elif self._zoom == 0:
                self.fitInView()
            else:
                self._zoom = 0


class RegionSelectionDialog(QDialog):
    """窗口区域选择对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择捕获区域")
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 获取屏幕尺寸
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(0, 0, screen.width(), screen.height())
        
        # 选择区域
        self.selection_start = None
        self.selection_end = None
        self.selection_rect = None
        self.selected_region = None
        
        # 提示标签
        self.label = QLabel("拖动鼠标选择区域，按Enter确认或ESC取消", self)
        self.label.setStyleSheet("background-color: rgba(0,0,0,0.7); color: white; padding: 5px;")
        self.label.move(10, 10)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QPen(QColor(255, 255, 255, 200), 2))
        
        # 绘制半透明覆盖层
        painter.fillRect(self.rect(), QBrush(QColor(0, 0, 0, 100)))
        
        # 绘制选择区域
        if self.selection_rect:
            painter.fillRect(self.selection_rect, QBrush(QColor(255, 255, 255, 50)))
            painter.drawRect(self.selection_rect)
            
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selection_start = event.pos()
            self.selection_end = event.pos()
            self.update()
            
    def mouseMoveEvent(self, event):
        if self.selection_start:
            self.selection_end = event.pos()
            self.selection_rect = QRect(self.selection_start, self.selection_end).normalized()
            self.update()
            
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.selection_rect:
            self.selected_region = (
                self.selection_rect.x(),
                self.selection_rect.y(),
                self.selection_rect.width(),
                self.selection_rect.height()
            )
            self.accept()  # 自动确认选择
            



class ProcessSelectionDialog(QDialog):
    """增强的进程选择对话框，支持多选"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择目标进程")
        self.setWindowModality(Qt.ApplicationModal)
        self.resize(600, 500)
        
        self.layout = QVBoxLayout()
        
        # 筛选区域
        self.filter_group = QGroupBox("进程筛选")
        self.filter_layout = QHBoxLayout()
        
        self.filter_label = QLabel("筛选条件:")
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["所有进程", "图形窗口", "高CPU占用", "高内存占用", "置顶窗口"])
        self.filter_text = QLineEdit()
        self.filter_text.setPlaceholderText("输入进程名...")
        self.refresh_btn = QPushButton("刷新")
        
        self.filter_layout.addWidget(self.filter_label)
        self.filter_layout.addWidget(self.filter_combo)
        self.filter_layout.addWidget(self.filter_text)
        self.filter_layout.addWidget(self.refresh_btn)
        self.filter_group.setLayout(self.filter_layout)
        
        # 进程列表 (支持多选)
        self.process_list = QListWidget()
        self.process_list.setSelectionMode(QListWidget.MultiSelection)
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
        
        # 真实进程列表
        self.processes = []
        self.refresh_processes()

        # 连接信号
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self.refresh_btn.clicked.connect(self.refresh_processes)
        self.process_list.itemSelectionChanged.connect(self.show_process_detail)
        self.filter_combo.currentIndexChanged.connect(self.refresh_processes)
        self.filter_text.textChanged.connect(self.refresh_processes)
    
    def get_process_list(self):
        """获取系统进程列表，包含窗口标题和置顶状态"""
        process_list = []
        
        def callback(hwnd, extra):
            if win32gui.IsWindowVisible(hwnd):
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    title = win32gui.GetWindowText(hwnd)
                    if title:  # 只显示有窗口标题的进程
                        process = psutil.Process(pid)
                        
                        # 检查窗口是否置顶
                        style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                        is_topmost = (style & win32con.WS_EX_TOPMOST) != 0
                        
                        process_info = {
                            'pid': pid,
                            'name': process.name(),
                            'title': title,
                            'cpu': process.cpu_percent(),
                            'memory': process.memory_percent(),
                            'hwnd': hwnd,
                            'topmost': is_topmost
                        }
                        process_list.append(process_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        
        # 枚举所有窗口
        win32gui.EnumWindows(callback, None)
        return process_list

    def refresh_processes(self):
        self.process_list.clear()
        filter_type = self.filter_combo.currentText()
        filter_text = self.filter_text.text().lower()
        
        self.processes = self.get_process_list()
        
        for proc in self.processes:
            # 筛选条件
            if filter_text and filter_text not in proc["name"].lower() and filter_text not in proc["title"].lower():
                continue
                
            if filter_type == "高CPU占用" and proc["cpu"] < 5:
                continue
                
            if filter_type == "高内存占用" and proc["memory"] < 100:
                continue
                
            if filter_type == "置顶窗口" and not proc["topmost"]:
                continue
                
            item = QListWidgetItem()
            text = f"{proc['title']} ({proc['name']} - PID: {proc['pid']})"
            if proc['topmost']:
                text += " [置顶]"
            item.setText(text)
            item.setIcon(QIcon.fromTheme("application-x-executable"))
            item.setData(Qt.UserRole, proc)
            self.process_list.addItem(item)
    
    def show_process_detail(self):
        selected = self.process_list.selectedItems()
        if not selected:
            return
            
        proc = selected[0].data(Qt.UserRole)
        details = f"""
        <b>窗口标题:</b> {proc['title']}<br>
        <b>进程名称:</b> {proc['name']}<br>
        <b>进程ID:</b> {proc['pid']}<br>
        <b>CPU占用:</b> {proc['cpu']:.1f}%<br>
        <b>内存占用:</b> {proc['memory']:.1f} MB<br>
        <b>窗口状态:</b> {"置顶" if proc['topmost'] else "普通"}<br>
        """
        self.detail_label.setText(details)
    
    def selected_processes(self):
        """返回选中的进程列表"""
        selected = []
        for item in self.process_list.selectedItems():
            selected.append(item.data(Qt.UserRole))
        return selected


class TrajectoryAnalyzer:
    """轨迹分析工具类"""
    def __init__(self):
        self.trajectories = []
        self.smooth_cache = {}
        
    def add_trajectory(self, points):
        """添加一条轨迹"""
        self.trajectories.append(points)
        
    def smooth_trajectory(self, points, sigma=3):
        """使用高斯滤波平滑轨迹"""
        if len(points) < 3:
            return points
            
        # 检查缓存
        cache_key = hash(tuple(points))
        if cache_key in self.smooth_cache:
            return self.smooth_cache[cache_key]
            
        x = [p[0] for p in points]
        y = [p[1] for p in points]
        
        # 应用高斯滤波
        x_smooth = gaussian_filter1d(x, sigma=sigma)
        y_smooth = gaussian_filter1d(y, sigma=sigma)
        
        smoothed = list(zip(x_smooth, y_smooth))
        self.smooth_cache[cache_key] = smoothed
        return smoothed
        
    def calculate_velocity(self, points):
        """计算轨迹点的速度"""
        if len(points) < 2:
            return []
            
        velocities = []
        for i in range(1, len(points)):
            dx = points[i][0] - points[i-1][0]
            dy = points[i][1] - points[i-1][1]
            distance = np.sqrt(dx**2 + dy**2)
            velocities.append(distance)  # 像素/帧
            
        return velocities
        
    def calculate_acceleration(self, velocities):
        """计算加速度"""
        if len(velocities) < 2:
            return []
            
        accelerations = []
        for i in range(1, len(velocities)):
            accelerations.append(velocities[i] - velocities[i-1])  # 像素/帧²
            
        return accelerations
        
    def predict_path(self, points, steps=10):
        """预测未来路径(简单线性回归)"""
        if len(points) < 3:
            return []
            
        x = np.array([p[0] for p in points]).reshape(-1, 1)
        y = np.array([p[1] for p in points]).reshape(-1, 1)
        
        model_x = LinearRegression()
        model_y = LinearRegression()
        
        time_steps = np.array(range(len(points))).reshape(-1, 1)
        model_x.fit(time_steps, x)
        model_y.fit(time_steps, y)
        
        future_steps = np.array(range(len(points), len(points)+steps)).reshape(-1, 1)
        future_x = model_x.predict(future_steps)
        future_y = model_y.predict(future_steps)
        
        return list(zip(future_x.flatten(), future_y.flatten()))
        
    def cluster_trajectories(self, n_clusters=3):
        """对多条轨迹进行聚类"""
        if not self.trajectories:
            return []
            
        # 提取特征: 每条轨迹的平均x,y和长度
        features = []
        for traj in self.trajectories:
            if not traj:
                continue
            x = [p[0] for p in traj]
            y = [p[1] for p in traj]
            features.append([
                np.mean(x), np.mean(y), len(traj)
            ])
            
        if len(features) < n_clusters:
            return [0] * len(features)
            
        kmeans = KMeans(n_clusters=n_clusters)
        clusters = kmeans.fit_predict(features)
        return clusters
        
    def generate_heatmap(self, width, height, sigma=15):
        """生成热力图"""
        heatmap = np.zeros((height, width))
        
        for traj in self.trajectories:
            for x, y in traj:
                if 0 <= x < width and 0 <= y < height:
                    heatmap[int(y), int(x)] += 1
                    
        # 应用高斯模糊
        heatmap = cv2.GaussianBlur(heatmap, (0, 0), sigma)
        
        # 归一化
        if heatmap.max() > 0:
            heatmap = heatmap / heatmap.max()
            
        return heatmap


class MotionDetector:
    """增强的运动检测器，支持多种算法"""
    def __init__(self):
        self.prev_frame = None
        self.prev_gray = None
        self.min_contour_area = 100
        self.threshold = 25
        self.detection_roi = None  # (x, y, w, h)
        self.detection_method = "frame_diff"  # frame_diff, background_sub, optical_flow
        self.background_model = None
        self.background_alpha = 0.05  # 背景模型学习率
        self.optical_flow_params = dict(
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
        )
        self.tracked_points = None
        self.tracking_colors = None
        
    def set_roi(self, roi):
        """设置检测区域"""
        self.detection_roi = roi
        
    def set_method(self, method):
        """设置检测方法"""
        self.detection_method = method
        
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
            frame_roi = frame[y:y+h, x:x+w]
        else:
            frame_roi = frame
            
        motion_centers = []
        
        if self.detection_method == "frame_diff":
            motion_centers = self._frame_diff(gray)
        elif self.detection_method == "background_sub":
            motion_centers = self._background_subtraction(gray)
        elif self.detection_method == "optical_flow":
            motion_centers = self._optical_flow(frame_roi, gray)
            
        # 如果有ROI，调整坐标
        if self.detection_roi and motion_centers:
            motion_centers = [(x + self.detection_roi[0], y + self.detection_roi[1]) 
                             for (x, y) in motion_centers]
        
        return motion_centers
        
    def _frame_diff(self, gray):
        """帧差法检测运动"""
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
                    motion_centers.append((cx, cy))
        
        return motion_centers
        
    def _background_subtraction(self, gray):
        """背景减除法检测运动"""
        if self.background_model is None:
            self.background_model = gray.copy().astype(np.float32)
            return []
            
        # 更新背景模型
        cv2.accumulateWeighted(gray, self.background_model, self.background_alpha)
        
        # 计算与背景的差异
        background = self.background_model.astype(np.uint8)
        frame_diff = cv2.absdiff(gray, background)
        
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
                M = cv2.moments(cnt)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    motion_centers.append((cx, cy))
        
        return motion_centers
        
    def _optical_flow(self, frame, gray):
        """光流法检测运动"""
        if self.prev_gray is None:
            self.prev_gray = gray
            # 初始化跟踪点
            feature_params = dict(
                maxCorners=100,
                qualityLevel=0.3,
                minDistance=7,
                blockSize=7
            )
            self.tracked_points = cv2.goodFeaturesToTrack(gray, mask=None, **feature_params)
            self.tracking_colors = np.random.randint(0, 255, (100, 3))
            return []
            
        # 计算光流
        new_points, status, _ = cv2.calcOpticalFlowPyrLK(
            self.prev_gray, gray, self.tracked_points, None, **self.optical_flow_params)
        
        # 只保留好的点
        good_new = new_points[status == 1]
        good_old = self.tracked_points[status == 1]
        
        # 更新跟踪点
        self.tracked_points = good_new.reshape(-1, 1, 2)
        self.prev_gray = gray.copy()
        
        # 计算运动向量
        motion_centers = []
        for i, (new, old) in enumerate(zip(good_new, good_old)):
            a, b = new.ravel()
            c, d = old.ravel()
            
            # 计算运动距离
            distance = np.sqrt((a-c)**2 + (b-d)**2)
            if distance > 2:  # 移动超过2像素才认为是运动
                motion_centers.append((int(a), int(b)))
        
        return motion_centers


class TrajectoryWidget(QWidget):
    """增强的轨迹显示部件，支持所有新功能"""
    def __init__(self):
        super().__init__()
        self.trajectory_points = []  # 存储所有轨迹点
        self.current_frame = None    # 当前帧图像
        self.trajectory_colors = []   # 不同轨迹颜色
        self.active_trajectory = 0   # 当前活动轨迹索引
        self.show_trajectory = True  # 是否显示轨迹
        self.show_points = True       # 是否显示轨迹点
        self.show_info = True        # 是否显示信息
        self.grid_size = 50          # 网格大小
        self.show_grid = False       # 是否显示网格
        self.measure_points = []      # 测量点
        self.measure_mode = False    # 是否处于测量模式
        self.annotation_mode = False  # 是否处于标注模式
        self.annotations = []        # 存储所有标注
        self.heatmap = None          # 热力图数据
        self.show_heatmap = False    # 是否显示热力图
        self.velocity_vectors = []   # 速度向量
        self.show_velocity = False   # 是否显示速度
        self.predicted_paths = []    # 预测路径
        self.show_prediction = False # 是否显示预测路径
        self.smooth_trajectory = False  # 是否平滑轨迹
        self.trajectory_analyzer = TrajectoryAnalyzer()  # 轨迹分析器
        
        self.setMouseTracking(True)
        self.setMinimumSize(640, 480)
        
        # 初始化颜色生成器
        self.color_index = 0
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
    def get_next_color(self):
        """生成视觉区分度极高的HSV颜色（支持上千条轨迹）"""
        # 可调参数（根据需求自定义）
        GOLDEN_ANGLE = 137.508  # 黄金角分散色相
        SATURATION_RANGE = (180, 255)  # 饱和度范围（避免灰暗）
        VALUE_RANGE = (200, 255)       # 明度范围（避免太暗）
        HUE_STEP = 10                 # 基础色相步长（可减小以增加颜色数量）
        # 动态计算HSV值
        hue = (self.color_index * GOLDEN_ANGLE) % 360  # 使用黄金角分散色相
        saturation = SATURATION_RANGE[1] - (self.color_index % 5) * 15  # 饱和度波动
        value = VALUE_RANGE[1] - (self.color_index % 3) * 20           # 明度波动
        # 确保数值在有效范围内
        saturation = max(min(saturation, SATURATION_RANGE[1]), SATURATION_RANGE[0])
        value = max(min(value, VALUE_RANGE[1]), VALUE_RANGE[0])
        # 更新索引
        self.color_index += 1
        return QColor.fromHsv(int(hue), int(saturation), int(value))

    def setFrame(self, frame):
        """设置当前帧图像"""
        self.current_frame = frame
        self.update()
        
    def addPoint(self, point, trajectory_idx=0):
        """添加轨迹点"""
        while len(self.trajectory_points) <= trajectory_idx:
            self.trajectory_points.append([])
            
        self.trajectory_points[trajectory_idx].append(point)
        
        # 更新分析器
        if len(self.trajectory_points[trajectory_idx]) > 1:
            self.trajectory_analyzer.add_trajectory(self.trajectory_points[trajectory_idx])
            
            # 计算速度
            if len(self.trajectory_points[trajectory_idx]) > 2:
                velocities = self.trajectory_analyzer.calculate_velocity(
                    self.trajectory_points[trajectory_idx])
                if velocities:
                    last_point = self.trajectory_points[trajectory_idx][-1]
                    prev_point = self.trajectory_points[trajectory_idx][-2]
                    dx = last_point[0] - prev_point[0]
                    dy = last_point[1] - prev_point[1]
                    self.velocity_vectors.append((
                        prev_point[0], prev_point[1], dx, dy, velocities[-1]))
        
        self.update()
        
    def clearTrajectory(self, trajectory_idx=None):
        """清除轨迹"""
        if trajectory_idx is None:
            self.trajectory_points = []
            self.velocity_vectors = []
            self.predicted_paths = []
            self.trajectory_analyzer = TrajectoryAnalyzer()
        else:
            if trajectory_idx < len(self.trajectory_points):
                self.trajectory_points[trajectory_idx] = []
        self.update()
        
    def startMeasure(self):
        """开始测量"""
        self.measure_mode = not self.measure_mode
        if not self.measure_mode:
            self.measure_points = []
        self.update()
        self.setCursor(Qt.CrossCursor)
        
    def startAnnotation(self):
        """开始标注"""
        self.annotation_mode = not self.annotation_mode
        if not self.annotation_mode:
            pass
        self.update()
        self.setCursor(Qt.CrossCursor)
        
    def addAnnotation(self, annotation):
        """添加标注"""
        self.annotations.append(annotation)
        self.update()
        
    def clearAnnotations(self):
        """清除所有标注"""
        self.annotations = []
        self.update()
        
    def generateHeatmap(self):
        """生成热力图"""
        if not self.trajectory_points or not self.current_frame:
            return
            
        height, width = self.current_frame.shape[:2]
        self.heatmap = self.trajectory_analyzer.generate_heatmap(width, height)
        self.show_heatmap = True
        self.update()
        
    def toggleHeatmap(self, show):
        """切换热力图显示"""
        self.show_heatmap = show
        self.update()
        
    def toggleVelocity(self, show):
        """切换速度显示"""
        self.show_velocity = show
        self.update()
        
    def togglePrediction(self, show):
        """切换预测路径显示"""
        self.show_prediction = show
        if show and self.trajectory_points:
            self.predicted_paths = []
            for traj in self.trajectory_points:
                if len(traj) > 10:  # 只有足够长的轨迹才预测
                    self.predicted_paths.append(
                        self.trajectory_analyzer.predict_path(traj))
        self.update()
        
    def toggleSmoothTrajectory(self, smooth):
        """切换轨迹平滑"""
        self.smooth_trajectory = smooth
        self.update()
        
    def mergeTrajectories(self, indices):
        """合并多条轨迹"""
        if len(indices) < 2:
            return
            
        merged = []
        for idx in indices:
            if idx < len(self.trajectory_points):
                merged.extend(self.trajectory_points[idx])
                self.trajectory_points[idx] = []
                
        # 添加合并后的轨迹
        self.trajectory_points.append(merged)
        self.update()
        
    def splitTrajectory(self, trajectory_idx, split_index):
        """分割轨迹"""
        if trajectory_idx >= len(self.trajectory_points):
            return
            
        traj = self.trajectory_points[trajectory_idx]
        if split_index >= len(traj):
            return
            
        # 分割为两条轨迹
        first_part = traj[:split_index]
        second_part = traj[split_index:]
        
        self.trajectory_points[trajectory_idx] = first_part
        self.trajectory_points.append(second_part)
        self.update()
        
    def mousePressEvent(self, event):
        if self.measure_mode and event.button() == Qt.LeftButton:
            pos = event.pos()
            if hasattr(self, 'display_rect') and self.display_rect.contains(pos):
                rel_x = pos.x() - self.display_rect.x()
                rel_y = pos.y() - self.display_rect.y()
                img_x = int(rel_x * self.current_frame.shape[1] / self.display_rect.width())
                img_y = int(rel_y * self.current_frame.shape[0] / self.display_rect.height())
                self.measure_points.append((img_x, img_y))
                self.update()
                
        elif self.annotation_mode and event.button() == Qt.LeftButton:
            pos = event.pos()
            if hasattr(self, 'display_rect') and self.display_rect.contains(pos):
                rel_x = pos.x() - self.display_rect.x()
                rel_y = pos.y() - self.display_rect.y()
                img_x = int(rel_x * self.current_frame.shape[1] / self.display_rect.width())
                img_y = int(rel_y * self.current_frame.shape[0] / self.display_rect.height())
                
                # 弹出对话框获取标注文本
                text, ok = QInputDialog.getText(self, "添加标注", "输入标注文本:")
                if ok and text:
                    self.addAnnotation({
                        'x': img_x,
                        'y': img_y,
                        'text': text,
                        'color': QColor(255, 255, 0)
                    })
                    
    def mouseMoveEvent(self, event):
        if self.measure_mode or self.annotation_mode:
            self.update()
            
    def paintEvent(self, event):
        if self.current_frame is None:
            return
            
        painter = QPainter(self)
        
        # 绘制背景
        painter.fillRect(self.rect(), QBrush(QColor(255, 255, 255)))
        
        # 绘制当前帧
        height, width, channels = self.current_frame.shape
        bytes_per_line = 3 * width
        q_img = QImage(self.current_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
        
        # 计算缩放后的尺寸，保持宽高比
        img_ratio = width / height
        widget_ratio = self.width() / self.height()
        
        if img_ratio > widget_ratio:
            display_width = self.width()
            display_height = int(display_width / img_ratio)
        else:
            display_height = self.height()
            display_width = int(display_height * img_ratio)
            
        # 居中显示
        x_offset = (self.width() - display_width) // 2
        y_offset = (self.height() - display_height) // 2
        
        self.display_rect = QRect(x_offset, y_offset, display_width, display_height)
        painter.drawPixmap(self.display_rect, QPixmap.fromImage(q_img))
        
        # 绘制热力图
        if self.show_heatmap and self.heatmap is not None:
            # 创建热力图图像
            heatmap_img = np.zeros((height, width, 3), dtype=np.uint8)
            
            # 应用颜色映射 (Jet)
            for y in range(height):
                for x in range(width):
                    val = self.heatmap[y, x]
                    if val > 0:
                        # Jet颜色映射 (蓝-青-黄-红)
                        if val < 0.25:
                            b = 255
                            g = int(val * 4 * 255)
                            r = 0
                        elif val < 0.5:
                            b = int((0.5 - val) * 4 * 255)
                            g = 255
                            r = 0
                        elif val < 0.75:
                            b = 0
                            g = 255
                            r = int((val - 0.5) * 4 * 255)
                        else:
                            b = 0
                            g = int((1.0 - val) * 4 * 255)
                            r = 255
                            
                        heatmap_img[y, x] = [r, g, b]
            
            # 转换为QImage并绘制
            heatmap_qimg = QImage(heatmap_img.data, width, height, 3 * width, QImage.Format_RGB888)
            painter.setOpacity(0.5)
            painter.drawPixmap(self.display_rect, QPixmap.fromImage(heatmap_qimg))
            painter.setOpacity(1.0)
        
        # 绘制网格
        if self.show_grid and self.display_rect.width() > 0:
            pen = QPen(QColor(255, 255, 255, 50), 1, Qt.DotLine)
            painter.setPen(pen)
            
            x_line = int(display_width / self.grid_size) + 1
            y_line = int(display_height / self.grid_size) + 1
            
            for i in range(x_line):
                x = x_offset + i * self.grid_size
                painter.drawLine(x, y_offset, x, y_offset + display_height)
            
            for i in range(y_line):
                y = y_offset + i * self.grid_size
                painter.drawLine(x_offset, y, x_offset + display_width, y)
    

        # 绘制轨迹
        if self.show_trajectory:
            for traj_idx, trajectory in enumerate(self.trajectory_points):
                if len(trajectory) > 1:
                    # 确保有足够的颜色，如果没有则生成新的
                    while traj_idx >= len(self.trajectory_colors):
                        self.trajectory_colors.append(self.get_next_color())
                        
                    color = self.trajectory_colors[traj_idx]
                    pen = QPen(color, 3)
                    painter.setPen(pen)
                    
                    # 选择原始轨迹或平滑轨迹
                    points_to_draw = trajectory
                    if self.smooth_trajectory:
                        points_to_draw = self.trajectory_analyzer.smooth_trajectory(trajectory)
                    
                    # 绘制轨迹线
                    for i in range(1, len(points_to_draw)):
                        prev_point = self._imageToWindow(points_to_draw[i-1])
                        curr_point = self._imageToWindow(points_to_draw[i])
                        if prev_point and curr_point:
                            painter.drawLine(prev_point, curr_point)

                    
                    # 绘制轨迹点
                    if self.show_points:
                        point_pen = QPen(color, 1)
                        painter.setPen(point_pen)
                        brush = QBrush(color)
                        painter.setBrush(brush)
                        
                        for point in points_to_draw:
                            win_point = self._imageToWindow(point)
                            if win_point:
                                painter.drawEllipse(win_point, 3, 3)
        
        # 绘制速度向量
        if self.show_velocity and self.velocity_vectors:
            for x, y, dx, dy, speed in self.velocity_vectors:
                start = self._imageToWindow((x, y))
                end = self._imageToWindow((x + dx, y + dy))
                if start and end:
                    # 根据速度大小设置颜色 (慢-绿, 快-红)
                    speed_color = QColor(
                        min(255, int(speed * 10)), 
                        max(0, 255 - int(speed * 10)), 
                        0
                    )
                    pen = QPen(speed_color, 2)
                    painter.setPen(pen)
                    painter.drawLine(start, end)
                    
                    # 绘制箭头
                    angle = np.arctan2(end.y() - start.y(), end.x() - start.x())
                    arrow_size = 10
                    arrow_p1 = end - QPoint(
                        int(arrow_size * np.cos(angle - np.pi / 6)),
                        int(arrow_size * np.sin(angle - np.pi / 6))
                    )
                    arrow_p2 = end - QPoint(
                        int(arrow_size * np.cos(angle + np.pi / 6)),
                        int(arrow_size * np.sin(angle + np.pi / 6))
                    )
                    painter.drawLine(end, arrow_p1)
                    painter.drawLine(end, arrow_p2)
        
        # 绘制预测路径
        if self.show_prediction and self.predicted_paths:
            for i, path in enumerate(self.predicted_paths):
                if len(path) > 1:
                    color = self.trajectory_colors[i % len(self.trajectory_colors)]
                    pen = QPen(color, 2, Qt.DashLine)
                    painter.setPen(pen)
                    
                    for j in range(1, len(path)):
                        prev_point = self._imageToWindow(path[j-1])
                        curr_point = self._imageToWindow(path[j])
                        if prev_point and curr_point:
                            painter.drawLine(prev_point, curr_point)
        
        # 绘制测量线和距离
        if len(self.measure_points) >= 1:
            pen = QPen(QColor(0, 255, 255), 2, Qt.DashLine)
            painter.setPen(pen)
            
            for i, point in enumerate(self.measure_points):
                win_point = self._imageToWindow(point)
                if win_point:
                    painter.drawEllipse(win_point, 5, 5)

                if i > 0:
                    prev_point = self._imageToWindow(self.measure_points[i-1])
                    curr_point = self._imageToWindow(point)
                    if prev_point and curr_point:
                        painter.drawLine(prev_point, curr_point)
                        
                        # 计算并显示距离
                        dx = point[0] - self.measure_points[i-1][0]
                        dy = point[1] - self.measure_points[i-1][1]
                        distance = np.sqrt(dx*dx + dy*dy)
                        mid_x = (prev_point.x() + curr_point.x()) // 2
                        mid_y = (prev_point.y() + curr_point.y()) // 2
                        painter.drawText(mid_x, mid_y, f"{distance:.1f}px")
            
            # 绘制当前鼠标位置到最后一个点的线
            if self.measure_mode and len(self.measure_points) > 0:
                mouse_pos = self.mapFromGlobal(QCursor.pos())
                img_pos = self._windowToImage(mouse_pos)
                if img_pos:
                    last_point = self._imageToWindow(self.measure_points[-1])
                    curr_point = self._imageToWindow(img_pos)
                    if last_point and curr_point:
                        painter.drawLine(last_point, curr_point)
                        
                        dx = img_pos[0] - self.measure_points[-1][0]
                        dy = img_pos[1] - self.measure_points[-1][1]
                        distance = np.sqrt(dx*dx + dy*dy)
                        mid_x = (last_point.x() + curr_point.x()) // 2
                        mid_y = (last_point.y() + curr_point.y()) // 2
                        painter.drawText(int(mid_x), int(mid_y), f"{distance:.1f}px")
        
        # 绘制标注
        for annotation in self.annotations:
            win_point = self._imageToWindow((annotation['x'], annotation['y']))
            if win_point:
                # 绘制文本背景
                font = painter.font()
                font.setPointSize(10)
                painter.setFont(font)
                fm = QFontMetrics(font)
                text_rect = fm.boundingRect(annotation['text'])
                
                bg_rect = QRect(
                    win_point.x() - 2, 
                    win_point.y() - text_rect.height() - 2,
                    text_rect.width() + 4,
                    text_rect.height() + 4
                )
                
                painter.setPen(QPen(QColor(0, 0, 0, 150)))
                painter.setBrush(QBrush(QColor(0, 0, 0, 150)))
                painter.drawRect(bg_rect)
                
                # 绘制文本
                painter.setPen(QPen(annotation['color']))
                painter.drawText(win_point.x(), win_point.y(), annotation['text'])
                
                # 绘制连接线
                painter.drawLine(win_point, QPoint(win_point.x(), win_point.y() - 5))
        
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
    
    def _windowToImage(self, window_point):
        """将窗口坐标转换为图像坐标"""
        if not hasattr(self, 'display_rect') or not self.display_rect or self.current_frame is None:
            return None
            
        if not self.display_rect.contains(window_point):
            return None
            
        rel_x = window_point.x() - self.display_rect.x()
        rel_y = window_point.y() - self.display_rect.y()
        
        img_x = int(rel_x * self.current_frame.shape[1] / self.display_rect.width())
        img_y = int(rel_y * self.current_frame.shape[0] / self.display_rect.height())
        
        return (img_x, img_y)
    
    def _imageToWindow(self, image_point):
        """将图像坐标转换为窗口坐标"""
        if not hasattr(self, 'display_rect') or not self.display_rect or self.current_frame is None:
            return None
            
        if (image_point[0] < 0 or image_point[0] >= self.current_frame.shape[1] or
            image_point[1] < 0 or image_point[1] >= self.current_frame.shape[0]):
            return None
            
        win_x = int(image_point[0] * self.display_rect.width() / self.current_frame.shape[1]) + self.display_rect.x()
        win_y = int(image_point[1] * self.display_rect.height() / self.current_frame.shape[0]) + self.display_rect.y()
        
        return QPoint(win_x, win_y)


class MainWindow(QMainWindow):
    """主窗口，包含所有增强功能"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("高级进程画面轨迹记录工具 (增强版)")
        
        # 获取主屏幕可用尺寸
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1400, screen.width() * 0.9), min(900, screen.height() * 0.9))
        self.setMinimumSize(1000, 700)
        
        # 初始化UI
        self.init_ui()
        
        # 初始化捕获相关
        self.camera = None
        self.capture_region = None  # (x, y, w, h)
        self.capture_fps = 30
        self.is_capturing = False
        self.capture_targets = []  # 多进程捕获目标
        
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
        self.load_style()
    
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
        self.tab_analysis = QWidget()  # 新增分析标签页
        
        self.tabs.addTab(self.tab_capture, "画面捕获")
        self.tabs.addTab(self.tab_trajectory, "轨迹分析")
        self.tabs.addTab(self.tab_analysis, "高级分析")  # 新增标签页
        self.tabs.addTab(self.tab_settings, "设置")
        
        # 初始化各标签页
        self.init_capture_tab()
        self.init_trajectory_tab()
        self.init_analysis_tab()  # 初始化分析标签页
        self.init_settings_tab()
        
        # 添加停靠窗口
        self.add_dock_windows()
    
    def add_dock_windows(self):
        """添加停靠窗口用于显示额外信息"""
        # 轨迹信息停靠窗口
        self.trajectory_info_dock = QDockWidget("轨迹信息", self)
        self.trajectory_info_text = QTextEdit()
        self.trajectory_info_text.setReadOnly(True)
        self.trajectory_info_dock.setWidget(self.trajectory_info_text)
        self.addDockWidget(Qt.RightDockWidgetArea, self.trajectory_info_dock)
        
        # 捕获日志停靠窗口
        self.capture_log_dock = QDockWidget("捕获日志", self)
        self.capture_log_text = QTextEdit()
        self.capture_log_text.setReadOnly(True)
        self.capture_log_dock.setWidget(self.capture_log_text)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.capture_log_dock)
    
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
        
        # 工具菜单
        tools_menu = menubar.addMenu("工具")
        
        region_action = QAction("选择捕获区域", self)
        multi_capture_action = QAction("多进程捕获", self)
        heatmap_action = QAction("生成热力图", self)
        
        tools_menu.addAction(region_action)
        tools_menu.addAction(multi_capture_action)
        tools_menu.addAction(heatmap_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        
        about_action = QAction("关于", self)
        help_menu.addAction(about_action)
        
        # 连接信号
        exit_action.triggered.connect(self.close)
        about_action.triggered.connect(self.show_about)
        region_action.triggered.connect(self.select_region)
        multi_capture_action.triggered.connect(self.select_multiple_processes)
        heatmap_action.triggered.connect(self.generate_heatmap)
    
    def create_toolbar(self):
        toolbar = QToolBar("主工具栏")
        self.addToolBar(toolbar)
        
        # 添加工具按钮
        select_process_act = QAction(QIcon.fromTheme("document-open"), "选择进程", self)
        select_region_act = QAction(QIcon.fromTheme("transform-move"), "选择区域", self)
        start_capture_act = QAction(QIcon.fromTheme("media-playback-start"), "开始捕获", self)
        stop_capture_act = QAction(QIcon.fromTheme("media-playback-stop"), "停止捕获", self)
        screenshot_act = QAction(QIcon.fromTheme("camera-photo"), "截图", self)
        heatmap_act = QAction(QIcon.fromTheme("color-management"), "热力图", self)
        
        toolbar.addAction(select_process_act)
        toolbar.addAction(select_region_act)
        toolbar.addSeparator()
        toolbar.addAction(start_capture_act)
        toolbar.addAction(stop_capture_act)
        toolbar.addSeparator()
        toolbar.addAction(screenshot_act)
        toolbar.addAction(heatmap_act)
        
        # 连接信号
        select_process_act.triggered.connect(self.select_process)
        select_region_act.triggered.connect(self.select_region)
        start_capture_act.triggered.connect(self.start_capture)
        stop_capture_act.triggered.connect(self.stop_capture)
        screenshot_act.triggered.connect(self.take_screenshot)
        heatmap_act.triggered.connect(self.generate_heatmap)
    
    def init_capture_tab(self):
        layout = QVBoxLayout()
        
        # 控制区域
        control_group = QGroupBox("捕获控制")
        control_layout = QHBoxLayout()
        
        self.select_process_btn = QPushButton("选择目标进程")
        self.select_region_btn = QPushButton("选择捕获区域")
        self.start_capture_btn = QPushButton("开始捕获")
        self.stop_capture_btn = QPushButton("停止捕获")
        self.screenshot_btn = QPushButton("截图")
        self.record_video_chk = QCheckBox("录制视频")
        self.multi_capture_btn = QPushButton("多进程捕获")
        
        control_layout.addWidget(self.select_process_btn)
        control_layout.addWidget(self.select_region_btn)
        control_layout.addWidget(self.start_capture_btn)
        control_layout.addWidget(self.stop_capture_btn)
        control_layout.addWidget(self.screenshot_btn)
        control_layout.addWidget(self.record_video_chk)
        control_layout.addWidget(self.multi_capture_btn)
        control_layout.addStretch()
        
        control_group.setLayout(control_layout)
        
        # 预览区域
        self.preview_label = QLabel("画面预览区域")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background-color: white; color: black; border: 1px solid #c0c0c0;")
        
        # 信息区域
        info_group = QGroupBox("捕获信息")
        info_layout = QHBoxLayout()
        
        self.fps_label = QLabel("帧率: 0")
        self.resolution_label = QLabel("分辨率: 0x0")
        self.time_label = QLabel("时间: 00:00:00")
        self.capture_target_label = QLabel("目标: 无")
        
        info_layout.addWidget(self.fps_label)
        info_layout.addWidget(self.resolution_label)
        info_layout.addWidget(self.time_label)
        info_layout.addWidget(self.capture_target_label)
        info_layout.addStretch()
        
        info_group.setLayout(info_layout)
        
        # 主布局
        layout.addWidget(control_group)
        layout.addWidget(self.preview_label, 1)
        layout.addWidget(info_group)
        
        self.tab_capture.setLayout(layout)
        
        # 连接信号
        self.select_process_btn.clicked.connect(self.select_process)
        self.select_region_btn.clicked.connect(self.select_region)
        self.start_capture_btn.clicked.connect(self.start_capture)
        self.stop_capture_btn.clicked.connect(self.stop_capture)
        self.screenshot_btn.clicked.connect(self.take_screenshot)
        self.record_video_chk.stateChanged.connect(self.toggle_video_recording)
        self.multi_capture_btn.clicked.connect(self.select_multiple_processes)
    
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
        self.annotation_btn = QPushButton("添加标注")
        self.measure_btn = QPushButton("测量工具")
        
        control_layout.addWidget(self.start_trajectory_btn)
        control_layout.addWidget(self.stop_trajectory_btn)
        control_layout.addWidget(self.clear_trajectory_btn)
        control_layout.addWidget(self.save_trajectory_btn)
        control_layout.addWidget(self.detect_motion_chk)
        control_layout.addWidget(self.new_trajectory_btn)
        control_layout.addWidget(self.annotation_btn)
        control_layout.addWidget(self.measure_btn)
        control_layout.addStretch()
        
        control_group.setLayout(control_layout)
        
        advanced_group = QGroupBox("高级功能")
        advanced_layout = QHBoxLayout()

        self.smooth_traj_btn = QPushButton("平滑轨迹")
        self.velocity_btn = QPushButton("显示速度")
        self.predict_btn = QPushButton("预测路径")
        self.cluster_btn = QPushButton("轨迹聚类")
        self.merge_btn = QPushButton("合并轨迹")
        self.split_btn = QPushButton("分割轨迹")

        advanced_layout.addWidget(self.smooth_traj_btn)
        advanced_layout.addWidget(self.velocity_btn)
        advanced_layout.addWidget(self.predict_btn)
        advanced_layout.addWidget(self.cluster_btn)
        advanced_layout.addWidget(self.merge_btn)
        advanced_layout.addWidget(self.split_btn)
        advanced_layout.addStretch()

        advanced_group.setLayout(advanced_layout)

        # 轨迹显示区域
        self.trajectory_widget = TrajectoryWidget()
        
        # 分析区域
        analysis_group = QGroupBox("轨迹分析")
        analysis_layout = QVBoxLayout()
        
        self.trajectory_info = QLabel("轨迹信息将显示在这里")
        self.trajectory_info.setWordWrap(True)
        
        self.export_btn = QPushButton("导出数据")
        self.heatmap_btn = QPushButton("生成热力图")
        
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.export_btn)
        btn_layout.addWidget(self.heatmap_btn)
        btn_layout.addStretch()
        
        analysis_layout.addWidget(self.trajectory_info)
        analysis_layout.addLayout(btn_layout)
        
        analysis_group.setLayout(analysis_layout)
        
        # 主布局
        layout.addWidget(control_group)
        layout.addWidget(advanced_group)
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
        self.annotation_btn.clicked.connect(self.toggle_annotation)
        self.measure_btn.clicked.connect(self.toggle_measure_tool)
        self.export_btn.clicked.connect(self.export_trajectory_data)
        self.heatmap_btn.clicked.connect(self.generate_heatmap)

        # ===== 连接高级功能按钮信号 =====
        self.smooth_traj_btn.clicked.connect(self.toggle_smooth_trajectory)
        self.velocity_btn.clicked.connect(self.toggle_velocity)
        self.predict_btn.clicked.connect(self.toggle_prediction)
        self.cluster_btn.clicked.connect(self.cluster_trajectories)
        self.merge_btn.clicked.connect(self.merge_trajectories)
        self.split_btn.clicked.connect(self.split_trajectory)

    def init_analysis_tab(self):
        """预留的高级分析标签页（未来扩展）"""
        layout = QVBoxLayout()
        placeholder = QLabel("高级分析功能将在此处扩展")
        placeholder.setAlignment(Qt.AlignCenter)
        layout.addWidget(placeholder)
        self.tab_analysis.setLayout(layout)



    
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
        
        self.detection_method_combo = QComboBox()
        self.detection_method_combo.addItems(["帧差法", "背景减除法", "光流法"])
        
        capture_layout.addRow("帧率 (FPS):", self.fps_spin)
        capture_layout.addRow("捕获区域:", self.region_combo)
        capture_layout.addRow("运动检测方法:", self.detection_method_combo)
        
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
        
        self.traj_smooth = QCheckBox()
        self.traj_smooth.setChecked(False)
        
        trajectory_layout.addRow("轨迹宽度:", self.traj_width_spin)
        trajectory_layout.addRow("显示轨迹点:", self.traj_show_points)
        trajectory_layout.addRow("显示信息:", self.traj_show_info)
        trajectory_layout.addRow("平滑轨迹:", self.traj_smooth)
        
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
        
        self.roi_x_spin = QSpinBox()
        self.roi_x_spin.setRange(0, 9999)
        
        self.roi_y_spin = QSpinBox()
        self.roi_y_spin.setRange(0, 9999)
        
        self.roi_w_spin = QSpinBox()
        self.roi_w_spin.setRange(1, 9999)
        
        self.roi_h_spin = QSpinBox()
        self.roi_h_spin.setRange(1, 9999)
        
        motion_layout.addRow("检测阈值:", self.motion_threshold)
        motion_layout.addRow("最小区域:", self.min_area_spin)
        motion_layout.addRow("ROI X:", self.roi_x_spin)
        motion_layout.addRow("ROI Y:", self.roi_y_spin)
        motion_layout.addRow("ROI 宽度:", self.roi_w_spin)
        motion_layout.addRow("ROI 高度:", self.roi_h_spin)
        
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
        self.traj_smooth.stateChanged.connect(self.toggle_smooth_trajectory)
        self.motion_threshold.valueChanged.connect(self.update_motion_threshold)
        self.min_area_spin.valueChanged.connect(self.update_min_area)
        self.detection_method_combo.currentIndexChanged.connect(self.update_detection_method)
        
        # ROI设置
        self.roi_x_spin.valueChanged.connect(self.update_roi)
        self.roi_y_spin.valueChanged.connect(self.update_roi)
        self.roi_w_spin.valueChanged.connect(self.update_roi)
        self.roi_h_spin.valueChanged.connect(self.update_roi)
    
    def load_style(self):
        """加载样式表"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                background: white;
            }
            QTabBar::tab {
                background: #e0e0e0;
                color: black;
                padding: 8px;
                border: 1px solid #c0c0c0;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background: white;
            }
            QGroupBox {
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                margin-top: 10px;
                padding-top: 15px;
                color: black;
            }
            QLabel {
                color: black;
            }
            QPushButton {
                background-color: #e0e0e0;
                color: black;
                border: 1px solid #c0c0c0;
                padding: 5px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
            QPushButton:pressed {
                background-color: #c0c0c0;
            }
            QListWidget {
                background-color: white;
                color: black;
                border: 1px solid #c0c0c0;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: white;
                color: black;
                border: 1px solid #c0c0c0;
                padding: 3px;
            }
            QDockWidget {
                background: #e0e0e0;
                color: black;
            }
            QTextEdit {
                background-color: white;
                color: black;
            }
        """)

    def select_process(self):
        """选择目标进程"""
        dialog = ProcessSelectionDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            selected_items = dialog.process_list.selectedItems()
            if selected_items:
                proc = selected_items[0].data(Qt.UserRole)
                self.capture_targets = [proc]  # 单进程模式
                self.statusBar().showMessage(f"已选择进程: {proc['title']} (PID: {proc['pid']})", 3000)
                self.capture_target_label.setText(f"目标: {proc['title']}")
                
                # 初始化捕获
                try:
                    self.camera = dxcam.create()
                    self.statusBar().showMessage("DirectX Surface Sharing初始化成功", 3000)
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"初始化失败: {e}")
    
    def select_multiple_processes(self):
        """选择多个进程进行捕获"""
        dialog = ProcessSelectionDialog(self)
        dialog.setWindowTitle("选择多个目标进程")
        if dialog.exec_() == QDialog.Accepted:
            self.capture_targets = dialog.selected_processes()
            if self.capture_targets:
                target_names = ", ".join([p['title'] for p in self.capture_targets])
                self.statusBar().showMessage(f"已选择 {len(self.capture_targets)} 个进程: {target_names}", 5000)
                self.capture_target_label.setText(f"目标: {len(self.capture_targets)}个进程")
                
                # 初始化捕获
                try:
                    self.camera = dxcam.create()
                    self.statusBar().showMessage("多进程捕获初始化成功", 3000)
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"初始化失败: {e}")
    
    def select_region(self):
        """选择捕获区域"""
        if not self.capture_targets:
            QMessageBox.warning(self, "警告", "请先选择目标进程")
            return
            
        dialog = RegionSelectionDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.capture_region = dialog.selected_region
            self.statusBar().showMessage(
                f"已选择捕获区域: {self.capture_region[0]}x{self.capture_region[1]} "
                f"{self.capture_region[2]}x{self.capture_region[3]}", 3000)
            
            # 更新ROI设置
            self.roi_x_spin.setValue(self.capture_region[0])
            self.roi_y_spin.setValue(self.capture_region[1])
            self.roi_w_spin.setValue(self.capture_region[2])
            self.roi_h_spin.setValue(self.capture_region[3])
    
    def start_capture(self):
        """开始捕获"""
        if not self.capture_targets:
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
        """停止捕获"""
        self.capture_timer.stop()
        self.is_capturing = False
        
        # 停止视频录制
        if self.video_writer is not None:
            self.stop_video_recording()
        
        self.statusBar().showMessage("画面捕获已停止", 3000)
    
    def capture_frame(self):
        """捕获帧"""
        if not self.capture_targets or self.camera is None:
            return
        
        # 多进程捕获模式
        if len(self.capture_targets) > 1:
            frames = []
            for target in self.capture_targets:
                frame = self.camera.grab(region=self.capture_region)
                if frame is not None:
                    frames.append(frame)
            
            if not frames:
                return
                
            # 拼接多个画面
            if len(frames) == 2:
                # 两画面水平排列
                frame = np.hstack(frames)
            else:
                # 多于两画面使用网格排列
                rows = int(np.ceil(np.sqrt(len(frames))))
                cols = int(np.ceil(len(frames) / rows))
                
                row_imgs = []
                for i in range(rows):
                    start = i * cols
                    end = min((i + 1) * cols, len(frames))
                    row = np.hstack(frames[start:end])
                    row_imgs.append(row)
                
                frame = np.vstack(row_imgs)
        else:
            # 单进程捕获模式
            frame = self.camera.grab(region=self.capture_region)
        
        if frame is not None:
            # 确保图像是RGB格式
            if frame.shape[2] == 3:  # 已经RGB格式
                frame_rgb = frame
            else:  # 如果是BGR格式
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # 获取图像尺寸
            height, width, channel = frame_rgb.shape
            bytes_per_line = 3 * width
            
            # 创建QImage
            q_img = QImage(frame_rgb.data, width, height, bytes_per_line, QImage.Format_RGB888)
            
            # 更新预览
            self.preview_label.setPixmap(QPixmap.fromImage(q_img).scaled(
                self.preview_label.width(), 
                self.preview_label.height(), 
                Qt.KeepAspectRatio))
            
            # 更新信息显示
            elapsed = time.time() - self.record_start_time
            self.fps_label.setText(f"帧率: {self.capture_fps}")
            self.resolution_label.setText(f"分辨率: {width}x{height}")
            self.time_label.setText(f"时间: {datetime.utcfromtimestamp(elapsed).strftime('%H:%M:%S')}")
            
            # 更新轨迹页面的当前帧
            self.trajectory_widget.setFrame(frame_rgb)
            
            # 运动检测
            if self.detect_motion:
                motion_centers = self.motion_detector.detect(frame_rgb)
                for center in motion_centers:
                    self.trajectory_widget.addPoint(center, self.trajectory_widget.active_trajectory)
            
            # 录制视频
            if self.video_writer is not None:
                # 需要转换回BGR格式
                frame_bgr = frame_rgb[:, :, [2, 1, 0]]
                self.video_writer.write(frame_bgr)
    
    def start_video_recording(self):
        """开始视频录制"""
        if not self.capture_targets:
            return
            
        # 获取视频文件名
        filename, _ = QFileDialog.getSaveFileName(
            self, "保存视频文件", "", "MP4 文件 (*.mp4);;AVI 文件 (*.avi)")
            
        if not filename:
            self.record_video_chk.setChecked(False)
            return
            
        self.video_filename = filename
        
        # 获取帧尺寸
        if len(self.capture_targets) > 1:
            # 多进程捕获时使用固定尺寸
            width, height = 1920, 1080  # 可根据需要调整
        else:
            frame = self.camera.grab(region=self.capture_region)
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
        """停止视频录制"""
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None
            self.statusBar().showMessage(f"视频已保存到: {self.video_filename}", 5000)
    
    def toggle_video_recording(self, state):
        """切换视频录制状态"""
        if state == Qt.Checked and self.is_capturing:
            self.start_video_recording()
        elif self.video_writer is not None:
            self.stop_video_recording()
    
    def take_screenshot(self):
        """截图"""
        if not self.capture_targets or not self.is_capturing:
            QMessageBox.warning(self, "警告", "没有可捕获的画面")
            return
            
        frame = self.camera.grab(region=self.capture_region)
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
        """开始记录轨迹"""
        if not self.is_capturing:
            QMessageBox.warning(self, "警告", "请先开始画面捕获")
            return
            
        self.is_recording = True
        self.statusBar().showMessage("轨迹记录已开始", 3000)
    
    def stop_trajectory(self):
        """停止记录轨迹"""
        self.is_recording = False
        self.statusBar().showMessage("轨迹记录已停止", 3000)
    
    def clear_trajectory(self):
        """清除轨迹"""
        if self.trajectory_widget:
            self.trajectory_widget.clearTrajectory()
            self.statusBar().showMessage("轨迹已清除", 3000)
    
    def save_trajectory(self):
        """保存轨迹数据"""
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
                    "points": traj,
                    "velocity": self.trajectory_widget.trajectory_analyzer.calculate_velocity(traj),
                    "acceleration": self.trajectory_widget.trajectory_analyzer.calculate_acceleration(
                        self.trajectory_widget.trajectory_analyzer.calculate_velocity(traj))
                })
            
            # 保存为JSON
            if filename.endswith('.json'):
                with open(filename, 'w') as f:
                    json.dump(traj_data, f, indent=2)
            # 保存为CSV
            elif filename.endswith('.csv'):
                with open(filename, 'w') as f:
                    f.write("trajectory_id,x,y,velocity,acceleration\n")
                    for i, traj in enumerate(self.trajectory_widget.trajectory_points):
                        velocities = self.trajectory_widget.trajectory_analyzer.calculate_velocity(traj)
                        accelerations = self.trajectory_widget.trajectory_analyzer.calculate_acceleration(velocities)
                        
                        # 第一个点没有速度和加速度
                        f.write(f"{i},{traj[0][0]},{traj[0][1]},,\n")
                        
                        for j in range(1, len(traj)):
                            vel = velocities[j-1] if j-1 < len(velocities) else ""
                            acc = accelerations[j-2] if j-2 >= 0 and j-2 < len(accelerations) else ""
                            f.write(f"{i},{traj[j][0]},{traj[j][1]},{vel},{acc}\n")
            
            self.statusBar().showMessage(f"轨迹数据已保存到: {filename}", 5000)
    
    def toggle_motion_detection(self, state):
        """切换运动检测"""
        self.detect_motion = state == Qt.Checked
        if self.detect_motion:
            # 根据选择的方法初始化检测器
            method = self.detection_method_combo.currentText()
            if method == "帧差法":
                self.motion_detector.set_method("frame_diff")
            elif method == "背景减除法":
                self.motion_detector.set_method("background_sub")
            elif method == "光流法":
                self.motion_detector.set_method("optical_flow")
            
            self.statusBar().showMessage(f"运动检测已启用 ({method})", 3000)
        else:
            self.statusBar().showMessage("运动检测已禁用", 3000)
    
    def update_detection_method(self, index):
        """更新运动检测方法"""
        if self.detect_motion:
            method = self.detection_method_combo.currentText()
            if method == "帧差法":
                self.motion_detector.set_method("frame_diff")
            elif method == "背景减除法":
                self.motion_detector.set_method("background_sub")
            elif method == "光流法":
                self.motion_detector.set_method("optical_flow")
            
            self.statusBar().showMessage(f"运动检测方法已切换为: {method}", 3000)
    
    def new_trajectory(self):
        """新建轨迹"""
        self.trajectory_widget.active_trajectory = self.trajectory_count
        self.trajectory_count += 1
        self.statusBar().showMessage(f"新建轨迹 {self.trajectory_widget.active_trajectory + 1}", 3000)
    
    def toggle_measure_tool(self):
        """切换测量工具"""
        self.trajectory_widget.startMeasure()
        if self.trajectory_widget.measure_mode:
            self.measure_btn.setText("结束测量")
        else:
            self.measure_btn.setText("测量工具")
    
    def toggle_annotation(self):
        """切换标注模式"""
        self.trajectory_widget.startAnnotation()
        if self.trajectory_widget.annotation_mode:
            self.annotation_btn.setText("结束标注")
        else:
            self.annotation_btn.setText("添加标注")
    
    def generate_heatmap(self):
        """生成热力图"""
        if not self.trajectory_widget.trajectory_points:
            QMessageBox.warning(self, "警告", "没有轨迹数据可生成热力图")
            return
            
        self.trajectory_widget.generateHeatmap()
        self.statusBar().showMessage("热力图已生成", 3000)
    
    def export_trajectory_data(self):
        """导出轨迹数据"""
        self.save_trajectory()
    
    def update_capture_fps(self, fps):
        """更新捕获帧率"""
        self.capture_fps = fps
        if self.is_capturing:
            self.capture_timer.setInterval(int(1000 / fps))
            self.statusBar().showMessage(f"帧率已更新: {fps}FPS", 2000)
    
    def update_trajectory_width(self, width):
        """更新轨迹宽度"""
        # 可以在TrajectoryWidget中添加轨迹宽度属性
        pass
    
    def toggle_show_points(self, state):
        """切换显示轨迹点"""
        self.trajectory_widget.show_points = state == Qt.Checked
        self.trajectory_widget.update()
    
    def toggle_show_info(self, state):
        """切换显示信息"""
        self.trajectory_widget.show_info = state == Qt.Checked
        self.trajectory_widget.update()
    
    def toggle_smooth_trajectory(self):
        """切换轨迹平滑"""
        enabled = not self.trajectory_widget.smooth_trajectory
        self.trajectory_widget.toggleSmoothTrajectory(enabled)
        
        # 更新按钮样式
        self.smooth_traj_btn.setStyleSheet(
            "background-color: #4CAF50; color: white;" if enabled else ""
        )
        
        # 显示在状态栏而不是analysis_status
        status = "轨迹平滑已启用 | 使用高斯滤波消除抖动" if enabled else "轨迹平滑已禁用"
        self.statusBar().showMessage(status, 3000)
        
        self.trajectory_widget.update()


    
    def toggle_velocity(self):
        """切换速度显示"""
        self.trajectory_widget.toggleVelocity(not self.trajectory_widget.show_velocity)
        if self.trajectory_widget.show_velocity:
            self.velocity_btn.setText("隐藏速度")
            self.statusBar().showMessage("速度显示已启用", 2000)  # 改为状态栏显示
        else:
            self.velocity_btn.setText("显示速度")
            self.statusBar().showMessage("速度显示已禁用", 2000)  # 改为状态栏显示

    
    def toggle_prediction(self):
        """切换预测路径显示"""
        self.trajectory_widget.togglePrediction(not self.trajectory_widget.show_prediction)
        if self.trajectory_widget.show_prediction:
            self.predict_btn.setText("隐藏预测")
            self.statusBar().showMessage("预测路径显示已启用", 2000)  # 改为状态栏显示
        else:
            self.predict_btn.setText("预测路径")
            self.statusBar().showMessage("预测路径显示已禁用", 2000)  # 改为状态栏显示

    
    def update_motion_threshold(self, value):
        """更新运动检测阈值"""
        self.motion_detector.threshold = value
    
    def update_min_area(self, value):
        """更新最小检测区域"""
        self.motion_detector.min_contour_area = value
    
    def update_roi(self):
        """更新ROI设置"""
        x = self.roi_x_spin.value()
        y = self.roi_y_spin.value()
        w = self.roi_w_spin.value()
        h = self.roi_h_spin.value()
        
        if w > 0 and h > 0:
            self.motion_detector.set_roi((x, y, w, h))
            if self.capture_region is None:
                self.capture_region = (x, y, w, h)
            else:
                self.capture_region = (x, y, w, h)
            self.statusBar().showMessage(f"ROI已更新: {x}x{y} {w}x{h}", 2000)
    
    def cluster_trajectories(self):
        """轨迹聚类"""
        if not self.trajectory_widget.trajectory_points:
            QMessageBox.warning(self, "警告", "没有轨迹数据可聚类")
            return
            
        n_clusters, ok = QInputDialog.getInt(self, "轨迹聚类", "输入聚类数量:", 2, 2, 10)
        if ok:
            clusters = self.trajectory_widget.trajectory_analyzer.cluster_trajectories(n_clusters)
            
            # 更新轨迹颜色以反映聚类结果
            cluster_colors = [
                QColor(255, 0, 0),   # 红
                QColor(0, 255, 0),   # 绿
                QColor(0, 0, 255),   # 蓝
                QColor(255, 255, 0), # 黄
                QColor(255, 0, 255), # 紫
                QColor(0, 255, 255), # 青
            ]
            
            for i, cluster_id in enumerate(clusters):
                if i < len(self.trajectory_widget.trajectory_colors):
                    self.trajectory_widget.trajectory_colors[i] = cluster_colors[cluster_id % len(cluster_colors)]
            
            self.trajectory_widget.update()
            self.statusBar().showMessage(f"轨迹已聚类为 {n_clusters} 类", 3000)
    
    def merge_trajectories(self):
        """合并轨迹"""
        if len(self.trajectory_widget.trajectory_points) < 2:
            QMessageBox.warning(self, "警告", "至少需要两条轨迹才能合并")
            return
            
        # 弹出对话框让用户选择要合并的轨迹
        items = [f"轨迹 {i+1} (点数: {len(traj)})" 
                for i, traj in enumerate(self.trajectory_widget.trajectory_points)]
        selected, ok = QInputDialog.getItem(
            self, "合并轨迹", "选择要合并的轨迹 (多选用逗号分隔):", 
            items, 0, False)
        
        if ok and selected:
            try:
                # 解析用户选择 (例如 "1,3,5")
                indices = [int(i.strip()) - 1 for i in selected.split(",")]
                self.trajectory_widget.mergeTrajectories(indices)
                self.statusBar().showMessage(f"已合并 {len(indices)} 条轨迹", 3000)
            except:
                QMessageBox.warning(self, "警告", "无效的选择格式")
    
    def split_trajectory(self):
        """分割轨迹"""
        if not self.trajectory_widget.trajectory_points:
            QMessageBox.warning(self, "警告", "没有轨迹可分割")
            return
            
        # 弹出对话框让用户选择要分割的轨迹和分割点
        items = [f"轨迹 {i+1} (点数: {len(traj)})" 
                for i, traj in enumerate(self.trajectory_widget.trajectory_points)]
        traj_idx, ok1 = QInputDialog.getItem(
            self, "分割轨迹", "选择要分割的轨迹:", items, 0, False)
        
        if ok1 and traj_idx:
            try:
                idx = items.index(traj_idx)
                point_idx, ok2 = QInputDialog.getInt(
                    self, "分割轨迹", f"输入分割点索引 (1-{len(self.trajectory_widget.trajectory_points[idx])-1}):", 
                    1, 1, len(self.trajectory_widget.trajectory_points[idx])-1)
                
                if ok2:
                    self.trajectory_widget.splitTrajectory(idx, point_idx)
                    self.statusBar().showMessage(f"轨迹 {idx+1} 已在点 {point_idx} 处分割", 3000)
            except:
                QMessageBox.warning(self, "警告", "无效的选择")
    



    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, "关于", 
            "<h2>高级进程画面轨迹记录工具 (增强版)</h2>"
            "<p>版本 2.0</p>"
            "<p>使用Python和PyQt5开发</p>"
            "<p>增强功能:</p>"
            "<ul>"
            "<li>多进程捕获</li>"
            "<li>区域选择</li>"
            "<li>轨迹平滑</li>"
            "<li>速度/加速度分析</li>"
            "<li>轨迹预测</li>"
            "<li>热力图生成</li>"
            "<li>高级运动检测</li>"
            "</ul>")
    
    def closeEvent(self, event):
        """关闭事件处理"""
        # 停止所有活动
        if self.is_capturing:
            self.stop_capture()
        
        if self.video_writer is not None:
            self.stop_video_recording()
        
        event.accept()

    def show_analysis_results(self):
        """在分析视图显示结果"""
        if not hasattr(self.trajectory_widget, 'current_frame') or not self.trajectory_widget.current_frame:
            self.analysis_status.setText("错误: 没有可分析的帧数据")
            return
        
        scene = QGraphicsScene()
        
        # 1. 显示基础图像
        height, width = self.trajectory_widget.current_frame.shape[:2]
        bytes_per_line = 3 * width
        q_img = QImage(
            self.trajectory_widget.current_frame.data, 
            width, height, bytes_per_line, 
            QImage.Format_RGB888
        )
        scene.addPixmap(QPixmap.fromImage(q_img))
        
        # 2. 显示热力图
        if self.trajectory_widget.show_heatmap and self.trajectory_widget.heatmap is not None:
            heatmap_img = np.zeros((height, width, 3), dtype=np.uint8)
            # ...热力图生成代码...
            scene.addPixmap(QPixmap.fromImage(heatmap_img))
        
        # 3. 显示速度向量
        if self.trajectory_widget.show_velocity:
            for x, y, dx, dy, speed in self.trajectory_widget.velocity_vectors:
                # ...绘制箭头代码...
                scene.addLine(line, pen)
        
        self.analysis_view.setScene(scene)
        self.analysis_view.fitInView()
        self.analysis_status.setText("分析结果可视化完成")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置中文显示
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())