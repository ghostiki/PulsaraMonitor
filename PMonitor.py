import streamlit as st
import pandas as pd
import time
from curl_cffi import requests
import difflib


def get_user_timezone():
    pass


st.set_page_config(page_title="Pulsara Monitor", layout="wide")

COLOR_MAP = {
    "Обычный": "#FFFFFF", "Необычный": "#20B2AA", "Особый": "#1E90FF",
    "Редкий": "#9370DB", "Исключительный": "#FF4500", "Легендарный": "#FFD700"
}

QUALITY_MAP = {
    "Любая": None, "Обычный": 0, "Необычный": 1, "Особый": 2,
    "Редкий": 3, "Исключительный": 4, "Легендарный": 5
}

if 'session' not in st.session_state:
    st.session_state.session = requests.Session(impersonate="chrome120")


@st.cache_data(ttl=3600)
def get_all_items():
    try:
        url = "https://backend.stalnote.ru/noauthorize/GameItems/uniqAll"
        res = st.session_state.session.get(url, timeout=10)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return []


def find_item_fuzzy(user_query):
    all_items = get_all_items()
    if not all_items:
        return None, None
    user_query = user_query.lower().strip()
    for item in all_items:
        if item.get('name', '').lower() == user_query:
            return item.get('id'), item.get('name')
    names_list = [item.get('name', '') for item in all_items]
    matches = difflib.get_close_matches(
        user_query, names_list, n=1, cutoff=0.5)
    if matches:
        best_match = matches[0]
        for item in all_items:
            if item.get('name') == best_match:
                return item.get('id'), item.get('name')
    return None, None


def get_market_data(item_id):
    if not item_id:
        return []
    try:
        url = f"https://backend.stalnote.ru/noauthorize/auctionitem/{item_id}"
        res = st.session_state.session.get(url, timeout=10)
        return res.json() if res.status_code == 200 else []
    except:
        return []


st.sidebar.markdown("### 🔍 ПАРАМЕТРЫ")
item_input = st.sidebar.text_input(
    "Название предмета",
    value="",
    placeholder="Введите название"
)

st.sidebar.markdown("---")
selected_q = st.sidebar.selectbox("Редкость", list(QUALITY_MAP.keys()))
pot_options = ["Любая"] + [str(i) for i in range(16)]
target_pot_raw = st.sidebar.selectbox("Заточка", pot_options)
target_pot_val = int(target_pot_raw) if target_pot_raw != "Любая" else "Любая"

min_amount = st.sidebar.number_input("Мин. кол-во", min_value=1, value=1)
max_price = st.sidebar.number_input(
    "Макс. цена (за шт.)", min_value=0, value=0)
refresh_sec = st.sidebar.slider("Частота обновления (сек)", 5, 60, 10)

placeholder = st.empty()

if len(item_input.strip()) < 2:
    with placeholder.container():
        st.markdown(
            "<div style='display: flex; justify-content: center; align-items: center; height: 75vh; flex-direction: column;'>"
            "<h1 style='color: #FFD700; font-family: sans-serif; font-size: 70px; margin-bottom: 10px; font-weight: 800;'>PULSARA MONITOR</h1>"
            "<div style='background: #1f2329; padding: 20px 40px; border-radius: 15px; border: 1px solid #333; text-align: center;'>"
            "<p style='color: #fff; font-size: 18px; margin: 0;'>Используйте панель слева, чтобы найти нужный лот</p>"
            "</div>"
            "</div>",
            unsafe_allow_html=True
        )
else:
    target_id, final_name = find_item_fuzzy(item_input)

    if not target_id:
        placeholder.error(f"❌ Предмет '{item_input}' не найден в базе данных.")
    else:
        with placeholder.container():
            raw_data = get_market_data(target_id)

            has_varied_pot = any(lot.get('pottential', 0)
                                 > 0 for lot in raw_data)
            has_varied_quality = len(set(lot.get('quality', 0)
                                     for lot in raw_data)) > 1
            show_amount_col = any(lot.get('ammount', 1) >
                                  1 for lot in raw_data)

            processed_lots = []
            for lot in raw_data:
                if has_varied_quality:
                    q_val = QUALITY_MAP[selected_q]
                    if q_val is not None and lot.get('quality') != q_val:
                        continue
                if has_varied_pot:
                    if target_pot_val != "Любая" and lot.get('pottential') != target_pot_val:
                        continue

                amount = lot.get('ammount', 1)
                if show_amount_col and amount < min_amount:
                    continue

                buyout = lot.get('buyoutPrice', 0)
                if buyout <= 0:
                    continue
                unit_p = int(buyout / amount)
                if max_price > 0 and unit_p > max_price:
                    continue

                q_name = {0: "Обычный", 1: "Необычный", 2: "Особый", 3: "Редкий",
                          4: "Исключительный", 5: "Легендарный"}.get(lot.get('quality', 0), "Обычный")

                processed_lots.append({
                    "unit_p_val": unit_p,
                    "unit_p": f"{unit_p:,}".replace(",", " "),
                    "amount": amount,
                    "total": f"{buyout:,}".replace(",", " "),
                    "pot": f"+{lot.get('pottential')}",
                    "quality": q_name,
                    "color": COLOR_MAP.get(q_name, "#FFFFFF")
                })

            if processed_lots:
                update_ts = time.time() * 1000

                st.components.v1.html(
                    f"""
                    <div style="display: flex; align-items: center; font-family: sans-serif; background-color: #0e1117; color: white; padding: 10px;">
                        <div style="font-size: 20px; font-weight: bold; text-transform: uppercase;">
                            📦 {final_name}
                        </div>
                        <div style="margin: 0 15px; color: #444; font-size: 20px;">|</div>
                        <div id="update-time" style="font-size: 20px; font-weight: bold; color: #FFD700; font-family: monospace;">
                            --:--:--
                        </div>
                    </div>

                    <script>
                        function formatTime() {{
                            const serverTime = new Date({update_ts});
                            const localTime = serverTime.toLocaleTimeString('ru-RU', {{ 
                                hour: '2-digit', 
                                minute: '2-digit', 
                                second: '2-digit' 
                            }});
                            
                            document.getElementById('update-time').innerText = localTime;
                        }}
                        formatTime();
                    </script>
                    """,
                    height=60,
                )

                sorted_lots = sorted(
                    processed_lots, key=lambda x: x["unit_p_val"])
                price_head = "Цена" if not show_amount_col else "Цена за шт."
                th = f"<th>{price_head}</th>"
                if show_amount_col:
                    th += "<th>Кол-во</th><th>Цена</th>"
                if has_varied_pot:
                    th += "<th>Заточка</th>"
                if has_varied_quality:
                    th += "<th>Редкость</th>"

                rows_html = ""
                for lot in sorted_lots:
                    rows_html += f"<tr style='color: {lot['color']}; border-bottom: 1px solid #222;'>"
                    rows_html += f"<td style='padding: 12px;'>{lot['unit_p']}</td>"
                    if show_amount_col:
                        rows_html += f"<td>{lot['amount']}</td><td>{lot['total']}</td>"
                    if has_varied_pot:
                        rows_html += f"<td>{lot['pot']}</td>"
                    if has_varied_quality:
                        rows_html += f"<td>{lot['quality']}</td>"
                    rows_html += "</tr>"

                table_style = "<style>.st-table-wrap { max-height: 600px; overflow-y: auto; border: 1px solid #333; border-radius: 8px; background: #0e1117; } table { width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 14px; } th { position: sticky; top: 0; background: #1f2329; color: #777; padding: 12px; text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; } td { padding: 11px 12px; }</style>"
                full_html = f"{table_style}<div class='st-table-wrap'><table><thead><tr>{th}</tr></thead><tbody>{rows_html}</tbody></table></div>"
                st.components.v1.html(full_html, height=610)
            else:
                st.info("По заданным фильтрам лотов не найдено.")

        time.sleep(refresh_sec)
        st.rerun()
