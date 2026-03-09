import streamlit as st
import pulp
import pandas as pd

st.set_page_config(page_title="看護師シフト作成AI", layout="wide")

# ==========================================
# 1. セッションステートの初期化
# ==========================================
if "nurses_data" not in st.session_state:
    data = {}
    for i in range(1, 31):
        name = f"Nurse_{i:02d}"
        if i <= 5: role = "リーダー"
        elif i <= 22: role = "一般"
        else: role = "新人"
        
        can_night = False if role == "新人" else True
        data[name] = {
            "role": role, 
            "can_night": can_night,
            "wants_3_days_off": False, 
            "wants_weekend_off": False, 
            "rhythm": "おまかせ"
        }
    st.session_state.nurses_data = data

if "ng_pairs" not in st.session_state: st.session_state.ng_pairs = []
if "edu_pairs" not in st.session_state: st.session_state.edu_pairs = [] 
if "pairing_rules" not in st.session_state:
    st.session_state.pairing_rules = {
        "day_rookie_leader": False,    
        "night_min_leader": True,      
        "night_rookie_leader": True    
    }

# ==========================================
# 2. サイドバー
# ==========================================
st.sidebar.title("🏥 メニュー")
page = st.sidebar.radio("画面を選択", ["⚙️ 初期設定（マスタ管理）", "📅 今月のシフト作成"])
st.sidebar.markdown("---")
days = list(range(1, 31))
weekends = [d for d in days if d % 7 == 6 or d % 7 == 0]

# ==========================================
# 画面A：⚙️ 初期設定（マスタ管理）
# ==========================================
if page == "⚙️ 初期設定（マスタ管理）":
    st.title("⚙️ スタッフ初期設定（マスタ管理）")
    
    st.subheader("1️⃣ スタッフの追加と設定")
    with st.expander("👥 登録済みスタッフ（全属性の一括設定）", expanded=True):
        h1, h2, h3, h4, h5, h6 = st.columns([1.5, 1.5, 1, 1, 1, 2])
        h1.markdown("**👤 スタッフ**")
        h2.markdown("**🎓 クラス**")
        h3.markdown("**🌙 夜勤**")
        h4.markdown("**🌴 3連休**")
        h5.markdown("**㊗️ 土日祝休**")
        h6.markdown("**⏱️ リズム**")
        st.divider()

        for n, data in list(st.session_state.nurses_data.items()):
            c1, c2, c3, c4, c5, c6, c7 = st.columns([1.5, 1.5, 1, 1, 1, 2, 0.5])
            c1.markdown(f"**{n}**")
            new_role = c2.selectbox("クラス", ["リーダー", "一般", "新人"], index=["リーダー", "一般", "新人"].index(data["role"]), key=f"role_{n}", label_visibility="collapsed")
            new_can_night = c3.checkbox("夜勤", value=data.get("can_night", True), key=f"night_{n}")
            new_3d = c4.checkbox("3連休", value=data["wants_3_days_off"], key=f"3d_{n}")
            new_weekend = c5.checkbox("土日休", value=data.get("wants_weekend_off", False), key=f"we_{n}") 
            new_rhythm = c6.selectbox("リズム", ["おまかせ", "2連休ベース", "1日休みベース"], index=["おまかせ", "2連休ベース", "1日休みベース"].index(data["rhythm"]), key=f"rhy_{n}", label_visibility="collapsed")
            
            st.session_state.nurses_data[n].update({"role": new_role, "can_night": new_can_night, "wants_3_days_off": new_3d, "wants_weekend_off": new_weekend, "rhythm": new_rhythm})
            
            if c7.button("🗑️", key=f"del_{n}", help="削除"):
                del st.session_state.nurses_data[n]
                st.session_state.ng_pairs = [p for p in st.session_state.ng_pairs if p[0] != n and p[1] != n]
                st.session_state.edu_pairs = [p for p in st.session_state.edu_pairs if p[0] != n and p[1] != n]
                st.rerun()
            st.divider()

    col_ng, col_edu = st.columns(2)
    with col_ng:
        st.subheader("2️⃣ 💔 相性（NGペア）")
        nurses_list = list(st.session_state.nurses_data.keys())
        ng_1 = st.selectbox("スタッフ1", nurses_list, key="ng_1")
        ng_2 = st.selectbox("スタッフ2", nurses_list, key="ng_2")
        if st.button("NG登録", use_container_width=True) and ng_1 != ng_2:
            if (ng_1, ng_2) not in st.session_state.ng_pairs and (ng_2, ng_1) not in st.session_state.ng_pairs:
                st.session_state.ng_pairs.append((ng_1, ng_2))
                st.rerun()
        for i, (n1, n2) in enumerate(st.session_state.ng_pairs):
            st.markdown(f"🚫 {n1} ⚡ {n2}")

    with col_edu:
        st.subheader("3️⃣ 👨‍🏫 教育ペア（一緒にする）")
        st.markdown("※日勤で月3回以上同シフトになるようAIが配慮します")
        edu_1 = st.selectbox("プリセプター", nurses_list, key="edu_1")
        edu_2 = st.selectbox("プリセプティ", nurses_list, key="edu_2")
        if st.button("教育ペア登録", use_container_width=True) and edu_1 != edu_2:
            if (edu_1, edu_2) not in st.session_state.edu_pairs and (edu_2, edu_1) not in st.session_state.edu_pairs:
                st.session_state.edu_pairs.append((edu_1, edu_2))
                st.rerun()
        for i, (n1, n2) in enumerate(st.session_state.edu_pairs):
            st.markdown(f"👨‍🏫 {n1} 🤝 {n2}")

    st.subheader("4️⃣ 🛡️ クラスのペアリング設定（医療安全）")
    st.session_state.pairing_rules["day_rookie_leader"] = st.checkbox("日勤の新人数以上のリーダーを配置する", value=st.session_state.pairing_rules["day_rookie_leader"])
    st.session_state.pairing_rules["night_min_leader"] = st.checkbox("夜勤（3名）の中に、必ずリーダーを最低1名以上配置する", value=st.session_state.pairing_rules["night_min_leader"])
    st.session_state.pairing_rules["night_rookie_leader"] = st.checkbox("夜勤に入る新人数以上のリーダーを配置する", value=st.session_state.pairing_rules["night_rookie_leader"])

# ==========================================
# 画面B：📅 今月のシフト作成 ＆ シミュレーション
# ==========================================
elif page == "📅 今月のシフト作成":
    st.title("📅 今月のシフト作成 ＆ 組織課題シミュレーション")
    nurses = list(st.session_state.nurses_data.keys())
    if len(nurses) == 0: st.stop()

    base_leaders = [n for n in nurses if st.session_state.nurses_data[n]["role"] == "リーダー"]
    base_generals = [n for n in nurses if st.session_state.nurses_data[n]["role"] == "一般"]
    current_rookies = [n for n in nurses if st.session_state.nurses_data[n]["role"] == "新人"]

    st.markdown("### 💡 現場改善シミュレータ")
    col_sim1, col_sim2 = st.columns([1, 1])
    with col_sim1:
        sim_promoted = st.multiselect("特例で『リーダー』として扱う一般スタッフを選択", base_generals)
    with col_sim2:
        c2_1, c2_2, c2_3 = st.columns(3)
        leader_night_max = c2_1.slider("👑 リーダー上限", 4, 10, 6)
        general_night_max = c2_2.slider("👤 一般上限", 4, 10, 6)
        rookie_night_max = c2_3.slider("🔰 新人上限", 4, 10, 4)

    current_leaders = base_leaders + sim_promoted
    
    # --- ★改修：日・夜合算のハードワークポイントカレンダー設定 ---
    st.markdown("### ⚙️ 今月のカレンダー設定（ハードワークポイント）")
    st.markdown("手術日や週末など、日勤・夜勤それぞれで**「負担の大きい曜日」**を指定します。AIが両方を合算して評価し、特定のスタッフばかりが「損な役回り」にならないよう、全体の負荷を自動で平準化します。")
    
    c_cal1, c_cal2, c_cal3, c_cal4 = st.columns(4)
    with c_cal1: busy_day_d1 = st.selectbox("☀️ 忙しい日勤①", ["なし", "月", "火", "水", "木", "金", "土", "日"])
    with c_cal2: busy_day_d2 = st.selectbox("☀️ 忙しい日勤②", ["なし", "月", "火", "水", "木", "金", "土", "日"])
    with c_cal3: busy_day_n1 = st.selectbox("🌙 忙しい夜勤①", ["なし", "月", "火", "水", "木", "金", "土", "日"])
    with c_cal4: busy_day_n2 = st.selectbox("🌙 忙しい夜勤②", ["なし", "月", "火", "水", "木", "金", "土", "日"])
    
    busy_mod_map = {"月": 1, "火": 2, "水": 3, "木": 4, "金": 5, "土": 6, "日": 0}
    
    busy_days_day = list(set([d for name in [busy_day_d1, busy_day_d2] if name != "なし" for d in days if d % 7 == busy_mod_map[name]]))
    busy_days_night = list(set([d for name in [busy_day_n1, busy_day_n2] if name != "なし" for d in days if d % 7 == busy_mod_map[name]]))

    st.markdown("### 📝 今月の希望・月跨ぎを入力")
    requests_off, requests_day, requests_night, prev_last_shift = {}, {}, {}, {}
    with st.expander("全スタッフの希望入力パネル", expanded=True):
        h_col1, h_col2, h_col3, h_col4, h_col5 = st.columns([1.5, 1, 1.5, 1.5, 1.5])
        h_col1.markdown("**👤 スタッフ**")
        h_col2.markdown("**🔙 前月末**")
        h_col3.markdown("**🌴 休み希望**")
        h_col4.markdown("**☀️ 日勤希望**")
        h_col5.markdown("**🌙 夜勤希望**")
        st.divider()

        for n in nurses:
            col1, col2, col3, col4, col5 = st.columns([1.5, 1, 1.5, 1.5, 1.5])
            can_night = st.session_state.nurses_data[n].get("can_night", True)
            col1.markdown(f"**{n}**\n({st.session_state.nurses_data[n]['role']})")
            
            prev_last_shift[n] = col2.selectbox("前月最終日", ["休/日", "入", "明"], key=f"prev_{n}", label_visibility="collapsed")
            requests_off[n] = col3.multiselect("🌴 休み", days, key=f"req_off_{n}", label_visibility="collapsed")
            requests_day[n] = col4.multiselect("☀️ 日勤", days, key=f"req_day_{n}", label_visibility="collapsed")
            requests_night[n] = col5.multiselect("🌙 夜勤", days, key=f"req_night_{n}", label_visibility="collapsed", disabled=not can_night)
            st.divider()

    if st.button("✨ シミュレーション条件で究極シフトを作成する", type="primary"):
        with st.spinner("日夜合算のハードワーク公平化を含む、大規模最適化を実行中...（約1〜2分かかります）"):
            shifts_stage1 = ["入", "明", "未"] 
            shifts_stage2 = ["入", "明", "日", "休"] 
            
            # --- 第1段階：夜勤 ---
            prob1 = pulp.LpProblem("Stage1_Night_Soft", pulp.LpMinimize)
            x1 = pulp.LpVariable.dicts("x1", (nurses, days, shifts_stage1), cat=pulp.LpBinary)
            penalty1 = []

            for n in nurses:
                for d in days: prob1 += pulp.lpSum([x1[n][d][s] for s in shifts_stage1]) == 1
                for d in requests_off[n] + requests_day[n]: prob1 += x1[n][d]["入"] == 0; prob1 += x1[n][d]["明"] == 0
                for d in requests_night[n]: prob1 += x1[n][d]["入"] == 1
                
                if prev_last_shift[n] == "入": prob1 += x1[n][1]["明"] == 1
                elif prev_last_shift[n] == "明": prob1 += x1[n][1]["入"] == 0; prob1 += x1[n][1]["明"] == 0
                else: prob1 += x1[n][1]["明"] == 0

                for d in range(1, 30):
                    prob1 += x1[n][d+1]["明"] == x1[n][d]["入"]
                    prob1 += x1[n][d+1]["入"] <= 1 - x1[n][d]["明"]
                
                can_night = st.session_state.nurses_data[n].get("can_night", True)
                if not can_night:
                    for d in days: prob1 += x1[n][d]["入"] == 0
                else:
                    max_night = leader_night_max if n in current_leaders else (rookie_night_max if n in current_rookies else general_night_max)
                    prob1 += pulp.lpSum([x1[n][d]["入"] for d in days]) >= 2
                    prob1 += pulp.lpSum([x1[n][d]["入"] for d in days]) <= max_night

            for d in days:
                prob1 += pulp.lpSum([x1[n][d]["入"] for n in nurses]) == 3
                if st.session_state.pairing_rules["night_min_leader"]:
                    prob1 += pulp.lpSum([x1[n][d]["入"] for n in current_leaders]) >= 1
                prob1 += pulp.lpSum([x1[n][d]["入"] for n in current_rookies]) <= 1

            for ng1, ng2 in st.session_state.ng_pairs:
                if ng1 in nurses and ng2 in nurses:
                    for d in days:
                        is_ng_night = pulp.LpVariable(f"ng_night_{ng1}_{ng2}_{d}", cat=pulp.LpBinary)
                        prob1 += is_ng_night >= x1[ng1][d]["入"] + x1[ng2][d]["入"] - 1
                        penalty1.append(500 * is_ng_night)

            # 夜勤単体でのハードワーク過重も優しく防いでおく
            if len(busy_days_night) > 0:
                avg_night_hw = len(busy_days_night) * 3 / len([n for n in nurses if st.session_state.nurses_data[n].get("can_night", True)])
                allowed_max_night_hw = int(avg_night_hw) + 2
                for n in nurses:
                    night_hw_cnt = pulp.lpSum([x1[n][d]["入"] for d in busy_days_night])
                    is_over_night_hw = pulp.LpVariable(f"over_night_hw_{n}", cat=pulp.LpBinary)
                    prob1 += night_hw_cnt - allowed_max_night_hw <= len(busy_days_night) * is_over_night_hw
                    penalty1.append(50 * is_over_night_hw)

            prob1 += pulp.lpSum(penalty1)
            prob1.solve(pulp.PULP_CBC_CMD(msg=False))
            
            if pulp.LpStatus[prob1.status] != "Optimal":
                st.error("第1段階（夜勤配置）で解が見つかりませんでした。制約が厳しすぎるか、特定日の枠が埋まりません。")
                st.stop()
                
            stage1_results = {n: {d: s for d in days for s in shifts_stage1 if pulp.value(x1[n][d][s]) == 1} for n in nurses}

            # --- 第2段階：日勤・休み ---
            prob2 = pulp.LpProblem("Stage2_Day_Soft", pulp.LpMinimize)
            x2 = pulp.LpVariable.dicts("x2", (nurses, days, shifts_stage2), cat=pulp.LpBinary)
            penalty2 = []

            for n in nurses:
                for d in days:
                    prob2 += pulp.lpSum([x2[n][d][s] for s in shifts_stage2]) == 1
                    if stage1_results[n][d] in ["入", "明"]: prob2 += x2[n][d][stage1_results[n][d]] == 1 
                    else: prob2 += x2[n][d]["入"] == 0; prob2 += x2[n][d]["明"] == 0
                
                if prev_last_shift[n] == "明": prob2 += x2[n][1]["休"] == 1
                for d in requests_off[n]: prob2 += x2[n][d]["休"] == 1
                for d in requests_day[n]: prob2 += x2[n][d]["日"] == 1
                prob2 += pulp.lpSum([x2[n][d]["休"] for d in days]) >= 9
                prob2 += pulp.lpSum([x2[n][d]["休"] for d in days]) <= 11
                for d in range(1, 30): prob2 += x2[n][d+1]["休"] >= x2[n][d]["明"]
                for d in range(1, 26): prob2 += pulp.lpSum([x2[n][d+k]["休"] for k in range(6)]) >= 1
                
                for d in range(1, 23): prob2 += pulp.lpSum([x2[n][d+i]["休"] for i in range(9)]) >= 2

                for d in range(1, 25):
                    is_bad_pattern = pulp.LpVariable(f"bad51_{n}_{d}", cat=pulp.LpBinary)
                    work_sum = pulp.lpSum([1 - x2[n][d+i]["休"] for i in range(5)])
                    prob2 += is_bad_pattern >= work_sum + x2[n][d+5]["休"] + (1 - x2[n][d+6]["休"]) - 6
                    penalty2.append(200 * is_bad_pattern)

                if st.session_state.nurses_data[n].get("wants_weekend_off", False):
                    weekend_off_cnt = pulp.lpSum([x2[n][w]["休"] for w in weekends])
                    is_we_sat = pulp.LpVariable(f"we_sat_{n}", cat=pulp.LpBinary)
                    prob2 += weekend_off_cnt >= 4 * is_we_sat 
                    penalty2.append(50 * (1 - is_we_sat))

                pref = st.session_state.nurses_data[n]
                if pref["wants_3_days_off"]:
                    y3 = pulp.LpVariable.dicts(f"y3_{n}", range(1, 29), cat=pulp.LpBinary)
                    is_sat = pulp.LpVariable(f"sat_3d_{n}", cat=pulp.LpBinary)
                    for d in range(1, 29): prob2 += 3 * y3[d] <= x2[n][d]["休"] + x2[n][d+1]["休"] + x2[n][d+2]["休"]
                    prob2 += is_sat <= pulp.lpSum([y3[d] for d in range(1, 29)])
                    penalty2.append(100 * (1 - is_sat))

            for edu1, edu2 in st.session_state.edu_pairs:
                if edu1 in nurses and edu2 in nurses:
                    same_day_vars = []
                    for d in days:
                        is_same = pulp.LpVariable(f"edu_same_{edu1}_{edu2}_{d}", cat=pulp.LpBinary)
                        prob2 += is_same <= x2[edu1][d]["日"]
                        prob2 += is_same <= x2[edu2][d]["日"]
                        prob2 += is_same >= x2[edu1][d]["日"] + x2[edu2][d]["日"] - 1
                        same_day_vars.append(is_same)
                    is_edu_sat = pulp.LpVariable(f"edu_sat_{edu1}_{edu2}", cat=pulp.LpBinary)
                    prob2 += pulp.lpSum(same_day_vars) >= 3 * is_edu_sat 
                    penalty2.append(150 * (1 - is_edu_sat))

            for ng1, ng2 in st.session_state.ng_pairs:
                if ng1 in nurses and ng2 in nurses:
                    for d in days:
                        is_ng_day = pulp.LpVariable(f"ng_day_{ng1}_{ng2}_{d}", cat=pulp.LpBinary)
                        prob2 += is_ng_day >= x2[ng1][d]["日"] + x2[ng2][d]["日"] - 1
                        penalty2.append(500 * is_ng_day)

            # --- ★改修：日夜合算のハードワークポイント公平化 ---
            if len(busy_days_day) > 0 or len(busy_days_night) > 0:
                # 病棟全体でさばく必要がある「ハードワーク枠」の総数
                total_hw_slots = (len(busy_days_day) * 11) + (len(busy_days_night) * 3)
                # 1人あたりの平均担当回数
                avg_hw = total_hw_slots / len(nurses)
                # 平均値よりも2回多くなったら「不公平な過重負担」としてペナルティ
                allowed_max_hw = int(avg_hw) + 2 
                
                for n in nurses:
                    # 日勤の忙しい日の担当回数（変数：AIがこれから決める）
                    day_hw_cnt = pulp.lpSum([x2[n][d]["日"] for d in busy_days_day])
                    # 夜勤の忙しい日の担当回数（定数：第1段階ですでに確定している）
                    night_hw_cnt_val = sum([1 for d in busy_days_night if stage1_results[n][d] == "入"])
                    
                    is_over_hw = pulp.LpVariable(f"over_hw_{n}", cat=pulp.LpBinary)
                    # 合計値が上限を超えた場合、is_over_hw が 1 になる
                    max_possible = len(busy_days_day) + len(busy_days_night)
                    prob2 += day_hw_cnt + night_hw_cnt_val - allowed_max_hw <= max_possible * is_over_hw
                    # 過重負担をAIに回避させる（重いペナルティ）
                    penalty2.append(100 * is_over_hw)

            for d in days:
                if d in busy_days_day:
                    prob2 += pulp.lpSum([x2[n][d]["日"] for n in nurses]) >= 11 
                else:
                    prob2 += pulp.lpSum([x2[n][d]["日"] for n in nurses]) >= 10
                    
                if st.session_state.pairing_rules["day_rookie_leader"]:
                    prob2 += pulp.lpSum([x2[n][d]["日"] for n in current_leaders]) >= pulp.lpSum([x2[n][d]["日"] for n in current_rookies])

            prob2 += pulp.lpSum(penalty2)
            prob2.solve(pulp.PULP_CBC_CMD(msg=False))
            
            if pulp.LpStatus[prob2.status] != "Optimal":
                st.error("第2段階で解が見つかりませんでした。休みの希望や条件が厳しすぎます。")
                st.stop()

            schedule_data = []
            for n in nurses:
                row_data = {"看護師": n}
                for d in days:
                    assigned = [s for s in shifts_stage2 if pulp.value(x2[n][d][s]) == 1][0]
                    if d in requests_off[n] and assigned == "休": row_data[str(d)] = "休*"
                    elif d in requests_night[n] and assigned == "入": row_data[str(d)] = "入*"
                    elif d in requests_day[n] and assigned == "日": row_data[str(d)] = "日*"
                    else: row_data[str(d)] = assigned
                schedule_data.append(row_data)
                
            st.success("🎉 日・夜合算のハードワーク公平化を含めた究極のシフトが完成しました！")
            st.dataframe(pd.DataFrame(schedule_data), width='stretch')