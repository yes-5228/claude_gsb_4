"""水电月度抄表接口测试：用量/费用、环比、异常判定与链式重算。"""

from datetime import date

API = "/api/v1/utility-records"


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def create_record(client, restroom_id, year, month, **overrides):
    payload = {
        "restroom_id": restroom_id,
        "period_year": year,
        "period_month": month,
        "reader": "抄表员",
        "water_reading": None,
        "elec_reading": None,
        **overrides,
    }
    return client.post(API, json=payload)


def test_consecutive_usage_fee_and_change(client, restroom):
    today = date.today()
    y0, m0 = shift_month(today.year, today.month, -2)
    y1, m1 = shift_month(today.year, today.month, -1)
    y2, m2 = today.year, today.month

    first = create_record(client, restroom["id"], y0, m0, water_reading=100, elec_reading=200)
    assert first.status_code == 201, first.text
    assert first.json()["water_usage"] is None
    assert first.json()["water_fee"] is None
    assert first.json()["water_change_pct"] is None
    assert first.json()["status"] == "正常"

    second = create_record(client, restroom["id"], y1, m1, water_reading=112, elec_reading=230)
    body = second.json()
    assert body["water_usage"] == 12.0
    assert body["water_fee"] == 55.2
    assert body["elec_usage"] == 30.0
    assert body["elec_fee"] == 24.0
    # 第二条是首个可对比月份，无上期用量，环比为空
    assert body["water_change_pct"] is None
    assert body["status"] == "正常"

    third = create_record(client, restroom["id"], y2, m2, water_reading=124, elec_reading=260)
    body = third.json()
    assert body["water_usage"] == 12.0
    assert body["water_change_pct"] == 0.0
    assert body["elec_change_pct"] == 0.0
    assert body["total_fee"] == 79.2


def test_spike_flagged_abnormal_with_reasons(client, restroom):
    today = date.today()
    y0, m0 = shift_month(today.year, today.month, -2)
    y1, m1 = shift_month(today.year, today.month, -1)
    create_record(client, restroom["id"], y0, m0, water_reading=100)
    create_record(client, restroom["id"], y1, m1, water_reading=110)  # 用量 10
    spike = create_record(client, restroom["id"], today.year, today.month, water_reading=125)  # +50%
    body = spike.json()
    assert body["water_usage"] == 15.0
    assert body["water_status"] == "用量偏高"
    assert len(body["water_reasons"]) == 4
    assert body["status"] == "异常"

    listed = client.get(
        API, params={"restroom_id": restroom["id"], "abnormal": "true"}
    ).json()
    assert listed["meta"]["total"] == 1
    assert listed["items"][0]["id"] == body["id"]

    normal_only = client.get(
        API, params={"restroom_id": restroom["id"], "abnormal": "false"}
    ).json()
    assert normal_only["meta"]["total"] == 2


def test_small_change_within_floor_is_normal(client, restroom):
    today = date.today()
    y0, m0 = shift_month(today.year, today.month, -2)
    y1, m1 = shift_month(today.year, today.month, -1)
    create_record(client, restroom["id"], y0, m0, water_reading=100)
    create_record(client, restroom["id"], y1, m1, water_reading=102)  # 用量 2，首个可比月
    # 2 -> 3 是 +50%，但绝对增量 1 吨未超过噪声门槛，不告警
    current = create_record(client, restroom["id"], today.year, today.month, water_reading=103)
    body = current.json()
    assert body["water_usage"] == 1.0
    assert body["water_change_pct"] == -50.0
    assert body["water_status"] == "正常"
    assert body["status"] == "正常"


def test_reading_decrease_flags_low_and_zero_fee(client, restroom):
    today = date.today()
    y, m = shift_month(today.year, today.month, -1)
    create_record(client, restroom["id"], y, m, water_reading=100)
    back = create_record(client, restroom["id"], today.year, today.month, water_reading=90)
    body = back.json()
    assert body["water_usage"] == -10.0
    assert body["water_status"] == "用量偏低"
    assert any("回退" in reason for reason in body["water_reasons"])
    assert body["water_fee"] == 0.0
    assert body["status"] == "异常"


def test_manual_fee_locked_survives_recompute(client, restroom):
    today = date.today()
    y, m = shift_month(today.year, today.month, -1)
    first = create_record(client, restroom["id"], y, m, water_reading=100)
    second = create_record(
        client,
        restroom["id"],
        today.year,
        today.month,
        water_reading=110,
        water_fee_auto=False,
        water_fee=99,
    )
    assert second.json()["water_fee"] == 99.0
    assert second.json()["water_fee_locked"] is True

    # 修改上期表底触发链式重算：本期用量变为 8，但手工水费保留
    patched = client.patch(
        f"{API}/{first.json()['id']}", json={"water_reading": 102}
    )
    assert patched.status_code == 200, patched.text
    reloaded = client.get(f"{API}/{second.json()['id']}").json()
    assert reloaded["water_usage"] == 8.0
    assert reloaded["water_fee"] == 99.0
    assert reloaded["water_fee_locked"] is True


def test_duplicate_period_rejected(client, restroom):
    today = date.today()
    ok = create_record(client, restroom["id"], today.year, today.month, water_reading=100)
    assert ok.status_code == 201
    dup = create_record(client, restroom["id"], today.year, today.month, water_reading=110)
    assert dup.status_code == 400
    assert "已存在" in dup.json()["detail"]


def test_edit_old_month_rolls_forward(client, restroom):
    today = date.today()
    y0, m0 = shift_month(today.year, today.month, -2)
    y1, m1 = shift_month(today.year, today.month, -1)
    r0 = create_record(client, restroom["id"], y0, m0, water_reading=100).json()
    create_record(client, restroom["id"], y1, m1, water_reading=110)
    r2 = create_record(client, restroom["id"], today.year, today.month, water_reading=120).json()

    client.patch(f"{API}/{r0['id']}", json={"water_reading": 102})
    middle = client.get(
        API,
        params={"restroom_id": restroom["id"], "period_year": y1, "period_month": m1},
    ).json()["items"][0]
    assert middle["water_usage"] == 8.0
    latest = client.get(f"{API}/{r2['id']}").json()
    assert latest["water_usage"] == 10.0


def test_delete_recomputes_successor_against_new_predecessor(client, restroom):
    today = date.today()
    y0, m0 = shift_month(today.year, today.month, -2)
    y1, m1 = shift_month(today.year, today.month, -1)
    create_record(client, restroom["id"], y0, m0, water_reading=100)
    middle = create_record(client, restroom["id"], y1, m1, water_reading=110).json()
    latest = create_record(client, restroom["id"], today.year, today.month, water_reading=120).json()

    assert client.delete(f"{API}/{middle['id']}").status_code == 200
    reloaded = client.get(f"{API}/{latest['id']}").json()
    # 中间月删除后，最新月直接对最早月取差
    assert reloaded["water_usage"] == 20.0
    assert reloaded["water_change_pct"] is None


def test_restroom_delete_guard_and_cascade(client, restroom):
    today = date.today()
    create_record(client, restroom["id"], today.year, today.month, water_reading=100)
    blocked = client.delete(f"/api/v1/restrooms/{restroom['id']}")
    assert blocked.status_code == 409
    assert "水电记录" in blocked.json()["detail"]

    forced = client.delete(f"/api/v1/restrooms/{restroom['id']}", params={"force": "true"})
    assert forced.status_code == 200
    listed = client.get(API, params={"restroom_id": restroom["id"]}).json()
    assert listed["meta"]["total"] == 0


def test_baseline_and_dictionaries(client, restroom):
    today = date.today()
    y, m = shift_month(today.year, today.month, -1)
    before = client.get(
        f"{API}/baseline",
        params={
            "restroom_id": restroom["id"],
            "period_year": y,
            "period_month": m,
        },
    ).json()
    assert before["exists"] is False
    assert before["prev_year"] is None
    assert before["water_unit_price"] == 4.6
    assert before["elec_unit_price"] == 0.8

    create_record(client, restroom["id"], y, m, water_reading=100, elec_reading=500)
    next_baseline = client.get(
        f"{API}/baseline",
        params={
            "restroom_id": restroom["id"],
            "period_year": today.year,
            "period_month": today.month,
        },
    ).json()
    assert next_baseline["exists"] is False
    assert next_baseline["prev_month"] == m
    assert next_baseline["water_reading"] == 100
    assert next_baseline["elec_reading"] == 500

    dictionaries = client.get("/api/v1/meta/dictionaries").json()
    assert dictionaries["utility_water_unit_price"] == 4.6
    assert dictionaries["utility_change_threshold"] == 0.3
    assert dictionaries["utility_water_floor"] == 2.0
    assert len(dictionaries["utility_reasons"]["water_high"]) == 4


def test_single_utility_record(client, restroom):
    today = date.today()
    response = create_record(
        client, restroom["id"], today.year, today.month, water_reading=100
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["elec_usage"] is None
    assert body["elec_fee"] is None
    assert body["total_fee"] == 0.0  # 首个可对比月之前无用量


def test_requires_at_least_one_reading_and_fee_amount(client, restroom):
    today = date.today()
    neither = client.post(
        API,
        json={
            "restroom_id": restroom["id"],
            "period_year": today.year,
            "period_month": today.month,
            "reader": "抄表员",
        },
    )
    assert neither.status_code == 422

    missing_fee = client.post(
        API,
        json={
            "restroom_id": restroom["id"],
            "period_year": today.year,
            "period_month": today.month,
            "reader": "抄表员",
            "water_reading": 100,
            "water_fee_auto": False,
        },
    )
    assert missing_fee.status_code == 422


def test_zero_usage_then_jump_does_not_crash(client, restroom):
    # 跨年排序：12 月 -> 次年 1 月
    create_record(client, restroom["id"], 2023, 12, water_reading=100)
    create_record(client, restroom["id"], 2024, 1, water_reading=100)  # 用量 0
    jumped = create_record(client, restroom["id"], 2024, 2, water_reading=130)  # 上期为 0
    body = jumped.json()
    assert body["water_usage"] == 30.0
    assert body["water_change_pct"] is None
    assert body["water_status"] == "正常"


def test_list_newest_period_first_and_restroom_embedded(client, restroom):
    today = date.today()
    y, m = shift_month(today.year, today.month, -1)
    create_record(client, restroom["id"], y, m, water_reading=100)
    create_record(client, restroom["id"], today.year, today.month, water_reading=110)
    rows = client.get(API, params={"restroom_id": restroom["id"]}).json()["items"]
    assert (rows[0]["period_year"], rows[0]["period_month"]) == (today.year, today.month)
    assert rows[0]["restroom"]["id"] == restroom["id"]
    assert rows[0]["restroom"]["name"] == restroom["name"]
