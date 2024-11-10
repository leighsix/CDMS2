import sys, logging
import folium
from PyQt6.QtCore import Qt, QCoreApplication, QTranslator, QObject, QDir
from branca.colormap import LinearColormap


class CalMapView(QObject):
    def __init__(self, coordinates_list, map_obj):
        super().__init__()
        self.load_map(coordinates_list, map_obj)

    @staticmethod
    def parse_coordinates(coord_string):
        """경위도 문자열을 파싱하여 위도와 경도를 반환합니다."""
        lat_str, lon_str = coord_string.split(',')
        lat = float(lat_str[1:])  # 'N' 제거
        lon = float(lon_str[1:])  # 'E' 제거
        return lat, lon

    def load_map(self, coordinates_list, map_obj):
        if not coordinates_list:
            return

        composition_group = self.tr('구성군')
        assets_name = self.tr('자산명')
        coordinates = self.tr('좌표')
        engagement_effects = self.tr('교전효과 수준')
        bmd_priorities = self.tr('BMD 우선순위')

        # 구성군별 색상 정의
        unit_colors = {
            self.tr('지상군'): 'red',
            self.tr('해군'): 'blue',
            self.tr('공군'): 'skyblue',
            self.tr('기타'): 'black'
        }

        # BMD 우선순위별 모양 정의 (고정된 매핑)
        bmd_shapes = {
            self.tr('지휘통제시설'): 1,  # 원
            self.tr('비행단'): 2,  # 삼각형
            self.tr('군수기지'): 3,  # 사각형
            self.tr('해군기지'): 4,  # 다이아몬드
            self.tr('주요레이다'): 5,  # 오각형
            self.tr('None'): 6  # 육각형
        }



        # 구성군 범례 생성
        legend_html = f'''
        <div style="position: fixed; bottom: 20px; right: 20px; width: 150px; 
                    border:2px solid grey; z-index:9999; font-size:14px; background-color:white;">
            <div style="position: relative; top: 3px; left: 3px;">
            <strong>{composition_group}</strong><br>
        '''
        for unit, color in unit_colors.items():
            legend_html += f'''
            <div style="display: flex; align-items: center; margin: 3px;">
                <div style="background-color: {color}; width: 15px; height: 15px; margin-right: 5px;"></div>
                <span>{unit}</span>
            </div>
            '''
        legend_html += '</div></div>'

        # BMD 우선순위 범례 생성
        bmd_legend_html = f'''
        <div style="position: fixed; bottom: 20px; left: 20px; width: 150px; 
                    border:2px solid grey; z-index:9999; font-size:14px; background-color:white;">
            <div style="position: relative; top: 3px; left: 3px;">
            <strong>{bmd_priorities}</strong><br>
        '''
        for priority, shape in bmd_shapes.items():
            bmd_legend_html += f'''
            <div style="display: flex; align-items: center; margin: 3px;">
                <div style="width: 15px; height: 15px; margin-right: 5px; display: flex; justify-content: center; align-items: center;">
                    {self.get_shape_html(shape, 'black')}
                </div>
                <span>{priority}</span>
            </div>
            '''
        bmd_legend_html += '</div></div>'

        for unit, asset_name, area, coordinate, engagement_effectiveness, bmd_priority in coordinates_list:
            try:
                lat, lon = self.parse_coordinates(coordinate)

                # 구성군에 따른 색상 선택
                color = unit_colors.get(unit, 'black')

                # BMD 우선순위에 따른 모양 선택
                shape = bmd_shapes[bmd_priority]

                # 커스텀 아이콘 생성
                icon = folium.DivIcon(html=self.get_shape_html(shape, color))

                # 마커 생성
                folium.Marker(
                    location=[lat, lon],
                    icon=icon,
                    popup=folium.Popup(f"""
                        <b>{composition_group}:</b> {unit}<br>
                        <b>{assets_name}:</b> {asset_name}<br>
                        <b>{coordinates}:</b> {coordinate}<br>
                        <b>{engagement_effects}:</b> {engagement_effectiveness}<br>
                        <b>{bmd_priorities}:</b> {bmd_priority}<br>
                    """, max_width=200)
                ).add_to(map_obj)

            except Exception as e:
                logging.error(self.tr(f"좌표 변환 오류 {coordinate}: {e}"))
                continue

        map_obj.get_root().html.add_child(folium.Element(legend_html))
        map_obj.get_root().html.add_child(folium.Element(bmd_legend_html))

    # 모양별 HTML 생성 함수
    @staticmethod
    def get_shape_html(shape_num, color):
        shapes = {
            1: f'''<svg width="20" height="20" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="45" fill="{color}"/>
                <path d="M50 20 L80 65 H20 Z" fill="white"/>
                <circle cx="50" cy="50" r="15" fill="white"/>
                <path d="M35 45 L65 45 L65 55 L35 55 Z" fill="{color}"/>
            </svg>''',  # 지휘통제시설 - 통신/제어를 상징하는 안테나 형태

            2: f'''<svg width="20" height="20" viewBox="0 0 100 100">
                <path d="M50 10 L90 90 L10 90 Z" fill="{color}"/>
                <path d="M30 50 L50 30 L70 50 L60 80 L40 80 Z" fill="white"/>
                <path d="M45 40 L55 40 L55 60 L45 60 Z" fill="{color}"/>
            </svg>''',  # 비행단 - 상승하는 비행기 형상

            3: f'''<svg width="20" height="20" viewBox="0 0 100 100">
                <rect x="10" y="10" width="80" height="80" rx="10" fill="{color}"/>
                <path d="M30 40 H70 M30 50 H70 M30 60 H70" stroke="white" stroke-width="8"/>
                <rect x="25" y="30" width="50" height="40" fill="white"/>
            </svg>''',  # 군수기지 - 창고/보관 형태

            4: f'''<svg width="20" height="20" viewBox="0 0 100 100">
                <path d="M50 0 L100 50 L50 100 L0 50 Z" fill="{color}"/>
                <path d="M35 35 L65 35 L65 65 L35 65 Z" fill="white"/>
                <path d="M30 50 H70" stroke="{color}" stroke-width="6"/>
            </svg>''',  # 해군기지 - 정박지 형태

            5: f'''<svg width="20" height="20" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="45" fill="{color}"/>
                <path d="M50 15 A35 35 0 0 1 85 50 L50 50 Z" fill="white"/>
                <circle cx="50" cy="50" r="15" fill="{color}"/>
                <circle cx="50" cy="50" r="5" fill="white"/>
            </svg>''',  # 주요레이다 - 레이다 스캔 형태

            6: f'''<svg width="20" height="20" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="40" fill="{color}"/>
                <circle cx="50" cy="50" r="20" fill="white"/>
            </svg>'''  # 기본 형태
        }
        return shapes[shape_num]

class PriorityCalMapView(QObject):
    def __init__(self, coordinates_list, map_obj):
        super().__init__()
        self.load_map(coordinates_list, map_obj)

    @staticmethod
    def parse_coordinates(coord_string):
        """경위도 문자열을 파싱하여 위도와 경도를 반환합니다."""
        lat_str, lon_str = coord_string.split(',')
        lat = float(lat_str[1:])  # 'N' 제거
        lon = float(lon_str[1:])  # 'E' 제거
        return lat, lon

    def load_map(self, coordinates_list, map_obj):
        if not coordinates_list:
            return

        priorities = self.tr('우선순위')
        composition_group = self.tr('구성군')
        assets_name = self.tr('자산명')
        coordinates = self.tr('좌표')
        engagement_effects = self.tr('교전효과 수준')
        bmd_priorities = self.tr('BMD 우선순위')

        # 우선순위 정렬 및 색상 계산
        coordinates_list.sort(key=lambda x: x[0])  # 우선순위로 정렬
        max_priority = max(item[0] for item in coordinates_list)
        min_priority = min(item[0] for item in coordinates_list)

        # 그라데이션 색상맵 생성
        colormap = LinearColormap(colors=['red', 'yellow', 'green'], vmin=int(min_priority), vmax=int(max_priority))
        colormap.caption = priorities
        colormap.add_to(map_obj)

        # BMD 우선순위별 모양 정의 (고정된 매핑)
        bmd_shapes = {
            self.tr('지휘통제시설'): 1,  # 원
            self.tr('비행단'): 2,  # 삼각형
            self.tr('군수기지'): 3,  # 사각형
            self.tr('해군기지'): 4,  # 다이아몬드
            self.tr('주요레이다'): 5,  # 오각형
            self.tr('None'): 6  # 육각형
        }

        for priority, unit, asset_name, area, coordinate, engagement_effectiveness, bmd_priority in coordinates_list:
            try:
                lat, lon = self.parse_coordinates(coordinate)

                # 우선순위에 따른 색상 선택
                color = colormap(int(priority))

                # BMD 우선순위에 따른 모양 선택
                shape = bmd_shapes[bmd_priority]

                # 커스텀 아이콘 생성
                icon = folium.DivIcon(html=self.get_shape_html(shape, color))

                # 마커 생성
                folium.Marker(
                    location=[lat, lon],
                    icon=icon,
                    popup=folium.Popup(f"""
                        <b>{priorities}:</b> {priority}<br>
                        <b>{composition_group}:</b> {unit}<br>
                        <b>{assets_name}:</b> {asset_name}<br>
                        <b>{coordinates}:</b> {coordinate}<br>
                        <b>{engagement_effects}:</b> {engagement_effectiveness}<br>
                        <b>{bmd_priorities}:</b> {bmd_priority}<br>
                    """, max_width=200)
                ).add_to(map_obj)

            except Exception as e:
                logging.error(self.tr(f"좌표 변환 오류 {coordinate}: {e}"))
                continue

        # BMD 우선순위 범례 생성
        bmd_legend_html = f'''
        <div style="position: fixed; bottom: 20px; left: 20px; width: 150px; 
                    border:2px solid grey; z-index:9999; font-size:14px; background-color:white;">
            <div style="position: relative; top: 3px; left: 3px;">
            <strong>{bmd_priorities}</strong><br>
        '''
        for priority, shape in bmd_shapes.items():
            bmd_legend_html += f'''
            <div style="display: flex; align-items: center; margin: 3px;">
                <div style="width: 15px; height: 15px; margin-right: 5px; display: flex; justify-content: center; align-items: center;">
                    {self.get_shape_html(shape, 'black')}
                </div>
                <span>{priority}</span>
            </div>
            '''
        bmd_legend_html += '</div></div>'

        map_obj.get_root().html.add_child(folium.Element(bmd_legend_html))

    # 모양별 HTML 생성 함수
    @staticmethod
    def get_shape_html(shape_num, color):
        shapes = {
            1: f'''<svg width="20" height="20" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="45" fill="{color}"/>
                <path d="M50 20 L80 65 H20 Z" fill="white"/>
                <circle cx="50" cy="50" r="15" fill="white"/>
                <path d="M35 45 L65 45 L65 55 L35 55 Z" fill="{color}"/>
            </svg>''',  # 지휘통제시설 - 통신/제어를 상징하는 안테나 형태

            2: f'''<svg width="20" height="20" viewBox="0 0 100 100">
                <path d="M50 10 L90 90 L10 90 Z" fill="{color}"/>
                <path d="M30 50 L50 30 L70 50 L60 80 L40 80 Z" fill="white"/>
                <path d="M45 40 L55 40 L55 60 L45 60 Z" fill="{color}"/>
            </svg>''',  # 비행단 - 상승하는 비행기 형상

            3: f'''<svg width="20" height="20" viewBox="0 0 100 100">
                <rect x="10" y="10" width="80" height="80" rx="10" fill="{color}"/>
                <path d="M30 40 H70 M30 50 H70 M30 60 H70" stroke="white" stroke-width="8"/>
                <rect x="25" y="30" width="50" height="40" fill="white"/>
            </svg>''',  # 군수기지 - 창고/보관 형태

            4: f'''<svg width="20" height="20" viewBox="0 0 100 100">
                <path d="M50 0 L100 50 L50 100 L0 50 Z" fill="{color}"/>
                <path d="M35 35 L65 35 L65 65 L35 65 Z" fill="white"/>
                <path d="M30 50 H70" stroke="{color}" stroke-width="6"/>
            </svg>''',  # 해군기지 - 정박지 형태

            5: f'''<svg width="20" height="20" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="45" fill="{color}"/>
                <path d="M50 15 A35 35 0 0 1 85 50 L50 50 Z" fill="white"/>
                <circle cx="50" cy="50" r="15" fill="{color}"/>
                <circle cx="50" cy="50" r="5" fill="white"/>
            </svg>''',  # 주요레이다 - 레이다 스캔 형태

            6: f'''<svg width="20" height="20" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="40" fill="{color}"/>
                <circle cx="50" cy="50" r="20" fill="white"/>
            </svg>'''  # 기본 형태
        }
        return shapes[shape_num]



