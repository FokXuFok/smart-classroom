# -*- coding: utf-8 -*-
"""地理围栏测试（TDD：先于实现编写）"""
import math

from app.core.geofence import DEFAULT_COORD, haversine_m, within_range

# 纯纬度差（经度相同）时 haversine 距离 = dlat * R * pi / 180（精确线性关系）
M_PER_DEG_LAT = math.pi * 6371000.0 / 180.0


def test_same_point_distance_zero():
    lat, lng = DEFAULT_COORD
    assert abs(haversine_m(lat, lng, lat, lng)) < 0.5
    assert DEFAULT_COORD == (25.272, 110.331)


def test_within_100m():
    # 纬度 +0.0008° ≈ 89 米
    ok, dist = within_range(25.272, 110.331, 25.272 + 0.0008, 110.331, 100)
    assert ok is True
    assert 80 < dist < 100


def test_about_300m_out_of_range():
    # 纬度差 0.0027° ≈ 300 米，超出 200 米范围
    ok, dist = within_range(25.272, 110.331, 25.272 + 0.0027, 110.331, 200)
    assert ok is False
    assert dist > 200


def test_boundary_range_200m():
    # 用精确线性换算构造 199.5 米 / 200.5 米两个边界点
    near_dlat = 199.5 / M_PER_DEG_LAT
    far_dlat = 200.5 / M_PER_DEG_LAT

    ok_near, dist_near = within_range(
        25.272, 110.331, 25.272 + near_dlat, 110.331, 200
    )
    assert ok_near is True
    assert 199.0 < dist_near < 200.0

    ok_far, dist_far = within_range(25.272, 110.331, 25.272 + far_dlat, 110.331, 200)
    assert ok_far is False
    assert 200.0 < dist_far < 201.0


def test_none_coords():
    assert within_range(None, 110.331, 25.272, 110.331, 200) == (False, -1)
    assert within_range(25.272, None, 25.272, 110.331, 200) == (False, -1)
    assert within_range(25.272, 110.331, None, 110.331, 200) == (False, -1)
    assert within_range(25.272, 110.331, 25.272, None, 200) == (False, -1)
