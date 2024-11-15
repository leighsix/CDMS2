import sys
import sqlite3
import csv, json, re, os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget, QFileDialog, QMessageBox, QHBoxLayout, QSplitter, QComboBox, QLineEdit, QTableWidget, QPushButton, QLabel,
                             QGroupBox, QCheckBox, QHeaderView, QDialog, QTableWidgetItem)
import matplotlib.pyplot as plt
from simulation_map_view import SimulationCalMapView, SimulationWeaponMapView, SimulationEnemyBaseMapView, SimulationEnemyWeaponMapView
import io
import pandas as pd
import folium
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6 import QtWidgets, QtGui
from PyQt6.QtWidgets import *
from PyQt6.QtGui import QPixmap, QFont, QIcon, QLinearGradient, QColor, QPainter, QPainterPath, QPen
from PyQt6.QtCore import Qt, QCoreApplication, QTranslator, QObject, QDir, QRect, QPoint
from PyQt6 import QtCore
from PyQt6.QtCore import QUrl, QSize, QTimer, QTemporaryFile, QDir, QEventLoop, QDateTime
from setting import MapApp
import numpy as np
import math, logging
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog
from PyQt6.QtGui import QTextDocument, QTextCursor, QTextTableFormat, QTextFrameFormat, QTextLength, QTextCharFormat, QFont, QTextBlockFormat
from PyQt6.QtGui import QPagedPaintDevice, QPainter, QImage, QPageSize, QPageLayout
from PyQt6.QtCore import QUrl, QTemporaryFile, QSize, QTimer, QMarginsF, QThread
from missile_trajectory_calculator import MissileTrajectoryCalculator
from particle_swarm_optimization import MissileDefenseOptimizer, OptimizationWorker
from engagement_possiblity_calculator import EngagementPossibilityCalculator
from PyQt6.QtWidgets import QVBoxLayout, QWidget
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import concurrent.futures
import gc


class MissileDefenseApp(QDialog):
    def __init__(self, parent=None):
        super(MissileDefenseApp, self).__init__(parent)
        self.trajectories = []
        self.defense_trajectories = []
        self.engagement_zones = {}
        self.optimized_locations = []
        self.parent = parent
        self.conn = sqlite3.connect(self.parent.db_path)
        self.cursor = self.conn.cursor()
        self.map = folium.Map(
            location=[self.parent.map_app.loadSettings()['latitude'], self.parent.map_app.loadSettings()['longitude']],
            zoom_start=self.parent.map_app.loadSettings()['zoom'],
            tiles=self.parent.map_app.loadSettings()['style'])
        # 3D 그래프를 위한 Figure 객체 생성
        self.figure = plt.figure(figsize=(10, 8))
        self.ax = self.figure.add_subplot(111, projection='3d')
        self.canvas = FigureCanvas(self.figure)
        self.setWindowTitle(self.tr("미사일 방어 시뮬레이션"))
        self.setMinimumSize(1200, 800)
        self.load_dataframes()
        self.initUI()
        self.trajectory_calculator = MissileTrajectoryCalculator()
        self.engagement_calculator = EngagementPossibilityCalculator(self.weapon_systems_info, self.missile_info)
        self.optimizer = None  # optimizer 속성 추가
        self.optimized_locations = None
        self.show_defense_radius = False
        self.show_threat_radius = False
        self.update_map_with_trajectories()
        # QtWebEngine 캐시 설정
        profile = QWebEngineProfile.defaultProfile()
        profile.setCachePath(os.path.join(os.path.expanduser('~'), '.cache', 'qtwebengine'))
        profile.setPersistentStoragePath(os.path.join(os.path.expanduser('~'), '.cache', 'qtwebengine'))
        profile.clearHttpCache()
        # 초기 지도 로드

    def load_dataframes(self):
        try:
            conn = sqlite3.connect(self.parent.db_path)

            try:
                query = "SELECT * FROM cal_assets_priority_ko"
                self.cal_df_ko = pd.read_sql_query(query, conn,)
                query = "SELECT * FROM cal_assets_priority_en"
                self.cal_df_en = pd.read_sql_query(query, conn,)

            except sqlite3.OperationalError:
                print("assets_priority 테이블이 존재하지 않습니다.")
                self.cal_df_ko = pd.DataFrame(columns=["id", "priority", "unit", "asset_number", "manager", "contact",
                                                       "target_asset", "area", "coordinate", "mgrs", "description",
                                                       "dal_select", "weapon_system", "ammo_count", "threat_degree",
                                                       "engagement_effectiveness", "bmd_priority", "criticality", "vulnerability",
                                                       "threat", "total_score"])
                self.cal_df_en = pd.DataFrame(columns=["id", "priority", "unit", "asset_number", "manager", "contact",
                                                       "target_asset", "area", "coordinate", "mgrs", "description",
                                                       "dal_select", "weapon_system", "ammo_count", "threat_degree",
                                                       "engagement_effectiveness", "bmd_priority", "criticality", "vulnerability",
                                                       "threat", "total_score"])


            try:
                query = "SELECT * FROM dal_assets_priority_ko"
                self.dal_df_ko = pd.read_sql_query(query, conn,)
                query = "SELECT * FROM dal_assets_priority_en"
                self.dal_df_en = pd.read_sql_query(query, conn,)

            except sqlite3.OperationalError:
                print("defense_assets 테이블이 존재하지 않습니다.")
                self.dal_df_ko = pd.DataFrame(columns=["id", "priority", "unit", "asset_number", "manager", "contact",
                                                       "target_asset", "area", "coordinate", "mgrs", "description",
                                                       "dal_select", "weapon_system", "ammo_count", "threat_degree",
                                                       "engagement_effectiveness", "bmd_priority", "criticality", "vulnerability",
                                                       "threat", "total_score"])
                self.dal_df_en = pd.DataFrame(columns=["id", "priority", "unit", "asset_number", "manager", "contact",
                                                       "target_asset", "area", "coordinate", "mgrs", "description",
                                                       "dal_select", "weapon_system", "ammo_count", "threat_degree",
                                                       "engagement_effectiveness", "bmd_priority", "criticality", "vulnerability",
                                                       "threat", "total_score"])

            try:
                query = "SELECT * FROM enemy_bases_ko"
                self.enemy_bases_df_ko = pd.read_sql_query(query, conn,)
                query = "SELECT * FROM enemy_bases_en"
                self.enemy_bases_df_en = pd.read_sql_query(query, conn,)

            except sqlite3.OperationalError:
                print("defense_assets 테이블이 존재하지 않습니다.")
                self.enemy_bases_df_ko = pd.DataFrame(columns=["id", "base_name", "area", "coordinate", "mgrs", "weapon_system"])
                self.enemy_bases_df_en = pd.DataFrame(columns=["id", "base_name", "area", "coordinate", "mgrs", "weapon_system"])


            try:
                query = "SELECT * FROM weapon_assets_ko"
                self.weapon_assets_df_ko = pd.read_sql_query(query, conn,)
                query = "SELECT * FROM weapon_assets_en"
                self.weapon_assets_df_en = pd.read_sql_query(query, conn,)

            except sqlite3.OperationalError:
                print("defense_assets 테이블이 존재하지 않습니다.")
                self.weapon_assets_df_ko = pd.DataFrame(columns=["id", "unit", "area", "asset_name", "coordinate", "mgrs", "weapon_system", "ammo_count", "threat_degree", "dal_select"])
                self.weapon_assets_df_en = pd.DataFrame(columns=["id", "unit", "area", "asset_name", "coordinate", "mgrs", "weapon_system", "ammo_count", "threat_degree", "dal_select"])

        except sqlite3.Error as e:
            print(f"데이터베이스 연결 오류: {e}")

        finally:
            if conn:
                conn.close()

        # 수정된 조건문
        if (self.cal_df_ko.empty and self.dal_df_ko.empty and
                self.enemy_bases_df_ko.empty and self.weapon_assets_df_ko.empty):
            print("경고: 데이터를 불러오지 못했습니다. 빈 DataFrame을 사용합니다.")

    def refresh(self):
        self.trajectories = []
        self.defense_trajectories = []
        self.engagement_zones = {}
        self.optimized_locations = []

        # 테이블 초기화
        self.assets_table.uncheckAllRows()
        self.enemy_sites_table.uncheckAllRows()
        self.weapon_assets_table.uncheckAllRows()

        # 필터 초기화
        self.unit_filter.setCurrentIndex(0)
        self.missile_type_combo.setCurrentIndex(0)
        self.weapon_type_combo.setCurrentIndex(0)
        self.search_filter.clear()
        self.search_enemy_filter.clear()
        self.search_weapon_filter.clear()

        # 체크박스 초기화
        self.threat_radius_checkbox.setChecked(False)
        self.defense_radius_checkbox.setChecked(False)
        self.dal_select_checkbox.setChecked(False)

        # 결과 테이블 초기화
        self.result_table.clear()
        self.result_table.setRowCount(0)
        self.result_table.setColumnCount(0)

        # 데이터 다시 로드
        self.load_dataframes()
        self.load_assets()
        self.load_enemy_missile_sites()
        self.load_weapon_assets()

        # 지도 및 그래프 초기화
        self.update_map_with_trajectories()
        self.update_3d_graph()

    def initUI(self):
        """UI 초기화 메서드"""
        # UI 구성 변경
        main_layout = QVBoxLayout(self)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 좌측 위젯 (방어 대상 자산 우선순위 테이블)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # ... (필터, 테이블, 페이지네이션 코드 - ViewCopWindow 클래스 참고)
        # 필터 추가
        self.filter_layout = QHBoxLayout()

        self.unit_filter = QComboBox()
        self.unit_filter.addItems([self.tr("전체"), self.tr("지상군"), self.tr("해군"), self.tr("공군")])
        self.unit_filter.currentTextChanged.connect(self.load_assets)
        self.filter_layout.addWidget(self.unit_filter)

        # 방어대상자산 테이블 검색 기능
        self.filter_layout = QHBoxLayout()
        self.search_filter = QLineEdit()
        self.search_filter.setPlaceholderText(self.tr("방어대상자산 또는 지역 검색"))
        self.search_button = QPushButton(self.tr("찾기"))
        self.search_button.clicked.connect(self.load_assets)
        self.filter_layout.addWidget(self.search_filter)
        self.filter_layout.addWidget(self.search_button)
        left_layout.addLayout(self.filter_layout)

        left_layout.addLayout(self.filter_layout)

        self.assets_table = MyTableWidget()
        self.assets_table.setColumnCount(5)
        self.assets_table.setHorizontalHeaderLabels(
            ["", self.tr("우선순위"), self.tr("구성군"), self.tr("지역"), self.tr("방어대상자산")])

        # 행 번호 숨기기
        self.assets_table.verticalHeader().setVisible(False)

        font = QFont("강한공군체", 13)
        font.setBold(True)
        self.assets_table.horizontalHeader().setFont(font)
        header = self.assets_table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
        header.resizeSection(0, 40)
        header.resizeSection(1, 80)

        # 헤더 텍스트 중앙 정렬
        for column in range(header.count()):
            item = self.assets_table.horizontalHeaderItem(column)
            if item:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        # 나머지 열들이 남은 공간을 채우도록 설정
        for column in range(2, header.count()):
            self.assets_table.horizontalHeader().setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeMode.Stretch)

        left_layout.addWidget(self.assets_table)

        # 버튼 레이아웃 설정
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)
        button_layout.setContentsMargins(0, 20, 0, 20)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 버튼을 중앙에 정렬

        self.return_button = QPushButton(self.tr("메인화면"), self)
        self.return_button.clicked.connect(self.parent.show_main_page)
        self.return_button.setFont(QFont("강한공군체", 15, QFont.Weight.Bold))
        self.return_button.setFixedSize(250, 50)  # 버튼 크기 고정 (너비 200, 높이 50)
        self.return_button.setStyleSheet("QPushButton { text-align: center; }")  # 텍스트 가운데 정렬
        button_layout.addWidget(self.return_button)
        left_layout.addLayout(button_layout)  # 버튼 레이아웃을 left_layout에 추가

        # 우측 상단 위젯 (적 기지 테이블)
        top_right_widget = QWidget()
        top_right_layout = QVBoxLayout(top_right_widget)



        # 우측 상단 테이블: 적 미사일 발사기지
        top_right_layout.addWidget(QLabel(self.tr("적 미사일 기지 목록")))

        # 필터 추가
        self.enemy_filter_layout = QHBoxLayout()

        # 적 미사일 기지 테이블 검색 기능
        self.enemy_filter_layout = QHBoxLayout()
        self.search_enemy_filter = QLineEdit()
        self.search_enemy_filter.setPlaceholderText(self.tr("적 기지명 또는 지역 검색"))
        self.search_enemy_button = QPushButton(self.tr("찾기"))
        self.search_enemy_button.clicked.connect(self.load_enemy_missile_sites)
        self.enemy_filter_layout.addWidget(self.search_enemy_filter)
        self.enemy_filter_layout.addWidget(self.search_enemy_button)
        top_right_layout.addLayout(self.enemy_filter_layout)

        # 미사일 타입 콤보박스
        self.missile_type_combo = QComboBox()
        with open('missile_info.json', 'r', encoding='utf-8') as file:
            missile_types = json.load(file)
        missile_types_list = [self.tr('전체')] + list(missile_types.keys())
        # 무기체계 이름들을 콤보박스에 추가
        self.missile_type_combo.addItems(missile_types_list)
        self.missile_type_combo.currentTextChanged.connect(self.load_enemy_missile_sites)
        self.enemy_filter_layout.addWidget(self.missile_type_combo)

        # 위협반경 표시 체크박스
        self.threat_radius_checkbox = QCheckBox(self.tr("위협반경 표시"))
        self.threat_radius_checkbox.stateChanged.connect(self.toggle_threat_radius)
        self.enemy_filter_layout.addWidget(self.threat_radius_checkbox)

        top_right_layout.addLayout(self.enemy_filter_layout)

        self.enemy_sites_table = MyTableWidget()
        self.enemy_sites_table.setColumnCount(4)
        self.enemy_sites_table.setHorizontalHeaderLabels(["", self.tr("발사기지"), self.tr("경위도"), self.tr("보유미사일")])
        # 행 번호 숨기기
        self.enemy_sites_table.verticalHeader().setVisible(False)
        font = QFont("강한공군체", 13)
        font.setBold(True)
        self.enemy_sites_table.horizontalHeader().setFont(font)
        header = self.enemy_sites_table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
        header.resizeSection(0, 40)
        # 헤더 텍스트 중앙 정렬
        for column in range(header.count()):
            item = self.enemy_sites_table.horizontalHeaderItem(column)
            if item:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        # 나머지 열들이 남은 공간을 채우도록 설정
        for column in range(1, header.count()):
            self.enemy_sites_table.horizontalHeader().setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeMode.Stretch)

        top_right_layout.addWidget(self.enemy_sites_table)

        # 우측 하단 위젯 (방어 자산 테이블)
        bottom_right_widget = QWidget()
        bottom_right_layout = QVBoxLayout(bottom_right_widget)

        # 우측 중간 테이블 변경
        bottom_right_layout.addWidget(QLabel(self.tr("방어포대 자산 목록")))

        # 필터 추가
        self.weapon_filter_layout = QHBoxLayout()
        # 무기 자산 테이블 검색 기능
        self.weapon_filter_layout = QHBoxLayout()
        self.search_weapon_filter = QLineEdit()
        self.search_weapon_filter.setPlaceholderText(self.tr("방어포대 검색"))
        self.search_weapon_button = QPushButton(self.tr("찾기"))
        self.search_weapon_button.clicked.connect(self.load_weapon_assets)
        self.weapon_filter_layout.addWidget(self.search_weapon_filter)
        self.weapon_filter_layout.addWidget(self.search_weapon_button)
        bottom_right_layout.addLayout(self.weapon_filter_layout)

        # 미사일 타입 콤보박스
        self.weapon_type_combo = QComboBox()
        with open('weapon_systems.json', 'r', encoding='utf-8') as file:
            weapon_types = json.load(file)
        weapon_types_list = [self.tr('전체')] + list(weapon_types.keys())
        # 무기체계 이름들을 콤보박스에 추가
        self.weapon_type_combo.addItems(weapon_types_list)
        self.weapon_type_combo.currentTextChanged.connect(self.load_weapon_assets)
        self.weapon_filter_layout.addWidget(self.weapon_type_combo)

        # 방어반경 표시 체크박스
        self.defense_radius_checkbox = QCheckBox(self.tr("방어반경 표시"))
        self.defense_radius_checkbox.stateChanged.connect(self.toggle_defense_radius)
        self.weapon_filter_layout.addWidget(self.defense_radius_checkbox)

        bottom_right_layout.addLayout(self.weapon_filter_layout)

        # 방어반경 표시 체크박스
        self.dal_select_checkbox = QCheckBox(self.tr("방어자산만 표시"))
        self.dal_select_checkbox.stateChanged.connect(self.load_weapon_assets)
        bottom_right_layout.addWidget(self.dal_select_checkbox)

        self.weapon_assets_table = MyTableWidget()
        self.weapon_assets_table.setColumnCount(5)  # 체크박스 열 추가
        self.weapon_assets_table.setHorizontalHeaderLabels(
            ["", self.tr("구성군"), self.tr("지역"), self.tr("자산명"), self.tr("무기체계")])
        # 행 번호 숨기기
        self.weapon_assets_table.verticalHeader().setVisible(False)
        font = QFont("강한공군체", 13)
        font.setBold(True)
        self.weapon_assets_table.horizontalHeader().setFont(font)
        header = self.weapon_assets_table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
        header.resizeSection(0, 40)
        # 헤더 텍스트 중앙 정렬
        for column in range(header.count()):
            item = self.weapon_assets_table.horizontalHeaderItem(column)
            if item:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        # 나머지 열들이 남은 공간을 채우도록 설정
        for column in range(1, header.count()):
            self.weapon_assets_table.horizontalHeader().setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeMode.Stretch)

        bottom_right_layout.addWidget(self.weapon_assets_table)

        # 중앙 위젯 (지도)
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)

        # 시뮬레이션 버튼 레이아웃
        simulate_button_layout = QHBoxLayout()
        simulate_button_layout.setSpacing(20)
        simulate_button_layout.setContentsMargins(0, 20, 0, 20)
        simulate_button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 미사일 궤적 분석 버튼
        self.analyze_trajectories_button = QPushButton(self.tr("미사일 궤적분석"))
        self.analyze_trajectories_button.setFont(QFont("강한공군체", 12, QFont.Weight.Bold))
        self.analyze_trajectories_button.setFixedSize(200, 30)
        self.analyze_trajectories_button.setStyleSheet("QPushButton { text-align: center; }")
        self.analyze_trajectories_button.clicked.connect(self.run_trajectory_analysis)
        simulate_button_layout.addWidget(self.analyze_trajectories_button)

        # 최적 방어포대 위치 산출 버튼
        self.optimize_locations_button = QPushButton(self.tr("최적 방어포대 위치산출"))
        self.optimize_locations_button.setFont(QFont("강한공군체", 12, QFont.Weight.Bold))
        self.optimize_locations_button.setFixedSize(200, 30)
        self.optimize_locations_button.setStyleSheet("QPushButton { text-align: center; }")
        self.optimize_locations_button.clicked.connect(self.run_location_optimization)
        simulate_button_layout.addWidget(self.optimize_locations_button)

        # 초기화 버튼 추가
        self.reset_button = QPushButton(self.tr("초기화"))
        self.reset_button.setFont(QFont("강한공군체", 12, QFont.Weight.Bold))
        self.reset_button.setFixedSize(100, 30)
        self.reset_button.setStyleSheet("QPushButton { text-align: center; }")
        self.reset_button.clicked.connect(self.reset_simulation)
        simulate_button_layout.addWidget(self.reset_button)

        center_layout.addLayout(simulate_button_layout)

        # 방어반경 표시 체크박스와 지도 출력 버튼을 위한 수평 레이아웃
        print_button_layout = QHBoxLayout()
        # 지도 출력 버튼
        self.print_button = QPushButton(self.tr("지도 출력"), self)
        self.print_button.setFont(QFont("강한공군체", 12, QFont.Weight.Bold))
        self.print_button.setFixedSize(130, 30)
        self.print_button.setStyleSheet("QPushButton { text-align: center; }")
        self.print_button.clicked.connect(self.print_map)
        print_button_layout.addWidget(self.print_button, alignment=Qt.AlignmentFlag.AlignRight)
        # 수평 레이아웃을 center_layout에 추가
        center_layout.addLayout(print_button_layout)

        center_top_widget = QWidget()
        center_top_layout = QVBoxLayout(center_top_widget)
        self.map_view = QWebEngineView()  # 지도 표시용 웹뷰
        center_top_layout.addWidget(self.map_view)
        center_top_layout.setSpacing(0)
        center_top_layout.setContentsMargins(0, 0, 0, 0)

        # 3D 그래프와 테이블을 평행하게 배치하기 위한 수평 레이아웃
        center_bottom_layout = QHBoxLayout()

        # 3D 그래프 위젯
        center_bottom_left_widget = QWidget()
        center_bottom_left_layout = QVBoxLayout(center_bottom_left_widget)
        center_bottom_left_layout.addWidget(self.canvas)
        center_bottom_left_layout.setSpacing(0)
        center_bottom_left_layout.setContentsMargins(0, 0, 0, 0)

        # 테이블 위젯
        center_bottom_right_widget = QWidget()
        center_bottom_right_layout = QVBoxLayout(center_bottom_right_widget)

        # 결과 테이블 위에 출력 버튼 추가
        result_table_layout = QVBoxLayout()
        result_table_layout.setSpacing(0)
        result_table_layout.setContentsMargins(0, 0, 0, 0)

        print_button_layout = QHBoxLayout()
        print_button_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.print_button = QPushButton(self.tr("결과 테이블 출력"), self)
        self.print_button.setFont(QFont("강한공군체", 12, QFont.Weight.Bold))
        self.print_button.setFixedSize(150, 30)
        self.print_button.setStyleSheet("QPushButton { text-align: center; }")
        self.print_button.clicked.connect(self.print_result_table)
        print_button_layout.addWidget(self.print_button)

        self.result_table = QTableWidget()
        self.result_table.setRowCount(0)
        self.result_table.setColumnCount(0)

        result_table_layout.addLayout(print_button_layout)
        result_table_layout.addWidget(self.result_table)

        center_bottom_right_layout.addLayout(result_table_layout)

        # 3D 그래프와 테이블을 수평 레이아웃에 추가
        center_bottom_layout.addWidget(center_bottom_left_widget)
        center_bottom_layout.addWidget(center_bottom_right_widget)

        # QSplitter를 사용하여 위젯들을 배치하고 크기 조절 가능하게 함
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(center_top_widget)

        # 하단 위젯 (3D 그래프와 테이블)
        center_bottom_widget = QWidget()
        center_bottom_layout = QHBoxLayout(center_bottom_widget)

        # 3D 그래프와 테이블 사이의 QSplitter 추가
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        bottom_splitter.addWidget(center_bottom_left_widget)
        bottom_splitter.addWidget(center_bottom_right_widget)
        center_bottom_layout.addWidget(bottom_splitter)

        splitter.addWidget(center_bottom_widget)

        center_layout.addWidget(splitter)

        # 초기 크기 설정
        self.map_view.setMinimumSize(600, 400)
        self.canvas.setMinimumSize(400, 300)
        self.result_table.setMinimumSize(400, 300)

        # 스플리터 초기 비율 설정
        splitter.setSizes([600, 400])  # 지도와 하단 위젯의 비율
        bottom_splitter.setSizes([400, 400])  # 3D 그래프와 테이블의 비율

        # 3D 그래프 여백 최소화
        self.ax.margins(x=0.02, y=0.02)
        self.ax.set_box_aspect((1, 1, 0.5))  # 그래프 비율 조정
        self.figure.tight_layout()  # 그래프 레이아웃 최적화

        # Splitter에 위젯 추가 및 레이아웃 설정
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.addWidget(top_right_widget)
        right_splitter.addWidget(bottom_right_widget)

        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(center_widget)
        main_splitter.addWidget(right_splitter)

        main_layout.addWidget(main_splitter)

        self.setLayout(main_layout)

        # 데이터베이스 연결 및 데이터 로드
        self.load_dataframes()

        with open("missile_info.json", "r", encoding="utf-8") as f:
            self.missile_info = json.load(f)
        with open("weapon_systems.json", "r", encoding="utf-8") as f:
            self.weapon_systems_info = json.load(f)

        self.load_assets()
        self.load_enemy_missile_sites()
        self.load_weapon_assets()
        # 초기 지도 표시 (필요에 따라 수정)
        self.update_map_with_trajectories()

    # 초기화 메서드 추가
    def reset_simulation(self):
        """시뮬레이션 상태를 초기화하는 메서드"""
        reply = QMessageBox.question(self,
                                     self.tr("초기화 확인"),
                                     self.tr("시뮬레이션을 초기화하시겠습니까?"),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # 데이터 초기화
                self.trajectories = []
                self.defense_trajectories = []
                self.engagement_zones = {}
                self.optimized_locations = []

                # 테이블 초기화
                self.assets_table.uncheckAllRows()
                self.enemy_sites_table.uncheckAllRows()
                self.weapon_assets_table.uncheckAllRows()

                # 필터 초기화
                self.unit_filter.setCurrentIndex(0)
                self.missile_type_combo.setCurrentIndex(0)
                self.weapon_type_combo.setCurrentIndex(0)
                self.search_filter.clear()
                self.search_enemy_filter.clear()
                self.search_weapon_filter.clear()

                # 체크박스 초기화
                self.threat_radius_checkbox.setChecked(False)
                self.defense_radius_checkbox.setChecked(False)
                self.dal_select_checkbox.setChecked(False)

                # 결과 테이블 초기화
                self.result_table.clear()
                self.result_table.setRowCount(0)
                self.result_table.setColumnCount(0)

                # 데이터 다시 로드
                self.load_dataframes()
                self.load_assets()
                self.load_enemy_missile_sites()
                self.load_weapon_assets()

                # 지도 및 그래프 초기화
                self.update_map_with_trajectories()
                self.update_3d_graph()

                QMessageBox.information(self,
                                        self.tr("초기화 완료"),
                                        self.tr("시뮬레이션이 성공적으로 초기화되었습니다."))

            except Exception as e:
                QMessageBox.critical(self,
                                     self.tr("초기화 오류"),
                                     self.tr(f"초기화 중 오류가 발생했습니다: {str(e)}"))

    def toggle_defense_radius(self, state):
        self.show_defense_radius = state == Qt.CheckState.Checked.value
        self.update_map_with_trajectories()

    def toggle_threat_radius(self, state):
        self.show_threat_radius = state == Qt.CheckState.Checked.value
        self.update_map_with_trajectories()

    def load_assets(self):
        filtered_df = self.cal_df_ko if self.parent.selected_language == 'ko' else self.cal_df_en

        unit_filter_text = self.unit_filter.currentText()
        if unit_filter_text != self.tr("전체"):
            filtered_df = filtered_df[filtered_df['unit'] == unit_filter_text]

        search_filter_text = self.search_filter.text()
        if search_filter_text:
            filtered_df = filtered_df[
                (filtered_df['target_asset'].str.contains(search_filter_text, case=False)) |
                (filtered_df['area'].str.contains(search_filter_text, case=False))
            ]

        filtered_df = filtered_df.sort_values('priority')

        self.assets_table.uncheckAllRows()
        self.assets_table.setRowCount(len(filtered_df))
        for row, (_, asset) in enumerate(filtered_df.iterrows()):
            checkbox = CenteredCheckBox()
            self.assets_table.setCellWidget(row, 0, checkbox)
            checkbox.checkbox.stateChanged.connect(self.update_map_with_trajectories)
            for col, value in enumerate(asset[['priority', 'unit', 'area', 'target_asset']], start=1):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.assets_table.setItem(row, col, item)
        self.update_map_with_trajectories()

    def load_enemy_missile_sites(self):
        filtered_df = self.enemy_bases_df_ko if self.parent.selected_language == 'ko' else self.enemy_bases_df_en

        search_filter_text = self.search_enemy_filter.text()
        if search_filter_text:
            filtered_df = filtered_df[
                (filtered_df['base_name'].str.contains(search_filter_text, case=False)) |
                (filtered_df['area'].str.contains(search_filter_text, case=False)) |
                (filtered_df['weapon_system'].str.contains(search_filter_text, case=False))
            ]

        missile_filter_text = self.missile_type_combo.currentText()
        if missile_filter_text != self.tr("전체"):
            filtered_df = filtered_df[
                filtered_df['weapon_system'].apply(lambda x: missile_filter_text in x.split(', '))]

        self.enemy_sites_table.uncheckAllRows()
        self.enemy_sites_table.setRowCount(len(filtered_df))
        for row, (_, base) in enumerate(filtered_df.iterrows()):
            checkbox = CenteredCheckBox()
            self.enemy_sites_table.setCellWidget(row, 0, checkbox)
            checkbox.checkbox.stateChanged.connect(self.update_map_with_trajectories)
            for col, value in enumerate(base[['base_name', 'coordinate', 'weapon_system']], start=1):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.enemy_sites_table.setItem(row, col, item)
        self.update_map_with_trajectories()

    def load_weapon_assets(self):
        # 테이블 초기화
        weapon_assets_df = self.weapon_assets_df_ko if self.parent.selected_language == 'ko' else self.weapon_assets_df_en
        # 필터링 추가
        search_filter_text = self.search_weapon_filter.text()
        if self.dal_select_checkbox.isChecked():
            weapon_assets_df = weapon_assets_df[weapon_assets_df['dal_select'] == 1]
        if search_filter_text:
            weapon_assets_df = weapon_assets_df[
                (weapon_assets_df['asset_name'].str.contains(search_filter_text, case=False)) |
                (weapon_assets_df['area'].str.contains(search_filter_text, case=False)) |
                (weapon_assets_df['unit'].str.contains(search_filter_text, case=False))
                ]
        weapon_type_filter_text = self.weapon_type_combo.currentText()
        if weapon_type_filter_text != self.tr("전체"):
            weapon_assets_df = weapon_assets_df[weapon_assets_df['weapon_system'] == weapon_type_filter_text]
        self.weapon_assets_table.uncheckAllRows()
        self.weapon_assets_table.setRowCount(len(weapon_assets_df))
        for row, (_, weapons) in enumerate(weapon_assets_df.iterrows()):
            checkbox = CenteredCheckBox()
            self.weapon_assets_table.setCellWidget(row, 0, checkbox)
            checkbox.checkbox.stateChanged.connect(self.update_map_with_trajectories)
            for col, value in enumerate(weapons[['unit', 'area', 'asset_name', 'weapon_system']], start=1):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.weapon_assets_table.setItem(row, col, item)
        self.update_map_with_trajectories()

    def run_trajectory_analysis(self):
        try:
            # 진행 상태 다이얼로그 생성
            progress = QProgressDialog(self.tr("미사일 궤적 분석 중..."), None, 0, 100, self)
            progress.setWindowTitle(self.tr("미사일 궤도 분석"))
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setAutoClose(True)
            progress.setMinimumDuration(0)
            progress.setValue(0)

            # 궤적 계산
            progress.setValue(20)
            self.calculate_trajectories()

            if not hasattr(self, 'trajectories') or len(self.trajectories) == 0:
                progress.setValue(100)
                self.update_map_with_trajectories()
                return

            # 고유한 방어 가능 궤적 계산
            progress.setValue(40)
            total_trajectories = len(self.trajectories)
            unique_defensible_trajectories = set()
            for defense_trajectory in self.defense_trajectories:
                base_lat, base_lon = defense_trajectory['base_coordinate']
                target_lat, target_lon = defense_trajectory['target_coordinate']
                trajectory_key = (base_lat, base_lon, target_lat, target_lon)
                unique_defensible_trajectories.add(trajectory_key)

            defensible_trajectories = len(unique_defensible_trajectories)
            defense_rate = (defensible_trajectories / total_trajectories) * 100 if total_trajectories > 0 else 0

            # 지도 및 결과 테이블 업데이트
            progress.setValue(70)
            self.update_map_with_trajectories()
            progress.setValue(90)
            self.update_result_table_for_analysis(total_trajectories, defensible_trajectories, defense_rate)

            # 완료
            progress.setValue(100)
            QMessageBox.information(self, self.tr("완료"), self.tr("미사일 궤적 분석이 완료되었습니다."))

        except Exception as e:
            QMessageBox.critical(self, self.tr("오류"), self.tr(f"미사일 궤적 분석 오류: {e}"))

    def calculate_trajectories(self):
        try:
            selected_enemy_weapons = self.get_selected_enemy_weapons()
            selected_weapon_assets = self.get_selected_weapon_assets()
            selected_assets = self.get_selected_assets()

            if not selected_enemy_weapons or not selected_assets:
                return

            self.trajectories = []
            self.defense_trajectories = []

            # 모든 궤적 계산을 한 번에 수행
            all_trajectories = []
            for base_name, missile_lat_lon, enemy_weapon in selected_enemy_weapons:
                missile_lat, missile_lon = self.parse_coordinates(missile_lat_lon)
                for target_name, target_lat_lon, dal_select, priority in selected_assets:
                    target_lat, target_lon = self.parse_coordinates(target_lat_lon)
                    distance = self.trajectory_calculator.calculate_distance(missile_lat, missile_lon, target_lat,
                                                                             target_lon)
                    missile_types = self.determine_missile_type(distance, base_name)

                    if missile_types and enemy_weapon in missile_types:
                        trajectory = self.calculate_trajectory((missile_lat, missile_lon), (target_lat, target_lon),
                                                               enemy_weapon)
                        if trajectory:
                            all_trajectories.append({
                                'base_name': base_name,
                                'base_coordinate': (missile_lat, missile_lon),
                                'target_name': target_name,
                                'target_coordinate': (target_lat, target_lon),
                                'missile_type': enemy_weapon,
                                'trajectory': trajectory,
                                'priority' : priority
                            })

            self.trajectories = all_trajectories

            if selected_weapon_assets:
                # 방어 자산에 대한 벡터화된 계산
                defense_assets = np.array([(self.parse_coordinates(defense_lat_lon), weapon_type, int(threat_degree))
                                           for _, _, _, defense_lat_lon, weapon_type, _, threat_degree, _ in
                                           selected_weapon_assets], dtype=object)

                defense_lats = np.array([coord[0] for coord, _, _ in defense_assets])
                defense_lons = np.array([coord[1] for coord, _, _ in defense_assets])
                weapon_types = np.array([weapon for _, weapon, _ in defense_assets])
                threat_azimuths = np.array([threat for _, _, threat in defense_assets])

                trajectories_list = [t['trajectory'] for t in all_trajectories]

                for i, (defense_lat, defense_lon, weapon_type, threat_azimuth) in enumerate(
                        zip(defense_lats, defense_lons, weapon_types, threat_azimuths)):
                    engagement_possible = self.engagement_calculator.check_engagement_possibility_vectorized(
                        defense_lat, defense_lon, weapon_type, trajectories_list, threat_azimuth)

                    for j, is_possible in enumerate(engagement_possible):
                        if is_possible:
                            trajectory = all_trajectories[j]
                            defense_result = {
                                'base_name': trajectory['base_name'],
                                'base_coordinate': trajectory['base_coordinate'],
                                'target_name': trajectory['target_name'],
                                'target_coordinate': trajectory['target_coordinate'],
                                'defense_name': selected_weapon_assets[i][2],
                                'defense_coordinate': (defense_lat, defense_lon),
                                'weapon_type': weapon_type,
                                'missile_type': trajectory['missile_type'],
                                'threat_azimuth': threat_azimuth,
                                'trajectory': trajectory['trajectory'],
                            }
                            self.defense_trajectories.append(defense_result)


        except Exception as e:
            import traceback
            error_msg = f"궤적 계산 중 오류 발생: {str(e)}\n{traceback.format_exc()}"
            QMessageBox.critical(self, self.tr("에러"), self.tr(error_msg))

    def is_trajectory_defended(self, points):
        for defense_tr_dic in self.defense_trajectories:
            defense_points = [(float(lat), float(lon)) for lat, lon, _ in defense_tr_dic['trajectory']]
            if self.is_same_trajectory(points, defense_points):
                return True
        return False

    def is_trajectory_defended_with_alt(self, points):
        for defense_tr_dic in self.defense_trajectories:
            defense_points = [(float(lat), float(lon), float(alt)) for lat, lon, alt in defense_tr_dic['trajectory']]
            if self.is_same_trajectory(points, defense_points):
                return True
        return False

    def calculate_trajectory(self, missile_base, target, missile_type):
        """미사일 궤적을 계산하는 메서드 (MissileTrajectoryCalculator 사용)"""
        try:
            return self.trajectory_calculator.calculate_trajectory(missile_base, target, missile_type)
        except Exception as e:
            print(f"Error calculating trajectory: {e}")
            return None

    def update_map_with_trajectories(self):
        """미사일 궤적 및 방어 궤적을 지도에 표시하는 메서드"""
        try:
            # 맵 생성 전 이전 객체 정리
            if hasattr(self, 'map'):
                del self.map
            gc.collect()

            self.map = folium.Map(
                location=[self.parent.map_app.loadSettings()['latitude'],
                          self.parent.map_app.loadSettings()['longitude']],
                zoom_start=self.parent.map_app.loadSettings()['zoom'],
                tiles=self.parent.map_app.loadSettings()['style'],
                prefer_canvas=True
            )

            trajectory_group = folium.FeatureGroup(name="Trajectories", show=True)
            defense_group = folium.FeatureGroup(name="Defense", show=True)

            self._add_assets_to_map(self.map)

            BATCH_SIZE = 100  # 배치 크기 감소
            MAX_TRAJECTORIES = 500  # 최대 궤적 수 감소

            if hasattr(self, 'trajectories'):
                # 전체 데이터 수 제한
                trajectories = self.trajectories[:MAX_TRAJECTORIES] if len(
                    self.trajectories) > MAX_TRAJECTORIES else self.trajectories
                trajectories_batches = [trajectories[i:i + BATCH_SIZE]
                                        for i in range(0, len(trajectories), BATCH_SIZE)]
                # 메모리 관리를 위한 가비지 컬렉션 추가
                gc.collect()

                with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
                    futures = []
                    for batch in trajectories_batches:
                        future = executor.submit(self._process_trajectory_batch, batch,
                                                 trajectory_group, defense_group)
                        futures.append(future)
                    concurrent.futures.wait(futures)

            # 지도에 궤적을 그룹으로 추가
            self.map.add_child(trajectory_group)
            self.map.add_child(defense_group)
            folium.LayerControl().add_to(self.map)
            gc.collect()

            data = io.BytesIO()
            self.map.save(data, close_file=False)
            html_content = data.getvalue().decode()

            QtCore.QTimer.singleShot(50, lambda: self._update_webview(html_content))

        except Exception as e:
            print(f"지도 업데이트 중 오류 발생: {str(e)}")

    def _add_assets_to_map(self, map_obj):
        """자산 정보를 지도에 추가하는 헬퍼 메서드"""
        selected_assets = self.get_selected_assets()
        if selected_assets:
            SimulationCalMapView(selected_assets, map_obj)

        selected_defense_assets = self.get_selected_weapon_assets()
        if selected_defense_assets:
            SimulationWeaponMapView(selected_defense_assets, map_obj, self.show_defense_radius)

        selected_enemy_bases = self.get_selected_enemy_bases()
        if selected_enemy_bases:
            SimulationEnemyBaseMapView(selected_enemy_bases, map_obj)

        selected_enemy_weapons = self.get_selected_enemy_weapons()
        if selected_enemy_weapons:
            SimulationEnemyWeaponMapView(selected_enemy_weapons, map_obj, self.show_threat_radius)

    def _process_trajectory_batch(self, batch, trajectory_group, defense_group):
        """궤적 배치를 처리하는 헬퍼 메서드"""
        try:
            for trajectory_data in batch:
                trajectory = trajectory_data['trajectory']
                points = [(float(np.asarray(lat).item()), float(np.asarray(lon).item()))
                          for lat, lon, _ in trajectory]

                is_defended = self.is_trajectory_defended(points)
                color = "green" if is_defended else "red"

                # 궤적을 단순화하여 직선으로 표현
                simplified_points = self._simplify_trajectory(points)

                folium.PolyLine(
                    locations=simplified_points,
                    color=color,
                    weight=0.5,  # 선 두께 감소
                    opacity=0.5,  # 투명도 증가
                    smooth_factor=3,  # 스무딩 팩터 증가
                    no_clip=True  # 클리핑 비활성화로 렌더링 성능 향상
                ).add_to(trajectory_group)

                if is_defended:
                    self._process_defense_trajectories_optimized(points, trajectory, defense_group)
        except Exception as e:
            print(f"궤적 처리 중 오류 발생: {str(e)}")

    def _simplify_trajectory(self, points, tolerance=3):
        """궤적을 가속화하기 위해 점을 단순화하는 메서드"""
        if len(points) <= 2:  # 최소 두 개의 점을 가져야 함
            return points

        # 데이터 포인트 수를 더 적극적으로 줄임
        max_points = 10  # 최대 포인트 수 제한
        if len(points) > max_points:
            step = len(points) // max_points
            points = points[::step]

        simplified_points = [points[0]]
        for point in points[1:-1]:
            if self._calculate_distance(simplified_points[-1], point) > tolerance:
                simplified_points.append(point)
        simplified_points.append(points[-1])

        return simplified_points

    @staticmethod
    def _calculate_distance(point1, point2):
        """두 점 간의 거리 계산"""
        return ((point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2) ** 0.5

    def _process_defense_trajectories_optimized(self, points, trajectory, defense_group):
        """방어 궤적을 처리하는 최적화된 헬퍼 메서드"""
        """최적화된 방어 궤적 처리 메서드"""
        for defense_tr_dic in self.defense_trajectories:
            if self.is_same_trajectory(points, [(float(lat), float(lon))
                                        for lat, lon, _ in defense_tr_dic['trajectory']]):
                defense_coordinate = defense_tr_dic['defense_coordinate']
                intercept_point = self.engagement_calculator.find_intercept_point_vectorized(
                    defense_coordinate[0],
                    defense_coordinate[1],
                    trajectory,
                    defense_tr_dic['weapon_type'],
                    defense_tr_dic['threat_azimuth']
                )

                if intercept_point:
                    intercept = self.tr('요격지점')
                    folium.Marker(
                        location=intercept_point[:2],
                        icon=folium.DivIcon(html=f"""
                            <div style="font-size: 11px; color: blue; 
                            text-shadow: 1px 1px 1px white;">X</div>"""),
                        popup=folium.Popup(f"{intercept}: ({intercept_point[0]:.5f}, {intercept_point[1]:.5f})", max_width=200)
                    ).add_to(defense_group)

                    folium.PolyLine(
                        locations=[defense_coordinate, intercept_point[:2]],
                        color="blue",
                        weight=0.5,  # 선 두께 감소
                        opacity=0.5,  # 투명도 증가
                        smooth_factor=3,  # 스무딩 팩터 증가
                        no_clip=True,  # 클리핑 비활성화로 렌더링 성능 향상
                        dash_array='4, 4'
                    ).add_to(defense_group)

    def _update_webview(self, html_content):
        """웹뷰 업데이트를 위한 헬퍼 메서드"""
        try:
            self.map_view.setHtml(html_content)
            self.map_view.update()
            self.update_3d_graph()
        except Exception as e:
            print(f"웹뷰 업데이트 중 오류 발생: {str(e)}")

    def update_result_table_for_analysis(self, total_trajectories=None, defensible_trajectories=None,
                                         defense_rate=None):
        self.result_table.clear()  # 기존 데이터 초기화
        self.result_table.setRowCount(0)  # 행 초기화

        if total_trajectories is not None:
            # 궤적 분석 결과 업데이트
            self.result_table.setColumnCount(3)
            self.result_table.setHorizontalHeaderLabels([self.tr("총 미사일 궤적"), self.tr("방어 가능 궤적"), self.tr("방어율")])
            self.result_table.insertRow(0)

            # 중앙 정렬을 위한 아이템 설정
            item1 = QTableWidgetItem(str(total_trajectories))
            item1.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.result_table.setItem(0, 0, item1)

            item2 = QTableWidgetItem(str(defensible_trajectories))
            item2.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.result_table.setItem(0, 1, item2)

            item3 = QTableWidgetItem(f"{defense_rate:.2f}%")
            item3.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.result_table.setItem(0, 2, item3)

        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.result_table.verticalHeader().setVisible(False)

    def update_3d_graph(self):
        self.ax.clear()
        self.ax.set_xlabel('Longitude')
        self.ax.set_ylabel('Latitude')
        self.ax.set_zlabel('Altitude')

        # 선택된 자산, 방어 자산, 적 기지 표시
        for asset in self.get_selected_assets():
            lat, lon = self.parse_coordinates(asset[1])
            self.ax.scatter(lon, lat, 0, c='blue', marker='o')

        for defense_asset in self.get_selected_weapon_assets():
            lat, lon = self.parse_coordinates(defense_asset[3])
            self.ax.scatter(lon, lat, 0, c='green', marker='s')

        for enemy_base in self.get_selected_enemy_bases():
            lat, lon = self.parse_coordinates(enemy_base[1])
            self.ax.scatter(lon, lat, 0, c='red', marker='^')

        # 미사일 궤적 및 방어 궤적 표시
        if hasattr(self, 'trajectories') and self.trajectories:
            all_lats = []
            all_lons = []
            all_alts = []

            for trajectory_data in self.trajectories:
                trajectory = trajectory_data['trajectory']
                longitudes = [float(point[1]) for point in trajectory]
                latitudes = [float(point[0]) for point in trajectory]
                altitudes = [float(point[2]) for point in trajectory]

                all_lats.extend(latitudes)
                all_lons.extend(longitudes)
                all_alts.extend(altitudes)

                # 모든 궤적을 표시하되, 방어 여부에 따라 색상만 다르게 지정
                points = list(zip(latitudes, longitudes, altitudes))
                is_defended = self.is_trajectory_defended_with_alt(points)
                color = "green" if is_defended else "red"

                # 궤적을 단순화하여 표시
                simplified_points = self._simplify_trajectory_for_3d(points)
                simplified_lats = [point[0] for point in simplified_points]
                simplified_lons = [point[1] for point in simplified_points]
                simplified_alts = [point[2] for point in simplified_points]

                self.ax.plot(simplified_lons, simplified_lats, simplified_alts, color=color, linewidth=0.5, alpha=0.8)

                if is_defended:
                    for defense_tr_dic in self.defense_trajectories:
                        defense_points = [(float(lat), float(lon), float(alt)) for lat, lon, alt in
                                          defense_tr_dic['trajectory']]
                        if self.is_same_trajectory(points, defense_points):
                            defense_coordinate = defense_tr_dic['defense_coordinate']
                            weapon_type = defense_tr_dic['weapon_type']
                            threat_azimuth = defense_tr_dic['threat_azimuth']
                            intercept_point = self.engagement_calculator.find_intercept_point_vectorized(
                                defense_coordinate[0],
                                defense_coordinate[1],
                                trajectory,
                                weapon_type,
                                threat_azimuth)
                            if intercept_point:
                                defense_lon, defense_lat = defense_coordinate[1], defense_coordinate[0]
                                intercept_lat, intercept_lon, intercept_alt = intercept_point
                                self.ax.plot([defense_lon, intercept_lon],
                                             [defense_lat, intercept_lat],
                                             [0, intercept_alt],
                                             color="blue", linewidth=0.4, alpha=0.6)
                                self.ax.scatter(intercept_lon, intercept_lat, intercept_alt,
                                                color="blue", marker='x', s=12)

        self.canvas.draw()

    def _simplify_trajectory_for_3d(self, points, tolerance=0.3):
        """궤적을 가속화하기 위해 점을 단순화하는 메서드"""
        if len(points) <= 2:  # 최소 두 개의 점을 가져야 함
            return points

        simplified_points = [points[0]]
        for point in points[1:-1]:
            if self._calculate_distance(simplified_points[-1], point) > tolerance:
                simplified_points.append(point)
        simplified_points.append(points[-1])

        return simplified_points

    def determine_missile_type(self, distance, base_name):
        """거리와 기지명에 따라 미사일 종류를 결정하는 메서드"""
        available_missiles = []

        # 현재 선택된 언어에 따라 적절한 DataFrame 선택
        df = self.enemy_bases_df_ko if self.parent.selected_language == 'ko' else self.enemy_bases_df_en

        # 해당 기지의 무기 시스템 정보 가져오기
        base_info = df[df['base_name'] == base_name]

        if not base_info.empty:
            weapons = base_info.iloc[0]['weapon_system'].split(', ')

            for missile_type, info in self.missile_info.items():
                if missile_type in weapons and int(info["min_radius"]) <= distance <= int(info["max_radius"]):
                    available_missiles.append(missile_type)

        if available_missiles:
            return available_missiles
        else:
            return None

    def run_location_optimization(self):
        try:
            # optimization_thread가 실제로 실행 중인지 확인
            if (hasattr(self, 'optimization_thread') and self.optimization_thread.isRunning() and
                    hasattr(self,'optimization_worker') and self.optimization_worker.is_running):
                return

            self.optimized_locations = []
            self.trajectories = []
            self.defense_trajectories = []
            self.calculate_trajectories_for_optimization()
            selected_weapon_assets = self.get_selected_weapon_assets()

            if not selected_weapon_assets:
                raise ValueError(self.tr("선택된 방어 자산이 없습니다."))

            self.optimizer = MissileDefenseOptimizer(
                self.trajectories,
                self.weapon_systems_info,
                grid_bounds=(
                    (self.parent.map_app.loadSettings()['lat_min'], self.parent.map_app.loadSettings()['lat_max']),
                    (self.parent.map_app.loadSettings()['lon_min'], self.parent.map_app.loadSettings()['lon_max'])),
                engagement_calculator=self.engagement_calculator
            )

            # 기존 스레드/워커 정리
            if hasattr(self, 'optimization_worker'):
                self.optimization_worker.stop()
                self.optimization_worker.deleteLater()
            if hasattr(self, 'optimization_thread'):
                self.optimization_thread.quit()
                self.optimization_thread.wait()
                self.optimization_thread.deleteLater()

            # 새 스레드/워커 생성
            self.optimization_thread = QThread()
            self.optimization_worker = OptimizationWorker(
                self.optimizer,
                selected_weapon_assets
            )
            self.optimization_worker._is_running = True

            # 프로그레스 다이얼로그 설정 부분만 수정
            self.progress_dialog = QDialog(self)
            self.progress_dialog.setWindowTitle(self.tr("최적화 진행 상황"))
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)

            layout = QVBoxLayout()

            # 전체 진행률 표시
            total_label = QLabel(self.tr("현재 시도 진행률:"))
            self.total_progress_bar = QProgressBar()
            self.total_progress_bar.setRange(0, 100)

            # 현재 반복 진행률 표시
            iteration_label = QLabel(self.tr("전체 진행률:"))
            self.iteration_progress_bar = QProgressBar()
            self.iteration_progress_bar.setRange(0, 100)

            # 취소 버튼
            cancel_button = QPushButton(self.tr("취소"))
            cancel_button.setFont(QFont("강한공군체", 12, QFont.Weight.Bold))
            cancel_button.setFixedSize(100, 30)
            cancel_button.setStyleSheet("QPushButton { text-align: center; }")
            cancel_button.clicked.connect(self.cancel_optimization)

            layout.addWidget(total_label)
            layout.addWidget(self.total_progress_bar)
            layout.addWidget(iteration_label)
            layout.addWidget(self.iteration_progress_bar)
            layout.addWidget(cancel_button)

            self.progress_dialog.setLayout(layout)


            # run_location_optimization 메서드 내의 시그널 연결 부분을 다음과 같이 수정
            # 워커를 스레드로 이동하기 전에 시그널 연결
            self.optimization_worker.finished.connect(self._on_optimization_complete)
            self.optimization_worker.error.connect(self._on_optimization_error)
            self.optimization_worker.progress.connect(self._update_total_progress)
            self.optimization_worker.iteration_progress.connect(self._update_iteration_progress)
            self.optimization_worker.moveToThread(self.optimization_thread)
            self.optimization_thread.started.connect(self.optimization_worker.run)
            self.optimization_thread.finished.connect(self.cleanup_optimization)

            self.progress_dialog.show()
            self.optimization_thread.start()

        except Exception as e:
            if hasattr(self, 'progress_dialog'):
                self.progress_dialog.close()
            QMessageBox.critical(self, self.tr("오류"),
                                 self.tr(f"최적화 실행 중 오류 발생: {str(e)}"))

    def _update_total_progress(self, progress):
        if hasattr(self, 'progress_dialog') and self.progress_dialog.isVisible():
            progress = min(progress, 100)
            self.total_progress_bar.setValue(progress)

    def _update_iteration_progress(self, attempt, progress):
        if hasattr(self, 'progress_dialog') and self.progress_dialog.isVisible():
            self.iteration_progress_bar.setValue(progress//10)

    def _on_optimization_complete(self, optimized_locations):
        try:
            # 결과 처리를 먼저 수행
            self.handle_optimization_complete(optimized_locations)

            if hasattr(self, 'progress_dialog') and self.progress_dialog.isVisible():
                self.progress_dialog.close()

            # 최적화 관련 객체들 정리
            if hasattr(self, 'optimization_worker'):
                self.optimization_worker.stop()
                self.optimization_worker._is_running = False
                self.optimization_worker.moveToThread(QApplication.instance().thread())

            if hasattr(self, 'optimization_thread'):
                self.optimization_thread.quit()
                if not self.optimization_thread.wait(5000):  # 5초 타임아웃
                    self.optimization_thread.terminate()
                    self.optimization_thread.wait()

            # 객체 삭제 전에 참조 저장
            worker = self.optimization_worker if hasattr(self, 'optimization_worker') else None
            thread = self.optimization_thread if hasattr(self, 'optimization_thread') else None

            # 참조 제거
            if hasattr(self, 'optimization_worker'):
                delattr(self, 'optimization_worker')
            if hasattr(self, 'optimization_thread'):
                delattr(self, 'optimization_thread')

            # 객체 삭제
            if worker:
                worker.deleteLater()
            if thread:
                thread.deleteLater()

        except Exception as e:
            QMessageBox.critical(self, self.tr("오류"),
                                 self.tr(f"최적화 완료 처리 중 오류 발생: {str(e)}"))

    def cleanup_optimization(self):
        try:
            if hasattr(self, 'progress_dialog') and self.progress_dialog.isVisible():
                self.progress_dialog.close()

            if hasattr(self, 'optimization_worker'):
                self.optimization_worker.stop()
                self.optimization_worker._is_running = False
                self.optimization_worker.moveToThread(QApplication.instance().thread())

            if hasattr(self, 'optimization_thread'):
                self.optimization_thread.quit()
                if not self.optimization_thread.wait(5000):
                    self.optimization_thread.terminate()
                    self.optimization_thread.wait()

            # 객체 삭제 전에 참조 저장
            worker = self.optimization_worker if hasattr(self, 'optimization_worker') else None
            thread = self.optimization_thread if hasattr(self, 'optimization_thread') else None

            # 참조 제거
            if hasattr(self, 'optimization_worker'):
                delattr(self, 'optimization_worker')
            if hasattr(self, 'optimization_thread'):
                delattr(self, 'optimization_thread')

            # 객체 삭제
            if worker:
                worker.deleteLater()
            if thread:
                thread.deleteLater()

        except Exception as e:
            QMessageBox.critical(self, self.tr("오류"),
                                 self.tr(f"정리 작업 중 오류 발생: {str(e)}"))

    def _on_optimization_error(self, error_message):
        self.progress_dialog.close()
        self.handle_optimization_error(error_message)

    def cancel_optimization(self):
        try:
            reply = QMessageBox.question(self,
                                         self.tr("취소 확인"),
                                         self.tr("최적화를 취소하시겠습니까?"),
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                if hasattr(self, 'optimization_worker'):
                    # 워커 중지 플래그 설정
                    self.optimization_worker.stop()

                if hasattr(self, 'optimizer'):
                    # 최적화 프로세스 즉시 중단
                    self.optimizer.stop_optimization()

                # 스레드 강제 종료
                self.terminate_thread()

                # 메모리 정리 및 리소스 해제
                self._cleanup_optimization_resources()

                # UI 업데이트
                if hasattr(self, 'progress_dialog'):
                    self.progress_dialog.close()

                QMessageBox.information(self, self.tr("취소 완료"),
                                        self.tr("최적화가 성공적으로 취소되었습니다."))

        except Exception as e:
            QMessageBox.critical(self, self.tr("취소 오류"), self.tr(f"최적화 취소 중 오류가 발생했습니다: {str(e)}"))

        finally:
            # 상태 초기화 보장
            self.reset_optimization_state()

    def terminate_thread(self):
        if hasattr(self, 'optimization_thread'):
            self.optimization_thread.requestInterruption()
            self.optimization_thread.quit()
            self.optimization_thread.terminate()
            self.optimization_thread.wait()  # 완전한 종료 대기

    def _cleanup_optimization_resources(self):
        """최적화 관련 리소스 정리를 위한 헬퍼 메서드"""
        if hasattr(self, 'optimization_worker'):
            self.optimization_worker.moveToThread(QApplication.instance().thread())
            self.optimization_worker.deleteLater()
            delattr(self, 'optimization_worker')

        if hasattr(self, 'optimization_thread'):
            self.optimization_thread.deleteLater()
            delattr(self, 'optimization_thread')

    def reset_optimization_state(self):
        """최적화 상태 초기화를 위한 헬퍼 메서드"""
        self.optimized_locations = []
        self.trajectories = []
        self.defense_trajectories = []
        self.engagement_zones = {}

    def handle_optimization_complete(self, optimization_result):
        try:
            # optimization_result가 튜플이며 첫 번째 요소가 위치 목록, 두 번째 요소가 요약 정보
            if not isinstance(optimization_result, tuple) or len(optimization_result) != 2:
                raise ValueError(self.tr("잘못된 최적화 결과 형식입니다"))

            locations, summary = optimization_result
            self.optimized_locations = locations

            # 관련 데이터 업데이트
            self.calculate_trajectories_for_optimization()
            self.update_result_table_for_optimization()
            self.update_map_with_optimized_locations()
            self.update_3d_graph_for_optimization()

            # 요약 정보가 있는 경우에만 표시
            if isinstance(summary, dict):
                self.show_optimization_summary(summary)
            if self.parent.selected_language == 'ko':
                QMessageBox.information(self, "최적화 완료",
                                        f"최적화가 성공적으로 완료되었습니다.\n"
                                        f"총 방어율: {summary.get('best_scores', {}).get('total_defense_rate', 0):.1f}%")
            if self.parent.selected_language == 'en':
                QMessageBox.information(self, "Optimization Complete",
                                        f"Optimization has been successfully completed.\n"
                                        f"Total defense rate: {summary.get('best_scores', {}).get('total_defense_rate', 0):.1f}%")

        except Exception as e:
            QMessageBox.critical(self, self.tr("오류"), self.tr(f"최적화 결과 처리 중 오류가 발생했습니다: {str(e)}"))

    def handle_optimization_error(self, error_message):
        QMessageBox.critical(self, self.tr("오류"), self.tr(f"최적화 중 오류 발생: {error_message}"))

    def calculate_trajectories_for_optimization(self):
        try:
            if self.trajectories is not None:
                selected_enemy_weapons = self.get_selected_enemy_weapons()
                selected_assets = self.get_selected_assets()
                if not selected_enemy_weapons or not selected_assets:
                    return

                self.trajectories = []
                self.defense_trajectories = []

                # 모든 미사일 발사 위치와 목표물 위치를 배열로 준비
                missile_positions = np.array([self.parse_coordinates(weapon[1]) for weapon in selected_enemy_weapons])
                target_positions = np.array([self.parse_coordinates(asset[1]) for asset in selected_assets])

                # 모든 조합의 거리 계산
                distances = self.calculate_distance_vectorized(
                    missile_positions[:, 0][:, np.newaxis],
                    missile_positions[:, 1][:, np.newaxis],
                    target_positions[:, 0],
                    target_positions[:, 1]
                )

                for i, (base_name, _, enemy_weapon) in enumerate(selected_enemy_weapons):
                    for j, (target_name, _, _, priority) in enumerate(selected_assets):
                        distance = distances[i, j]
                        missile_types = self.determine_missile_type(distance, base_name)

                        if missile_types and enemy_weapon in missile_types:
                            trajectory = self.calculate_trajectory(
                                tuple(missile_positions[i]),
                                tuple(target_positions[j]),
                                enemy_weapon
                            )
                            if trajectory:
                                result = {
                                    'base_name': base_name,
                                    'base_coordinate': tuple(missile_positions[i]),
                                    'target_name': target_name,
                                    'target_coordinate': tuple(target_positions[j]),
                                    'missile_type': enemy_weapon,
                                    'trajectory': trajectory,
                                    'priority': priority
                                }
                                self.trajectories.append(result)

                else:
                    if self.optimized_locations:
                        defense_positions = np.array([loc['defense_coordinate'] for loc in self.optimized_locations])
                        weapon_types = [loc['weapon_type'] for loc in self.optimized_locations]
                        threat_azimuths = np.array([int(loc['threat_azimuth']) for loc in self.optimized_locations])

                        trajectories_array = np.array([t['trajectory'] for t in self.trajectories])

                        for i, optimal_location_dic in enumerate(self.optimized_locations):
                            engagement_results = self.engagement_calculator.check_engagement_possibility_vectorized(
                                defense_positions[i][0], defense_positions[i][1],
                                weapon_types[i], trajectories_array, threat_azimuths[i]
                            )

                            # NumPy 배열을 개별 boolean 값으로 처리
                            for j, engagement_possible in enumerate(engagement_results):
                                if engagement_possible.item():  # .item()을 사용하여 스칼라 값으로 변환
                                    trajectory_info = self.trajectories[j]
                                    defense_result = {
                                        'base_name': trajectory_info['base_name'],
                                        'base_coordinate': trajectory_info['base_coordinate'],
                                        'target_name': trajectory_info['target_name'],
                                        'target_coordinate': trajectory_info['target_coordinate'],
                                        'defense_name': optimal_location_dic['defense_name'],
                                        'defense_coordinate': optimal_location_dic['defense_coordinate'],
                                        'weapon_type': optimal_location_dic['weapon_type'],
                                        'missile_type': trajectory_info['missile_type'],
                                        'threat_azimuth': optimal_location_dic['threat_azimuth'],
                                        'trajectory': trajectory_info['trajectory'],
                                    }
                                    self.defense_trajectories.append(defense_result)

        except Exception as e:
            QMessageBox.critical(self, self.tr("에러"), self.tr(f"궤적 계산 중 오류 발생: {str(e)}"))

    def update_result_table_for_optimization(self):
        self.result_table.clear()
        self.result_table.setRowCount(0)
        self.result_table.setColumnCount(6)  # 컬럼 수를 6개로 변경
        self.result_table.setHorizontalHeaderLabels([
            self.tr("최적 위치명"), self.tr("최적 위치 좌표"), self.tr("무기체계"), self.tr("위협 방위각"),
            self.tr("방어 가능 자산(미사일 유형)"), self.tr("방어율")
        ])

        for optimal_location in self.optimized_locations:
            row = self.result_table.rowCount()
            self.result_table.insertRow(row)

            # 방어 가능 자산과 미사일 유형을 결합
            defense_assets_missiles = []
            for dt in self.defense_trajectories:
                if dt['defense_name'] == optimal_location['defense_name']:
                    defense_assets_missiles.append(f"{dt['target_name']}({dt['base_name']}, {dt['missile_type']})")

            for col, value in enumerate([
                str(optimal_location['defense_name']),
                f"{optimal_location['defense_coordinate'][0]:.5f}, {optimal_location['defense_coordinate'][1]:.5f}",
                optimal_location['weapon_type'],
                f"{optimal_location['threat_azimuth']}",
                '\n'.join(defense_assets_missiles),  # 줄바꿈으로 표시
                f"{optimal_location['defense_rate']:.2f}%"
            ]):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.result_table.setItem(row, col, item)
                if col == 4:  # 방어 가능 자산 컬럼의 경우
                    self.result_table.verticalHeader().setSectionResizeMode(row, QHeaderView.ResizeMode.ResizeToContents)

        # 총 방어율 계산 및 추가
        total_trajectories = len(self.trajectories)
        unique_defensible_trajectories = set()
        for defense_trajectory in self.defense_trajectories:
            base_lat, base_lon = defense_trajectory['base_coordinate']
            target_lat, target_lon = defense_trajectory['target_coordinate']
            missile_type = defense_trajectory['missile_type']
            trajectory_key = (base_lat, base_lon, target_lat, target_lon, missile_type)
            unique_defensible_trajectories.add(trajectory_key)

        defensible_trajectories = len(unique_defensible_trajectories)
        defense_rate = (defensible_trajectories / total_trajectories) * 100 if total_trajectories > 0 else 0

        row = self.result_table.rowCount()
        self.result_table.insertRow(row)
        for col, value in enumerate([self.tr("총 방어율"), "", "", "", "", f"{defense_rate:.2f}%"]):
            if value:
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.result_table.setItem(row, col, item)

        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.result_table.verticalHeader().setVisible(False)

    def update_map_with_optimized_locations(self):
        """미사일 궤적, 방어 궤적, 격자, 최적 위치를 지도에 표시하는 메서드"""
        try:
            self.map = folium.Map(
                location=[self.parent.map_app.loadSettings()['latitude'],
                          self.parent.map_app.loadSettings()['longitude']],
                zoom_start=self.parent.map_app.loadSettings()['zoom'],
                tiles=self.parent.map_app.loadSettings()['style'],
                prefer_canvas=True
            )

            # FeatureGroup 생성
            grid_group = folium.FeatureGroup(name="Grid", show=True)
            trajectory_group = folium.FeatureGroup(name="Trajectories", show=True)
            defense_group = folium.FeatureGroup(name="Defense", show=True)

            # 자산 추가
            self._add_assets_to_map(self.map)

            # 격자 추가
            self._add_grid_to_map(grid_group)

            BATCH_SIZE = 100
            MAX_TRAJECTORIES = 500

            if hasattr(self, 'trajectories'):
                # 전체 데이터 수 제한

                trajectories = self.trajectories[:MAX_TRAJECTORIES] if len(
                    self.trajectories) > MAX_TRAJECTORIES else self.trajectories

                trajectories_batches = [trajectories[i:i + BATCH_SIZE]
                                        for i in range(0, len(trajectories), BATCH_SIZE)]

                # 메모리 관리를 위한 가비지 컬렉션 추가
                gc.collect()

                with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
                    futures = []
                    for batch in trajectories_batches:
                        future = executor.submit(self._process_trajectory_batch, batch,
                                                 trajectory_group, defense_group)
                        futures.append(future)
                    concurrent.futures.wait(futures)

            # 최적화된 방어 위치 추가
            self._add_optimal_defense_locations(defense_group)

            # FeatureGroup들을 지도에 추가
            self.map.add_child(grid_group)
            self.map.add_child(trajectory_group)
            self.map.add_child(defense_group)
            folium.LayerControl().add_to(self.map)
            gc.collect()

            # 웹뷰 업데이트
            data = io.BytesIO()
            self.map.save(data, close_file=False)
            html_content = data.getvalue().decode()

            QtCore.QTimer.singleShot(10, lambda: self._update_webview_for_optimization(html_content))

        except Exception as e:
            print(f"지도 업데이트 중 오류 발생: {str(e)}")

    def _add_grid_to_map(self, grid_group):
        min_lat = min(center[0] for center in self.optimizer.grid_centers.values())
        max_lat = max(center[0] for center in self.optimizer.grid_centers.values())
        min_lon = min(center[1] for center in self.optimizer.grid_centers.values())
        max_lon = max(center[1] for center in self.optimizer.grid_centers.values())

        # 20km 간격으로 변환
        lat_step = 20.0 / 111
        center_lat = (min_lat + max_lat) / 2
        lon_step = 20.0 / (111 * np.cos(np.radians(center_lat)))

        # 위도선 그리기
        for lat in np.arange(min_lat, max_lat + lat_step, lat_step):
            folium.PolyLine(
                locations=[[lat, min_lon], [lat, max_lon]],
                color="gray",
                weight=0.5,
                opacity=0.5
            ).add_to(grid_group)

        # 경도선 그리기
        for lon in np.arange(min_lon, max_lon + lon_step, lon_step):
            folium.PolyLine(
                locations=[[min_lat, lon], [max_lat, lon]],
                color="gray",
                weight=0.5,
                opacity=0.5
            ).add_to(grid_group)

    def _add_optimal_defense_locations(self, defense_group):
        """최적화된 방어 위치를 지도에 추가하는 헬퍼 메서드"""
        optimal_location = self.tr('최적 방어 위치')
        coordinates = self.tr('좌표')
        weapon_systems = self.tr("무기체계")

        for optimal_defense_trajectory in self.optimized_locations:
            optimal_lat, optimal_lon = optimal_defense_trajectory['defense_coordinate']

            icon = folium.DivIcon(html=f"""
                <div style="
                    width: 13px;
                    height: 13px;
                    border-radius: 0%;
                    background-color: purple;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    color: white;
                    font-weight: bold;
                    font-size: 8px;
                    border: 0.5px solid white;
                    box-shadow: 0 0 2px rgba(0,0,0,0.2);
                ">
                </div>
            """)

            folium.Marker(
                location=[float(optimal_lat), float(optimal_lon)],
                icon=icon,
                popup=folium.Popup(f"""
                    <b>{optimal_location}:</b> {optimal_defense_trajectory['defense_name']}<br>
                    <b>{coordinates}:</b> {float(optimal_lat):.5f}, {float(optimal_lon):.5f}<br>
                    <b>{weapon_systems}:</b> {optimal_defense_trajectory['weapon_type']}
                """, max_width=200)
            ).add_to(defense_group)

    def _update_webview_for_optimization(self, html_content):
        """웹뷰 업데이트를 위한 헬퍼 메서드"""
        try:
            self.map_view.setHtml(html_content)
            self.map_view.update()
            self.update_3d_graph_for_optimization()
        except Exception as e:
            print(f"웹뷰 업데이트 중 오류 발생: {str(e)}")

    def update_3d_graph_for_optimization(self):
        self.ax.clear()
        self.ax.set_xlabel('Longitude')
        self.ax.set_ylabel('Latitude')
        self.ax.set_zlabel('Altitude')

        # 선택된 자산, 방어 자산, 적 기지 표시
        for asset in self.get_selected_assets():
            lat, lon = self.parse_coordinates(asset[1])
            self.ax.scatter(lon, lat, 0, c='blue', marker='o')

        for optimal_location_dic in self.optimized_locations:
            lat, lon = optimal_location_dic['defense_coordinate']
            self.ax.scatter(float(lon), float(lat), 0, c='purple', marker='s')

        for enemy_base in self.get_selected_enemy_bases():
            lat, lon = self.parse_coordinates(enemy_base[1])
            self.ax.scatter(lon, lat, 0, c='red', marker='^')

        # 미사일 궤적 및 방어 궤적 표시
        if hasattr(self, 'trajectories') and self.trajectories:
            all_lats = []
            all_lons = []
            all_alts = []

            for trajectory_data in self.trajectories:
                trajectory = trajectory_data['trajectory']
                longitudes = [float(point[1]) for point in trajectory]
                latitudes = [float(point[0]) for point in trajectory]
                altitudes = [float(point[2]) for point in trajectory]

                all_lats.extend(latitudes)
                all_lons.extend(longitudes)
                all_alts.extend(altitudes)

                # 모든 궤적을 표시하되, 방어 여부에 따라 색상만 다르게 지정
                points = list(zip(latitudes, longitudes, altitudes))
                is_defended = self.is_trajectory_defended_with_alt(points)
                color = "green" if is_defended else "red"

                # 궤적을 단순화하여 표시
                simplified_points = self._simplify_trajectory_for_3d(points)
                simplified_lats = [point[0] for point in simplified_points]
                simplified_lons = [point[1] for point in simplified_points]
                simplified_alts = [point[2] for point in simplified_points]

                self.ax.plot(simplified_lons, simplified_lats, simplified_alts, color=color, linewidth=0.5, alpha=0.8)

                if is_defended:
                    for defense_tr_dic in self.defense_trajectories:
                        defense_points = [(float(lat), float(lon), float(alt)) for lat, lon, alt in
                                          defense_tr_dic['trajectory']]
                        if self.is_same_trajectory(points, defense_points):
                            defense_coordinate = defense_tr_dic['defense_coordinate']
                            weapon_type = defense_tr_dic['weapon_type']
                            threat_azimuth = defense_tr_dic['threat_azimuth']
                            intercept_point = self.engagement_calculator.find_intercept_point_vectorized(
                                defense_coordinate[0],
                                defense_coordinate[1],
                                trajectory,
                                weapon_type,
                                threat_azimuth)
                            if intercept_point:
                                defense_lon, defense_lat = defense_coordinate[1], defense_coordinate[0]
                                intercept_lat, intercept_lon, intercept_alt = intercept_point
                                self.ax.plot([defense_lon, intercept_lon],
                                             [defense_lat, intercept_lat],
                                             [0, intercept_alt],
                                             color="blue", linewidth=0.4, alpha=0.6)
                                self.ax.scatter(intercept_lon, intercept_lat, intercept_alt,
                                                color="blue", marker='x', s=12)

        self.canvas.draw()

    def show_optimization_summary(self, summary):
        try:
            if self.parent.selected_language == 'ko':
                msg = f"""최적화 결과 요약:
    - 총 {summary.get('attempts', 0)}회 최적화 시도 수행
    - {'최적화된 위치가 더 우수함' if summary.get('is_improved', False) else '최초 위치가 더 우수하여 유지'}

    최종 선택된 위치의 점수:
    - 우선순위 가점: {summary.get('best_scores', {}).get('priority_score', 0):.0f}점
    - 방어율 가점: {summary.get('best_scores', {}).get('defense_rate_score', 0):.0f}점
    - 최소방어율 페널티: {summary.get('best_scores', {}).get('min_defense_penalty', 0):.0f}점
    - 방어범위 페널티: {summary.get('best_scores', {}).get('coverage_penalty', 0):.0f}점
    - 중복방어 페널티: {summary.get('best_scores', {}).get('overlap_penalty', 0):.0f}점
    - 총 방어율: {summary.get('best_scores', {}).get('total_defense_rate', 0):.1f}%
    - 최종 점수: {summary.get('best_scores', {}).get('total_score', 0):.0f}점
    """
            else:
                msg = f"""Optimization Result Summary:
    - Total optimization attempts: {summary.get('attempts', 0)}
    - {'Optimized position is better' if summary.get('is_improved', False) else 'Initial position maintained as better'}

    Final Selected Position Scores:
    - Priority bonus: {summary.get('best_scores', {}).get('priority_score', 0):.0f} points
    - Defense rate bonus: {summary.get('best_scores', {}).get('defense_rate_score', 0):.0f} points  
    - Minimum defense rate penalty: {summary.get('best_scores', {}).get('min_defense_penalty', 0):.0f} points
    - Coverage penalty: {summary.get('best_scores', {}).get('coverage_penalty', 0):.0f} points
    - Overlap penalty: {summary.get('best_scores', {}).get('overlap_penalty', 0):.0f} points
    - Total defense rate: {summary.get('best_scores', {}).get('total_defense_rate', 0):.1f}%
    - Final score: {summary.get('best_scores', {}).get('total_score', 0):.0f} points
    """

            QMessageBox.information(None, self.tr("최적화 결과 요약"), msg)
        except Exception as e:
            QMessageBox.critical(None, self.tr("오류"), self.tr(f"결과 요약 표시 중 오류 발생: {str(e)}"))

    def get_selected_assets(self):
        selected_assets = []
        asset_info_ko = pd.DataFrame()
        asset_info_en = pd.DataFrame()
        for row in range(self.assets_table.rowCount()):
            checkbox_widget = self.assets_table.cellWidget(row, 0)
            if checkbox_widget and checkbox_widget.checkbox.isChecked():
                priority = int(self.assets_table.item(row, 1).text())
                unit = self.assets_table.item(row, 2).text()
                area = self.assets_table.item(row, 3).text()
                asset_name = self.assets_table.item(row, 4).text()
                if self.parent.selected_language == 'ko':
                    asset_info_ko = self.cal_df_ko[
                        (self.cal_df_ko['target_asset'] == asset_name) &
                        (self.cal_df_ko['area'] == area) &
                        (self.cal_df_ko['unit'] == unit)
                        ]
                else:
                    asset_info_en = self.cal_df_en[
                        (self.cal_df_en['target_asset'] == asset_name) &
                        (self.cal_df_en['area'] == area) &
                        (self.cal_df_en['unit'] == unit)
                        ]
                dal_select = asset_info_ko.iloc[0]['dal_select']  if self.parent.selected_language == 'ko' else asset_info_en.iloc[0]['dal_select']
                coord = asset_info_ko.iloc[0]['coordinate'] if self.parent.selected_language == 'ko' else asset_info_en.iloc[0]['coordinate']
                selected_assets.append((asset_name, coord, dal_select, priority))
        return selected_assets

    def get_selected_weapon_assets(self):
        weapon_assets = []
        for row in range(self.weapon_assets_table.rowCount()):
            checkbox_widget = self.weapon_assets_table.cellWidget(row, 0)
            if checkbox_widget and checkbox_widget.checkbox.isChecked():
                unit = self.weapon_assets_table.item(row, 1).text()
                area = self.weapon_assets_table.item(row, 2).text()
                asset_name = self.weapon_assets_table.item(row, 3).text()
                weapon_system = self.weapon_assets_table.item(row, 4).text()

                asset_info = self.weapon_assets_df_ko if self.parent.selected_language == 'ko' else self.weapon_assets_df_en
                asset_info = asset_info[
                    (asset_info['unit'] == unit) &
                    (asset_info['area'] == area) &
                    (asset_info['asset_name'] == asset_name)
                    ]

                if not asset_info.empty:
                    unit = asset_info.iloc[0]['unit']
                    area = asset_info.iloc[0]['area']
                    coord = asset_info.iloc[0]['coordinate']
                    ammo_count = asset_info.iloc[0]['ammo_count']
                    threat_degree = asset_info.iloc[0]['threat_degree']
                    dal_select = asset_info.iloc[0]['dal_select']
                    weapon_assets.append((unit, area, asset_name, coord, weapon_system, ammo_count, threat_degree, dal_select))

        return weapon_assets

    def get_selected_enemy_bases(self):
        selected_enemy_bases = []
        for row in range(self.enemy_sites_table.rowCount()):
            checkbox_widget = self.enemy_sites_table.cellWidget(row, 0)
            if checkbox_widget and checkbox_widget.checkbox.isChecked():
                base_name = self.enemy_sites_table.item(row, 1).text()
                coordinate = self.enemy_sites_table.item(row, 2).text()
                weapon_system = self.enemy_sites_table.item(row, 3).text()
                selected_enemy_bases.append((base_name, coordinate, weapon_system))
        return selected_enemy_bases

    def get_selected_enemy_weapons(self):
        selected_enemy_weapons = []
        for row in range(self.enemy_sites_table.rowCount()):
            checkbox_widget = self.enemy_sites_table.cellWidget(row, 0)
            if checkbox_widget and checkbox_widget.checkbox.isChecked():
                base_name = self.enemy_sites_table.item(row, 1).text()
                coordinate = self.enemy_sites_table.item(row, 2).text()
                weapon_system = self.enemy_sites_table.item(row, 3).text()
                weapon_systems_list = weapon_system.split(", ")
                for weapon in weapon_systems_list:
                    if self.missile_type_combo.currentText() == self.tr('전체'):
                        selected_enemy_weapons.append((base_name, coordinate, weapon))
                    else:
                        if weapon == self.missile_type_combo.currentText():
                            selected_enemy_weapons.append((base_name, coordinate, weapon))
        return selected_enemy_weapons

    @staticmethod
    def parse_coordinates(coord_string):
        """경위도 문자열을 파싱하여 위도와 경도를 반환합니다."""
        lat_str, lon_str = coord_string.split(',')
        lat = float(lat_str[1:])  # 'N' 제거
        lon = float(lon_str[1:])  # 'E' 제거
        return lat, lon

    @staticmethod
    def calculate_bearing(lat1, lon1, lat2, lon2):
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlon = lon2 - lon1
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        bearing = math.atan2(y, x)
        return math.degrees(bearing)

    @staticmethod
    def calculate_distance(lat1, lon1, lat2, lon2):
        """두 지점 간의 거리를 계산하는 메서드 (km 단위)"""
        R = 6371  # 지구 반지름 (km)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(math.radians(lat1)) * math.cos(
            math.radians(lat2)) * math.sin(dlon / 2) * math.sin(dlon / 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c
        return distance

    @staticmethod
    def is_same_trajectory(trajectory1, trajectory2):
        """두 궤적이 동일한지 확인하는 메서드"""
        if not isinstance(trajectory1, list) or not isinstance(trajectory2, list):
            return False
        if len(trajectory1) != len(trajectory2):
            return False
        return all(np.array_equal(np.array(p1), np.array(p2)) for p1, p2 in zip(trajectory1, trajectory2))

    @staticmethod
    def calculate_distance_vectorized(lat1, lon1, lat2, lon2):
        R = 6371
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
        return R * c

    def print_map(self):
        self.printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        self.printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        self.printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))  # A4 크기 지정
        self.printer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Unit.Millimeter)

        self.preview = QPrintPreviewDialog(self.printer, self)
        self.preview.setMinimumSize(1000, 800)
        self.preview.paintRequested.connect(self.handle_print_requested)
        self.preview.finished.connect(self.print_map_finished)
        self.preview.exec()

    def handle_print_requested(self, printer):
        try:
            painter = QPainter()
            painter.begin(printer)

            page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)

            title_font = QFont("Arial", 16, QFont.Weight.Bold)
            painter.setFont(title_font)
            title_rect = painter.boundingRect(page_rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter, "Simulation Result")
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter, "Simulation Result")

            full_map = self.map_view.grab()

            combined_image = full_map.toImage()

            content_rect = page_rect.adjusted(0, title_rect.height() + 10, 0, -30)
            scaled_image = combined_image.scaled(QSize(int(content_rect.width()), int(content_rect.height())),
                                                 Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

            x = int(content_rect.left() + (content_rect.width() - scaled_image.width()) / 2)
            y = int(content_rect.top() + (content_rect.height() - scaled_image.height()) / 2)
            painter.drawImage(x, y, scaled_image)

            info_font = QFont("Arial", 8)
            painter.setFont(info_font)
            current_time = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
            info_text = self.tr(f"인쇄 일시: {current_time}")
            painter.drawText(page_rect.adjusted(10, -20, -10, -10), Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight, info_text)

            painter.end()
        except Exception as e:
            print(self.tr(f"인쇄 중 오류 발생: {str(e)}"))
            self.print_success = False
        else:
            self.print_success = True

    def print_map_finished(self, result):
        if self.print_success:
            QMessageBox.information(self, self.tr("인쇄 완료"), self.tr("지도가 성공적으로 출력되었습니다."))
        else:
            QMessageBox.warning(self, self.tr("인쇄 실패"), self.tr("지도 출력 중 오류가 발생했습니다."))

    def print_result_table(self):
        try:
            document = QTextDocument()
            cursor = QTextCursor(document)

            # 개선된 CSS 스타일
            document.setDefaultStyleSheet("""
                @page { size: A4 landscape; margin: 10mm; }
                body { 
                    font-family: 'Malgun Gothic', sans-serif;
                    width: 100%;
                    margin: 0 auto;
                    background-color: #ffffff;
                }
                h1 { 
                    color: #2c3e50; 
                    text-align: center;
                    margin-bottom: 20px;
                    font-size: 22px;
                    padding: 10px;
                    border-bottom: 2px solid #3498db;
                }
                .info { 
                    padding: 5px;
                    color: #7f8c8d;
                    font-size: 12px;
                    margin-bottom: 15px;
                }
                table { 
                    border-collapse: collapse; 
                    width: 100%;
                    margin: 10px auto;
                    background-color: #ffffff;
                }
                th { 
                    color: black;
                    text-align: center;
                    font-weight: bold;
                    padding: 12px 8px;
                    border: 1px solid #2980b9;
                }
                td { 
                    border: 1px solid #bdc3c7;
                    padding: 8px;
                    text-align: center;
                    color: #2c3e50;
                }
                tr:nth-child(even) {
                    background-color: #f9f9f9;
                }
                tr:hover {
                    background-color: #f5f6fa;
                }
            """)

            font = QFont("Arial", 10)
            document.setDefaultFont(font)

            if self.result_table.columnCount() == 3:
                cursor.insertHtml(f"""
                <h1 align='center'>{self.tr("미사일 궤적 분석 결과")}</h1>
                <div class='info' style='text-align: right;'>
                    {self.tr("보고서 생성 일시: ")} {QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")}
                </div>
            """)
            else:
                cursor.insertHtml(f"""
                    <h1 align='center'>{self.tr("최적 방어포대 위치 및 위협 방위각")}</h1>
                    <div class='info' style='text-align: right;'>
                        {self.tr("보고서 생성 일시: ")} {QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")}
                    </div>
                """)

            # 테이블 포맷 설정
            table_format = QTextTableFormat()
            table_format.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
            table_format.setCellPadding(1)
            table_format.setCellSpacing(0)
            table_format.setAlignment(Qt.AlignmentFlag.AlignCenter)
            table_format.setWidth(QTextLength(QTextLength.Type.PercentageLength, 100))

            rows = self.result_table.rowCount() + 1
            cols = self.result_table.columnCount()

            table = cursor.insertTable(rows, cols, table_format)

            # 테이블 헤더 삽입
            header_row = table.cellAt(0, 0).firstCursorPosition()
            for col in range(cols):
                header_row.insertHtml(f"<th>{self.result_table.horizontalHeaderItem(col).text()}</th>")
                header_row.movePosition(QTextCursor.MoveOperation.NextCell)

            # 테이블 데이터 삽입
            for row in range(self.result_table.rowCount()):
                data_row = table.cellAt(row + 1, 0).firstCursorPosition()
                for col in range(cols):
                    item = self.result_table.item(row, col)
                    if item:
                        if row == self.result_table.rowCount() - 1 and col == cols - 1 and cols > 3:
                            data_row.insertHtml(f"{item.text()}<br>")
                        else:
                            data_row.insertText(item.text())
                            data_row.movePosition(QTextCursor.MoveOperation.NextCell)

            preview = QPrintPreviewDialog()
            preview.setWindowIcon(QIcon("image/logo.png"))

            def handle_print(printer):
                printer.setPageOrientation(QPageLayout.Orientation.Portrait)
                page_layout = QPageLayout(
                    QPageSize(QPageSize.PageSizeId.A4),
                    QPageLayout.Orientation.Portrait,
                    QMarginsF(1, 1, 1, 1),
                    QPageLayout.Unit.Millimeter
                )
                printer.setPageLayout(page_layout)
                document.print(printer)

            preview.paintRequested.connect(handle_print)
            preview.exec()

            QCoreApplication.processEvents()

        except Exception as e:
            QMessageBox.critical(self, self.tr("오류"), self.tr("다음 오류가 발생했습니다: {}").format(str(e)))

class CheckBoxHeader(QHeaderView):
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.isOn = False

    def paintSection(self, painter, rect, logicalIndex):
        painter.save()
        super().paintSection(painter, rect, logicalIndex)
        painter.restore()

        if logicalIndex == 0:
            option = QStyleOptionButton()
            option.rect = QRect(rect.x() + rect.width() // 2 - 12, rect.y() + rect.height() // 2 - 12, 24, 24)
            option.state = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Active
            if self.isOn:
                option.state |= QStyle.StateFlag.State_On
            else:
                option.state |= QStyle.StateFlag.State_Off
            self.style().drawControl(QStyle.ControlElement.CE_CheckBox, option, painter)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            x = self.logicalIndexAt(event.pos().x())
            if x == 0:
                self.isOn = not self.isOn
                self.updateSection(0)
                self.parent().on_header_clicked(self.isOn)
        super().mousePressEvent(event)

class CenteredCheckBox(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        self.checkbox = QCheckBox()
        self.checkbox.setStyleSheet("QCheckBox::indicator { width: 24px; height: 24px; }")
        layout.addWidget(self.checkbox)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def isChecked(self):
        return self.checkbox.isChecked()

    def setChecked(self, checked):
        self.checkbox.setChecked(checked)

class MyTableWidget(QTableWidget):
    def __init__(self, *args):
        super().__init__(*args)
        self.header = CheckBoxHeader(Qt.Orientation.Horizontal, self)
        self.setHorizontalHeader(self.header)

    def on_header_clicked(self, checked):
        for row in range(self.rowCount()):
            checkbox_widget = self.cellWidget(row, 0)
            if isinstance(checkbox_widget, CenteredCheckBox):
                checkbox_widget.setChecked(checked)

    def uncheckAllRows(self):
        self.header.isOn = False
        self.header.updateSection(0)
        self.on_header_clicked(False)


class MainWindow(QtWidgets.QMainWindow, QObject):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setWindowTitle("CAL/DAL Management System")
        self.setWindowIcon(QIcon("logo.png"))
        self.setMinimumSize(800, 600)
        self.map_app = MapApp()
        self.selected_language = "ko"  # 기본 언어 설정
        self.central_widget = QtWidgets.QStackedWidget(self)
        self.setCentralWidget(self.central_widget)
        self.db_path = 'assets_management.db'
        self.missile_defense_window = MissileDefenseApp(self)
        self.central_widget.addWidget(self.missile_defense_window)


    def show_main_page(self):
        self.central_widget.setCurrentIndex(0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


