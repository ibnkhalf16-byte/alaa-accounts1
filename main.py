# -*- coding: utf-8 -*-
from datetime import datetime
import flet as ft
from flet import Colors, Icons
from supabase import create_client, Client
import hashlib
import hmac
import os

# =========================================================
# الربط السحابي (Supabase)
# =========================================================
SUPABASE_URL = "https://moccsagndofjwtjmqtdd.supabase.co"
SUPABASE_KEY = "sb_publishable_L-mFR01JF4qMRQXm16Mr2A_CqDxCZo0"

try:
    db: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception:
    db = None

DEFAULT_PASSWORD = "1234"

# =========================================================
# أدوات الحساب والتنسيق وكلمة المرور من الكود الأصلي
# =========================================================
def today():
    return datetime.now().strftime("%Y-%m-%d")

def money(value):
    try:
        return f"{float(value):,.2f}"
    except Exception:
        return "0.00"

def num_text(value):
    try:
        number = float(value)
        return f"{number:,.2f}".rstrip("0").rstrip(".")
    except Exception:
        return "0"

def clean_number(value):
    return str(value).strip().replace(",", "").replace("،", "")

def get_number(value, label, allow_zero=False):
    try:
        text = clean_number(value)
        if text == "":
            raise ValueError
        number = float(text)
        if number < 0:
            raise ValueError
        if not allow_zero and number <= 0:
            raise ValueError
        return number
    except Exception:
        raise ValueError(f"أدخل {label} بشكل صحيح.")

def normalize_item(value):
    return " ".join(str(value or "").strip().lower().split())

def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
    return salt.hex() + ":" + digest.hex()

def verify_password(password, stored):
    try:
        salt_hex, digest_hex = stored.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False

# =========================================================
# واجهة التطبيق
# =========================================================
def main(page: ft.Page):
    page.title = "حسابات علاء أبو شادي"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.rtl = True
    page.padding = 0
    page.bgcolor = "#F8FAFC"

    def notify(msg, is_error=False):
        page.snack_bar = ft.SnackBar(
            content=ft.Text(msg, color=Colors.WHITE, size=13, weight=ft.FontWeight.BOLD),
            bgcolor=Colors.RED_700 if is_error else Colors.GREEN_700,
            duration=3500
        )
        page.snack_bar.open = True
        page.update()

    # --- استعلامات قاعدة البيانات السحابية ---
    def get_setting(key):
        try:
            res = db.table("settings").select("value").eq("key", key).execute().data
            if res:
                return res[0]["value"]
            if key == "password_hash":
                h = hash_password(DEFAULT_PASSWORD)
                db.table("settings").insert({"key": key, "value": h}).execute()
                return h
        except Exception:
            return hash_password(DEFAULT_PASSWORD)
        return None

    def set_setting(key, value):
        try:
            db.table("settings").upsert({"key": key, "value": value}).execute()
        except Exception as err:
            notify(f"خطأ حفظ الإعدادات: {err}", is_error=True)

    def fetch_persons():
        try:
            return db.table("persons").select("*").order("name").execute().data or []
        except Exception as err:
            notify(f"خطأ جلب الأشخاص: {err}", is_error=True)
            return []

    def fetch_trips():
        try:
            return db.table("trips").select("*, persons(name)").order("date").order("id").execute().data or []
        except Exception as err:
            notify(f"خطأ جلب النقلات: {err}", is_error=True)
            return []

    def fetch_payments():
        try:
            return db.table("payments").select("*, persons(name)").order("date").order("id").execute().data or []
        except Exception as err:
            notify(f"خطأ جلب السدادات: {err}", is_error=True)
            return []

    # =====================================================
    # التحقق وكلمة المرور
    # =====================================================
    def ask_auth(action_name, callback):
        pwd_box = ft.TextField(label="كلمة المرور", password=True, can_reveal_password=True, autofocus=True)
        dlg = ft.AlertDialog(
            title=ft.Text("حماية العمليات", weight=ft.FontWeight.BOLD),
            content=ft.Column([
                ft.Text(f"أدخل كلمة المرور للسماح بـ {action_name}:", size=13),
                pwd_box
            ], tight=True, spacing=10),
            actions=[
                ft.TextButton("إلغاء", on_click=lambda e: page.close(dlg)),
                ft.ElevatedButton("تأكيد", on_click=lambda e: confirm_auth(pwd_box.value, dlg, callback), bgcolor=Colors.BLUE_700, color=Colors.WHITE)
            ]
        )
        def confirm_auth(entered, dialog, cb):
            stored = get_setting("password_hash")
            if verify_password(entered or "", stored):
                page.close(dialog)
                cb()
            else:
                notify("كلمة المرور غير صحيحة!", is_error=True)
        page.open(dlg)

    # =====================================================
    # خوارزمية متابعة شراء وبيع الأوزان (من ملف نهائي تماماً)
    # =====================================================
    def trip_statuses():
        rows = fetch_trips()
        purchases = {
            row["id"]: {
                "weight": float(row["weight"] or 0),
                "remaining": float(row["weight"] or 0),
                "item": normalize_item(row["item"]),
            }
            for row in rows
            if row["operation"] == "purchase"
        }

        sold = {trip_id: 0.0 for trip_id in purchases}
        matched = {row["id"]: 0.0 for row in rows}
        statuses = {}

        # 1. النقلات المرتبطة مباشرة
        linked_sales = [
            row for row in rows
            if row["operation"] == "sale"
            and row.get("source_trip_id")
        ]
        linked_sales.sort(key=lambda r: (r["date"], r["id"]))

        for sale in linked_sales:
            source_id = int(sale["source_trip_id"])
            purchase = purchases.get(source_id)

            if not purchase:
                statuses[sale["id"]] = "مباع بدون شراء: مصدر النقلة غير موجود"
                continue

            sale_weight = max(float(sale["weight"] or 0), 0.0)
            take = min(sale_weight, purchase["remaining"])

            purchase["remaining"] -= take
            sold[source_id] += take
            matched[sale["id"]] += take
            remaining_sale = sale_weight - take

            if remaining_sale <= 0.000000001:
                statuses[sale["id"]] = "تم شراء الوزنة"
            elif take > 0.000000001:
                statuses[sale["id"]] = f"جزء بدون شراء: {num_text(remaining_sale)} طن"
            else:
                statuses[sale["id"]] = f"مباع بدون شراء: {num_text(remaining_sale)} طن"

        # 2. النقلات المباعة بدون ربط مباشر (FIFO)
        queues = {}
        for row in rows:
            if row["operation"] != "purchase":
                continue
            item = normalize_item(row["item"])
            queues.setdefault(item, []).append(row["id"])

        for sale in rows:
            if sale["operation"] != "sale" or sale.get("source_trip_id"):
                continue

            item = normalize_item(sale["item"])
            queue = queues.get(item, [])
            need = max(float(sale["weight"] or 0), 0.0)

            while need > 0.000000001 and queue:
                purchase_id = queue[0]
                purchase = purchases[purchase_id]

                if purchase["remaining"] <= 0.000000001:
                    queue.pop(0)
                    continue

                take = min(need, purchase["remaining"])
                purchase["remaining"] -= take
                need -= take
                sold[purchase_id] += take
                matched[sale["id"]] += take

                if purchase["remaining"] <= 0.000000001:
                    queue.pop(0)

            if need <= 0.000000001:
                statuses[sale["id"]] = "تم شراء الوزنة"
            elif matched[sale["id"]] > 0.000000001:
                statuses[sale["id"]] = f"جزء بدون شراء: {num_text(need)} طن"
            else:
                statuses[sale["id"]] = "لم يتم شراء هذه الوزنة"

        # 3. حالة كل نقلة شراء
        for row in rows:
            if row["operation"] != "purchase":
                continue
            remaining = purchases[row["id"]]["remaining"]
            sold_weight = sold.get(row["id"], 0.0)

            if remaining <= 0.000000001:
                statuses[row["id"]] = "تم بيع الوزنة"
            elif sold_weight <= 0.000000001:
                statuses[row["id"]] = "لم يتم بيع هذه الوزنة"
            else:
                statuses[row["id"]] = f"متبقي للبيع: {num_text(remaining)} طن"

        return statuses

    # =====================================================
    # رصيد كل شخص (حسابات نهائي بدقة)
    # =====================================================
    def get_person_balance(person_id, person_data, trips_data, payments_data):
        sales = sum(float(t["total"]) for t in trips_data if t["person_id"] == person_id and t["operation"] == "sale")
        purchases = sum(float(t["total"]) for t in trips_data if t["person_id"] == person_id and t["operation"] == "purchase")
        from_customer = sum(float(p["amount"]) for p in payments_data if p["person_id"] == person_id and p["direction"] == "from_customer")
        to_supplier = sum(float(p["amount"]) for p in payments_data if p["person_id"] == person_id and p["direction"] == "to_supplier")

        opening_receivable = float(person_data.get("opening_receivable") or 0)
        opening_payable = float(person_data.get("opening_payable") or 0)

        receivable = opening_receivable + sales - from_customer
        payable = opening_payable + purchases - to_supplier
        net = receivable - payable

        return {
            "sales": sales,
            "purchases": purchases,
            "from_customer": from_customer,
            "to_supplier": to_supplier,
            "opening_receivable": opening_receivable,
            "opening_payable": opening_payable,
            "receivable": receivable,
            "payable": payable,
            "net": net
        }

    # =====================================================
    # أحداث كشف الحساب والترتيب الدقيق
    # =====================================================
    def statement_events(person_id, person, trips, payments):
        events = []
        opening_receivable = float(person.get("opening_receivable") or 0)
        opening_payable = float(person.get("opening_payable") or 0)

        if opening_receivable > 0:
            events.append({
                "date": "قبل البداية", "id": -2, "type": "رصيد أول المدة", "desc": "رصيد أول المدة للعميل",
                "vehicle": "", "driver": "", "weight": 0, "price": 0, "debit": opening_receivable, "credit": 0
            })
        if opening_payable > 0:
            events.append({
                "date": "قبل البداية", "id": -1, "type": "رصيد أول المدة", "desc": "رصيد أول المدة للمورد",
                "vehicle": "", "driver": "", "weight": 0, "price": 0, "debit": 0, "credit": opening_payable
            })

        for trip in trips:
            if trip["person_id"] != person_id:
                continue
            if trip["operation"] == "sale":
                events.append({
                    "date": trip["date"], "id": trip["id"] * 2, "type": "بيع", "desc": trip["item"],
                    "vehicle": trip.get("vehicle") or "", "driver": trip.get("driver") or "",
                    "weight": trip["weight"], "price": trip["price"], "debit": trip["total"], "credit": 0
                })
            else:
                events.append({
                    "date": trip["date"], "id": trip["id"] * 2, "type": "شراء", "desc": trip["item"],
                    "vehicle": trip.get("vehicle") or "", "driver": trip.get("driver") or "",
                    "weight": trip["weight"], "price": trip["price"], "debit": 0, "credit": trip["total"]
                })

        for payment in payments:
            if payment["person_id"] != person_id:
                continue
            if payment["direction"] == "from_customer":
                desc = "سداد نقدي من العميل" if payment["payment_type"] == "cash" else f"نقلة سداد من العميل - {payment.get('item') or ''}"
                events.append({
                    "date": payment["date"], "id": 100000000 + payment["id"], "type": "سداد من العميل",
                    "desc": desc, "vehicle": payment.get("vehicle") or "", "driver": payment.get("driver") or "",
                    "weight": payment.get("weight") or 0, "price": payment.get("price") or 0,
                    "debit": 0, "credit": payment["amount"]
                })
            else:
                desc = "سداد نقدي للمورد" if payment["payment_type"] == "cash" else f"نقلة سداد للمورد - {payment.get('item') or ''}"
                events.append({
                    "date": payment["date"], "id": 100000000 + payment["id"], "type": "سداد للمورد",
                    "desc": desc, "vehicle": payment.get("vehicle") or "", "driver": payment.get("driver") or "",
                    "weight": payment.get("weight") or 0, "price": payment.get("price") or 0,
                    "debit": payment["amount"], "credit": 0
                })

        def statement_sort_key(event):
            if event["date"] == "قبل البداية":
                return (0, datetime.min, int(event.get("id") or 0))
            try:
                event_date = datetime.strptime(str(event["date"]), "%Y-%m-%d")
            except Exception:
                event_date = datetime.max
            return (1, event_date, int(event.get("id") or 0))

        events.sort(key=statement_sort_key)
        return events

    # الترويسة الموحدة
    def header_bar(title, subtitle):
        return ft.Container(
            content=ft.Column([
                ft.Text(title, size=18, weight=ft.FontWeight.BOLD, color=Colors.WHITE),
                ft.Text(subtitle, size=11, color=Colors.BLUE_GREY_100),
            ], spacing=1),
            bgcolor="#1E293B",
            padding=ft.padding.only(left=18, right=18, top=12, bottom=12),
            border_radius=ft.border_radius.only(bottom_left=14, bottom_right=14),
            shadow=ft.BoxShadow(blur_radius=5, color=Colors.BLACK12)
        )

    # =====================================================
    # 1. شاشة الرئيسية (لوحة الحسابات العامة)
    # =====================================================
    def view_dashboard():
        persons = fetch_persons()
        trips = fetch_trips()
        payments = fetch_payments()

        sales = sum(float(t["total"]) for t in trips if t["operation"] == "sale")
        purchases = sum(float(t["total"]) for t in trips if t["operation"] == "purchase")

        receivable = 0
        payable = 0
        for p in persons:
            b = get_person_balance(p["id"], p, trips, payments)
            receivable += max(0, b["receivable"])
            payable += max(0, b["payable"])

        def stat_box(title, val_str, icon, color):
            return ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Icon(icon, color=color, size=24),
                        bgcolor=ft.colors.with_opacity(0.12, color),
                        padding=10,
                        border_radius=10
                    ),
                    ft.Column([
                        ft.Text(title, size=11, color=Colors.BLUE_GREY_600),
                        ft.Text(val_str, size=16, weight=ft.FontWeight.BOLD, color=Colors.BLUE_GREY_900),
                    ], spacing=1, expand=True)
                ]),
                bgcolor=Colors.WHITE,
                padding=12,
                border_radius=10,
                border=ft.border.all(1, "#E2E8F0"),
                shadow=ft.BoxShadow(blur_radius=3, color=Colors.BLACK12)
            )

        return ft.Column([
            header_bar("📊 لوحة الحسابات العامة", "ملخص سريع للمبيعات والمشتريات والمبالغ المستحقة"),
            ft.Container(
                content=ft.Column([
                    stat_box("إجمالي المبيعات", f"{money(sales)} ج.م", Icons.ARROW_UPWARD_ROUNDED, Colors.GREEN_700),
                    stat_box("إجمالي المشتريات", f"{money(purchases)} ج.م", Icons.ARROW_DOWNWARD_ROUNDED, Colors.ORANGE_800),
                    stat_box("مستحقات العملاء (لك)", f"{money(receivable)} ج.م", Icons.ACCOUNT_BALANCE_WALLET_ROUNDED, Colors.BLUE_700),
                    stat_box("مستحقات الموردين (عليك)", f"{money(payable)} ج.م", Icons.PAYMENTS_ROUNDED, Colors.RED_700),
                    stat_box("إجمالي الأشخاص المسجلين", f"{len(persons)} طرف", Icons.PEOPLE_ALT_ROUNDED, Colors.PURPLE_700),
                ], spacing=8),
                padding=14
            )
        ], scroll=ft.ScrollMode.AUTO, expand=True)

    # =====================================================
    # 2. شاشة العملاء والموردين
    # =====================================================
    def view_persons():
        persons = fetch_persons()
        trips = fetch_trips()
        payments = fetch_payments()

        name_in = ft.TextField(label="الاسم", bgcolor=Colors.WHITE, border_color="#CBD5E1")
        phone_in = ft.TextField(label="الهاتف", keyboard_type=ft.KeyboardType.PHONE, bgcolor=Colors.WHITE, border_color="#CBD5E1")
        address_in = ft.TextField(label="العنوان", bgcolor=Colors.WHITE, border_color="#CBD5E1")
        notes_in = ft.TextField(label="ملاحظات", bgcolor=Colors.WHITE, border_color="#CBD5E1")
        rec_in = ft.TextField(label="رصيد أول المدة: للعميل عندك", value="0", keyboard_type=ft.KeyboardType.NUMBER, bgcolor=Colors.WHITE, border_color="#CBD5E1", expand=True)
        pay_in = ft.TextField(label="رصيد أول المدة: عليك للمورد", value="0", keyboard_type=ft.KeyboardType.NUMBER, bgcolor=Colors.WHITE, border_color="#CBD5E1", expand=True)

        edit_id = [None]
        save_btn = ft.ElevatedButton("حفظ شخص جديد", icon=Icons.SAVE_ROUNDED, bgcolor=Colors.GREEN_700, color=Colors.WHITE, height=44, width=page.width)

        def save_person(e):
            if not name_in.value or not name_in.value.strip():
                notify("اكتب اسم الشخص.", is_error=True); return
            try:
                rec_val = get_number(rec_in.value, "رصيد أول المدة للعميل", True)
                pay_val = get_number(pay_in.value, "رصيد أول المدة للمورد", True)

                if edit_id[0]:
                    db.table("persons").update({
                        "name": name_in.value.strip(),
                        "phone": phone_in.value.strip() if phone_in.value else "",
                        "address": address_in.value.strip() if address_in.value else "",
                        "notes": notes_in.value.strip() if notes_in.value else "",
                        "opening_receivable": rec_val,
                        "opening_payable": pay_val
                    }).eq("id", edit_id[0]).execute()
                    notify("تم تعديل الشخص.")
                else:
                    db.table("persons").insert({
                        "name": name_in.value.strip(),
                        "phone": phone_in.value.strip() if phone_in.value else "",
                        "address": address_in.value.strip() if address_in.value else "",
                        "notes": notes_in.value.strip() if notes_in.value else "",
                        "opening_receivable": rec_val,
                        "opening_payable": pay_val
                    }).execute()
                    notify("تم حفظ الشخص بنجاح.")

                refresh_content()
            except Exception as err:
                notify(f"خطأ: {err}", is_error=True)

        save_btn.on_click = save_person

        def start_edit(p):
            ask_auth("تعديل بيانات الشخص", lambda: apply_edit(p))

        def apply_edit(p):
            edit_id[0] = p["id"]
            name_in.value = p["name"]
            phone_in.value = p.get("phone") or ""
            address_in.value = p.get("address") or ""
            notes_in.value = p.get("notes") or ""
            rec_in.value = num_text(p.get("opening_receivable") or 0)
            pay_in.value = num_text(p.get("opening_payable") or 0)
            save_btn.text = "حفظ تعديل الشخص"
            page.update()

        def start_delete(p_id):
            ask_auth("حذف الشخص", lambda: apply_delete(p_id))

        def apply_delete(p_id):
            has_trips = any(t["person_id"] == p_id for t in trips)
            has_payments = any(p["person_id"] == p_id for p in payments)
            if has_trips or has_payments:
                notify("لا يمكن الحذف: هذا الشخص لديه بيانات مالية مسجلة.", is_error=True); return
            try:
                db.table("persons").delete().eq("id", p_id).execute()
                notify("تم حذف الشخص.")
                refresh_content()
            except Exception as err:
                notify(f"خطأ في الحذف: {err}", is_error=True)

        persons_cards = ft.Column(spacing=8)
        for p in persons:
            b = get_person_balance(p["id"], p, trips, payments)
            persons_cards.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text(p["name"], weight=ft.FontWeight.BOLD, size=14),
                            ft.Row([
                                ft.IconButton(Icons.EDIT_ROUNDED, icon_size=18, icon_color=Colors.BLUE_700, on_click=lambda e, pr=p: start_edit(pr)),
                                ft.IconButton(Icons.DELETE_ROUNDED, icon_size=18, icon_color=Colors.RED_700, on_click=lambda e, pid=p["id"]: start_delete(pid)),
                            ], spacing=0)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Text(f"له عند العميل: {money(b['receivable'])} | عليه للمورد: {money(b['payable'])}", size=11, color=Colors.GREY_700),
                        ft.Text(f"صافي الحساب: {money(b['net'])} ج.م", size=12, weight=ft.FontWeight.BOLD, color=Colors.BLUE_900),
                    ], spacing=2),
                    bgcolor=Colors.WHITE,
                    padding=10,
                    border_radius=8,
                    border=ft.border.all(1, "#E2E8F0")
                )
            )

        return ft.Column([
            header_bar("👥 العملاء والموردون", "تسجيل ومتابعة الأطراف وأرصدة أول المدة"),
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Column([
                            name_in,
                            phone_in,
                            address_in,
                            notes_in,
                            ft.Row([rec_in, pay_in], spacing=8),
                            save_btn
                        ], spacing=8),
                        bgcolor=Colors.WHITE,
                        padding=12,
                        border_radius=10,
                        border=ft.border.all(1, "#E2E8F0")
                    ),
                    ft.Text("قائمة الأشخاص والأرصدة:", size=13, weight=ft.FontWeight.BOLD, color=Colors.BLUE_GREY_800),
                    persons_cards
                ], spacing=12),
                padding=14
            )
        ], scroll=ft.ScrollMode.AUTO, expand=True)

    # =====================================================
    # 3. شاشة النقلات (شراء / بيع / بيع النقلة المشتراة)
    # =====================================================
    def view_trips():
        persons = fetch_persons()
        trips = fetch_trips()
        statuses = trip_statuses()

        person_dd = ft.Dropdown(
            label="الطرف",
            options=[ft.dropdown.Option(key=str(p["id"]), text=p["name"]) for p in persons],
            bgcolor=Colors.WHITE,
            border_color="#CBD5E1"
        )
        op_choice = ft.SegmentedButton(
            selected={"purchase"},
            allow_multiple_selection=False,
            segments=[
                ft.Segment(value="purchase", label=ft.Text("شراء من مورد")),
                ft.Segment(value="sale", label=ft.Text("بيع لعميل")),
            ]
        )
        date_txt = ft.TextField(label="التاريخ", value=today(), bgcolor=Colors.WHITE, border_color="#CBD5E1")
        car_txt = ft.TextField(label="رقم السيارة", bgcolor=Colors.WHITE, border_color="#CBD5E1", expand=True)
        driver_txt = ft.TextField(label="السائق", bgcolor=Colors.WHITE, border_color="#CBD5E1", expand=True)
        item_txt = ft.TextField(label="البضاعة", bgcolor=Colors.WHITE, border_color="#CBD5E1")
        weight_txt = ft.TextField(label="الوزن بالطن", keyboard_type=ft.KeyboardType.NUMBER, bgcolor=Colors.WHITE, border_color="#CBD5E1", expand=True)
        price_txt = ft.TextField(label="سعر الطن", keyboard_type=ft.KeyboardType.NUMBER, bgcolor=Colors.WHITE, border_color="#CBD5E1", expand=True)
        total_txt = ft.TextField(label="الإجمالي", value="0.00", read_only=True, bgcolor=Colors.WHITE, border_color="#CBD5E1")
        notes_txt = ft.TextField(label="ملاحظات", bgcolor=Colors.WHITE, border_color="#CBD5E1")

        edit_trip_id = [None]
        save_btn = ft.ElevatedButton("حفظ النقلة", icon=Icons.SAVE_ROUNDED, bgcolor=Colors.GREEN_700, color=Colors.WHITE, height=44, width=page.width)

        def calc_trip(e):
            try:
                w = float(clean_number(weight_txt.value) or 0)
                p = float(clean_number(price_txt.value) or 0)
                total_txt.value = money(w * p)
            except Exception:
                total_txt.value = "0.00"
            page.update()

        weight_txt.on_change = calc_trip
        price_txt.on_change = calc_trip

        def submit_trip(e):
            if not person_dd.value:
                notify("اختر الطرف.", is_error=True); return
            if not item_txt.value or not item_txt.value.strip():
                notify("اكتب نوع البضاعة.", is_error=True); return

            try:
                w = get_number(weight_txt.value, "الوزن بالطن")
                p = get_number(price_txt.value, "سعر الطن")
                tot = round(w * p, 2)
                op = list(op_choice.selected)[0]

                data_payload = {
                    "person_id": int(person_dd.value),
                    "operation": op,
                    "date": date_txt.value.strip(),
                    "vehicle": car_txt.value.strip() if car_txt.value else "",
                    "driver": driver_txt.value.strip() if driver_txt.value else "",
                    "item": item_txt.value.strip(),
                    "weight": w,
                    "price": p,
                    "total": tot,
                    "notes": notes_txt.value.strip() if notes_txt.value else ""
                }

                if edit_trip_id[0]:
                    db.table("trips").update(data_payload).eq("id", edit_trip_id[0]).execute()
                    notify("تم تعديل النقلة بنجاح.")
                else:
                    db.table("trips").insert(data_payload).execute()
                    notify("تم حفظ النقلة بنجاح.")

                refresh_content()
            except Exception as err:
                notify(f"خطأ: {err}", is_error=True)

        save_btn.on_click = submit_trip

        def start_edit_trip(t):
            ask_auth("تعديل النقلة", lambda: apply_edit_trip(t))

        def apply_edit_trip(t):
            edit_trip_id[0] = t["id"]
            person_dd.value = str(t["person_id"])
            op_choice.selected = {t["operation"]}
            date_txt.value = t["date"]
            car_txt.value = t.get("vehicle") or ""
            driver_txt.value = t.get("driver") or ""
            item_txt.value = t["item"]
            weight_txt.value = num_text(t["weight"])
            price_txt.value = num_text(t["price"])
            total_txt.value = money(t["total"])
            notes_txt.value = t.get("notes") or ""
            save_btn.text = "حفظ تعديل النقلة"
            page.update()

        def start_delete_trip(tid):
            ask_auth("حذف النقلة", lambda: apply_delete_trip(tid))

        def apply_delete_trip(tid):
            try:
                db.table("trips").delete().eq("id", tid).execute()
                notify("تم حذف النقلة.")
                refresh_content()
            except Exception as err:
                notify(f"خطأ في الحذف: {err}", is_error=True)

        # نافذة بيع النقلة المشتراة لعميل
        def sell_selected_purchase(trip):
            if trip["operation"] != "purchase":
                notify("يجب اختيار نقلة من نوع شراء من مورد.", is_error=True); return

            st = statuses.get(trip["id"], "")
            remaining = float(trip["weight"])
            if st.startswith("متبقي للبيع:"):
                try:
                    remaining = float(clean_number(st.replace("متبقي للبيع:", "").replace("طن", "").strip()))
                except Exception:
                    remaining = 0.0
            elif st == "تم بيع الوزنة":
                remaining = 0.0

            if remaining <= 0.000000001:
                notify("هذه النقلة تم بيعها بالكامل ولا يوجد وزن متاح للبيع.", is_error=True); return

            cust_dd = ft.Dropdown(label="العميل", options=[ft.dropdown.Option(key=str(p["id"]), text=p["name"]) for p in persons])
            w_box = ft.TextField(label="الوزن المباع (طن)", value=num_text(remaining), keyboard_type=ft.KeyboardType.NUMBER)
            sp_box = ft.TextField(label="سعر بيع الطن", keyboard_type=ft.KeyboardType.NUMBER)

            dlg = ft.AlertDialog(
                title=ft.Text("بيع النقلة المشتراة لعميل", weight=ft.FontWeight.BOLD),
                content=ft.Column([
                    cust_dd, w_box, sp_box
                ], tight=True, spacing=8),
                actions=[
                    ft.TextButton("إلغاء", on_click=lambda e: page.close(dlg)),
                    ft.ElevatedButton("تأكيد البيع", on_click=lambda e: confirm_sell(dlg, trip, cust_dd.value, w_box.value, sp_box.value, remaining), bgcolor=Colors.GREEN_700, color=Colors.WHITE)
                ]
            )
            page.open(dlg)

        def confirm_sell(dialog, purchase_trip, cust_id, w_val, sp_val, rem_avail):
            if not cust_id:
                notify("اختر العميل.", is_error=True); return
            try:
                weight = get_number(w_val, "الوزن المباع")
                sale_price = get_number(sp_val, "سعر بيع الطن")
            except ValueError as err:
                notify(str(err), is_error=True); return

            if weight <= 0 or weight > rem_avail + 0.000000001:
                notify("الوزن المباع يجب أن يكون أكبر من صفر ولا يتجاوز الوزن المتاح.", is_error=True); return

            def do_sell():
                page.close(dialog)
                tot = round(weight * sale_price, 2)
                try:
                    db.table("trips").insert({
                        "person_id": int(cust_id),
                        "operation": "sale",
                        "date": today(),
                        "vehicle": purchase_trip.get("vehicle") or "",
                        "driver": purchase_trip.get("driver") or "",
                        "item": purchase_trip["item"],
                        "weight": weight,
                        "price": sale_price,
                        "total": tot,
                        "notes": "بيع مباشر من نقلة مشتراة",
                        "source_trip_id": purchase_trip["id"]
                    }).execute()
                    notify("تم بيع النقلة للعميل بنجاح.")
                    refresh_content()
                except Exception as err:
                    notify(f"خطأ في البيع: {err}", is_error=True)

            ask_auth("بيع النقلة", do_sell)

        trips_list = ft.Column(spacing=8)
        for t in reversed(trips):
            st = statuses.get(t["id"], "")
            is_sale = t["operation"] == "sale"
            p_name = t.get("persons", {}).get("name") if t.get("persons") else "طرف"

            trips_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text(f"#{t['id']} | {p_name} ({'بيع لعميل' if is_sale else 'شراء من مورد'})", weight=ft.FontWeight.BOLD, size=13),
                            ft.Row([
                                ft.IconButton(Icons.FORWARD_ROUNDED, icon_size=18, icon_color=Colors.GREEN_700, tooltip="بيع النقلة", on_click=lambda e, tr=t: sell_selected_purchase(tr)) if not is_sale else ft.Container(),
                                ft.IconButton(Icons.EDIT_ROUNDED, icon_size=18, icon_color=Colors.BLUE_700, on_click=lambda e, tr=t: start_edit_trip(tr)),
                                ft.IconButton(Icons.DELETE_ROUNDED, icon_size=18, icon_color=Colors.RED_700, on_click=lambda e, tid=t["id"]: start_delete_trip(tid)),
                            ], spacing=0)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Text(f"{t['item']} | {num_text(t['weight'])} طن × {money(t['price'])} = {money(t['total'])} ج.م", size=11, color=Colors.GREY_800),
                        ft.Row([
                            ft.Text(f"التاريخ: {t['date']}", size=10, color=Colors.GREY_600),
                            ft.Text(f"حالة النقلة: {st}", size=11, weight=ft.FontWeight.BOLD, color=Colors.GREEN_700 if "تم" in st else (Colors.ORANGE_800 if "متبقي" in st else Colors.RED_700)),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                    ], spacing=2),
                    bgcolor=Colors.WHITE,
                    padding=10,
                    border_radius=8,
                    border=ft.border.all(1, "#E2E8F0")
                )
            )

        return ft.Column([
            header_bar("🚚 النقلات", "تسجيل شراء وبيع النقلات مع متابعة حالة الأوزان"),
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Column([
                            person_dd,
                            op_choice,
                            date_txt,
                            ft.Row([car_txt, driver_txt], spacing=8),
                            item_txt,
                            ft.Row([weight_txt, price_txt], spacing=8),
                            total_txt,
                            notes_txt,
                            save_btn
                        ], spacing=8),
                        bgcolor=Colors.WHITE,
                        padding=12,
                        border_radius=10,
                        border=ft.border.all(1, "#E2E8F0")
                    ),
                    ft.Text("قائمة النقلات وحالاتها:", size=13, weight=ft.FontWeight.BOLD, color=Colors.BLUE_GREY_800),
                    trips_list
                ], spacing=12),
                padding=14
            )
        ], scroll=ft.ScrollMode.AUTO, expand=True)

    # =====================================================
    # 4. شاشة السداد
    # =====================================================
    def view_payments():
        persons = fetch_persons()
        payments = fetch_payments()

        person_dd = ft.Dropdown(
            label="الطرف",
            options=[ft.dropdown.Option(key=str(p["id"]), text=p["name"]) for p in persons],
            bgcolor=Colors.WHITE,
            border_color="#CBD5E1"
        )
        type_choice = ft.SegmentedButton(
            selected={"cash"},
            allow_multiple_selection=False,
            segments=[
                ft.Segment(value="cash", label=ft.Text("نقدي")),
                ft.Segment(value="trip", label=ft.Text("نقلة")),
            ]
        )
        dir_choice = ft.SegmentedButton(
            selected={"to_supplier"},
            allow_multiple_selection=False,
            segments=[
                ft.Segment(value="to_supplier", label=ft.Text("سداد لمورد")),
                ft.Segment(value="from_customer", label=ft.Text("سداد من عميل")),
            ]
        )
        date_txt = ft.TextField(label="التاريخ", value=today(), bgcolor=Colors.WHITE, border_color="#CBD5E1")
        amount_txt = ft.TextField(label="المبلغ", keyboard_type=ft.KeyboardType.NUMBER, bgcolor=Colors.WHITE, border_color="#CBD5E1")
        car_txt = ft.TextField(label="رقم السيارة", bgcolor=Colors.WHITE, border_color="#CBD5E1", expand=True)
        driver_txt = ft.TextField(label="السائق", bgcolor=Colors.WHITE, border_color="#CBD5E1", expand=True)
        item_txt = ft.TextField(label="البضاعة", bgcolor=Colors.WHITE, border_color="#CBD5E1")
        weight_txt = ft.TextField(label="الوزن بالطن", keyboard_type=ft.KeyboardType.NUMBER, bgcolor=Colors.WHITE, border_color="#CBD5E1", expand=True)
        price_txt = ft.TextField(label="سعر الطن", keyboard_type=ft.KeyboardType.NUMBER, bgcolor=Colors.WHITE, border_color="#CBD5E1", expand=True)
        desc_txt = ft.TextField(label="الوصف", bgcolor=Colors.WHITE, border_color="#CBD5E1")

        edit_pay_id = [None]
        save_btn = ft.ElevatedButton("حفظ السداد", icon=Icons.SAVE_ROUNDED, bgcolor=Colors.GREEN_700, color=Colors.WHITE, height=44, width=page.width)

        def calc_pay(e):
            if "trip" in type_choice.selected:
                try:
                    w = float(clean_number(weight_txt.value) or 0)
                    p = float(clean_number(price_txt.value) or 0)
                    amount_txt.value = money(w * p)
                except Exception:
                    amount_txt.value = "0.00"
                page.update()

        weight_txt.on_change = calc_pay
        price_txt.on_change = calc_pay

        def submit_payment(e):
            if not person_dd.value:
                notify("اختر الطرف.", is_error=True); return
            try:
                ptype = list(type_choice.selected)[0]
                pdir = list(dir_choice.selected)[0]

                if ptype == "trip":
                    w = get_number(weight_txt.value, "وزن نقلة السداد")
                    p = get_number(price_txt.value, "سعر طن نقلة السداد")
                    amount = round(w * p, 2)
                else:
                    amount = get_number(amount_txt.value, "مبلغ السداد")
                    w, p = 0, 0

                payload = {
                    "person_id": int(person_dd.value),
                    "payment_type": ptype,
                    "direction": pdir,
                    "date": date_txt.value.strip(),
                    "amount": amount,
                    "vehicle": car_txt.value.strip() if car_txt.value else "",
                    "driver": driver_txt.value.strip() if driver_txt.value else "",
                    "item": item_txt.value.strip() if item_txt.value else "",
                    "weight": w,
                    "price": p,
                    "description": desc_txt.value.strip() if desc_txt.value else ""
                }

                if edit_pay_id[0]:
                    db.table("payments").update(payload).eq("id", edit_pay_id[0]).execute()
                    notify("تم تعديل السداد.")
                else:
                    db.table("payments").insert(payload).execute()
                    notify("تم حفظ السداد بنجاح.")

                refresh_content()
            except Exception as err:
                notify(f"خطأ: {err}", is_error=True)

        save_btn.on_click = submit_payment

        def start_edit_payment(pm):
            ask_auth("تعديل السداد", lambda: apply_edit_pay(pm))

        def apply_edit_pay(pm):
            edit_pay_id[0] = pm["id"]
            person_dd.value = str(pm["person_id"])
            type_choice.selected = {pm["payment_type"]}
            dir_choice.selected = {pm["direction"]}
            date_txt.value = pm["date"]
            amount_txt.value = money(pm["amount"])
            car_txt.value = pm.get("vehicle") or ""
            driver_txt.value = pm.get("driver") or ""
            item_txt.value = pm.get("item") or ""
            weight_txt.value = num_text(pm.get("weight") or 0)
            price_txt.value = num_text(pm.get("price") or 0)
            desc_txt.value = pm.get("description") or ""
            save_btn.text = "حفظ تعديل السداد"
            page.update()

        def start_delete_payment(pid):
            ask_auth("حذف السداد", lambda: apply_delete_pay(pid))

        def apply_delete_pay(pid):
            try:
                db.table("payments").delete().eq("id", pid).execute()
                notify("تم حذف السداد.")
                refresh_content()
            except Exception as err:
                notify(f"خطأ في الحذف: {err}", is_error=True)

        payments_list = ft.Column(spacing=8)
        for pm in reversed(payments):
            p_name = pm.get("persons", {}).get("name") if pm.get("persons") else "طرف"
            is_from_cust = pm["direction"] == "from_customer"
            payments_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text(f"#{pm['id']} | {p_name} ({'سداد من عميل' if is_from_cust else 'سداد لمورد'})", weight=ft.FontWeight.BOLD, size=13),
                            ft.Row([
                                ft.IconButton(Icons.EDIT_ROUNDED, icon_size=18, icon_color=Colors.BLUE_700, on_click=lambda e, pmm=pm: start_edit_payment(pmm)),
                                ft.IconButton(Icons.DELETE_ROUNDED, icon_size=18, icon_color=Colors.RED_700, on_click=lambda e, pid=pm["id"]: start_delete_payment(pid)),
                            ], spacing=0)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Text(f"النوع: {'نقدي' if pm['payment_type']=='cash' else 'نقلة'} | المبلغ: {money(pm['amount'])} ج.م", size=11, color=Colors.GREY_800),
                        ft.Text(f"الوصف: {pm.get('description') or 'بدون'} | التاريخ: {pm['date']}", size=10, color=Colors.GREY_600),
                    ], spacing=2),
                    bgcolor=Colors.WHITE,
                    padding=10,
                    border_radius=8,
                    border=ft.border.all(1, "#E2E8F0")
                )
            )

        return ft.Column([
            header_bar("💵 السداد", "تسجيل المقبوضات والمدفوعات نقدياً أو بنقلة"),
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Column([
                            person_dd,
                            type_choice,
                            dir_choice,
                            date_txt,
                            amount_txt,
                            ft.Row([car_txt, driver_txt], spacing=8),
                            item_txt,
                            ft.Row([weight_txt, price_txt], spacing=8),
                            desc_txt,
                            save_btn
                        ], spacing=8),
                        bgcolor=Colors.WHITE,
                        padding=12,
                        border_radius=10,
                        border=ft.border.all(1, "#E2E8F0")
                    ),
                    ft.Text("قائمة حركات السداد:", size=13, weight=ft.FontWeight.BOLD, color=Colors.BLUE_GREY_800),
                    payments_list
                ], spacing=12),
                padding=14
            )
        ], scroll=ft.ScrollMode.AUTO, expand=True)

    # =====================================================
    # 5. شاشة كشف الحساب
    # =====================================================
    def view_statement():
        persons = fetch_persons()
        trips = fetch_trips()
        payments = fetch_payments()

        person_dd = ft.Dropdown(
            label="اختر الطرف لعرض كشف الحساب",
            options=[ft.dropdown.Option(key=str(p["id"]), text=p["name"]) for p in persons],
            bgcolor=Colors.WHITE,
            border_color="#CBD5E1"
        )
        statement_view = ft.Column(spacing=6)
        summary_txt = ft.Text("اختر شخصًا ثم اضغط عرض كشف الحساب", size=12, weight=ft.FontWeight.BOLD)

        def show_stmt(e):
            if not person_dd.value:
                return
            p_id = int(person_dd.value)
            p_obj = next((p for p in persons if p["id"] == p_id), None)
            if not p_obj:
                return

            statement_view.controls.clear()
            events = statement_events(p_id, p_obj, trips, payments)

            balance = 0
            total_debit = 0
            total_credit = 0

            for ev in events:
                total_debit += ev["debit"]
                total_credit += ev["credit"]
                balance += (ev["debit"] - ev["credit"])

                statement_view.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Text(f"{ev['type']} - {ev['desc']}", weight=ft.FontWeight.BOLD, size=13),
                                ft.Text(f"الرصيد: {money(balance)}", weight=ft.FontWeight.BOLD, size=12, color=Colors.BLUE_900)
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Row([
                                ft.Text(f"مدين: {money(ev['debit'])}", size=11, color=Colors.GREEN_700),
                                ft.Text(f"دائن: {money(ev['credit'])}", size=11, color=Colors.RED_700),
                                ft.Text(f"التاريخ: {ev['date']}", size=10, color=Colors.GREY_600)
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                        ], spacing=2),
                        bgcolor=Colors.WHITE,
                        padding=10,
                        border_radius=8,
                        border=ft.border.all(1, "#E2E8F0")
                    )
                )

            status = "الحساب متزن" if abs(balance) <= 0.005 else f"الرصيد النهائي: {money(balance)}"
            summary_txt.value = f"إجمالي المدين: {money(total_debit)} | إجمالي الدائن: {money(total_credit)}\n{status}"
            page.update()

        return ft.Column([
            header_bar("📄 كشف الحساب", "كشف مالي فقط — لا تظهر فيه حالة شراء أو بيع الوزنة"),
            ft.Container(
                content=ft.Column([
                    person_dd,
                    ft.ElevatedButton("عرض كشف الحساب", icon=Icons.SEARCH_ROUNDED, on_click=show_stmt, bgcolor=Colors.BLUE_700, color=Colors.WHITE, height=44, width=page.width),
                    ft.Container(
                        content=summary_txt,
                        bgcolor=Colors.WHITE,
                        padding=12,
                        border_radius=8,
                        border=ft.border.all(1, "#E2E8F0")
                    ),
                    statement_view
                ], spacing=12),
                padding=14
            )
        ], scroll=ft.ScrollMode.AUTO, expand=True)

    # =====================================================
    # 6. شاشة متابعة الأوزان والأرباح
    # =====================================================
    def view_weights_and_profits():
        trips = fetch_trips()

        # حساب الأوزان
        grouped_weights = {}
        for row in trips:
            item_key = normalize_item(row["item"])
            if item_key not in grouped_weights:
                grouped_weights[item_key] = [row["item"], 0.0, 0.0]
            if row["operation"] == "purchase":
                grouped_weights[item_key][1] += float(row["weight"])
            else:
                grouped_weights[item_key][2] += float(row["weight"])

        total_purchase = sum(d[1] for d in grouped_weights.values())
        total_sale = sum(d[2] for d in grouped_weights.values())

        weights_cards = ft.Column(spacing=6)
        for it_k, d in grouped_weights.items():
            pur, sal = d[1], d[2]
            net = pur - sal
            rem = max(net, 0)
            short = max(-net, 0)
            weights_cards.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(d[0], weight=ft.FontWeight.BOLD, size=14),
                        ft.Row([
                            ft.Text(f"شراء: {num_text(pur)} طن", size=11),
                            ft.Text(f"بيع: {num_text(sal)} طن", size=11),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([
                            ft.Text(f"متبقي للبيع: {num_text(rem)} طن", size=11, color=Colors.GREEN_700 if rem > 0 else Colors.GREY_600),
                            ft.Text(f"مباع بدون شراء: {num_text(short)} طن", size=11, color=Colors.RED_700 if short > 0 else Colors.GREY_600),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ], spacing=2),
                    bgcolor=Colors.WHITE,
                    padding=10,
                    border_radius=8,
                    border=ft.border.all(1, "#E2E8F0")
                )
            )

        # حساب الأرباح
        sales_tot = sum(float(t["total"]) for t in trips if t["operation"] == "sale")
        purchases_tot = sum(float(t["total"]) for t in trips if t["operation"] == "purchase")
        profit_tot = sales_tot - purchases_tot

        grouped_profits = {}
        for row in trips:
            it = row["item"]
            key = normalize_item(it)
            if key not in grouped_profits:
                grouped_profits[key] = [it, 0.0, 0.0]
            if row["operation"] == "sale":
                grouped_profits[key][1] += float(row["total"])
            else:
                grouped_profits[key][2] += float(row["total"])

        profits_cards = ft.Column(spacing=6)
        for d in grouped_profits.values():
            profits_cards.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Text(d[0], weight=ft.FontWeight.BOLD, size=13, expand=True),
                        ft.Column([
                            ft.Text(f"مبيعات: {money(d[1])}", size=11, color=Colors.GREEN_700),
                            ft.Text(f"مشتريات: {money(d[2])}", size=11, color=Colors.ORANGE_800),
                            ft.Text(f"الفرق: {money(d[1] - d[2])} ج.م", size=12, weight=ft.FontWeight.BOLD, color=Colors.BLUE_900)
                        ], alignment=ft.MainAxisAlignment.END, spacing=1)
                    ]),
                    bgcolor=Colors.WHITE,
                    padding=10,
                    border_radius=8,
                    border=ft.border.all(1, "#E2E8F0")
                )
            )

        return ft.Column([
            header_bar("⚖️ الأوزان والأرباح", "متابعة أرصدة الأصناف وتقرير الأرباح الإجمالية"),
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Text(f"إجمالي الأطنان المشتراة: {num_text(total_purchase)} | المباعة: {num_text(total_sale)}\nالصافي المخزني: {num_text(total_purchase - total_sale)} طن", size=12, weight=ft.FontWeight.BOLD),
                        bgcolor=Colors.WHITE, padding=12, border_radius=8, border=ft.border.all(1, "#E2E8F0")
                    ),
                    ft.Text("متابعة أوزان الأصناف:", size=13, weight=ft.FontWeight.BOLD, color=Colors.BLUE_GREY_800),
                    weights_cards,
                    ft.Container(
                        content=ft.Text(f"إجمالي المبيعات: {money(sales_tot)} | المشتريات: {money(purchases_tot)}\nالربح الإجمالي: {money(profit_tot)} ج.م", size=12, weight=ft.FontWeight.BOLD),
                        bgcolor=Colors.WHITE, padding=12, border_radius=8, border=ft.border.all(1, "#E2E8F0")
                    ),
                    ft.Text("أرباح الأصناف:", size=13, weight=ft.FontWeight.BOLD, color=Colors.BLUE_GREY_800),
                    profits_cards,
                ], spacing=12),
                padding=14
            )
        ], scroll=ft.ScrollMode.AUTO, expand=True)

    # =====================================================
    # 7. الإعدادات وتغيير كلمة المرور
    # =====================================================
    def view_settings():
        old_pwd = ft.TextField(label="كلمة المرور الحالية", password=True, can_reveal_password=True, bgcolor=Colors.WHITE, border_color="#CBD5E1")
        new_pwd = ft.TextField(label="كلمة المرور الجديدة", password=True, can_reveal_password=True, bgcolor=Colors.WHITE, border_color="#CBD5E1")
        confirm_pwd = ft.TextField(label="تأكيد كلمة المرور الجديدة", password=True, can_reveal_password=True, bgcolor=Colors.WHITE, border_color="#CBD5E1")

        def change_pwd(e):
            stored = get_setting("password_hash")
            if not verify_password(old_pwd.value or "", stored):
                notify("كلمة المرور الحالية غير صحيحة.", is_error=True); return
            if not new_pwd.value or len(new_pwd.value) < 4:
                notify("يجب أن تكون كلمة المرور 4 أحرف أو أرقام على الأقل.", is_error=True); return
            if new_pwd.value != confirm_pwd.value:
                notify("كلمتا المرور غير متطابقتين.", is_error=True); return

            set_setting("password_hash", hash_password(new_pwd.value))
            old_pwd.value = ""
            new_pwd.value = ""
            confirm_pwd.value = ""
            notify("تم تغيير كلمة المرور بنجاح.")

        return ft.Column([
            header_bar("⚙️ الإعدادات والأمان", "إدارة كلمة المرور وحماية العمليات"),
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Column([
                            ft.Text("تغيير كلمة المرور", weight=ft.FontWeight.BOLD, size=14),
                            old_pwd, new_pwd, confirm_pwd,
                            ft.ElevatedButton("تحديث كلمة المرور", icon=Icons.LOCK_RESET_ROUNDED, on_click=change_pwd, bgcolor=Colors.BLUE_700, color=Colors.WHITE, height=44, width=page.width)
                        ], spacing=10),
                        bgcolor=Colors.WHITE,
                        padding=14,
                        border_radius=10,
                        border=ft.border.all(1, "#E2E8F0")
                    ),
                    ft.Text("كلمة المرور الافتراضية لأول تشغيل: 1234", size=11, color=Colors.GREY_600)
                ], spacing=10),
                padding=14
            )
        ], scroll=ft.ScrollMode.AUTO, expand=True)

    # =====================================================
    # نافذة تسجيل الدخول عند بدء التشغيل
    # =====================================================
    content_area = ft.Container(expand=True)

    def refresh_content():
        idx = page.navigation_bar.selected_index
        if idx == 0:
            content_area.content = view_dashboard()
        elif idx == 1:
            content_area.content = view_trips()
        elif idx == 2:
            content_area.content = view_payments()
        elif idx == 3:
            content_area.content = view_statement()
        elif idx == 4:
            content_area.content = view_persons()
        elif idx == 5:
            content_area.content = view_weights_and_profits()
        elif idx == 6:
            content_area.content = view_settings()
        page.update()

    def nav_change(e):
        refresh_content()

    page.navigation_bar = ft.NavigationBar(
        selected_index=0,
        bgcolor=Colors.WHITE,
        on_change=nav_change,
        destinations=[
            ft.NavigationBarDestination(icon=Icons.DASHBOARD_ROUNDED, label="الرئيسية"),
            ft.NavigationBarDestination(icon=Icons.LOCAL_SHIPPING_ROUNDED, label="النقلات"),
            ft.NavigationBarDestination(icon=Icons.PAYMENTS_ROUNDED, label="السداد"),
            ft.NavigationBarDestination(icon=Icons.RECEIPT_LONG_ROUNDED, label="كشف حساب"),
            ft.NavigationBarDestination(icon=Icons.PEOPLE_ROUNDED, label="الأطراف"),
            ft.NavigationBarDestination(icon=Icons.SCALE_ROUNDED, label="الأوزان"),
            ft.NavigationBarDestination(icon=Icons.SETTINGS_ROUNDED, label="الإعدادات"),
        ]
    )

    # شاشة تسجيل الدخول الأولية
    login_pwd = ft.TextField(label="كلمة المرور", password=True, can_reveal_password=True)
    def do_login(e):
        stored = get_setting("password_hash")
        if verify_password(login_pwd.value or "", stored):
            page.dialog.open = False
            refresh_content()
        else:
            notify("كلمة المرور غير صحيحة!", is_error=True)

    login_dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("تسجيل الدخول", weight=ft.FontWeight.BOLD),
        content=ft.Column([
            ft.Text("أدخل كلمة المرور لفتح التطبيق:"),
            login_pwd
        ], tight=True, spacing=10),
        actions=[
            ft.ElevatedButton("دخول", on_click=do_login, bgcolor=Colors.BLUE_700, color=Colors.WHITE)
        ]
    )

    page.add(ft.SafeArea(content_area, expand=True))
    page.dialog = login_dlg
    login_dlg.open = True
    page.update()

ft.app(target=main)

