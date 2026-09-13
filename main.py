# -*- coding: utf-8 -*-
from datetime import datetime
import flet as ft
from flet import Colors, Icons
from supabase import create_client, Client

# =========================================================
# بيانات الاتصال بقاعدة البيانات السحابية (Supabase)
# =========================================================
SUPABASE_URL = "https://moccsagndofjwtjmqtdd.supabase.co"
SUPABASE_KEY = "sb_publishable_L-mFR01JF4qMRQXm16Mr2A_CqDxCZo0"

# الاتصال المباشر بالسيرفر السحابي
db: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def money_str(val):
    return f"{float(val or 0):,.2f} ج.م"


def main(page: ft.Page):
    page.title = "حسابات علاء أبو شادي"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.rtl = True
    page.padding = 12

    # --- استعلامات قاعدة البيانات السحابية ---
    def fetch_persons():
        try:
            res = db.table("persons").select("*").order("name").execute()
            return res.data or []
        except Exception:
            return []

    def fetch_totals():
        try:
            trips = db.table("trips").select("operation, total").execute().data or []
            sales = sum(float(t["total"]) for t in trips if t["operation"] == "sale")
            purchases = sum(float(t["total"]) for t in trips if t["operation"] == "purchase")
            return sales, purchases
        except Exception:
            return 0.0, 0.0

    # --- 1. شاشة لوحة التحكم (الرئيسية) ---
    def view_dashboard():
        sales, purchases = fetch_totals()
        persons = fetch_persons()

        return ft.Column([
            ft.Text("📊 لوحة الحسابات السحابية", size=22, weight=ft.FontWeight.BOLD, color=Colors.BLUE_GREY_900),
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text("إجمالي المبيعات", size=14, color=Colors.GREY_600),
                        ft.Text(money_str(sales), size=22, weight=ft.FontWeight.BOLD, color=Colors.GREEN_700),
                    ]),
                    padding=16
                )
            ),
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text("إجمالي المشتريات", size=14, color=Colors.GREY_600),
                        ft.Text(money_str(purchases), size=22, weight=ft.FontWeight.BOLD, color=Colors.ORANGE_800),
                    ]),
                    padding=16
                )
            ),
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text("الأرباح التقديرية", size=14, color=Colors.GREY_600),
                        ft.Text(money_str(sales - purchases), size=22, weight=ft.FontWeight.BOLD, color=Colors.BLUE_800),
                    ]),
                    padding=16
                )
            ),
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text("عدد العملاء والموردين المسجلين", size=14, color=Colors.GREY_600),
                        ft.Text(f"{len(persons)} طرف", size=18, weight=ft.FontWeight.BOLD, color=Colors.BLUE_GREY_800),
                    ]),
                    padding=16
                )
            ),
        ], scroll=ft.ScrollMode.AUTO, spacing=10)

    # --- 2. شاشة تسجيل نقلة بضاعة ---
    def view_trips():
        persons = fetch_persons()
        person_dropdown = ft.Dropdown(
            label="اختر الطرف",
            options=[ft.dropdown.Option(key=str(p["id"]), text=p["name"]) for p in persons]
        )
        op_radio = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value="purchase", label="شراء من مورد"),
                ft.Radio(value="sale", label="بيع لعميل"),
            ]),
            value="purchase"
        )
        item_field = ft.TextField(label="نوع البضاعة (ذرة، قمح...)", dense=True)
        weight_field = ft.TextField(label="الوزن بالطن", keyboard_type=ft.KeyboardType.NUMBER, dense=True)
        price_field = ft.TextField(label="سعر الطن", keyboard_type=ft.KeyboardType.NUMBER, dense=True)
        car_field = ft.TextField(label="رقم السيارة", dense=True)
        driver_field = ft.TextField(label="اسم السائق", dense=True)

        def save_trip(e):
            if not person_dropdown.value or not weight_field.value or not price_field.value:
                page.snack_bar = ft.SnackBar(ft.Text("يرجى ملء الحقول الأساسية أولاً!"))
                page.snack_bar.open = True
                page.update()
                return

            try:
                w = float(weight_field.value)
                p = float(price_field.value)
                tot = round(w * p, 2)

                db.table("trips").insert({
                    "person_id": int(person_dropdown.value),
                    "operation": op_radio.value,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "vehicle": car_field.value,
                    "driver": driver_field.value,
                    "item": item_field.value,
                    "weight": w,
                    "price": p,
                    "total": tot,
                    "notes": ""
                }).execute()

                weight_field.value = ""
                price_field.value = ""
                car_field.value = ""
                driver_field.value = ""
                item_field.value = ""
                page.snack_bar = ft.SnackBar(ft.Text("تم حفظ النقلة في السحابة بنجاح ✅"))
            except Exception as err:
                page.snack_bar = ft.SnackBar(ft.Text(f"خطأ أثناء الحفظ: {err}"))

            page.snack_bar.open = True
            page.update()

        return ft.Column([
            ft.Text("🚚 تسجيل نقلة غلال", size=20, weight=ft.FontWeight.BOLD),
            person_dropdown,
            op_radio,
            item_field,
            ft.Row([weight_field, price_field]),
            ft.Row([car_field, driver_field]),
            ft.ElevatedButton("حفظ النقلة سحابياً", on_click=save_trip, bgcolor=Colors.BLUE_700, color=Colors.WHITE, height=48),
        ], scroll=ft.ScrollMode.AUTO, spacing=12)

    # --- 3. شاشة تسجيل طرف (عميل / مورد) ---
    def view_persons():
        name_in = ft.TextField(label="الاسم الكامل", dense=True)
        phone_in = ft.TextField(label="رقم الهاتف", keyboard_type=ft.KeyboardType.PHONE, dense=True)
        address_in = ft.TextField(label="العنوان", dense=True)
        rec_in = ft.TextField(label="رصيد أول المدة: له عندك (مدين)", value="0", keyboard_type=ft.KeyboardType.NUMBER, dense=True)
        pay_in = ft.TextField(label="رصيد أول المدة: عليك للمورد (دائن)", value="0", keyboard_type=ft.KeyboardType.NUMBER, dense=True)

        def save_person(e):
            if not name_in.value:
                return

            try:
                db.table("persons").insert({
                    "name": name_in.value.strip(),
                    "phone": phone_in.value.strip(),
                    "address": address_in.value.strip(),
                    "opening_receivable": float(rec_in.value or 0),
                    "opening_payable": float(pay_in.value or 0),
                }).execute()

                name_in.value = ""
                phone_in.value = ""
                address_in.value = ""
                rec_in.value = "0"
                pay_in.value = "0"
                page.snack_bar = ft.SnackBar(ft.Text("تمت إضافة الطرف إلى قاعدة البيانات ✅"))
            except Exception as err:
                page.snack_bar = ft.SnackBar(ft.Text(f"خطأ: {err}"))

            page.snack_bar.open = True
            page.update()

        return ft.Column([
            ft.Text("👥 إضافة طرف جديد", size=20, weight=ft.FontWeight.BOLD),
            name_in,
            phone_in,
            address_in,
            ft.Row([rec_in, pay_in]),
            ft.ElevatedButton("حفظ الطرف سحابياً", on_click=save_person, bgcolor=Colors.GREEN_700, color=Colors.WHITE, height=48),
        ], scroll=ft.ScrollMode.AUTO, spacing=12)

    body_container = ft.Container(content=view_dashboard(), expand=True)

    def nav_change(e):
        idx = e.control.selected_index
        if idx == 0:
            body_container.content = view_dashboard()
        elif idx == 1:
            body_container.content = view_trips()
        elif idx == 2:
            body_container.content = view_persons()
        page.update()

    page.navigation_bar = ft.NavigationBar(
        selected_index=0,
        on_change=nav_change,
        destinations=[
            ft.NavigationBarDestination(icon=Icons.DASHBOARD_ROUNDED, label="الرئيسية"),
            ft.NavigationBarDestination(icon=Icons.LOCAL_SHIPPING_ROUNDED, label="نقلة"),
            ft.NavigationBarDestination(icon=Icons.PERSON_ADD_ROUNDED, label="إضافة طرف"),
        ]
    )

    page.add(body_container)


ft.app(target=main)
