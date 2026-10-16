"""Read-only questions about the apt-leader database (schema `apt`)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from hub_mcp.db import QueryError, Reader, clamp, like_tokens

UNITS_NOTE = (
    "가격(price_manwon, recent_price, price_3m, peak_price, prev_high)은 만원, ppp는 전용면적 평당가(만원/평), "
    "chg_*·from_peak·change_12m은 비율(0.05 = +5%)입니다. 통계는 4층 이상 거래만 씁니다. "
    "band는 전용면적 구간(59/74/84/large), mode=auto는 단지마다 대표 면적대를 쓴 순위입니다. "
    "district_rank.band는 그 면적대만 놓고 본 시군구 순위, district_rank.auto는 apt_leaders 기본(auto) 순위입니다."
)

COMPLEX_SQL = """
select c.id, c.key, c.apt_name, c.umd_name, c.jibun, s.name as sgg_name, c.sgg_code, c.build_year,
       k.households, k.dong_count
from apt.complex c
join apt.sgg s on s.code = c.sgg_code
left join apt.complex_kapt k on k.complex_id = c.id
where c.id = %(id)s
"""

HOME_ID_SQL = "select id from apt.complex where key = %(key)s"

METRICS_SQL = """
select band, recent_ppp, recent_price, ppp_3m, price_3m, trades_12m, chg_1m, chg_3m, chg_6m, chg_12m,
       peak_price, peak_ym, from_peak, as_of_ym
from apt.complex_metric
where complex_id = %(id)s
order by trades_12m desc, band
"""

# Rank within the chosen band and in the `auto` ranking apt_leaders shows by default; they can differ.
RANK_SQL = "select mode, rank from apt.leader_rank where complex_id = %(id)s and mode in (%(band)s, 'auto')"

SERIES_SQL = """
select ym, rolling_ppp, rolling_price, window_trades, volume
from apt.month_series
where complex_id = %(id)s and band = %(band)s
order by ym desc
limit %(months)s
"""

TRADES_SQL = """
select contract_date, price_manwon, area_m2, floor, band
from apt.trade
where complex_id = %(id)s and (%(band)s::text is null or band = %(band)s)
order by contract_date desc
limit 10
"""

SGG_STAT_SQL = """
select leader_ppp, leader_change, leader_n, as_of_ym, record_complexes
from apt.sgg_stat
where sgg_code = %(sgg)s
"""

SEARCH_SQL = """
select c.id, c.apt_name, c.umd_name, s.name as sgg_name, c.build_year,
       coalesce(array_agg(m.band order by m.band) filter (where m.band is not null), '{}') as bands
from apt.complex c
join apt.sgg s on s.code = c.sgg_code
left join apt.complex_metric m on m.complex_id = c.id
where replace(c.apt_name, ' ', '') ilike all(%(likes)s)
  and (%(district_likes)s::text[] is null or replace(s.name, ' ', '') ilike all(%(district_likes)s))
group by c.id, s.name
order by count(m.band) desc, c.apt_name
limit %(limit)s
"""

DISTRICT_SQL = """
select code, name from apt.sgg
where replace(name, ' ', '') ilike all(%(likes)s)
order by name
limit 10
"""

LEADERS_SQL = """
select r.rank, r.complex_id, c.apt_name, c.umd_name, r.band, r.recent_ppp, r.trades_12m, r.change_12m,
       m.price_3m, m.chg_3m, m.from_peak
from apt.leader_rank r
join apt.complex c on c.id = r.complex_id
left join apt.complex_metric m on m.complex_id = r.complex_id and m.band = r.band
where r.sgg_code = %(sgg)s and r.mode = %(mode)s
order by r.rank
limit %(limit)s
"""

RECORDS_SQL = """
select r.contract_date, r.complex_id, c.apt_name, s.name as sgg_name, r.band, r.area_m2, r.floor,
       r.price_manwon, r.prev_high, r.prev_date
from apt.record_trade r
join apt.complex c on c.id = r.complex_id
join apt.sgg s on s.code = r.sgg_code
where r.contract_date >= %(since)s and (%(sgg)s::text is null or r.sgg_code = %(sgg)s)
order by r.contract_date desc, r.price_manwon desc
limit %(limit)s
"""


def complex_detail(db: Reader, complex_id: int, band: str | None, months: int) -> dict[str, Any]:
    info = db.one(COMPLEX_SQL, {"id": complex_id})
    if info is None:
        raise QueryError(f"단지 id {complex_id}를 찾지 못했습니다. apt_search로 먼저 찾아 주세요.")
    metrics = db.all(METRICS_SQL, {"id": complex_id})
    chosen = band or (metrics[0]["band"] if metrics else None)
    ranks = {r["mode"]: r["rank"] for r in db.all(RANK_SQL, {"id": complex_id, "band": chosen})}
    series: list[dict[str, Any]] = []
    if chosen is not None:
        series = list(reversed(db.all(SERIES_SQL, {"id": complex_id, "band": chosen, "months": clamp(months, 1, 60)})))
    return {
        "complex": info,
        "band": chosen,
        "metric": next((m for m in metrics if m["band"] == chosen), None),
        "bands_with_data": [m["band"] for m in metrics],
        "district_rank": {"band": ranks.get(chosen), "auto": ranks.get("auto")},
        "series": series,
        "recent_trades": db.all(TRADES_SQL, {"id": complex_id, "band": chosen}),
        "notes": [UNITS_NOTE],
    }


def my_home(db: Reader, home_key: str | None, home_band: str | None) -> dict[str, Any]:
    if not home_key:
        raise QueryError("APT_HOME_KEY가 설정되지 않았습니다. my-hub/.env를 확인해 주세요.")
    row = db.one(HOME_ID_SQL, {"key": home_key})
    if row is None:
        raise QueryError(f"내 집 단지({home_key})를 apt-leader 데이터에서 찾지 못했습니다.")
    detail = complex_detail(db, row["id"], home_band, 24)
    return {"is_home": True, **detail, "district_stat": db.one(SGG_STAT_SQL, {"sgg": detail["complex"]["sgg_code"]})}


def search(db: Reader, name: str, district: str | None, limit: int) -> dict[str, Any]:
    params = {
        "likes": like_tokens(name),
        "district_likes": like_tokens(district) if district and district.strip() else None,
        "limit": clamp(limit, 1, 20),
    }
    return {"complexes": db.all(SEARCH_SQL, params)}


def resolve_district(db: Reader, name: str) -> dict[str, Any]:
    rows = db.all(DISTRICT_SQL, {"likes": like_tokens(name)})
    if not rows:
        raise QueryError(f"'{name}' 시군구를 찾지 못했습니다. 예: '분당구', '서울 강남구'.")
    if len(rows) > 1:
        names = ", ".join(r["name"] for r in rows)
        raise QueryError(f"'{name}'에 해당하는 시군구가 여러 개입니다: {names}. 시·도까지 함께 적어 주세요.")
    return rows[0]


def leaders(db: Reader, district: str, mode: str, limit: int) -> dict[str, Any]:
    sgg = resolve_district(db, district)
    return {
        "district": sgg,
        "mode": mode,
        "district_stat": db.one(SGG_STAT_SQL, {"sgg": sgg["code"]}),
        "leaders": db.all(LEADERS_SQL, {"sgg": sgg["code"], "mode": mode, "limit": clamp(limit, 1, 30)}),
        "notes": [UNITS_NOTE],
    }


def records(db: Reader, days: int, district: str | None, limit: int, today: date) -> dict[str, Any]:
    sgg = resolve_district(db, district) if district and district.strip() else None
    since = today - timedelta(days=clamp(days, 1, 92))
    rows = db.all(RECORDS_SQL, {"since": since, "sgg": sgg["code"] if sgg else None, "limit": clamp(limit, 1, 50)})
    return {"since": since.isoformat(), "district": sgg, "records": rows, "notes": [UNITS_NOTE]}
