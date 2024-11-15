from PyQt6 import QtWidgets
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *

from PyQt6.QtCore import Qt, QCoreApplication, QTranslator
from addasset import AddAssetWindow
import sys, logging
import sqlite3
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog
from PyQt6.QtGui import QTextDocument, QTextCursor, QTextTableFormat, QTextFrameFormat, QTextLength, QTextCharFormat, QFont, QTextBlockFormat
from PyQt6.QtGui import QPagedPaintDevice, QPainter, QImage, QPageSize, QPageLayout
from PyQt6.QtCore import QUrl, QTemporaryFile, QSize, QTimer, QMarginsF

from generate_dummy_data import engagement_effectiveness
from languageselection import Translator, LanguageSelectionWindow
from commander_guidance import BmdPriority, EngagementEffect
from common_map_view import CommonCalMapView
from dal_map_view import PriorityDalMapView, PriorityWeaponMapView
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QObject, QRect, QDateTime
from setting import SettingWindow, MapApp
from PyQt6.QtWebEngineWidgets import QWebEngineView
import folium
import io, json
import pandas as pd


class DalPriorityWindow(QDialog):
    """저장된 자산을 보여주는 창"""

    def __init__(self, parent):
        super(DalPriorityWindow, self).__init__(parent)
        self.parent = parent
        self.db_path = self.parent.db_path
        self.setMinimumSize(1024, 768)
        self.map = folium.Map(
            location=[self.parent.map_app.loadSettings()['latitude'], self.parent.map_app.loadSettings()['longitude']],
            zoom_start=self.parent.map_app.loadSettings()['zoom'],
            tiles=self.parent.map_app.loadSettings()['style'])
        self.initUI()
        self.load_assets()
        self.show_defense_radius = False
        self.update_map()

    def initUI(self):
        """UI 구성"""
        main_layout = QHBoxLayout()

        # 좌우측 너비 조정 가능하도록 설정
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # 왼쪽 레이아웃 구성
        left_layout.setSpacing(20)
        left_layout.setContentsMargins(30, 40, 30, 30)

        # 필터 그룹박스 생성
        filter_group = QGroupBox(self.tr("필터"))
        filter_group.setStyleSheet("font: 바른공군체; font-size: 18px; font-weight: bold;")

        # 필터 레이아웃 생성
        filter_layout = QGridLayout()
        filter_layout.setSpacing(10)
        filter_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)  # 왼쪽 상단 정렬

        # 구성군 선택 필터
        unit_filter_label = QLabel(self.tr("구성군 선택"), self)
        unit_filter_label.setStyleSheet("font: 바른공군체; font-size: 16px;")
        self.unit_filter = QComboBox()
        self.unit_filter.addItems([self.tr("전체"), self.tr("지상군"), self.tr("해군"), self.tr("공군"), self.tr("기타")])
        self.unit_filter.setFixedSize(150, 30)
        self.unit_filter.setStyleSheet("font: 바른공군체; font-size: 16px;")
        filter_layout.addWidget(unit_filter_label, 0, 0)
        filter_layout.addWidget(self.unit_filter, 0, 1)

        # BMD 우선순위 필터
        bmd_priority_filter_label = QLabel(self.tr("BMD 우선순위 목록"), self)
        bmd_priority_filter_label.setStyleSheet("font: 바른공군체; font-size: 16px;")
        self.bmd_priority_filter = QComboBox()
        self.bmd_priority_filter.addItems(
            [self.tr("전체"), self.tr("지휘통제시설"), self.tr("비행단"), self.tr("군수기지"), self.tr("해군기지"), self.tr("주요레이다")])
        self.bmd_priority_filter.setFixedSize(150, 30)
        self.bmd_priority_filter.setStyleSheet("font: 바른공군체; font-size: 16px;")
        filter_layout.addWidget(bmd_priority_filter_label, 1, 0)
        filter_layout.addWidget(self.bmd_priority_filter, 1, 1)

        # 교전효과 수준
        engagement_filter_label = QLabel(self.tr("교전효과 수준"), self)
        engagement_filter_label.setStyleSheet("font: 바른공군체; font-size: 16px;")
        self.engagement_filter = QComboBox()
        self.engagement_filter.addItems(
            [self.tr("전체"), self.tr("1단계: 원격발사대"), self.tr("2단계: 단층방어"), self.tr("3단계: 중첩방어"), self.tr("4단계: 다층방어")])
        self.engagement_filter.setFixedSize(250, 30)
        self.engagement_filter.setStyleSheet("font: 바른공군체; font-size: 16px;")
        filter_layout.addWidget(engagement_filter_label, 1, 2)
        filter_layout.addWidget(self.engagement_filter, 1, 3)

        # 검색 섹션
        search_label = QLabel(self.tr("검색"), self)
        search_label.setStyleSheet("font: 바른공군체; font-size: 16px;")
        self.asset_search_input = QLineEdit()
        self.asset_search_input.setPlaceholderText(self.tr("검색어를 입력하세요"))
        self.asset_search_input.setFixedSize(200, 30)
        self.asset_search_input.setStyleSheet("font: 바른공군체; font-size: 16px;")
        filter_layout.addWidget(search_label, 2, 0)
        filter_layout.addWidget(self.asset_search_input, 2, 1, 1, 2)

        # 콤보박스 이벤트 연결
        self.unit_filter.currentIndexChanged.connect(self.apply_filters)
        self.engagement_filter.currentIndexChanged.connect(self.apply_filters)
        self.bmd_priority_filter.currentIndexChanged.connect(self.apply_filters)

        # 찾기 버튼
        self.find_button = QPushButton(self.tr("찾기"))
        self.find_button.setFixedSize(80, 30)
        self.find_button.setStyleSheet("font: 바른공군체; font-size: 16px; font-weight: bold;")
        self.find_button.clicked.connect(self.apply_filters)
        filter_layout.addWidget(self.find_button, 2, 3)

        # 필터 그룹에 레이아웃 설정
        filter_group.setLayout(filter_layout)

        # 필터 그룹의 크기를 고정
        filter_group.setFixedHeight(filter_group.sizeHint().height())

        # 테이블 설정 부분 수정
        self.assets_table = MyTableWidget()
        self.assets_table.setColumnCount(23)  # 우선순위 열 추가
        self.assets_table.setHorizontalHeaderLabels([
            "", self.tr("우선순위"), self.tr("ID"), self.tr("구성군"), self.tr("자산번호"), self.tr("담당자"),
            self.tr("연락처"), self.tr("방어대상자산"), self.tr("지역"), self.tr("경위도"),
            self.tr("군사좌표(MGRS)"), self.tr("임무/기능 기술"), self.tr("방어자산"), self.tr("무기체계"), self.tr("보유탄수"),
            self.tr("위협방위"), self.tr("교전효과 수준"), self.tr("BMD 우선순위"),
            self.tr("중요도"), self.tr("취약성"), self.tr("위협"), self.tr("합산 점수"), self.tr("삭제")
        ])
        self.assets_table.verticalHeader().setVisible(False)

        self.assets_table.setAlternatingRowColors(True)
        self.assets_table.setStyleSheet("QTableWidget {background-color: #ffffff; font: 바른공군체; font-size: 16px;}"
                                        "QTableWidget::item { padding: 8px; }")
        self.assets_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.assets_table.itemChanged.connect(self.on_checkbox_changed)

        font = QFont("강한공군체", 13)
        font.setBold(True)
        self.assets_table.horizontalHeader().setFont(font)

        # 헤더 설정
        header = self.assets_table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
        header.resizeSection(0, 50)
        header.resizeSection(1, 100)
        header.resizeSection(-1, 100)

        # 헤더 텍스트 중앙 정렬 및 자동 줄바꿈
        for column in range(header.count()):
            item = self.assets_table.horizontalHeaderItem(column)
            if item:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        # 테이블 설정
        self.assets_table.horizontalHeader().setStretchLastSection(False)
        self.assets_table.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        self.assets_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        # 각 열의 내용에 맞게 너비 설정
        for column in range(2, header.count() - 1):
            self.assets_table.horizontalHeader().setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeMode.Stretch)

        # 헤더 높이 자동 조절
        self.assets_table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.assets_table.verticalHeader().setDefaultSectionSize(60)

        # 버튼 레이아웃 수정
        button_layout = QHBoxLayout()
        button_layout.setSpacing(1)
        button_layout.setContentsMargins(0, 1, 0, 1)
        self.set_priority_button = QPushButton(self.tr("우선순위 결정"), self)
        self.set_priority_button.clicked.connect(self.set_priority)
        self.reset_button = QPushButton(self.tr("초기화"), self)
        self.reset_button.clicked.connect(self.reset_priority)
        self.print_button = QPushButton(self.tr("출력"), self)
        self.print_button.clicked.connect(self.print_assets_table)
        self.back_button = QPushButton(self.tr("메인화면"), self)
        self.back_button.clicked.connect(self.parent.show_main_page)

        for button in [self.set_priority_button, self.reset_button, self.print_button, self.back_button]:
            button.setFont(QFont("강한공군체", 12, QFont.Weight.Bold))
            button.setFixedSize(150, 50)
            button.setStyleSheet("QPushButton { text-align: center; }")

        button_layout.addWidget(self.set_priority_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addWidget(self.print_button)
        button_layout.addWidget(self.back_button)


        # 우선순위 이동 버튼
        move_buttons_layout = QVBoxLayout()
        self.move_up_button = QPushButton("↑")
        self.move_down_button = QPushButton("↓")
        self.move_up_button.clicked.connect(self.move_item_up)
        self.move_down_button.clicked.connect(self.move_item_down)

        # 버튼 크기 조정
        self.move_up_button.setFixedWidth(30)
        self.move_down_button.setFixedWidth(30)

        move_buttons_layout.addWidget(self.move_up_button)
        move_buttons_layout.addWidget(self.move_down_button)

        # 콤보박스 이벤트 연결
        self.unit_filter.currentIndexChanged.connect(self.check_filter_status)
        self.engagement_filter.currentIndexChanged.connect(self.check_filter_status)
        self.bmd_priority_filter.currentIndexChanged.connect(self.check_filter_status)
        self.asset_search_input.textChanged.connect(self.check_filter_status)


        # 테이블과 이동 버튼을 포함하는 레이아웃
        table_layout = QHBoxLayout()
        table_layout.addWidget(self.assets_table)
        table_layout.addLayout(move_buttons_layout)

        # 왼쪽 레이아웃에 위젯 추가 (변경된 부분)
        left_layout.addWidget(filter_group)
        left_layout.addLayout(table_layout)
        left_layout.addLayout(button_layout)

        # 오른쪽 레이아웃 구성
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # 무기체계 체크박스 그룹
        weapon_group = QGroupBox(self.tr("무기체계"))
        weapon_layout = QGridLayout()
        weapon_layout.setContentsMargins(5, 5, 5, 5)  # 여백 조정
        weapon_layout.setSpacing(15)  # 체크박스 간 간격 조정

        self.weapon_systems_checkboxes = {}
        weapon_systems = []
        with open('weapon_systems.json', 'r', encoding='utf-8') as file:
            weapon_systems_dic = json.load(file)

        for weapon in weapon_systems_dic.keys():
            weapon_systems.append(weapon)

        # 한 줄에 표시할 최대 아이템 수 설정
        max_columns = 4  # 이 값을 조절하여 한 줄에 표시될 체크박스 수를 조정할 수 있습니다

        for i, weapon in enumerate(weapon_systems):
            checkbox = QCheckBox(weapon)
            checkbox.stateChanged.connect(self.update_map)
            self.weapon_systems_checkboxes[weapon] = checkbox
            # i를 max_columns로 나누어 행과 열 위치 계산
            row = i // max_columns
            col = i % max_columns
            weapon_layout.addWidget(checkbox, row, col)

        weapon_group.setLayout(weapon_layout)
        # 높이를 자동으로 조정하도록 변경
        weapon_group.adjustSize()
        right_layout.addWidget(weapon_group)

        # 방어반경 체크박스
        self.defense_radius_checkbox = QCheckBox(self.tr("방어반경 표시"))
        self.defense_radius_checkbox.stateChanged.connect(self.toggle_defense_radius)
        right_layout.addWidget(self.defense_radius_checkbox)

        # 방어반경 표시 체크박스와 지도 출력 버튼을 위한 수평 레이아웃
        map_print_button_layout = QVBoxLayout()

        # 지도 출력 버튼
        self.map_print_button = QPushButton(self.tr("지도 출력"), self)
        self.map_print_button.setFont(QFont("강한공군체", 12, QFont.Weight.Bold))
        self.map_print_button.setFixedSize(120, 30)
        self.map_print_button.setStyleSheet("QPushButton { text-align: center; }")
        self.map_print_button.clicked.connect(self.print_map)
        map_print_button_layout.addWidget(self.map_print_button, alignment=Qt.AlignmentFlag.AlignRight)

        right_layout.addLayout(map_print_button_layout)

        self.map_view = QWebEngineView()
        right_layout.addWidget(self.map_view)

        self.stacked_widget = QStackedWidget(self)
        self.bmd_priority_page = BmdPriority(self)
        self.engagement_effectiveness_page = EngagementEffect(self)
        self.stacked_widget.addWidget(self.bmd_priority_page)
        self.stacked_widget.addWidget(self.engagement_effectiveness_page)

        right_layout.addWidget(self.stacked_widget)

        right_splitter = QSplitter(Qt.Orientation.Vertical)

        right_splitter.addWidget(self.map_view)
        right_splitter.addWidget(self.stacked_widget)
        right_splitter.setStretchFactor(0, 2)
        right_splitter.setStretchFactor(1, 1)

        # 오른쪽 레이아웃에 수직 스플리터 추가
        right_layout.addWidget(right_splitter)

        # 스플리터에 좌우 위젯 추가
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)

        # 메인 레이아웃에 스플리터 추가
        main_layout.addWidget(splitter)

        self.setLayout(main_layout)

        # 우측 하단에 버튼 추가
        right_bottom_layout = QHBoxLayout()
        self.bmd_priority_button = QPushButton(self.tr("BMD 우선순위"), self)
        self.engagement_effect_button = QPushButton(self.tr("교전효과 수준"), self)

        for button in [self.bmd_priority_button, self.engagement_effect_button]:
            button.setFont(QFont("강한공군체", 12, QFont.Weight.Bold))
            button.setFixedSize(150, 50)
            button.setStyleSheet("""
                    QPushButton {
                        background-color: #4a86e8;
                        color: white;
                        border-radius: 10px;
                    }
                    QPushButton:hover {
                        background-color: #3a76d8;
                    }
                """)

        right_bottom_layout.addWidget(self.bmd_priority_button)
        right_bottom_layout.addWidget(self.engagement_effect_button)

        # 버튼 클릭 이벤트 연결
        self.bmd_priority_button.clicked.connect(self.show_bmd_priority)
        self.engagement_effect_button.clicked.connect(self.show_engagement_effect)

        # 우측 레이아웃에 버튼 추가
        right_layout.addLayout(right_bottom_layout)

    def check_filter_status(self):
        if (self.unit_filter.currentText() != self.tr("전체") or
                self.engagement_filter.currentText() != self.tr("전체") or
                self.bmd_priority_filter.currentText() != self.tr("전체") or
                self.asset_search_input.text().strip()):
            self.move_up_button.setDisabled(True)
            self.move_down_button.setDisabled(True)
        else:
            self.move_up_button.setEnabled(True)
            self.move_down_button.setEnabled(True)

    def toggle_defense_radius(self, state):
        self.show_defense_radius = state == Qt.CheckState.Checked.value
        self.update_map()

    def on_checkbox_changed(self, item):
        if item.column() == 0:
            self.update_map()

    def refresh(self):
        """테이블을 초기 상태로 되돌리고 필터를 초기화하는 함수"""
        self.unit_filter.setCurrentIndex(0)  # 콤보박스를 "전체"로 설정
        self.engagement_filter.setCurrentIndex(0)
        self.bmd_priority_filter.setCurrentIndex(0)
        self.asset_search_input.clear()  # 검색 입력창 비우기
        self.assets_table.uncheckAllRows()
        for weapon_system, checkbox in self.weapon_systems_checkboxes.items():
            if checkbox.isChecked():
                checkbox.setChecked(False)
        self.defense_radius_checkbox.setChecked(False)
        self.defense_radius_checkbox.setChecked(False)
        self.load_assets()  # 테이블 데이터 새로고침
        self.update_map()

    def update_map(self):
        self.map = folium.Map(
            location=[self.parent.map_app.loadSettings()['latitude'], self.parent.map_app.loadSettings()['longitude']],
            zoom_start=self.parent.map_app.loadSettings()['zoom'],
            tiles=self.parent.map_app.loadSettings()['style'])
        selected_assets = self.get_selected_assets()
        selected_weapons = self.get_selected_weapons()
        if selected_assets:
            PriorityDalMapView(selected_assets, self.map)
        if selected_weapons:
            PriorityWeaponMapView(selected_weapons, self.map, show_defense_radius=self.show_defense_radius)

        data = io.BytesIO()
        self.map.save(data, close_file=False)
        html_content = data.getvalue().decode()
        self.map_view.setHtml(html_content)

    def get_selected_assets(self):
        selected_assets = []
        for row in range(self.assets_table.rowCount()):
            checkbox_widget = self.assets_table.cellWidget(row, 0)
            if checkbox_widget and checkbox_widget.isChecked():
                priority = int(self.assets_table.item(row, 1).text())
                unit = self.assets_table.item(row, 3).text()
                asset_name = self.assets_table.item(row, 7).text()
                area = self.assets_table.item(row, 8).text()
                coordinate = self.assets_table.item(row, 9).text()
                weapon_system = self.assets_table.item(row, 13).text()
                ammo_count = self.assets_table.item(row, 14).text()
                threat_degree = self.assets_table.item(row, 15).text()
                engagement_effectiveness = self.assets_table.item(row, 16).text()
                bmd_priority = self.assets_table.item(row, 17).text()
                selected_assets.append((priority, unit, asset_name, area, coordinate, weapon_system, ammo_count, threat_degree, engagement_effectiveness, bmd_priority))
        return selected_assets

    def get_selected_weapons(self):
        selected_assets = []
        for row in range(self.assets_table.rowCount()):
            checkbox_widget = self.assets_table.cellWidget(row, 0)
            if checkbox_widget and checkbox_widget.isChecked():
                priority = int(self.assets_table.item(row, 1).text())
                unit = self.assets_table.item(row, 3).text()
                asset_name = self.assets_table.item(row, 7).text()
                area = self.assets_table.item(row, 8).text()
                coordinate = self.assets_table.item(row, 9).text()
                weapon_systems_text = self.assets_table.item(row, 13).text()
                threat_degree = self.assets_table.item(row, 15).text()
                engagement_effectiveness = self.assets_table.item(row, 16).text()
                bmd_priority = self.assets_table.item(row, 17).text()
                # weapon_systems가 비어있거나 None인 경우 처리
                if not weapon_systems_text or weapon_systems_text.strip() == '':
                    for weapon_systems_check, checkbox in self.weapon_systems_checkboxes.items():
                        if checkbox.isChecked():
                            selected_assets.append((priority, unit, asset_name, area, coordinate, None, 0, threat_degree,
                                                    engagement_effectiveness, bmd_priority))
                else:
                    weapon_systems = weapon_systems_text.split(',')
                    for weapon_system in weapon_systems:
                        try:
                            weapon, ammo = weapon_system.strip().split('(')
                            ammo = int(ammo.rstrip(')'))
                        except ValueError:
                            weapon, ammo = None, 0

                        for weapon_systems_check, checkbox in self.weapon_systems_checkboxes.items():
                            if checkbox.isChecked() and weapon == weapon_systems_check:
                                selected_assets.append((priority, unit, asset_name, area, coordinate, weapon, ammo, threat_degree,
                                                        engagement_effectiveness, bmd_priority))
        return selected_assets

    def load_assets(self):
        """데이터베이스에서 자산 정보를 로드하여 테이블에 표시하는 함수"""
        # 기존의 cal_assets_priority_ko 테이블에서 우선순위 정보 확인
        self.parent.cursor.execute("SELECT COUNT(*) FROM dal_assets_priority_ko")
        priority_exists = self.parent.cursor.fetchone()[0] > 0

        if priority_exists:
            query_ko = f'''
                SELECT 
                    id, priority, unit, asset_number, manager, contact,
                    target_asset, area, coordinate, mgrs, description,
                    dal_select, weapon_system, ammo_count, threat_degree, engagement_effectiveness, bmd_priority,
                    criticality, vulnerability, threat, total_score 
                FROM dal_assets_priority_ko
            '''
            query_en = f'''
                SELECT 
                    id, priority, unit, asset_number, manager, contact,
                    target_asset, area, coordinate, mgrs, description,
                    dal_select, weapon_system, ammo_count, threat_degree, engagement_effectiveness, bmd_priority,
                    criticality, vulnerability, threat, total_score 
                FROM dal_assets_priority_en
            '''
        else:
            query_ko = f'''
                SELECT 
                    id, unit, asset_number, manager, contact,
                    target_asset, area, coordinate, mgrs, description,
                    dal_select, weapon_system, ammo_count, threat_degree, engagement_effectiveness, bmd_priority,
                    COALESCE(criticality, 0) + COALESCE(criticality_bonus_center, 0) + COALESCE(criticality_bonus_function, 0),
                    COALESCE(vulnerability_damage_protection, 0) + COALESCE(vulnerability_damage_dispersion, 0) + COALESCE(vulnerability_recovery_time, 0) + COALESCE(vulnerability_recovery_ability, 0),
                    COALESCE(threat_attack, 0) + COALESCE(threat_detection, 0),
                    (COALESCE(criticality, 0) + COALESCE(criticality_bonus_center, 0) + COALESCE(criticality_bonus_function, 0)) +
                    (COALESCE(vulnerability_damage_protection, 0) + COALESCE(vulnerability_damage_dispersion, 0) + COALESCE(vulnerability_recovery_time, 0) + COALESCE(vulnerability_recovery_ability, 0)) +
                    (COALESCE(threat_attack, 0) + COALESCE(threat_detection, 0)) AS total_score
                FROM cal_assets_ko
                WHERE dal_select = 1
            '''

            query_en = f'''
                SELECT 
                    id, unit, asset_number, manager, contact,
                    target_asset, area, coordinate, mgrs, description,
                    dal_select, weapon_system, ammo_count, threat_degree, engagement_effectiveness, bmd_priority,
                    COALESCE(criticality, 0) + COALESCE(criticality_bonus_center, 0) + COALESCE(criticality_bonus_function, 0),
                    COALESCE(vulnerability_damage_protection, 0) + COALESCE(vulnerability_damage_dispersion, 0) + COALESCE(vulnerability_recovery_time, 0) + COALESCE(vulnerability_recovery_ability, 0),
                    COALESCE(threat_attack, 0) + COALESCE(threat_detection, 0),
                    (COALESCE(criticality, 0) + COALESCE(criticality_bonus_center, 0) + COALESCE(criticality_bonus_function, 0)) +
                    (COALESCE(vulnerability_damage_protection, 0) + COALESCE(vulnerability_damage_dispersion, 0) + COALESCE(vulnerability_recovery_time, 0) + COALESCE(vulnerability_recovery_ability, 0)) +
                    (COALESCE(threat_attack, 0) + COALESCE(threat_detection, 0)) AS total_score
                FROM cal_assets_en
                WHERE dal_select = 1
            '''

        if priority_exists:
            query_ko += " ORDER BY priority"
            query_en += " ORDER BY priority"
        else:
            query_ko += " ORDER BY total_score DESC"
            query_en += " ORDER BY total_score DESC"

        self.parent.cursor.execute(query_ko)
        asset_data_ko = self.parent.cursor.fetchall()

        self.parent.cursor.execute(query_en)
        asset_data_en = self.parent.cursor.fetchall()

        # 데이터프레임 생성
        columns = ['id'] + [
            'unit', 'asset_number', 'manager', 'contact',
            'target_asset', 'area', 'coordinate', 'mgrs', 'description',
            'dal_select', 'weapon_system', 'ammo_count', 'threat_degree',
            'engagement_effectiveness', 'bmd_priority', 'criticality',
            'vulnerability', 'threat', 'total_score'
        ]

        if priority_exists:
            columns.insert(1, 'priority')

        self.df_ko = pd.DataFrame(asset_data_ko, columns=columns)
        self.df_en = pd.DataFrame(asset_data_en, columns=columns)

        # 우선순위가 없는 경우 임시 우선순위 설정
        if not priority_exists:
            self.df_ko['priority'] = range(1, len(self.df_ko) + 1)
            self.df_en['priority'] = range(1, len(self.df_en) + 1)

        if self.parent.selected_language == 'ko':
            self.df = self.df_ko
            self.update_table(self.df_ko)

        else:
            self.df = self.df_en
            self.update_table(self.df_en)

    def apply_filters(self):
        if not hasattr(self, 'df') or self.df is None:
            return
        filtered_df = self.df.copy()

        # 필터 적용
        unit_filter = self.unit_filter.currentText()
        engagement_filter = self.engagement_filter.currentText()
        bmd_priority_filter = self.bmd_priority_filter.currentText()
        search_text = self.asset_search_input.text().strip()

        if unit_filter != self.tr("전체"):
            filtered_df = filtered_df[filtered_df['unit'] == unit_filter]
        if engagement_filter != self.tr("전체"):
            filtered_df = filtered_df[filtered_df['engagement_effectiveness'] == engagement_filter]
        if bmd_priority_filter != self.tr("전체"):
            filtered_df = filtered_df[filtered_df['bmd_priority'] == bmd_priority_filter]

        # 검색 기능 구현 (지역과 방어대상자산명에 한해서)
        if search_text:
            filtered_df = filtered_df[
                filtered_df['area'].str.contains(search_text, case=False, na=False) |
                filtered_df['target_asset'].str.contains(search_text, case=False, na=False)
                ]

        # 인덱스 재설정
        filtered_df = filtered_df.reset_index(drop=True)

        self.update_table(filtered_df)  # 필터링된 데이터프레임을 update_table에 전달

    def update_table(self, df):
        self.assets_table.setRowCount(0)
        for row_position, row in df.iterrows():
            self.assets_table.insertRow(row_position)
            checkbox_widget = CenteredCheckBox()
            checkbox_widget.checkbox.stateChanged.connect(self.update_map)
            self.assets_table.setCellWidget(row_position, 0, checkbox_widget)

            priority_item = QTableWidgetItem(str(row['priority']))
            priority_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.assets_table.setItem(row_position, 1, priority_item)

            for col_position, (col_name, value) in enumerate(row.drop('priority').items()):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.assets_table.setItem(row_position, col_position + 2, item)

            delete_button = QPushButton(self.tr("삭제"))
            delete_button.setFont(QFont("바른공군체", 13))
            delete_button.setMaximumWidth(100)
            delete_button.clicked.connect(lambda _, row=row_position: self.delete_asset(row))
            self.assets_table.setCellWidget(row_position, len(row) + 1, delete_button)

        # 열 숨기기
        hidden_columns = [2, 4, 5, 6, 9, 10, 11, 12, 14, 15, 18, 19, 20, 21]
        for col in hidden_columns:
            self.assets_table.setColumnHidden(col, True)

        if self.unit_filter == self.tr("전체") or self.bmd_priority_filter == self.tr("전체") or self.engagement_filter == self.tr("전체"):
            self.update_priorities()

    def update_priorities(self):
        for row in range(self.assets_table.rowCount()):
            asset_id = int(self.assets_table.item(row, 2).text())
            if asset_id in self.df_ko['id'].values:
                self.df_ko.loc[self.df_ko['id'] == asset_id, 'priority'] = row + 1
                self.df_en.loc[self.df_en['id'] == asset_id, 'priority'] = row + 1
                priority_item = QTableWidgetItem(str(row + 1))
                priority_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.assets_table.setItem(row, 1, priority_item)
            else:
                priority_item = QTableWidgetItem(str(row + 1))
                priority_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.assets_table.setItem(row, 1, priority_item)

    def move_checked_items(self, direction):
        checked_rows = []
        for row in range(self.assets_table.rowCount()):
            checkbox_widget = self.assets_table.cellWidget(row, 0)
            if checkbox_widget and checkbox_widget.isChecked():
                checked_rows.append(row)

        if direction == -1:
            checked_rows.sort()
        else:
            checked_rows.sort(reverse=True)

        for row in checked_rows:
            target_row = row + direction
            if 0 <= target_row < self.assets_table.rowCount():
                # 데이터 이동
                for col in range(2, self.assets_table.columnCount()):
                    current_item = self.assets_table.takeItem(row, col)
                    target_item = self.assets_table.takeItem(target_row, col)
                    self.assets_table.setItem(target_row, col, current_item)
                    self.assets_table.setItem(row, col, target_item)

                # 체크박스 상태 변경
                current_checkbox = self.assets_table.cellWidget(row, 0)
                target_checkbox = self.assets_table.cellWidget(target_row, 0)
                current_checkbox.setChecked(False)
                target_checkbox.setChecked(True)

        self.update_priorities()

    def move_item_up(self):
        if self.check_filter_status():
            QMessageBox.warning(self, self.tr("경고"), self.tr("필터가 적용되어 있거나 검색어가 입력된 상태에서는 우선순위를 변경할 수 없습니다."))
        else:
            self.move_checked_items(-1)

    def move_item_down(self):
        if self.check_filter_status():
            QMessageBox.warning(self, self.tr("경고"), self.tr("필터가 적용되어 있거나 검색어가 입력된 상태에서는 우선순위를 변경할 수 없습니다."))
        else:
            self.move_checked_items(1)

    def reset_priority(self):
        reply = QMessageBox.question(self, self.tr("확인"),
                                     self.tr("정말로 우선순위를 초기화하시겠습니까?"),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            for lang in ['ko', 'en']:
                self.parent.cursor.execute(f"DELETE FROM dal_assets_priority_{lang}")
            self.parent.conn.commit()
            self.refresh()
            QMessageBox.information(self, self.tr("알림"), self.tr("우선순위가 초기화되었습니다."))

    def set_priority(self):
        try:
            for lang in ['ko', 'en']:
                self.parent.cursor.execute(f"DELETE FROM dal_assets_priority_{lang}")

            for _, row in self.df_ko.iterrows():
                self.parent.cursor.execute(f"""
                    INSERT INTO dal_assets_priority_ko
                    (id, priority, unit, asset_number, manager, contact, target_asset, area, coordinate, mgrs, 
                    description, dal_select, weapon_system, ammo_count, threat_degree, engagement_effectiveness, 
                    bmd_priority, criticality, vulnerability, threat, total_score) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    int(row['id']) if row['id'] and pd.notna(row['id']) else None,
                    int(row['priority']) if row['priority'] and pd.notna(row['priority']) else None,
                    row['unit'] if pd.notna(row['unit']) else None,
                    row['asset_number'] if pd.notna(row['asset_number']) else None,
                    row['manager'] if pd.notna(row['manager']) else None,
                    row['contact'] if pd.notna(row['contact']) else None,
                    row['target_asset'] if pd.notna(row['target_asset']) else None,
                    row['area'] if pd.notna(row['area']) else None,
                    row['coordinate'] if pd.notna(row['coordinate']) else None,
                    row['mgrs'] if pd.notna(row['mgrs']) else None,
                    row['description'] if pd.notna(row['description']) else None,
                    1 if row['dal_select'] in ['True', 'true', '1', 1] else 0,
                    row['weapon_system'] if pd.notna(row['weapon_system']) else None,
                    int(row['ammo_count']) if pd.notna(row['ammo_count']) else None,
                    int(row['threat_degree']) if pd.notna(row['threat_degree']) else None,
                    row['engagement_effectiveness'] if pd.notna(row['engagement_effectiveness']) else None,
                    row['bmd_priority'] if pd.notna(row['bmd_priority']) else None,
                    float(row['criticality']) if pd.notna(row['criticality']) else None,
                    float(row['vulnerability']) if pd.notna(row['vulnerability']) else None,
                    float(row['threat']) if pd.notna(row['threat']) else None,
                    float(row['total_score']) if pd.notna(row['total_score']) else None
                ))

            for _, row in self.df_en.iterrows():
                self.parent.cursor.execute(f"""
                    INSERT INTO dal_assets_priority_en
                    (id, priority, unit, asset_number, manager, contact, target_asset, area, coordinate, mgrs, 
                    description, dal_select, weapon_system, ammo_count, threat_degree, engagement_effectiveness, 
                    bmd_priority, criticality, vulnerability, threat, total_score) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    int(row['id']) if row['id'] and pd.notna(row['id']) else None,
                    int(row['priority']) if row['priority'] and pd.notna(row['priority']) else None,
                    row['unit'] if pd.notna(row['unit']) else None,
                    row['asset_number'] if pd.notna(row['asset_number']) else None,
                    row['manager'] if pd.notna(row['manager']) else None,
                    row['contact'] if pd.notna(row['contact']) else None,
                    row['target_asset'] if pd.notna(row['target_asset']) else None,
                    row['area'] if pd.notna(row['area']) else None,
                    row['coordinate'] if pd.notna(row['coordinate']) else None,
                    row['mgrs'] if pd.notna(row['mgrs']) else None,
                    row['description'] if pd.notna(row['description']) else None,
                    1 if row['dal_select'] in ['True', 'true', '1', 1] else 0,
                    row['weapon_system'] if pd.notna(row['weapon_system']) else None,
                    int(row['ammo_count']) if pd.notna(row['ammo_count']) else None,
                    int(row['threat_degree']) if pd.notna(row['threat_degree']) else None,
                    row['engagement_effectiveness'] if pd.notna(row['engagement_effectiveness']) else None,
                    row['bmd_priority'] if pd.notna(row['bmd_priority']) else None,
                    float(row['criticality']) if pd.notna(row['criticality']) else None,
                    float(row['vulnerability']) if pd.notna(row['vulnerability']) else None,
                    float(row['threat']) if pd.notna(row['threat']) else None,
                    float(row['total_score']) if pd.notna(row['total_score']) else None
                ))


            self.parent.conn.commit()
            QMessageBox.information(self, self.tr("알림"), self.tr("우선순위가 저장되었습니다."))
            self.refresh()  # 우선순위 저장 후 테이블 새로고침

        except Exception as e:
            QMessageBox.critical(self, self.tr("오류"), self.tr(f"우선순위 저장 중 오류가 발생했습니다: {str(e)}"))
            self.parent.conn.rollback()

    def delete_asset(self, row):
        """선택된 자산을 테이블에서만 삭제"""
        asset_id = self.assets_table.item(row, 2).text()
        target_asset = self.assets_table.item(row, 7).text()
        reply = QMessageBox.question(self, self.tr("확인"),
                                     self.tr("정말로 '{}' (ID: {}) 을(를) 테이블에서 삭제하시겠습니까?".format(target_asset, asset_id)),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.assets_table.removeRow(row)
            self.update_priorities()
            QMessageBox.information(self, "알림", f"'{target_asset}' (ID: {asset_id})이(가) 테이블에서 삭제되었습니다.")

    def show_bmd_priority(self):
        self.stacked_widget.setCurrentWidget(self.bmd_priority_page)
        self.bmd_priority_page.load_table_data()

    def show_engagement_effect(self):
        self.stacked_widget.setCurrentWidget(self.engagement_effectiveness_page)
        self.engagement_effectiveness_page.load_assets()

    def show_main_page(self):
        self.stacked_widget.setCurrentWidget(self.bmd_priority_page)

    def print_assets_table(self):
        try:
            document = QTextDocument()
            cursor = QTextCursor(document)

            # 개선된 CSS 스타일
            document.setDefaultStyleSheet("""
                @page { size: A4 portrait; margin: 10mm; }
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

            # 헤더 섹션
            cursor.insertHtml(f"""
                <h1>{self.tr("DAL 우선순위")}</h1>
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



            excluded_columns = [0, 2, 4, 5, 6, 9, 10, 11, 12, 14, 15, 18, 19, 20]
            cols = self.assets_table.columnCount() - len(excluded_columns) - 1
            rows = self.assets_table.rowCount()

            # 테이블 생성
            table = cursor.insertTable(rows, cols, table_format)

            # 헤더 추가
            header_col = 0
            for col in range(self.assets_table.columnCount()-1):
                if col not in excluded_columns:
                    cell = table.cellAt(0, header_col)
                    cellCursor = cell.firstCursorPosition()
                    header_text = self.assets_table.horizontalHeaderItem(col).text()
                    cellCursor.insertHtml(f"<th>{header_text}</th>")
                    header_col += 1

            # 데이터 추가
            for row in range(self.assets_table.rowCount()-1):
                data_col = 0
                for col in range(self.assets_table.columnCount()):
                    if col not in excluded_columns:
                        item = self.assets_table.item(row, col)
                        if item:
                            cell = table.cellAt(row + 1, data_col)
                            cellCursor = cell.firstCursorPosition()
                            cellCursor.insertText(item.text())
                        data_col += 1

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

    def print_map(self):
        self.printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        self.printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        self.printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))  # A4 크기 지정
        self.printer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Unit.Millimeter)

        self.preview = QPrintPreviewDialog(self.printer, self)
        self.preview.setMinimumSize(1000, 800)
        self.preview.paintRequested.connect(self.handle_print_requested)
        self.preview.finished.connect(self.print_finished)
        self.preview.exec()

    def handle_print_requested(self, printer):
        try:
            painter = QPainter()
            painter.begin(printer)

            page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)

            title_font = QFont("Arial", 16, QFont.Weight.Bold)
            painter.setFont(title_font)
            title_rect = painter.boundingRect(page_rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter, self.tr("DAL 우선순위"))
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter, self.tr("DAL 우선순위"))

            full_map = self.map_view.grab()

            content_rect = page_rect.adjusted(0, title_rect.height() + 10, 0, -30)
            scaled_image = full_map.scaled(QSize(int(content_rect.width()), int(content_rect.height())),
                                           Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

            x = int(content_rect.left() + (content_rect.width() - scaled_image.width()) / 2)
            y = int(content_rect.top() + (content_rect.height() - scaled_image.height()) / 2)
            painter.drawImage(x, y, scaled_image.toImage())

            info_font = QFont("Arial", 8)
            painter.setFont(info_font)
            current_time = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
            info_text = f"인쇄 일시: {current_time}"
            painter.drawText(page_rect.adjusted(10, -20, -10, -10), Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight, info_text)

            painter.end()
        except Exception as e:
            logging.error(f"인쇄 중 오류 발생: {str(e)}")
            self.print_success = False
        else:
            self.print_success = True

    def print_finished(self):
        if self.print_success:
            QMessageBox.information(self, self.tr("인쇄 완료"), self.tr("지도가 성공적으로 출력되었습니다."))
        else:
            QMessageBox.warning(self, self.tr("인쇄 실패"), self.tr("지도 출력 중 오류가 발생했습니다."))

class MainWindow(QMainWindow, QObject):
    """메인 윈도우 클래스"""

    def __init__(self):
        super().__init__()
        self.conn = sqlite3.connect('assets_management.db')
        self.db_path = 'assets_management.db'
        self.setWindowIcon(QIcon("image/logo.png"))
        self.setWindowTitle(self.tr("DAL 우선순위"))
        self.cursor = self.conn.cursor()
        self.stacked_widget = QStackedWidget(self)
        self.setCentralWidget(self.stacked_widget)
        self.map_app = MapApp()
        self.selected_language = "ko"
        self.translator = Translator(QApplication.instance())

        self.view_assets_page = DalPriorityWindow(self)

        self.stacked_widget.addWidget(self.view_assets_page)
        self.show_main_page()

    def show_main_page(self):
        self.stacked_widget.setCurrentIndex(0)

    def show_add_asset_page(self):
        """자산 추가 페이지 표시"""
        self.refresh_database()  # 데이터 갱신
        self.stacked_widget.setCurrentWidget(self.add_asset_page)

    def show_edit_asset_page(self):
        self.refresh_database()
        self.add_asset_page.reset_data()
        self.stacked_widget.setCurrentWidget(self.add_asset_page)

    def show_view_assets_page(self):
        """자산 추가 페이지 표시"""
        self.refresh_database()  # 데이터 갱신
        self.stacked_widget.setCurrentWidget(self.view_assets_page)

    def refresh_database(self):
        """데이터베이스 연결을 새로 고치기 위한 메서드"""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
        self.conn = sqlite3.connect('assets_management.db')
        self.cursor = self.conn.cursor()

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



if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())