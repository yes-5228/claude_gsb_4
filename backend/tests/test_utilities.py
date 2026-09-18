"""水电抄表记录接口测试：用量/费用/环比计算、异常判定与联动重算。"""

import pytest

BASE = "/api/v1/utilities"


def _create(client, restroom_id, period, reading, meter_type="水表", **extra):
    payload = {
        "restroom_id": restroom_id,
        "meter_type": meter_type,
        "period": period,
        "reading": reading,
        "unit_price": 2.0,
    }
    payload.update(extra)
    response = client.post(BASE, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_usage_fee_and_change_chain(client, restroom):
    rid = restroom["id"]
    first = _create(client, rid, "2026-05", 100.0)
    # 首次抄表无基期
    assert first["usage"] is None
    assert first["fee"] is None
    assert first["change_pct"] is None
    assert first["is_abnormal"] is False

    second = _create(client, rid, "2026-06", 160.0)
    assert second["prev_reading"] == 100.0  # 上期读数自动带出
    assert second["usage"] == 60.0
    assert second["fee"] == 120.0  # 60 × 2.0
    assert second["change_pct"] is None  # 上月无用量，无法环比

    third = _create(client, rid, "2026-07", 230.0)
    assert third["usage"] == 70.0
    assert third["change_pct"] == pytest.approx((70 - 60) / 60 * 100, abs=0.05)
    assert third["is_abnormal"] is False

    # 环比激增超 30% → 异常并给出可能原因
    fourth = _create(client, rid, "2026-08", 340.0)
    assert fourth["usage"] == 110.0
    assert fourth["change_pct"] == pytest.approx((110 - 70) / 70 * 100, abs=0.05)
    assert fourth["is_abnormal"] is True
    assert fourth["abnormal_reasons"]
    assert "漏水" in fourth["abnormal_reasons"][0]

    # 电表骤降提示语不同
    _create(client, rid, "2026-06", 500.0, meter_type="电表", prev_reading=400.0)
    drop = _create(client, rid, "2026-07", 550.0, meter_type="电表")
    assert drop["usage"] == 50.0
    assert drop["is_abnormal"] is True
    assert "电表" in drop["abnormal_reasons"][0]


def test_explicit_prev_reading_and_zero_usage(client, restroom):
    rid = restroom["id"]
    created = _create(client, rid, "2026-05", 150.0, prev_reading=100.0)
    assert created["usage"] == 50.0
    assert created["fee"] == 100.0

    zero = _create(client, rid, "2026-06", 150.0)
    assert zero["usage"] == 0.0
    assert zero["is_abnormal"] is True
    assert "用量为零" in zero["abnormal_reasons"][0]


def test_duplicate_period_rejected(client, restroom):
    rid = restroom["id"]
    _create(client, rid, "2026-05", 100.0)
    duplicate = client.post(
        BASE,
        json={
            "restroom_id": rid,
            "meter_type": "水表",
            "period": "2026-05",
            "reading": 200.0,
        },
    )
    assert duplicate.status_code == 409
    # 同月不同表计不受影响
    ok = client.post(
        BASE,
        json={
            "restroom_id": rid,
            "meter_type": "电表",
            "period": "2026-05",
            "reading": 200.0,
        },
    )
    assert ok.status_code == 201


def test_reading_below_prev_rejected(client, restroom):
    rid = restroom["id"]
    _create(client, rid, "2026-05", 100.0)
    response = client.post(
        BASE,
        json={
            "restroom_id": rid,
            "meter_type": "水表",
            "period": "2026-06",
            "reading": 90.0,
        },
    )
    assert response.status_code == 400
    assert "低于上期读数" in response.json()["detail"]


def test_successor_recalculated_on_update_and_delete(client, restroom):
    rid = restroom["id"]
    _create(client, rid, "2026-05", 0.0, prev_reading=0.0)  # 用量 0 的基期
    june = _create(client, rid, "2026-06", 100.0)
    july = _create(client, rid, "2026-07", 200.0)
    assert june["usage"] == 100.0
    assert july["change_pct"] == pytest.approx(0.0, abs=0.05)  # 与 6 月持平

    # 修改 6 月读数 → 7 月环比联动重算
    updated = client.patch(f"{BASE}/{june['id']}", json={"reading": 150.0}).json()
    assert updated["usage"] == 150.0
    refreshed = client.get(f"{BASE}/{july['id']}").json()
    assert refreshed["prev_reading"] == 150.0
    assert refreshed["usage"] == 50.0
    assert refreshed["change_pct"] == pytest.approx((50 - 150) / 150 * 100, abs=0.05)
    assert refreshed["is_abnormal"] is True  # 降幅超 30%

    # 删除 6 月 → 7 月失去基期
    assert client.delete(f"{BASE}/{updated['id']}").status_code == 200
    orphaned = client.get(f"{BASE}/{july['id']}").json()
    assert orphaned["prev_reading"] is None
    assert orphaned["usage"] is None
    assert orphaned["change_pct"] is None
    assert orphaned["is_abnormal"] is False


def test_summary_and_filters(client, restroom):
    rid = restroom["id"]
    _create(client, rid, "2026-05", 90.0, prev_reading=0.0)  # 水基期 90 吨
    _create(client, rid, "2026-06", 190.0)  # 水 100 吨 × 2 元，环比 +11% 正常
    _create(client, rid, "2026-06", 300.0, meter_type="电表", prev_reading=0.0)  # 电 300 度
    _create(client, rid, "2026-07", 490.0)  # 水 300 吨，环比 +200% 异常

    summary = client.get(BASE + "/summary", params={"period": "2026-06", "restroom_id": rid}).json()
    assert summary["period"] == "2026-06"
    assert summary["water_usage"] == 100.0
    assert summary["water_fee"] == 200.0
    assert summary["electricity_usage"] == 300.0
    assert summary["reading_count"] == 2

    summary_july = client.get(
        BASE + "/summary", params={"period": "2026-07", "restroom_id": rid}
    ).json()
    assert summary_july["water_change_pct"] == pytest.approx(200.0, abs=0.05)
    assert summary_july["abnormal_count"] == 1

    abnormal = client.get(BASE, params={"abnormal_only": "true", "restroom_id": rid}).json()
    assert abnormal["meta"]["total"] == 1
    assert abnormal["items"][0]["period"] == "2026-07"

    electricity = client.get(BASE, params={"meter_type": "电表", "restroom_id": rid}).json()
    assert electricity["meta"]["total"] == 1

    ranged = client.get(
        BASE, params={"period_from": "2026-06", "period_to": "2026-06", "restroom_id": rid}
    ).json()
    assert ranged["meta"]["total"] == 2

    by_restroom = client.get(BASE, params={"restroom_id": rid}).json()
    assert by_restroom["meta"]["total"] == 4


def test_restroom_delete_guard_counts_readings(client, restroom):
    _create(client, restroom["id"], "2026-05", 100.0)
    blocked = client.delete(f"/api/v1/restrooms/{restroom['id']}")
    assert blocked.status_code == 409
    assert "抄表记录" in blocked.json()["detail"]

    ok = client.delete(f"/api/v1/restrooms/{restroom['id']}", params={"force": "true"})
    assert ok.status_code == 200
    remaining = client.get(BASE, params={"restroom_id": restroom["id"]}).json()
    assert remaining["meta"]["total"] == 0
