import streamlit as st
import pulp
import pandas as pd
import os

st.set_page_config(page_title="看護部 統合シフト司令塔", layout="wide")

# ==========================================
# 📂 CSVファイル設定
# ==========================================
CSV_FILE = "staff_master.csv"

def parse_bool(val):
    if isinstance(val, bool): return val
    return str(val).strip().upper() in ['TRUE', '1', 'T', 'YES']

def load_staff_data():
    if not os.path.exists(CSV_FILE):
        return None
    try:
        df = pd.read_csv(CSV_FILE, encoding='utf-8-sig')
        data = {}
        for _, row in df.iterrows():
            data[row["name"]] = {
                "ward": row["ward"],
                "skill": row["skill"],
                "can_float": parse_bool(row.get("can_float", True)),
                "can_night": parse_bool(row.get("can_night", True)),
                "wants_3_days_off": parse_bool(row.get("wants_3_days_off", False)),
                "wants_weekend_off": parse_bool(row.get("wants_weekend_off", False)),
                "rhythm": row.get("rhythm", "おまかせ")
            }
        return data
    except Exception as e:
        st.error(f"🚨 CSV読み込みエラー: {e}")
        return None

def save_staff_data(data_dict):
    df = pd.DataFrame.from_dict(data_dict, orient='index').reset_index()
    df.columns = ["name", "ward", "skill", "can_float", "can_night", "wants_3_days_off", "wants_weekend_off", "rhythm"]
    try:
        df.to_csv(CSV_FILE, index=False, encoding='utf-8-sig')
        st.success(f"💾 マスタを `{CSV_FILE}` に保存しました！")
    except Exception as e:
        st.error(f"🚨 保存エラー: ファイルが開かれている可能性があります（{e}）")

# ==========================================
# 1. 初期データの設定
# ==========================================
WARDS = ["🏥 東病棟（外科）", "🏥 西病棟（内科）", "🚑 ICU"]

if "global_staff" not in st.session_state:
    loaded_data = load_staff_data()
    if loaded_data:
        st.session_state.global_staff = loaded_data
    else:
        data = {}
        for i in range(1, 91):
            name = f"Nurse_{i:02d}"
            ward = WARDS[(i-1)//30]
            mod = i % 30
            if mod in [1, 2, 3, 4, 5, 6]: skill = "A（指導）"
            elif mod in [25, 26, 27, 28, 29, 0]: skill = "C（支援）"
            else: skill = "B（自立）"
            data[name] = {
                "ward": ward, "skill": skill, "can_float": (skill != "C（支援）"),
                "can_night": (skill != "C（支援）"), "wants_3_days_off": False, 
                "wants_weekend_off": False, "rhythm": "おまかせ"
            }
        st.session_state.global_staff = data

if "target_points" not in st.session_state:
    st.session_state.target_points = {WARDS[0]: 28, WARDS[1]: 28, WARDS[2]: 24}

if "ng_pairs" not in st.session_state: st.session_state.ng_pairs = []
if "edu_pairs" not in st.session_state: st.session_state.edu_pairs = [] 
if "pairing_rules" not in st.session_state:
    st.session_state.pairing_rules = {"day_C_A": False, "night_min_A": True, "night_C_A": True}

if "busy_days" not in st.session_state:
    st.session_state.busy_days = {
        WARDS[0]: {"d1": "月", "d2": "木", "n1": "金", "n2": "土"},
        WARDS[1]: {"d1": "火", "d2": "金", "n1": "金", "n2": "土"},
        WARDS[2]: {"d1": "なし", "d2": "なし", "n1": "なし", "n2": "なし"} 
    }

days = list(range(1, 31))
weekends = [d for d in days if d % 7 == 6 or d % 7 == 0]

# ==========================================
# 2. UI構成
# ==========================================
st.sidebar.title("🏢 統合司令塔")
page = st.sidebar.radio("機能を選択", ["👥 病院全体マスタ・ルール設定", "📈 デマンド・ハードワーク設定", "📅 3段階・究極シフト作成"])
st.sidebar.markdown("---")
st.sidebar.info("💡 **【スキルポイント】**\n\n**A（指導）**: 自3pt / 応援2pt\n**B（自立）**: 自2pt / 応援2pt\n**C（支援）**: 自1pt / 応援不可")

if page == "👥 病院全体マスタ・ルール設定":
    c_title, c_btn = st.columns([3, 1])
    c_title.title("👥 病院全体マスタ ＆ ペアリング")
    if c_btn.button("💾 CSVを保存", type="primary", use_container_width=True):
        save_staff_data(st.session_state.global_staff)
    
    st.subheader("1️⃣ スタッフ属性の一括管理")
    filter_ward = st.selectbox("病棟絞り込み", ["すべて"] + WARDS)
    h1, h2, h3, h4, h5, h6 = st.columns([1.5, 1.5, 1.5, 1, 1, 1.5])
    h1.markdown("**名前**"); h2.markdown("**所属**"); h3.markdown("**スキル**"); h4.markdown("**応援**"); h5.markdown("**夜勤**"); h6.markdown("**リズム**")
    for n, data in st.session_state.global_staff.items():
        if filter_ward != "すべて" and data["ward"] != filter_ward: continue
        c1, c2, c3, c4, c5, c6 = st.columns([1.5, 1.5, 1.5, 1, 1, 1.5])
        c1.markdown(f"**{n}**")
        new_ward = c2.selectbox("病棟", WARDS, index=WARDS.index(data["ward"]), key=f"w_{n}", label_visibility="collapsed")
        new_skill = c3.selectbox("スキル", ["A（指導）", "B（自立）", "C（支援）"], index=["A（指導）", "B（自立）", "C（支援）"].index(data["skill"]), key=f"s_{n}", label_visibility="collapsed")
        is_float_disabled = True if new_skill == "C（支援）" else False
        new_float = c4.checkbox("応援", value=data["can_float"] if not is_float_disabled else False, disabled=is_float_disabled, key=f"f_{n}")
        new_night = c5.checkbox("夜勤", value=data["can_night"], key=f"n_{n}")
        new_rhythm = c6.selectbox("リズム", ["おまかせ", "2連休ベース", "1日休みベース"], index=["おまかせ", "2連休ベース", "1日休みベース"].index(data["rhythm"]), key=f"rhy_{n}", label_visibility="collapsed")
        st.session_state.global_staff[n].update({"ward": new_ward, "skill": new_skill, "can_float": new_float, "can_night": new_night, "rhythm": new_rhythm})

elif page == "📈 デマンド・ハードワーク設定":
    st.title("📈 目標デマンド ＆ 病棟別ハードワーク設定")
    c1, c2, c3 = st.columns(3)
    for i, w in enumerate(WARDS):
        with [c1, c2, c3][i]:
            st.markdown(f"**{w}**")
            ope = st.number_input("追加負荷（手術・入院等）", 0, 20, 5, key=f"load_{w}")
            st.session_state.target_points[w] = 20 + ope
            st.metric("目標ポイント", f"{st.session_state.target_points[w]} pt")
    
    st.divider()
    st.subheader("⚖️ 2. 【病棟別】日夜合算ハードワーク指定")
    tabs = st.tabs(WARDS)
    opts = ["なし", "月", "火", "水", "木", "金", "土", "日"]
    for i, w in enumerate(WARDS):
        with tabs[i]:
            cb1, cb2, cb3, cb4 = st.columns(4)
            b_d = st.session_state.busy_days[w]
            with cb1: b_d["d1"] = st.selectbox("☀️ 忙しい日勤①", opts, index=opts.index(b_d["d1"]), key=f"bd_d1_{w}")
            with cb2: b_d["d2"] = st.selectbox("☀️ 忙しい日勤②", opts, index=opts.index(b_d["d2"]), key=f"bd_d2_{w}")
            with cb3: b_d["n1"] = st.selectbox("🌙 忙しい夜勤①", opts, index=opts.index(b_d["n1"]), key=f"bd_n1_{w}")
            with cb4: b_d["n2"] = st.selectbox("🌙 忙しい夜勤②", opts, index=opts.index(b_d["n2"]), key=f"bd_n2_{w}")

elif page == "📅 3段階・究極シフト作成":
    st.title("📅 3段階ヒューリスティクス 究極シフト作成")
    
    c_lim1, c_lim2, c_lim3 = st.columns(3)
    max_night_A = c_lim1.slider("🎖️ 指導(A) 夜勤上限", 4, 10, 6)
    max_night_B = c_lim2.slider("👤 自立(B) 夜勤上限", 4, 10, 6)
    max_night_C = c_lim3.slider("🔰 支援(C) 夜勤上限", 4, 10, 4)

    requests_off, requests_day, requests_night, prev_last_shift = {}, {}, {}, {}
    with st.expander("📝 簡易希望入力（全体）", expanded=False):
        for n in st.session_state.global_staff.keys():
            c1, c2, c3, c4, c5 = st.columns([1.5, 1, 1.5, 1.5, 1.5])
            c1.markdown(f"**{n}**")
            prev_last_shift[n] = c2.selectbox("前月末", ["休/日", "入", "明"], key=f"p_{n}", label_visibility="collapsed")
            requests_off[n] = c3.multiselect("休み", days, key=f"ro_{n}", label_visibility="collapsed")
            requests_day[n] = c4.multiselect("日勤", days, key=f"rd_{n}", label_visibility="collapsed")
            requests_night[n] = c5.multiselect("夜勤", days, key=f"rn_{n}", label_visibility="collapsed", disabled=not st.session_state.global_staff[n]["can_night"])

    if st.button("🚀 全体最適AIエンジンを起動する", type="primary"):
        with st.spinner("🧠 AIが全病棟のリソースを最適化中...判断理由も記録しています"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            master_schedule = {n: {} for n in st.session_state.global_staff.keys()}
            shifts_stage1 = ["入", "明", "未"] 
            shifts_stage2 = ["入", "明", "日", "休"] 
            
            # --- 【Phase 1 & 2】 ---
            for w_idx, ward_name in enumerate(WARDS):
                status_text.text(f"計算中... 【Phase 1&2】{ward_name} の個別シフトを構築中")
                ward_nurses = [n for n, d in st.session_state.global_staff.items() if d["ward"] == ward_name]
                A_nurses = [n for n in ward_nurses if st.session_state.global_staff[n]["skill"] == "A（指導）"]
                B_nurses = [n for n in ward_nurses if st.session_state.global_staff[n]["skill"] == "B（自立）"]
                C_nurses = [n for n in ward_nurses if st.session_state.global_staff[n]["skill"] == "C（支援）"]

                # 1. 夜勤
                prob1 = pulp.LpProblem(f"Night_{w_idx}", pulp.LpMinimize)
                x1 = pulp.LpVariable.dicts(f"x1_{w_idx}", (ward_nurses, days, shifts_stage1), cat=pulp.LpBinary)
                for n in ward_nurses:
                    for d in days: prob1 += pulp.lpSum([x1[n][d][s] for s in shifts_stage1]) == 1
                    for d in requests_off.get(n, []) + requests_day.get(n, []): prob1 += x1[n][d]["入"] == 0; prob1 += x1[n][d]["明"] == 0
                    for d in requests_night.get(n, []): prob1 += x1[n][d]["入"] == 1
                    prev = prev_last_shift.get(n, "休/日")
                    if prev == "入": prob1 += x1[n][1]["明"] == 1
                    elif prev == "明": prob1 += x1[n][1]["入"] == 0; prob1 += x1[n][1]["明"] == 0
                    else: prob1 += x1[n][1]["明"] == 0
                    for d in range(1, 30):
                        prob1 += x1[n][d+1]["明"] == x1[n][d]["入"]; prob1 += x1[n][d+1]["入"] <= 1 - x1[n][d]["明"]
                    if not st.session_state.global_staff[n]["can_night"]:
                        for d in days: prob1 += x1[n][d]["入"] == 0
                    else:
                        max_n = max_night_A if n in A_nurses else (max_night_C if n in C_nurses else max_night_B)
                        prob1 += pulp.lpSum([x1[n][d]["入"] for d in days]) >= 2; prob1 += pulp.lpSum([x1[n][d]["入"] for d in days]) <= max_n
                for d in days:
                    prob1 += pulp.lpSum([x1[n][d]["入"] for n in ward_nurses]) == 3 
                    prob1 += pulp.lpSum([x1[n][d]["入"] for n in C_nurses]) <= 1
                    if st.session_state.pairing_rules["night_min_A"]: prob1 += pulp.lpSum([x1[n][d]["入"] for n in A_nurses]) >= 1
                prob1.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=40))
                stage1_results = {n: {d: [s for s in shifts_stage1 if pulp.value(x1[n][d][s]) == 1][0] for d in days} for n in ward_nurses}

                # 2. 日勤
                prob2 = pulp.LpProblem(f"Day_{w_idx}", pulp.LpMinimize)
                x2 = pulp.LpVariable.dicts(f"x2_{w_idx}", (ward_nurses, days, shifts_stage2), cat=pulp.LpBinary)
                for n in ward_nurses:
                    for d in days:
                        prob2 += pulp.lpSum([x2[n][d][s] for s in shifts_stage2]) == 1
                        if stage1_results[n][d] in ["入", "明"]: prob2 += x2[n][d][stage1_results[n][d]] == 1 
                        else: prob2 += x2[n][d]["入"] == 0; prob2 += x2[n][d]["明"] == 0
                    if prev_last_shift.get(n) == "明": prob2 += x2[n][1]["休"] == 1
                    for d in requests_off.get(n, []): prob2 += x2[n][d]["休"] == 1
                    for d in requests_day.get(n, []): prob2 += x2[n][d]["日"] == 1
                    prob2 += pulp.lpSum([x2[n][d]["休"] for d in days]) >= 9; prob2 += pulp.lpSum([x2[n][d]["休"] for d in days]) <= 11
                    for d in range(1, 30): prob2 += x2[n][d+1]["休"] >= x2[n][d]["明"]
                    for d in range(1, 26): prob2 += pulp.lpSum([x2[n][d+k]["休"] for k in range(6)]) >= 1
                for d in days: prob2 += pulp.lpSum([x2[n][d]["日"] for n in ward_nurses]) >= 9
                prob2.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=40))
                for n in ward_nurses:
                    for d in days: master_schedule[n][d] = {"shift": [s for s in shifts_stage2 if pulp.value(x2[n][d][s]) == 1][0], "loc": ward_name}
                progress_bar.progress((w_idx + 1) * 30)

            # --- 【Phase 3】応援調整 ＆ ログ記録 ---
            status_text.text("計算中... 【Phase 3】応援が必要な日を特定し、根拠を記録中")
            float_logs = []
            for d in days:
                daily_pts = {w: 0 for w in WARDS}
                work_nurses = {w: [] for w in WARDS}
                for n, sch in master_schedule.items():
                    if sch[d]["shift"] == "日":
                        w = sch[d]["loc"]
                        skill = st.session_state.global_staff[n]["skill"]
                        daily_pts[w] += (3 if skill == "A（指導）" else 2 if skill == "B（自立）" else 1)
                        work_nurses[w].append(n)
                
                adjusting = True
                while adjusting:
                    adjusting = False
                    deficits = [w for w in WARDS if daily_pts[w] < st.session_state.target_points[w]]
                    surpluses = [w for w in WARDS if daily_pts[w] > st.session_state.target_points[w]]
                    if deficits and surpluses:
                        t_w = sorted(deficits, key=lambda w: daily_pts[w] - st.session_state.target_points[w])[0]
                        s_w = sorted(surpluses, key=lambda w: daily_pts[w] - st.session_state.target_points[w], reverse=True)[0]
                        cands = [n for n in work_nurses[s_w] if st.session_state.global_staff[n]["can_float"]]
                        for cand in cands:
                            c_sk = st.session_state.global_staff[cand]["skill"]
                            lost_pt = (3 if c_sk == "A（指導）" else 2)
                            if daily_pts[s_w] - lost_pt < st.session_state.target_points[s_w]: continue
                            if c_sk == "A（指導）":
                                rem_A = sum(1 for n in work_nurses[s_w] if st.session_state.global_staff[n]["skill"] == "A（指導）" and n != cand)
                                if any(st.session_state.global_staff[n]["skill"] == "C（支援）" for n in work_nurses[s_w]) and rem_A == 0: continue
                            
                            # 応援決定！ログを残す
                            t_w_short = t_w.split(" ")[1][:2]
                            s_w_short = s_w.split(" ")[1][:2]
                            float_logs.append({
                                "日": f"{d}日", "スタッフ": cand, "移動": f"{s_w_short} ➔ {t_w_short}",
                                "理由": f"{t_w_short}の不足({st.session_state.target_points[t_w] - daily_pts[t_w]}pt)に対し、余裕のある{s_w_short}から{c_sk[0]}ランクを派遣。"
                            })
                            master_schedule[cand][d]["loc"] = t_w
                            work_nurses[s_w].remove(cand)
                            work_nurses[t_w].append(cand)
                            daily_pts[s_w] -= lost_pt
                            daily_pts[t_w] += 2
                            adjusting = True
                            break
            
            progress_bar.progress(100)
            status_text.text("✨ 究極の全体最適化が完了しました！")
            
            # --- 出力表示 ---
            out_data = []
            for n, sch in master_schedule.items():
                h_w = st.session_state.global_staff[n]["ward"].split(" ")[0]
                sk = st.session_state.global_staff[n]["skill"][0]
                row = {"所属": h_w, "名前": f"{n}\n({sk})"}
                for d in days:
                    s = sch[d]["shift"]; loc = sch[d]["loc"].split(" ")[0]
                    if s == "日" and loc != h_w: row[str(d)] = f"🚀応援({loc.replace('🏥','')})"
                    else: row[str(d)] = "休*" if d in requests_off.get(n, []) and s == "休" else s
                out_data.append(row)
            
            st.success("🎉 シフト表が完成しました！下に応援の調整理由を記載しています。")
            st.dataframe(pd.DataFrame(out_data).sort_values("所属"), width='stretch', height=600)
            
            if float_logs:
                st.subheader("📝 応援アサインの判断根拠（ログ）")
                st.table(pd.DataFrame(float_logs))
            else:
                st.info("今回のシフトでは、各病棟のリソースのみで目標デマンドを達成できたため、応援の必要はありませんでした。")