# -*- coding: utf-8 -*-
"""地理围栏：Haversine 球面距离"""
import math

DEFAULT_COORD = (25.272, 110.331)  # 桂林信息科技学院（演示默认坐标）

_EARTH_R_M = 6371000.0  # 地球平均半径（米）


def haversine_m(lat1, lng1, lat2, lng2) -> float:
    """两经纬度坐标间的球面距离（米）"""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    )
    return 2 * _EARTH_R_M * math.asin(math.sqrt(a))


def within_range(
    teacher_lat, teacher_lng, student_lat, student_lng, range_m
) -> tuple[bool, float]:
    """学生坐标是否落在教师坐标 range_m 米范围内 → (是否在范围内, 距离米)

    任一坐标为 None → (False, -1)
    """
    if None in (teacher_lat, teacher_lng, student_lat, student_lng):
        return False, -1
    dist = haversine_m(teacher_lat, teacher_lng, student_lat, student_lng)
    return dist <= range_m, dist
