"""策略实验室：定投信号、网格设计、轮动观察与通用回测"""

from __future__ import annotations

import json
from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.core.config import get_etf_universe
from src.dashboard.backtest_jobs import run_strategy_backtest_job
from src.dashboard.components import (
    render_empty_state,
    render_page_header,
    render_page_help,
    render_result_table,
)
from src.dashboard.formatting import format_display_datetime
from src.dashboard.services import save_backtest_scenario
from src.dashboard.styles import configure_dashboard_page, inject_global_styles
from src.dashboard.task_runner import (
    dashboard_task_to_dict,
    list_dashboard_tasks,
    submit_dashboard_task,
)
from src.data.storage import StorageEngine

configure_dashboard_page("策略实验室")
inject_global_styles()

render_page_header("策略实验室", "定投、网格、轮动观察、通用回测与批量回测。")
render_page_help(
    [
        (
            "页面用途",
            "用于设计 ETF 策略、提交后台回测、对比回测结果，并保存可复用的策略方案。",
        ),
        (
            "主要功能",
            [
                "信号工具：定投信号、网格设计、轮动观察。",
                "回测中心：通用回测、批量回测、回测结果、方案对比。",
            ],
        ),
        (
            "推荐使用顺序",
            [
                "在「信号工具」选择 ETF，确认行情日期与均线偏离是否合理。",
                "在「回测中心 → 通用回测」提交单策略任务，或「批量回测」覆盖多 ETF。",
                "到「回测结果」查看指标与曲线，满意后保存为方案。",
                "在「方案对比」横向比较已保存方案的收益与回撤。",
            ],
        ),
        ("数据依赖", "依赖 ETF 历史行情和策略配置；行情不足时请先在数据管理页补采。"),
    ]
)


def _load_etf_options() -> dict[str, str]:
    universe = get_etf_universe()
    options = {}
    for category in universe.get("etf_universe", {}).values():
        for item in category:
            label = f"{item['name']} ({item['code']})"
            options[label] = item["code"]
    return options


@st.cache_data(ttl=300)
def _load_price_data(code: str) -> pd.DataFrame:
    storage = StorageEngine()
    try:
        storage.init_schema()
        df = storage.get_etf_daily(code)
    except Exception:
        return pd.DataFrame()
    finally:
        storage.close()
    if not df.empty:
        df = df.copy()
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    return df


def _render_backtest_payload(payload: dict) -> None:
    summary = payload.get("summary", {})
    records = pd.DataFrame(payload.get("daily_records", []))
    if records.empty:
        st.info("暂无回测记录")
        return

    records["日期"] = pd.to_datetime(records["trade_date"])
    records["收益率"] = records["net_return"] * 100
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=records["日期"], y=records["收益率"], mode="lines", name="收益率"))
    fig.update_layout(height=360, yaxis_title="收益率(%)")
    st.plotly_chart(fig, width="stretch")

    st.download_button(
        "下载回测结果 JSON",
        data=json.dumps(payload, ensure_ascii=False, indent=2),
        file_name=(
            f"backtest_{summary.get('etf_code', 'etf')}_"
            f"{summary.get('start_date', '')}_{summary.get('end_date', '')}.json"
        ),
        mime="application/json",
    )

    orders = pd.DataFrame(payload.get("orders", []))
    if not orders.empty:
        orders = orders.rename(
            columns={
                "trade_date": "日期",
                "direction": "方向",
                "amount": "金额",
                "price": "价格",
                "shares": "份额",
                "reason": "原因",
            }
        )
        render_result_table(orders.tail(50), empty_message="暂无成交记录")


def _backtest_task_rows(limit: int = 100) -> list[dict]:
    return [
        dashboard_task_to_dict(task)
        for task in list_dashboard_tasks(limit)
        if task.task_type == "backtest"
    ]


def _backtest_templates() -> dict[str, dict]:
    return {
        "月度普通定投 1000": {
            "strategy_name": "普通定投",
            "params": {"amount": 1000, "frequency": "monthly"},
        },
        "周度普通定投 500": {
            "strategy_name": "普通定投",
            "params": {"amount": 500, "frequency": "weekly"},
        },
        "MA250 偏离定投": {
            "strategy_name": "均线偏离定投",
            "params": {"base_amount": 1000, "frequency": "monthly", "ma_period": 250},
        },
        "等差网格 20% 区间": {
            "strategy_name": "等差网格",
            "params": {"range_pct": 0.2, "num_grids": 10, "amount_per_grid": 1000},
        },
        "等比网格 25% 区间": {
            "strategy_name": "等比网格",
            "params": {"range_pct": 0.25, "num_grids": 12, "amount_per_grid": 1000},
        },
    }


def _materialize_template_params(template: dict, latest_price: float) -> dict:
    params = dict(template["params"])
    range_pct = params.pop("range_pct", None)
    if range_pct is not None:
        params["price_lower"] = round(latest_price * (1 - float(range_pct)), 4)
        params["price_upper"] = round(latest_price * (1 + float(range_pct)), 4)
    return params


def _safe_return(df: pd.DataFrame, days: int) -> float | None:
    if df.empty or len(df) <= days:
        return None
    latest = df["close"].iloc[-1]
    prev = df["close"].iloc[-days - 1]
    if prev == 0 or pd.isna(prev) or pd.isna(latest):
        return None
    return (latest / prev - 1) * 100


@st.cache_data(ttl=300)
def _load_saved_scenarios() -> pd.DataFrame:
    storage = StorageEngine()
    try:
        storage.init_schema()
        df = storage.get_backtest_scenarios()
    except Exception:
        return pd.DataFrame()
    finally:
        storage.close()
    return df


etf_options = _load_etf_options()

outer_signal, outer_backtest = st.tabs(["信号工具", "回测中心"])

with outer_signal:
    tab_dca, tab_grid, tab_rotation = st.tabs(["定投信号", "网格设计", "轮动观察"])
    with tab_dca:
        st.subheader("定投信号")
        selected_label = st.selectbox("选择 ETF", list(etf_options), key="dca_etf")
        code = etf_options[selected_label]
        df = _load_price_data(code)

        if df.empty:
            st.warning("暂无该 ETF 行情数据，请先到数据管理页更新。")
        else:
            amount = st.number_input("基础定投金额", min_value=100, value=1000, step=100)
            ma_period = st.slider("均线偏离周期", min_value=60, max_value=500, value=250, step=10)
            latest = df.iloc[-1]
            close = float(latest["close"])
            ma = df["close"].tail(ma_period).mean() if len(df) >= ma_period else None
            deviation = (close / ma - 1) * 100 if ma and ma > 0 else None

            dca_cols = st.columns(4)
            dca_cols[0].metric("最新价格", f"{close:.3f}")
            dca_cols[1].metric(
                "数据日期",
                format_display_datetime(latest["trade_date"], date_only=True),
            )
            dca_cols[2].metric("MA偏离", f"{deviation:+.1f}%" if deviation is not None else "--")

            if deviation is None:
                multiplier = 1.0
                reason = f"历史不足 {ma_period} 日，按基础金额"
            elif deviation < -12.5:
                multiplier = 4.0
                reason = "深度低于均线，强力加码"
            elif deviation < -5:
                multiplier = 3.0
                reason = "明显低于均线，加码"
            elif deviation < 0:
                multiplier = 2.0
                reason = "略低于均线，提高投入"
            elif deviation < 10:
                multiplier = 1.0
                reason = "常规投入"
            elif deviation < 20:
                multiplier = 0.6
                reason = "略偏热，降低投入"
            elif deviation < 30:
                multiplier = 0.3
                reason = "明显偏热，小额观察"
            else:
                multiplier = 0.0
                reason = "偏离过高，暂停"

            dca_cols[3].metric("建议金额", f"¥{amount * multiplier:,.0f}")
            st.info(reason)

            fig = go.Figure()
            recent = df.tail(360)
            fig.add_trace(go.Scatter(x=recent["trade_date"], y=recent["close"], name="收盘价"))
            if ma is not None:
                ma_series = recent["close"].rolling(ma_period, min_periods=20).mean()
                fig.add_trace(
                    go.Scatter(
                        x=recent["trade_date"],
                        y=ma_series,
                        name=f"MA{ma_period}",
                    )
                )
            fig.update_layout(height=360)
            st.plotly_chart(fig, width="stretch")

    with tab_grid:
        st.subheader("网格设计")
        selected_label = st.selectbox("选择 ETF", list(etf_options), key="grid_etf")
        code = etf_options[selected_label]
        df = _load_price_data(code)
        if df.empty:
            st.warning("暂无该 ETF 行情数据，请先到数据管理页更新。")
        else:
            latest_price = float(df["close"].iloc[-1])
            g1, g2, g3, g4 = st.columns(4)
            lower = g1.number_input("下限价格", value=round(latest_price * 0.8, 3), min_value=0.001)
            upper = g2.number_input("上限价格", value=round(latest_price * 1.2, 3), min_value=0.001)
            grids = g3.number_input("网格数量", value=10, min_value=2, max_value=80)
            grid_type = g4.selectbox("网格类型", ["等差", "等比"])

            if upper <= lower:
                st.error("上限价格必须大于下限价格")
            else:
                if grid_type == "等差":
                    lines = [lower + (upper - lower) * i / grids for i in range(grids + 1)]
                else:
                    ratio = upper / lower
                    lines = [lower * ratio ** (i / grids) for i in range(grids + 1)]

                st.metric("当前价格", f"{latest_price:.3f}")
                fig = go.Figure()
                recent = df.tail(240)
                fig.add_trace(go.Scatter(x=recent["trade_date"], y=recent["close"], name="收盘价"))
                for line in lines:
                    fig.add_hline(y=line, line_width=1, line_dash="dot", line_color="#999")
                fig.update_layout(height=420)
                st.plotly_chart(fig, width="stretch")
                grid_rows = pd.DataFrame(
                    {
                        "网格序号": range(len(lines)),
                        "价格": [round(x, 4) for x in lines],
                    }
                )
                st.dataframe(
                    grid_rows,
                    width="stretch",
                    hide_index=True,
                )

    with tab_rotation:
        st.subheader("轮动观察")
        pairs = {
            "上证50 vs 中证1000": ("510050", "512100"),
            "沪深300 vs 中证500": ("510300", "510500"),
            "人工智能 vs 机器人": ("515980", "562500"),
            "卫星主题双 ETF": ("563230", "159206"),
        }
        pair_name = st.selectbox("轮动配对", list(pairs))
        lookback = st.slider("动量回看天数", min_value=5, max_value=120, value=20, step=5)
        code_a, code_b = pairs[pair_name]
        df_a = _load_price_data(code_a)
        df_b = _load_price_data(code_b)

        if df_a.empty or df_b.empty:
            st.warning("配对 ETF 数据不足，请先更新行情。")
        else:
            ret_a = _safe_return(df_a, lookback)
            ret_b = _safe_return(df_b, lookback)
            c1, c2, c3 = st.columns(3)
            c1.metric(code_a, f"{ret_a:+.2f}%" if ret_a is not None else "--")
            c2.metric(code_b, f"{ret_b:+.2f}%" if ret_b is not None else "--")
            if ret_a is None or ret_b is None:
                c3.metric("建议持有", "--")
            else:
                c3.metric("建议持有", code_a if ret_a >= ret_b else code_b)

            chart = pd.merge(
                df_a[["trade_date", "close"]].rename(columns={"close": code_a}),
                df_b[["trade_date", "close"]].rename(columns={"close": code_b}),
                on="trade_date",
                how="inner",
            ).tail(240)
            chart[code_a] = (chart[code_a] / chart[code_a].iloc[0] - 1) * 100
            chart[code_b] = (chart[code_b] / chart[code_b].iloc[0] - 1) * 100
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=chart["trade_date"], y=chart[code_a], name=code_a))
            fig.add_trace(go.Scatter(x=chart["trade_date"], y=chart[code_b], name=code_b))
            fig.update_layout(height=380, yaxis_title="阶段收益率(%)")
            st.plotly_chart(fig, width="stretch")


with outer_backtest:
    tab_backtest, tab_batch, tab_results, tab_compare = st.tabs(
        ["通用回测", "批量回测", "回测结果", "方案对比"]
    )
    with tab_backtest:
        st.subheader("通用回测")
        selected_label = st.selectbox("选择 ETF", list(etf_options), key="bt_etf")
        code = etf_options[selected_label]
        df = _load_price_data(code)
        if df.empty:
            st.warning("暂无该 ETF 行情数据，请先到数据管理页更新。")
        else:
            min_date = df["trade_date"].iloc[0]
            max_date = df["trade_date"].iloc[-1]
            default_start = max(min_date, max_date - timedelta(days=365 * 3))
            b1, b2, b3 = st.columns(3)
            strategy_name = b1.selectbox(
                "策略",
                ["普通定投", "均线偏离定投", "等差网格", "等比网格"],
            )
            start = b2.date_input(
                "开始日期",
                value=default_start,
                min_value=min_date,
                max_value=max_date,
            )
            end = b3.date_input("结束日期", value=max_date, min_value=min_date, max_value=max_date)

            if strategy_name in ["普通定投", "均线偏离定投"]:
                p1, p2 = st.columns(2)
                base_amount = p1.number_input("投入金额", min_value=100, value=1000, step=100)
                frequency = p2.selectbox("频率", ["monthly", "weekly", "biweekly"])
                if strategy_name == "普通定投":
                    params = {"amount": base_amount, "frequency": frequency}
                else:
                    ma_period = st.slider("均线周期", 60, 500, 250, 10)
                    params = {
                        "base_amount": base_amount,
                        "frequency": frequency,
                        "ma_period": ma_period,
                    }
            else:
                latest_price = float(df["close"].iloc[-1])
                p1, p2, p3, p4 = st.columns(4)
                lower = p1.number_input("下限", value=round(latest_price * 0.8, 3), min_value=0.001)
                upper = p2.number_input("上限", value=round(latest_price * 1.2, 3), min_value=0.001)
                grids = p3.number_input("网格数", min_value=2, max_value=80, value=10)
                amount = p4.number_input("每格金额", min_value=100, value=1000, step=100)
                params = {
                    "price_lower": lower,
                    "price_upper": upper,
                    "num_grids": int(grids),
                    "amount_per_grid": amount,
                }

            if st.button("运行回测", type="primary"):
                task_key = (
                    f"backtest:{code}:{strategy_name}:{start.isoformat()}:{end.isoformat()}:"
                    f"{json.dumps(params, ensure_ascii=False, sort_keys=True)}"
                )
                task = submit_dashboard_task(
                    f"策略回测：{strategy_name} {code}",
                    run_strategy_backtest_job,
                    code,
                    strategy_name,
                    params,
                    start,
                    end,
                    task_key=task_key,
                    task_type="backtest",
                    tags=["strategy_lab", code, strategy_name],
                )
                st.success(f"已提交后台回测任务：{task.id}，可在“回测结果”查看。")

    with tab_batch:
        st.subheader("批量回测")
        st.caption("选择多个 ETF 和参数模板后，会按组合批量提交后台任务。")
        template_options = _backtest_templates()
        selected_etf_labels = st.multiselect(
            "ETF",
            list(etf_options),
            default=list(etf_options)[: min(3, len(etf_options))],
        )
        selected_templates = st.multiselect(
            "参数模板",
            list(template_options),
            default=list(template_options)[:2],
        )
        years = st.slider("回测窗口(年)", min_value=1, max_value=8, value=3)
        if st.button("提交批量回测", type="primary"):
            submitted = []
            skipped = []
            for etf_label in selected_etf_labels:
                etf_code = etf_options[etf_label]
                df_batch = _load_price_data(etf_code)
                if df_batch.empty:
                    skipped.append(f"{etf_code}: 无行情")
                    continue
                max_date = df_batch["trade_date"].iloc[-1]
                min_date = df_batch["trade_date"].iloc[0]
                start_date = max(min_date, max_date - timedelta(days=365 * years))
                latest_price = float(df_batch["close"].iloc[-1])
                for template_name in selected_templates:
                    template = template_options[template_name]
                    strategy = template["strategy_name"]
                    params = _materialize_template_params(template, latest_price)
                    task_key = (
                        f"backtest:{etf_code}:{strategy}:{start_date.isoformat()}:"
                        f"{max_date.isoformat()}:{template_name}:"
                        f"{json.dumps(params, ensure_ascii=False, sort_keys=True)}"
                    )
                    task = submit_dashboard_task(
                        f"批量回测：{template_name} {etf_code}",
                        run_strategy_backtest_job,
                        etf_code,
                        strategy,
                        params,
                        start_date,
                        max_date,
                        task_key=task_key,
                        task_type="backtest",
                        tags=["batch_backtest", etf_code, template_name],
                    )
                    submitted.append(task.id)
            if submitted:
                st.success(f"已提交 {len(submitted)} 个后台回测任务。")
            if skipped:
                st.warning("跳过：" + "；".join(skipped))

    with tab_results:
        st.subheader("回测结果")
        task_rows = _backtest_task_rows()
        if not task_rows:
            render_empty_state("暂无后台回测任务，请先在“通用回测”中提交。")
        else:
            task_display = pd.DataFrame(
                [
                    {
                        "任务ID": row["id"],
                        "任务": row["name"],
                        "状态": row["status"],
                        "创建时间": row["created_at"],
                        "结束时间": row["finished_at"] or "",
                        "错误": row["error"],
                    }
                    for row in task_rows
                ]
            )
            render_result_table(task_display, empty_message="暂无后台回测任务")
            options = {
                f"{row['created_at']} | {row['name']} | {row['status']}": row for row in task_rows
            }
            selected_label = st.selectbox("选择回测任务", list(options))
            selected_task = options[selected_label]
            if selected_task["status"] != "success":
                if selected_task["error"]:
                    st.error(selected_task["error"])
                else:
                    st.info("任务尚未完成，稍后刷新查看结果。")
            else:
                payload = selected_task.get("result") or {}
                summary = payload.get("summary", {})
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("总收益率", f"{summary.get('total_return', 0) * 100:.1f}%")
                m2.metric("年化收益", f"{summary.get('annual_return', 0) * 100:.1f}%")
                m3.metric("最大回撤", f"-{summary.get('max_drawdown', 0) * 100:.1f}%")
                m4.metric("交易次数", summary.get("total_trades", 0))
                m5, m6, m7 = st.columns(3)
                m5.metric("夏普比率", f"{summary.get('sharpe_ratio', 0):.2f}")
                m6.metric("累计投入", f"¥{summary.get('total_invested', 0):,.0f}")
                m7.metric("最终资产", f"¥{summary.get('final_value', 0):,.0f}")
                _render_backtest_payload(payload)

                s1, s2 = st.columns([2, 1])
                scenario_name = s1.text_input(
                    "方案名称",
                    value=f"{summary.get('strategy_name', '')} - {summary.get('etf_code', '')}",
                )
                if s2.button("保存为方案", width="stretch"):
                    save_payload = dict(summary)
                    save_payload["scenario_name"] = scenario_name
                    save_backtest_scenario(save_payload)
                    st.cache_data.clear()
                    st.success("方案已保存")

    with tab_compare:
        st.subheader("方案对比")
        scenarios = _load_saved_scenarios()
        if scenarios.empty:
            render_empty_state("暂无已保存方案，请先在通用回测中保存。")
        else:
            scenarios = scenarios.copy()
            scenarios["标签"] = (
                scenarios["scenario_name"]
                + " | "
                + scenarios["etf_code"]
                + " | "
                + scenarios["strategy_name"]
            )
            labels = scenarios["标签"].tolist()
            selected_labels = st.multiselect(
                "选择方案",
                labels,
                default=labels[: min(4, len(labels))],
            )
            selected = scenarios[scenarios["标签"].isin(selected_labels)].copy()
            if selected.empty:
                render_empty_state("请至少选择一个方案。")
            else:
                display = selected[
                    [
                        "scenario_name",
                        "etf_code",
                        "strategy_name",
                        "start_date",
                        "end_date",
                        "total_return",
                        "annual_return",
                        "max_drawdown",
                        "sharpe_ratio",
                        "total_trades",
                    ]
                ].rename(
                    columns={
                        "scenario_name": "方案",
                        "etf_code": "ETF",
                        "strategy_name": "策略",
                        "start_date": "开始",
                        "end_date": "结束",
                        "total_return": "总收益",
                        "annual_return": "年化",
                        "max_drawdown": "最大回撤",
                        "sharpe_ratio": "夏普",
                        "total_trades": "交易次数",
                    }
                )
                for col in ["总收益", "年化", "最大回撤"]:
                    display[col] = display[col].map(lambda value: f"{value * 100:.1f}%")
                st.dataframe(display, width="stretch", hide_index=True)

                chart_df = selected.copy()
                chart_df["最大回撤(%)"] = chart_df["max_drawdown"] * 100
                chart_df["年化收益(%)"] = chart_df["annual_return"] * 100
                fig_compare = go.Figure()
                for _, row in chart_df.iterrows():
                    params = json.loads(row["params"]) if row["params"] else {}
                    fig_compare.add_trace(
                        go.Scatter(
                            x=[row["最大回撤(%)"]],
                            y=[row["年化收益(%)"]],
                            mode="markers+text",
                            text=[row["scenario_name"]],
                            textposition="top center",
                            name=f"{row['scenario_name']} | {params}",
                            marker={"size": max(row["sharpe_ratio"], 0.1) * 12},
                        )
                    )
                fig_compare.update_layout(
                    height=420,
                    xaxis_title="最大回撤(%)",
                    yaxis_title="年化收益(%)",
                    showlegend=False,
                )
                st.plotly_chart(fig_compare, width="stretch")
