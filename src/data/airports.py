"""
机场数据加载与查询工具

提供机场数据加载、城市⇔机场转换、输入验证等功能。
"""

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 机场数据类型
AirportData = Dict[str, Any]


class AirportLoader:
    """机场数据加载器"""

    _instance: Optional["AirportLoader"] = None
    _airports: List[AirportData] = []
    _city_to_airports: Dict[str, List[AirportData]] = {}
    _city_code_to_name: Dict[str, str] = {}
    _airport_code_to_airport: Dict[str, AirportData] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not getattr(self, "_initialized", False):
            self._load_data()
            self._initialized = True

    def _load_data(self):
        """从 CSV 文件加载机场数据"""
        csv_path = Path(__file__).parent.parent.parent / "docs" / "airports.csv"

        if not csv_path.exists():
            logger.warning(f"机场数据文件不存在: {csv_path}")
            return

        try:
            with open(csv_path, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 提取关键字段
                    airport_code = row.get("机场代码", "").strip()
                    city = row.get("所属城市", "").strip()
                    city_code = row.get("城市三字码", "").strip()
                    country = row.get("所属国家/地区", "").strip()
                    airport_type = row.get("机场类型", "").strip()

                    if not airport_code:
                        continue

                    airport: AirportData = {
                        "code": airport_code,
                        "name": row.get("机场全称", "").strip(),
                        "short_name": row.get("机场简称", "").strip(),
                        "english_name": row.get("英文名", "").strip(),
                        "city": city,
                        "city_code": city_code,
                        "province": row.get("所属省州", "").strip(),
                        "country": country,
                        "type": "海关" if airport_type == "机场" else "非海关",
                        "is_customs": airport_type == "机场",
                    }

                    self._airports.append(airport)
                    self._airport_code_to_airport[airport_code] = airport

                    # 城市 → 机场列表
                    if city:
                        if city not in self._city_to_airports:
                            self._city_to_airports[city] = []
                        self._city_to_airports[city].append(airport)

                    # 城市三字码 → 城市名
                    if city_code:
                        self._city_code_to_name[city_code] = city

            logger.info(f"机场数据加载完成: {len(self._airports)} 条记录")

        except Exception as e:
            logger.error(f"加载机场数据失败: {e}")

    @property
    def all_airports(self) -> List[AirportData]:
        """所有机场列表"""
        return self._airports

    def get_by_code(self, code: str) -> Optional[AirportData]:
        """根据机场代码查询"""
        return self._airport_code_to_airport.get(code.upper())

    def get_by_city(self, city_name: str) -> List[AirportData]:
        """根据城市名查询机场列表"""
        return self._city_to_airports.get(city_name, [])

    def get_city_code(self, city_name: str) -> Optional[str]:
        """获取城市三字码"""
        airports = self._city_to_airports.get(city_name, [])
        if airports:
            return airports[0].get("city_code")
        return None

    def search(self, keyword: str) -> List[AirportData]:
        """搜索机场（支持城市名、机场名、代码模糊匹配）"""
        keyword = keyword.strip().lower()
        results = []

        for airport in self._airports:
            # 匹配城市名、机场名、英文名、代码
            if (keyword in airport.get("city", "").lower() or
                keyword in airport.get("name", "").lower() or
                keyword in airport.get("english_name", "").lower() or
                keyword in airport.get("code", "").lower()):
                results.append(airport)

        return results

    def get_stats(self) -> Dict[str, Any]:
        """获取机场数据统计"""
        # 按国家统计
        country_count: Dict[str, int] = {}
        # 按城市统计
        city_count: Dict[str, int] = {}
        # 海关机场数量
        customs_count = 0

        for airport in self._airports:
            country = airport.get("country", "未知")
            city = airport.get("city", "未知")
            is_customs = airport.get("is_customs", False)

            country_count[country] = country_count.get(country, 0) + 1
            city_count[city] = city_count.get(city, 0) + 1
            if is_customs:
                customs_count += 1

        # 取前20个
        top_countries = sorted(country_count.items(), key=lambda x: x[1], reverse=True)[:20]
        top_cities = sorted(city_count.items(), key=lambda x: x[1], reverse=True)[:20]

        return {
            "total": len(self._airports),
            "customs": customs_count,
            "non_customs": len(self._airports) - customs_count,
            "countries": len(country_count),
            "cities": len(city_count),
            "top_countries": dict(top_countries),
            "top_cities": dict(top_cities),
        }


# 全局单例
_airport_loader = AirportLoader()


def get_airport_loader() -> AirportLoader:
    """获取机场数据加载器实例"""
    return _airport_loader
