"""
firebase_groups.py — система груп для розповсюдження схем.
RTDB структура:
  groups/{group_id}/
    name, description, is_open, invite_code
    creator_user_id, creator_nickname, created_at
    members/{user_id}: {nickname, role, joined_at}
    schemes/{drawing_id}: {map_id, map_name, elements, ...}
  user_groups/{user_id}: {group_id: role}
"""
import json
import uuid
import time
import threading
import requests
import config
import firebase_identity
import firebase_reporter

PUBLIC_GROUP_ID = "public"
_group_schemes_cache = {}


def _rtdb_url(path):
    return firebase_reporter._rtdb_url(path)


def _put(path, data, timeout=8):
    return firebase_reporter._put(path, data, timeout)


def _post(path, data, timeout=8):
    return firebase_reporter._post(path, data, timeout)


def _get(path, timeout=10):
    if not firebase_reporter._is_configured():
        return None
    try:
        url = _rtdb_url(path)
        r = requests.get(url, headers=config.HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def create_group(name, description, user_id=None, nickname=None):
    """Створює закриту групу. Повертає (group_id, invite_code) або (None, помилка)."""
    if not firebase_reporter._is_configured():
        return None, "Firebase не налаштовано"

    identity = firebase_identity.get_identity()
    if not identity:
        return None, "Не зареєстровано"

    uid = user_id or identity.get("user_id", "")
    nick = nickname or identity.get("nickname", "")

    if not name or len(name.strip()) < 2:
        return None, "Назва має бути не менше 2 символів"
    name = name.strip()
    if len(name) > 50:
        return None, "Назва має бути не більше 50 символів"

    group_id = str(uuid.uuid4())
    invite_code = uuid.uuid4().hex[:6].upper()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    group_data = {
        "name": name,
        "description": (description or "").strip()[:200],
        "is_open": False,
        "invite_code": invite_code,
        "creator_user_id": uid,
        "creator_nickname": nick,
        "created_at": now,
        "members": {
            uid: {
                "nickname": nick,
                "role": "officer",
                "joined_at": now,
            }
        },
        "schemes": {},
    }

    ok = _put(f"groups/{group_id}", group_data)
    if not ok:
        return None, "Помилка створення групи"

    _put(f"user_groups/{uid}/{group_id}", {"role": "officer", "name": name})
    return group_id, invite_code


def join_group(invite_code, user_id=None, nickname=None):
    """Вступ у групу за інвайт-кодом. Повертає (group_id, group_name) або (None, помилка)."""
    if not firebase_reporter._is_configured():
        return None, "Firebase не налаштовано"

    identity = firebase_identity.get_identity()
    if not identity:
        return None, "Не зареєстровано"

    uid = user_id or identity.get("user_id", "")
    nick = nickname or identity.get("nickname", "")

    if not invite_code or len(invite_code.strip()) < 3:
        return None, "Невірний код"
    invite_code = invite_code.strip().upper()

    groups = _get("groups")
    if not groups:
        return None, "Помилка пошуку груп"

    target_gid = None
    target_name = None
    for gid, gdata in groups.items():
        if not isinstance(gdata, dict):
            continue
        if gdata.get("invite_code") == invite_code:
            target_gid = gid
            target_name = gdata.get("name", "?")
            break

    if not target_gid:
        return None, "Група з таким кодом не знайдена"

    members = groups[target_gid].get("members", {})
    if isinstance(members, dict) and uid in members:
        return target_gid, target_name

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    member_data = {
        "nickname": nick,
        "role": "member",
        "joined_at": now,
    }
    ok = _put(f"groups/{target_gid}/members/{uid}", member_data)
    if not ok:
        return None, "Помилка вступу в групу"

    _put(f"user_groups/{uid}/{target_gid}", {"role": "member", "name": target_name})
    return target_gid, target_name


def leave_group(group_id, user_id=None):
    """Виходить з групи."""
    if not firebase_reporter._is_configured():
        return False

    uid = user_id or firebase_identity.get_user_id()
    if not uid:
        return False

    _put(f"groups/{group_id}/members/{uid}", None)
    _put(f"user_groups/{uid}/{group_id}", None)
    return True


def get_user_groups(user_id=None):
    """Повертає dict {group_id: {role, name}} для користувача.
    Завжди включає PUBLIC_GROUP_ID."""
    uid = user_id or firebase_identity.get_user_id()
    result = {PUBLIC_GROUP_ID: {"role": "member", "name": "Public"}}

    if not uid:
        return result

    data = _get(f"user_groups/{uid}")
    if data and isinstance(data, dict):
        for gid, ginfo in data.items():
            if isinstance(ginfo, dict):
                result[gid] = ginfo
            elif isinstance(ginfo, str):
                result[gid] = {"role": ginfo, "name": gid}
    return result


def get_group_info(group_id):
    """Повертає метадані групи або None."""
    return _get(f"groups/{group_id}")


def _get_scheme_elements(elements_data):
    """Серіалізує elements_data в рядок та повертає кількість елементів."""
    if isinstance(elements_data, list):
        return json.dumps(elements_data, ensure_ascii=False), len(elements_data)
    elif isinstance(elements_data, dict):
        return json.dumps(elements_data, ensure_ascii=False), sum(
            len(v) for v in elements_data.values() if isinstance(v, list))
    elif isinstance(elements_data, str):
        return elements_data, len(json.loads(elements_data))
    return "[]", 0


def publish_to_group(group_id, map_id, map_name, elements_data, comment="", author_id=None, author_nick=None):
    """Публікує схему в групу. Повертає (drawing_id, ok, msg)."""
    if not firebase_reporter._is_configured():
        return None, False, "Firebase не налаштовано"

    identity = firebase_identity.get_identity()
    if not identity:
        return None, False, "Не зареєстровано"

    aid = author_id or identity.get("user_id", "")
    anick = author_nick or identity.get("nickname", "")
    elements_str, el_count = _get_scheme_elements(elements_data)
    drawing_id = str(uuid.uuid4())
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    scheme = {
        "drawing_id": drawing_id,
        "map_id": map_id,
        "map_name": map_name,
        "author_id": aid,
        "author_nickname": anick,
        "elements": elements_str,
        "element_count": el_count,
        "comment": (comment or "")[:500],
        "created_at": now,
        "updated_at": now,
        "updated_by": anick,
        "group_id": group_id,
    }

    ok = _put(f"groups/{group_id}/schemes/{drawing_id}", scheme, timeout=10)
    if not ok:
        return None, False, "Помилка публікації"
    return drawing_id, True, "Опубліковано в групу!"


def update_group_scheme(group_id, drawing_id, elements_data, comment="", updated_by=None):
    """Оновлює існуючу схему в групі (той самий drawing_id)."""
    if not firebase_reporter._is_configured():
        return False, "Firebase не налаштовано"

    identity = firebase_identity.get_identity()
    if not identity:
        return False, "Не зареєстровано"

    ub = updated_by or identity.get("nickname", "")
    elements_str, el_count = _get_scheme_elements(elements_data)
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    path = f"groups/{group_id}/schemes/{drawing_id}"
    existing = _get(path)
    if not existing:
        return False, "Схему не знайдено"

    existing["elements"] = elements_str
    existing["element_count"] = el_count
    existing["updated_at"] = now
    existing["updated_by"] = ub
    if comment:
        existing["comment"] = comment[:500]

    ok = _put(path, existing, timeout=10)
    if not ok:
        return False, "Помилка оновлення"
    return True, "Схему оновлено!"


def get_group_schemes(group_id):
    """Повертає dict {drawing_id: scheme_data} для групи з кешуванням."""
    if group_id in _group_schemes_cache:
        return _group_schemes_cache[group_id]
    data = _get(f"groups/{group_id}/schemes")
    if not data or not isinstance(data, dict):
        _group_schemes_cache[group_id] = {}
        return {}

    result = {}
    for sid, sdata in data.items():
        if not isinstance(sdata, dict):
            continue
        try:
            if isinstance(sdata.get("elements"), str):
                sdata["elements"] = json.loads(sdata["elements"])
        except Exception:
            continue
        result[sid] = sdata
    _group_schemes_cache[group_id] = result
    return result


def invalidate_group_schemes_cache(group_id=None):
    """Очищає кеш схем для групи або весь."""
    if group_id:
        _group_schemes_cache.pop(group_id, None)
    else:
        _group_schemes_cache.clear()


def get_group_schemes_meta(group_id):
    """Повертає {drawing_id: {updated_at, element_count}} — швидка перевірка без elements."""
    data = _get(f"groups/{group_id}/schemes")
    if not data or not isinstance(data, dict):
        return {}
    meta = {}
    for sid, sdata in data.items():
        if not isinstance(sdata, dict):
            continue
        meta[sid] = {
            "updated_at": sdata.get("updated_at", ""),
            "element_count": sdata.get("element_count", 0),
            "map_id": sdata.get("map_id", ""),
            "comment": (sdata.get("comment") or "")[:40],
            "updated_by": sdata.get("updated_by", ""),
        }
    return meta


def get_combined_schemes(group_id=None):
    """Повертає всі схеми, доступні користувачеві: публічні + його груп.
    group_id: якщо задано — тільки цю групу (для download діалогу).
    """
    user_id = firebase_identity.get_user_id()
    schemes = {}

    public_data = _get("schemes")
    if public_data and isinstance(public_data, dict):
        for sid, sdata in public_data.items():
            if isinstance(sdata, dict) and sdata.get("elements"):
                try:
                    if isinstance(sdata.get("elements"), str):
                        sdata["elements"] = json.loads(sdata["elements"])
                except Exception:
                    continue
                sdata["_source"] = "public"
                schemes[sid] = sdata

    if group_id:
        group_schemes = get_group_schemes(group_id)
        for sid, sdata in group_schemes.items():
            sdata["_source"] = group_id
            schemes[f"{group_id}__{sid}"] = sdata
    elif user_id:
        groups = get_user_groups(user_id)
        for gid in groups:
            if gid == PUBLIC_GROUP_ID:
                continue
            group_schemes = get_group_schemes(gid)
            for sid, sdata in group_schemes.items():
                sdata["_source"] = gid
                schemes[f"{gid}__{sid}"] = sdata

    return schemes


def get_user_role_in_group(group_id, user_id=None):
    """Повертає роль користувача в групі: 'officer', 'member' або None."""
    uid = user_id or firebase_identity.get_user_id()
    if not uid:
        return None
    groups = get_user_groups(uid)
    ginfo = groups.get(group_id)
    if ginfo and isinstance(ginfo, dict):
        return ginfo.get("role")
    return None


def delete_group_scheme(group_id, drawing_id):
    """Видаляє схему з групи."""
    if not firebase_reporter._is_configured():
        return False
    return _put(f"groups/{group_id}/schemes/{drawing_id}", None)


def import_between_groups(src_group_id, drawing_id, dst_group_id, author_nick=None):
    """Копіює схему з однієї групи в іншу. Повертає (new_drawing_id, ok, msg)."""
    src_schemes = get_group_schemes(src_group_id)
    src = src_schemes.get(drawing_id)
    if not src:
        return None, False, "Схему не знайдено в джерельній групі"

    identity = firebase_identity.get_identity()
    anick = author_nick or (identity.get("nickname", "") if identity else "")

    elements_data = src.get("elements", [])
    new_id = str(uuid.uuid4())
    elements_str, el_count = _get_scheme_elements(elements_data)
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    scheme = {
        "drawing_id": new_id,
        "map_id": src.get("map_id", ""),
        "map_name": src.get("map_name", ""),
        "author_id": identity.get("user_id", "") if identity else "",
        "author_nickname": anick,
        "elements": elements_str,
        "element_count": el_count,
        "comment": (src.get("comment") or "")[:500],
        "created_at": now,
        "updated_at": now,
        "updated_by": anick,
        "group_id": dst_group_id,
        "original_from": json.dumps({"group_id": src_group_id, "drawing_id": drawing_id}),
    }

    ok = _put(f"groups/{dst_group_id}/schemes/{new_id}", scheme, timeout=10)
    if not ok:
        return None, False, "Помилка імпорту"
    return new_id, True, "Схему імпортовано!"


def refresh_group_membership(user_id=None):
    """Перевіряє та оновлює локальний кеш груп з RTDB.
    Повертає dict {group_id: {role, name}}."""
    uid = user_id or firebase_identity.get_user_id()
    groups = get_user_groups(uid)

    for gid in list(groups.keys()):
        if gid == PUBLIC_GROUP_ID:
            continue
        ginfo = _get(f"groups/{gid}?shallow=true")
        if ginfo is None:
            continue
        members = _get(f"groups/{gid}/members")
        if isinstance(members, dict) and uid in members:
            member_info = members[uid]
            role = member_info.get("role", "member") if isinstance(member_info, dict) else "member"
            gname = (ginfo if isinstance(ginfo, str) else gid)
            groups[gid] = {"role": role, "name": gname}
            _put(f"user_groups/{uid}/{gid}", {"role": role, "name": gname})
        else:
            if gid in groups:
                del groups[gid]
            _put(f"user_groups/{uid}/{gid}", None)

    return groups
