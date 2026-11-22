import sys
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, 
                            QVBoxLayout, QPushButton, QLabel, QListWidget, 
                            QDialog, QHBoxLayout)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor
try:
    import dxcam
    DX_CAM_AVAILABLE = True
except ImportError:
    DX_CAM_AVAILABLE = False
    print("警告: dxcam 模块未安装，屏幕捕获功能将不可用")
    print("请使用命令安装: pip install dxcam")


class ProcessSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择目标进程")
        self.setWindowModality(Qt.ApplicationModal)
        self.resize(400, 300)
        
        self.layout = QVBoxLayout()
        
        self.label = QLabel("请选择目标进程:")
        self.process_list = QListWidget()
        
        # 模拟获取进程列表
        self.simulate_processes = [
            "explorer.exe - 文件资源管理器",
            "chrome.exe - Google Chrome",
            "notepad.exe - 记事本",
            "python.exe - Python 解释器",
            "dwm.exe - 桌面窗口管理器"
        ]
        
        self.process_list.addItems(self.simulate_processes)
        
        # 按钮布局
        self.button_layout = QHBoxLayout()
        self.ok_button = QPushButton("确定")
        self.cancel_button = QPushButton("取消")
        
        self.button_layout.addWidget(self.ok_button)
        self.button_layout.addWidget(self.cancel_button)
        
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.process_list)
        self.layout.addLayout(self.button_layout)
        
        self.setLayout(self.layout)
        
        # 连接信号
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)


class TrajectoryWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.trajectory_points = []
        self.current_frame = None
        self.setMinimumSize(640, 480)
        
    def set_frame(self, frame):
        self.current_frame = frame
        self.update()
        
    def add_point(self, point):
        self.trajectory_points.append(point)
        self.update()
        
    def clear_trajectory(self):
        self.trajectory_points = []
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        
        # 绘制当前帧
        if self.current_frame is not None:
            height, width, channel = self.current_frame.shape
            bytes_per_line = 3 * width
            q_img = QImage(self.current_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
            painter.drawPixmap(0, 0, QPixmap.fromImage(q_img).scaled(
                self.width(), self.height(), Qt.KeepAspectRatio)
            )
        
        # 绘制轨迹
        if len(self.trajectory_points) > 1:
            pen = QPen(QColor(255, 0, 0), 3)
            painter.setPen(pen)
            
            for i in range(1, len(self.trajectory_points)):
                prev_point = self.trajectory_points[i-1]
                curr_point = self.trajectory_points[i]
                painter.drawLine(prev_point[0], prev_point[1], 
                                curr_point[0], curr_point[1])
                
        painter.end()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("进程画面轨迹记录工具")
        self.resize(800, 600)
        
        # 主标签页
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # 创建标签页
        self.tab1 = QWidget()
        self.tab2 = QWidget()
        
        self.tabs.addTab(self.tab1, "画面捕获")
        self.tabs.addTab(self.tab2, "轨迹记录")
        
        # 初始化标签页
        self.init_tab1()
        self.init_tab2()
        
        # DirectX捕获相关
        self.camera = None
        self.capture_timer = QTimer()
        self.capture_timer.timeout.connect(self.capture_frame)
        
        # 轨迹记录相关
        self.trajectory_timer = QTimer()
        self.trajectory_timer.timeout.connect(self.update_trajectory)
        self.trajectory_points = []
        
    def init_tab1(self):
        layout = QVBoxLayout()
        
        self.select_process_btn = QPushButton("选择目标进程")
        self.start_capture_btn = QPushButton("开始捕获")
        self.stop_capture_btn = QPushButton("停止捕获")
        
        self.preview_label = QLabel("画面预览区域")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background-color: black; color: white;")
        
        layout.addWidget(self.select_process_btn)
        layout.addWidget(self.start_capture_btn)
        layout.addWidget(self.stop_capture_btn)
        layout.addWidget(self.preview_label)
        
        self.tab1.setLayout(layout)
        
        # 连接信号
        self.select_process_btn.clicked.connect(self.select_process)
        self.start_capture_btn.clicked.connect(self.start_capture)
        self.stop_capture_btn.clicked.connect(self.stop_capture)
        
    def init_tab2(self):
        layout = QVBoxLayout()
        
        self.trajectory_widget = TrajectoryWidget()
        
        self.start_trajectory_btn = QPushButton("开始记录轨迹")
        self.stop_trajectory_btn = QPushButton("停止记录轨迹")
        self.clear_trajectory_btn = QPushButton("清除轨迹")
        self.save_trajectory_btn = QPushButton("保存轨迹")
        
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.start_trajectory_btn)
        button_layout.addWidget(self.stop_trajectory_btn)
        button_layout.addWidget(self.clear_trajectory_btn)
        button_layout.addWidget(self.save_trajectory_btn)
        
        layout.addWidget(self.trajectory_widget)
        layout.addLayout(button_layout)
        
        self.tab2.setLayout(layout)
        
        # 连接信号
        self.start_trajectory_btn.clicked.connect(self.start_trajectory)
        self.stop_trajectory_btn.clicked.connect(self.stop_trajectory)
        self.clear_trajectory_btn.clicked.connect(self.clear_trajectory)
        self.save_trajectory_btn.clicked.connect(self.save_trajectory)
        
    def select_process(self):
        dialog = ProcessSelectionDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            selected_items = dialog.process_list.selectedItems()
            if selected_items:
                selected_process = selected_items[0].text()
                print(f"已选择进程: {selected_process}")
                # 这里应该实现真正的进程选择和捕获初始化
                # 模拟初始化DirectX捕获
                try:
                    if not DX_CAM_AVAILABLE:
                        print("错误: dxcam 模块不可用，无法初始化捕获")
                        return
                    self.camera = dxcam.create()
                    print("DirectX Surface Sharing初始化成功")
                except Exception as e:
                    print(f"初始化失败: {e}")
    
    def start_capture(self):
        if self.camera is None:
            print("请先选择目标进程")
            return
            
        self.capture_timer.start(33)  # 约30fps
        print("画面捕获已开始")
        
    def stop_capture(self):
        self.capture_timer.stop()
        print("画面捕获已停止")
        
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
            
            # 同时更新轨迹页面的当前帧
            self.trajectory_widget.set_frame(frame_rgb)
    
    def start_trajectory(self):
        if not self.capture_timer.isActive():
            print("请先开始画面捕获")
            return
            
        self.trajectory_timer.start(100)  # 每100ms记录一个点
        print("轨迹记录已开始")
        
    def stop_trajectory(self):
        self.trajectory_timer.stop()
        print("轨迹记录已停止")
        
    def clear_trajectory(self):
        self.trajectory_widget.clear_trajectory()
        print("轨迹已清除")
        
    def save_trajectory(self):
        if not self.trajectory_widget.trajectory_points:
            print("没有轨迹数据可保存")
            return
            
        # 这里应该实现保存轨迹到文件的逻辑
        print(f"已保存 {len(self.trajectory_widget.trajectory_points)} 个轨迹点")
        
    def update_trajectory(self):
        if self.camera is None:
            return
            
        # 模拟获取运动点 - 实际应用中应该使用运动检测算法
        frame = self.camera.grab()
        if frame is not None:
            # 这里简化处理，实际应该检测运动物体并获取中心点
            height, width = frame.shape[:2]
            center_x = width // 2 + int(50 * np.sin(len(self.trajectory_points) * 0.1))
            center_y = height // 2 + int(50 * np.cos(len(self.trajectory_points) * 0.1))
            
            self.trajectory_widget.add_point((center_x, center_y))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())