# -*- coding: utf-8 -*-
from datetime import datetime
import flet as ft
from flet import Colors, Icons
from supabase import create_client, Client

# =========================================================
# الربط السحابي
# =========================================================
SUPABASE_URL = "https://moccsagndofjwtjmqtdd.supabase.co"
SUPABASE_KEY = "sb_publishable_L-mFR01JF4qMRQXm16Mr2A_CqDxCZo0"

try:
    db: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    db = None

def money(val):
    try:
        return f"{float(val or 0):,.2f} ج.م"
    except Exception:
        return "0.00 ج.م"

def num_fmt(val):
    try:
        num = float(val or 0)
        return f"{num:,.2f}".rstrip("0").rstrip(".")
    except Exception:
        return "0"

def main(page: ft.Page):
    page.title = "حسابات علاء أبو شادي"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.rtl = True
    page.padding = 0
    page.bgcolor = "#F1F5F9"

    def notify(msg, is_error=False):
        page.snack_bar = ft.SnackBar(
            content=ft.Text(msg, color=Colors.WHITE, size=14, weight=ft.FontWeight.BOLD),
            bgcolor=Colors.RED_700 if is_error else Colors.GREEN_700,
            duration=3500
        )
        page.snack_bar.open = True
        page.update()

    # --- استعلامات البيانات ---
    def get_persons():
        if not db:
            return []
        try:
            return db.table("persons").select("*").order("name").execute().data or []
        except Exception as err:
            notify(f"خطأ جلب الأشخاص: {err}", is_error=True)
            return []

    def get_trips():
        if not db:
            return []
        try:
            return db.table("trips").select("*, persons(name)").order("date", desc=True).order("id", desc=True).execute().data or []
        except Exception as err:
            notify(f"خطأ جلب النقلات: {err}", is_error=True)
            return []

    # =====================================================
    # ترويسة الشاشات
    # =====================================================
    def header_card(title, subtitle):
        return ft.Container(
            content=ft.Column([
                ft.Text(title, size=20, weight=ft.FontWeight.BOLD, color=Colors.WHITE),
                ft.Text(subtitle, size=12, color=Colors.BLUE_GREY_100),
            ], spacing=2),
            bgcolor="#1E293B",
            padding=ft.padding.symmetric(horizontal=20, vertical=16),
            border_radius=ft.border_radius.only(bottom_left=15, bottom_right=15),
            shadow=ft.BoxShadow(spread_radius=1, blur_radius=8, color=Colors.BLACK12)
        )

    # =====================================================
    # 1. شاشة الرئيسية (لوحة التحكم)
    # =====================================================
    def view_dashboard():
        trips = get_trips()
        persons = get_persons()

        sales = sum(float(t.get("total") or 0) for t in trips if t.get("operation") == "sale")
        purchases = sum(float(t.get("total") or 0) for t in trips if t.get("operation") == "purchase")
        profit = sales - purchases

        def stat_card(label, value, icon, color):
            return ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Icon(icon, color=color, size=28),
                        bgcolor=ft.colors.with_opacity(0.12, color),
                        padding=12,
                        border_radius=12
                    ),
                    ft.Column([
                        ft.Text(label, size=12, color=Colors.BLUE_GREY_600),
                        ft.Text(value, size=18, weight=ft.FontWeight.BOLD, color=Colors.BLUE_GREY_900),
                    ], spacing=2, expand=True)
                ], alignment=ft.MainAxisAlignment.START),
                bgcolor=Colors.WHITE,
                padding=16,
                border_radius=12,
                border=ft.border.all(1, "#E2E8F0"),
                shadow=ft.BoxShadow(blur_radius=4, color=Colors.BLACK12)
            )

        return ft.Column([
            header_card("📊 لوحة الحسابات", "ملخص شامل لحركة النقلات والمبيعات"),
            ft.Container(
                content=ft.Column([
                    stat_card("إجمالي المبيعات", money(sales), Icons.ARROW_UPWARD_ROUNDED, Colors.GREEN_700),
                    stat_card("إجمالي المشتريات", money(purchases), Icons.ARROW_DOWNWARD_ROUNDED, Colors.ORANGE_800),
                    stat_card("الربح الإجمالي التقديري", money(profit), Icons.ACCOUNT_BALANCE_WALLET_ROUNDED, Colors.BLUE_700),
                    stat_card("عدد العملاء والموردين", f"{len(persons)} طرف", Icons.PEOPLE_ALT_ROUNDED, Colors.PURPLE_700),
                ], spacing=10),
                padding=16
            )
        ], scroll=ft.ScrollMode.AUTO, expand=True)

    # =====================================================
    # 2. شاشة تسجيل نقلة وعرض النقلات السابقة
    # =====================================================
    def view_trips():
        persons = get_persons()
        person_dd = ft.Dropdown(
            label="اختر الطرف (العميل أو المورد)",
            options=[ft.dropdown.Option(key=str(p["id"]), text=p["name"]) for p in persons],
            border_color="#CBD5E1",
            bgcolor=Colors.WHITE
        )
        op_choice = ft.SegmentedButton(
            selected={"purchase"},
            allow_multiple_selection=False,
            segments=[
                ft.Segment(value="purchase", label=ft.Text("شراء من مورد")),
                ft.Segment(value="sale", label=ft.Text("بيع لعميل")),
            ]
        )
        item_txt = ft.TextField(label="نوع البضاعة (ذرة، قمح...)", bgcolor=Colors.WHITE, border_color="#CBD5E1")
        weight_txt = ft.TextField(label="الوزن بالطن", keyboard_type=ft.KeyboardType.NUMBER, bgcolor=Colors.WHITE, border_color="#CBD5E1", expand=True)
        price_txt = ft.TextField(label="سعر الطن", keyboard_type=ft.KeyboardType.NUMBER, bgcolor=Colors.WHITE, border_color="#CBD5E1", expand=True)
        car_txt = ft.TextField(label="رقم السيارة", bgcolor=Colors.WHITE, border_color="#CBD5E1", expand=True)
        driver_txt = ft.TextField(label="اسم السائق", bgcolor=Colors.WHITE, border_color="#CBD5E1", expand=True)
        total_display = ft.Text("الإجمالي: 0.00 ج.م", size=15, weight=ft.FontWeight.BOLD, color=Colors.BLUE_900)

        def calc_total(e):
            try:
                w = float(weight_txt.value.strip().replace(",", "") or 0)
                p = float(price_txt.value.strip().replace(",", "") or 0)
                total_display.value = f"الإجمالي: {money(w * p)}"
            except Exception:
                total_display.value = "الإجمالي: 0.00 ج.م"
            page.update()

        weight_txt.on_change = calc_total
        price_txt.on_change = calc_total

        def submit_trip(e):
            if not person_dd.value:
                notify("يجب اختيار الطرف أولاً!", is_error=True); return
            if not item_txt.value or not weight_txt.value or not price_txt.value:
                notify("يرجى إدخال البضاعة والوزن والسعر!", is_error=True); return

            try:
                w = float(weight_txt.value.strip().replace(",", ""))
                p = float(price_txt.value.strip().replace(",", ""))
                tot = round(w * p, 2)
                op = list(op_choice.selected)[0]

                res = db.table("trips").insert({
                    "person_id": int(person_dd.value),
                    "operation": op,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "vehicle": car_txt.value.strip(),
                    "driver": driver_txt.value.strip(),
                    "item": item_txt.value.strip(),
                    "weight": w,
                    "price": p,
                    "total": tot,
                    "notes": ""
                }).execute()

                if res.data:
                    item_txt.value = ""
                    weight_txt.value = ""
                    price_txt.value = ""
                    car_txt.value = ""
                    driver_txt.value = ""
                    total_display.value = "الإجمالي: 0.00 ج.م"
                    notify("تم حفظ النقلة بنجاح ✅")
                    refresh_content()
            except Exception as err:
                notify(f"فشل الحفظ: {err}", is_error=True)

        # جدول أحدث النقلات المسجلة
        recent_trips = get_trips()[:15]
        trips_list = ft.Column(spacing=8)
        for t in recent_trips:
            p_name = t.get("persons", {}).get("name") if t.get("persons") else "طرف"
            is_sale = t.get("operation") == "sale"
            trips_list.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(Icons.NORTH_EAST if is_sale else Icons.SOUTH_WEST, color=Colors.GREEN_700 if is_sale else Colors.ORANGE_800),
                        ft.Column([
                            ft.Text(f"{p_name} - {t.get('item')}", weight=ft.FontWeight.BOLD, size=14),
                            ft.Text(f"{num_fmt(t.get('weight'))} طن × {money(t.get('price'))} | {t.get('date')}", size=11, color=Colors.GREY_600)
                        ], expand=True, spacing=1),
                        ft.Text(money(t.get("total")), weight=ft.FontWeight.BOLD, color=Colors.BLUE_GREY_900)
                    ]),
                    bgcolor=Colors.WHITE,
                    padding=12,
                    border_radius=8,
                    border=ft.border.all(1, "#E2E8F0")
                )
            )

        return ft.Column([
            header_card("🚚 تسجيل النقلات", "إدخال ومتابعة نقلات البيع والشراء"),
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Column([
                            person_dd,
                            op_choice,
                            item_txt,
                            ft.Row([weight_txt, price_txt], spacing=10),
                            ft.Row([car_txt, driver_txt], spacing=10),
                            total_display,
                            ft.ElevatedButton(
                                "حفظ النقلة",
                                icon=Icons.SAVE_ROUNDED,
                                on_click=submit_trip,
                                bgcolor=Colors.BLUE_700,
                                color=Colors.WHITE,
                                height=48,
                                width=page.width
                            )
                        ], spacing=10),
                        bgcolor=Colors.WHITE,
                        padding=15,
                        border_radius=12,
                        border=ft.border.all(1, "#E2E8F0")
                    ),
                    ft.Text("أحدث النقلات المسجلة:", size=14, weight=ft.FontWeight.BOLD, color=Colors.BLUE_GREY_800),
                    trips_list
                ], spacing=14),
                padding=16
            )
        ], scroll=ft.ScrollMode.AUTO, expand=True)

    # =====================================================
    # 3. شاشة العملاء والموردين
    # =====================================================
    def view_persons():
        name_in = ft.TextField(label="اسم الطرف بالكامل", bgcolor=Colors.WHITE, border_color="#CBD5E1")
        phone_in = ft.TextField(label="رقم الهاتف", keyboard_type=ft.KeyboardType.PHONE, bgcolor=Colors.WHITE, border_color="#CBD5E1")
        address_in = ft.TextField(label="العنوان", bgcolor=Colors.WHITE, border_color="#CBD5E1")
        rec_in = ft.TextField(label="رصيد لك عنده (أول المدة)", value="0", keyboard_type=ft.KeyboardType.NUMBER, bgcolor=Colors.WHITE, border_color="#CBD5E1", expand=True)
        pay_in = ft.TextField(label="رصيد له عندك (أول المدة)", value="0", keyboard_type=ft.KeyboardType.NUMBER, bgcolor=Colors.WHITE, border_color="#CBD5E1", expand=True)

        def save_person(e):
            if not name_in.value.strip():
                notify("اكتب اسم الشخص أولاً!", is_error=True); return

            try:
                rec_val = float(rec_in.value.strip().replace(",", "") or 0)
                pay_val = float(pay_in.value.strip().replace(",", "") or 0)

                res = db.table("persons").insert({
                    "name": name_in.value.strip(),
                    "phone": phone_in.value.strip(),
                    "address": address_in.value.strip(),
                    "opening_receivable": rec_val,
                    "opening_payable": pay_val
                }).execute()

                if res.data:
                    name_in.value = ""
                    phone_in.value = ""
                    address_in.value = ""
                    rec_in.value = "0"
                    pay_in.value = "0"
                    notify("تمت إضافة الطرف إلى قاعدة البيانات ✅")
                    refresh_content()
            except Exception as err:
                notify(f"فشل الحفظ: {err}", is_error=True)

        # قائمة الأشخاص الحاليين
        persons = get_persons()
        persons_list = ft.Column(spacing=6)
        for p in persons:
            persons_list.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.CircleAvatar(content=ft.Text(p["name"][:1]), bgcolor=Colors.BLUE_100, color=Colors.BLUE_900),
                        ft.Column([
                            ft.Text(p["name"], weight=ft.FontWeight.BOLD, size=14),
                            ft.Text(p.get("phone") or "بدون هاتف", size=11, color=Colors.GREY_600)
                        ], expand=True, spacing=1),
                    ]),
                    bgcolor=Colors.WHITE,
                    padding=10,
                    border_radius=8,
                    border=ft.border.all(1, "#E2E8F0")
                )
            )

        return ft.Column([
            header_card("👥 العملاء والموردون", "تسجيل الأطراف وضبط الأرصدة الافتتاحية"),
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Column([
                            name_in,
                            phone_in,
                            address_in,
                            ft.Row([rec_in, pay_in], spacing=10),
                            ft.ElevatedButton(
                                "حفظ الطرف",
                                icon=Icons.PERSON_ADD_ROUNDED,
                                on_click=save_person,
                                bgcolor=Colors.GREEN_700,
                                color=Colors.WHITE,
                                height=48,
                                width=page.width
                            )
                        ], spacing=10),
                        bgcolor=Colors.WHITE,
                        padding=15,
                        border_radius=12,
                        border=ft.border.all(1, "#E2E8F0")
                    ),
                    ft.Text("قائمة الأطراف المسجلة:", size=14, weight=ft.FontWeight.BOLD, color=Colors.BLUE_GREY_800),
                    persons_list
                ], spacing=14),
                padding=16
            )
        ], scroll=ft.ScrollMode.AUTO, expand=True)

    # =====================================================
    # التنقل وإطار الشاشة المريح (SafeArea)
    # =====================================================
    content_area = ft.Container(content=view_dashboard(), expand=True)

    def refresh_content():
        idx = page.navigation_bar.selected_index
        if idx == 0:
            content_area.content = view_dashboard()
        elif idx == 1:
            content_area.content = view_trips()
        elif idx == 2:
            content_area.content = view_persons()
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
            ft.NavigationBarDestination(icon=Icons.PEOPLE_ROUNDED, label="الأطراف"),
        ]
    )

    # حماية المحتوى من التداخل مع النوتش وشريط الهاتف العلوي
    page.add(ft.SafeArea(content_area, expand=True))

ft.app(target=main)
