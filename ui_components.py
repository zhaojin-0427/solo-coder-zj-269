import traceback

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc

from data_parser import CATEGORIES
from analytics import is_holiday_month


def empty_fig(title="暂无数据"):
    fig = go.Figure()
    fig.update_layout(title=title, height=300, xaxis=dict(visible=False), yaxis=dict(visible=False))
    return fig


def make_category_pie(df):
    if df.empty:
        return empty_fig()
    try:
        cat_sum = df.groupby('类别')['金额'].sum().reset_index()
        cat_sum = cat_sum.sort_values('金额', ascending=False)
        colors = px.colors.qualitative.Pastel
        fig = go.Figure(data=[go.Pie(
            labels=cat_sum['类别'],
            values=cat_sum['金额'],
            hole=0.4,
            marker=dict(colors=colors[:len(cat_sum)]),
            textinfo='label+percent',
            textposition='outside',
        )])
        fig.update_layout(
            title="支出类别分布",
            height=420,
            margin=dict(l=20, r=20, t=50, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=-0.1)
        )
        return fig
    except Exception:
        traceback.print_exc()
        return empty_fig("图表生成失败")


def make_budget_progress(df, budget_config):
    if df.empty:
        return empty_fig()
    try:
        monthly_sum = df.groupby('月份')['金额'].sum()
        if len(monthly_sum) == 0:
            return empty_fig()

        if budget_config:
            current_month = str(monthly_sum.index[-1])
            current_month_data = df[df['月份'] == current_month]
            cats = []
            spent_vals = []
            budget_vals = []
            flex_vals = []
            for cat in CATEGORIES:
                cat_spent = float(current_month_data[current_month_data['类别'] == cat]['金额'].sum())
                cfg = budget_config.get(cat, {})
                cat_budget = float(cfg.get('budget', 0))
                flex = float(cfg.get('flex_range', 10)) / 100.0
                if cat_budget > 0 or cat_spent > 0:
                    cats.append(cat)
                    spent_vals.append(round(cat_spent, 2))
                    budget_vals.append(round(cat_budget, 2))
                    flex_vals.append(round(cat_budget * (1 + flex), 2))

            if cats:
                pcts = []
                texts = []
                colors = []
                for s, b, f in zip(spent_vals, budget_vals, flex_vals):
                    if b > 0:
                        pct = min(s / b * 100, 150)
                        pcts.append(pct)
                        texts.append(f"{s}/{b}<br>{s/b*100:.0f}%")
                        if s > b:
                            colors.append('#d62728')
                        elif s > b * 0.8:
                            colors.append('#ff7f0e')
                        else:
                            colors.append('#2ca02c')
                    else:
                        pcts.append(0)
                        texts.append(f"{s}")
                        colors.append('#1f77b4')

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=cats, y=pcts,
                    marker_color=colors,
                    text=texts,
                    textposition='auto',
                    name='预算执行率'
                ))
                fig.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="预算线")
                fig.add_hline(y=110, line_dash="dot", line_color="orange", annotation_text="弹性上限")
                fig.update_layout(
                    title=f"{current_month} 各类别预算执行进度",
                    yaxis_title="执行率 (%)",
                    height=380,
                    margin=dict(l=40, r=20, t=50, b=40),
                    showlegend=False
                )
                return fig

        fig = go.Figure(go.Bar(
            x=list(monthly_sum.index), y=list(monthly_sum.values),
            marker_color='#636EFA',
            text=[f"¥{v:.0f}" for v in monthly_sum.values],
            textposition='outside'
        ))
        fig.update_layout(
            title="月度总支出",
            yaxis_title="金额 (¥)",
            height=380,
            margin=dict(l=40, r=20, t=50, b=40),
        )
        return fig
    except Exception:
        traceback.print_exc()
        return empty_fig("图表生成失败")


def make_heatmap(df):
    if df.empty:
        return empty_fig()
    try:
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_cn = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        hour_bins = [0, 6, 12, 14, 18, 22, 24]
        hour_labels = ['凌晨(0-6)', '上午(6-12)', '午间(12-14)', '下午(14-18)', '晚间(18-22)', '深夜(22-24)']

        df_copy = df.copy()
        df_copy['时段'] = pd.cut(df_copy['小时'], bins=hour_bins, labels=hour_labels, include_lowest=True, right=False)
        heat = df_copy.groupby(['星期', '时段'])['金额'].sum().unstack(fill_value=0)
        for d in day_order:
            if d not in heat.index:
                heat.loc[d] = 0
        heat = heat.reindex(day_order)
        heat.index = day_cn
        for hl in hour_labels:
            if hl not in heat.columns:
                heat[hl] = 0
        heat = heat[hour_labels]

        fig = go.Figure(data=go.Heatmap(
            z=heat.values,
            x=list(heat.columns),
            y=list(heat.index),
            colorscale='YlOrRd',
            text=[[f"¥{v:.0f}" for v in row] for row in heat.values],
            texttemplate="%{text}",
            hoverongaps=False
        ))
        fig.update_layout(
            title="消费时段热力图",
            height=380,
            margin=dict(l=60, r=20, t=50, b=40),
        )
        return fig
    except Exception:
        traceback.print_exc()
        return empty_fig("图表生成失败")


def make_emotion_scatter(df):
    if df.empty:
        return empty_fig()
    try:
        fig = px.scatter(
            df, x='日期', y='金额',
            color='情绪标签',
            size='金额',
            size_max=20,
            hover_data=['类别', '支付方式', '场景', '备注'],
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig.update_layout(
            title="情绪消费散点图",
            xaxis_title="日期",
            yaxis_title="金额 (¥)",
            height=420,
            margin=dict(l=40, r=20, t=50, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=-0.2)
        )
        return fig
    except Exception:
        traceback.print_exc()
        return empty_fig("图表生成失败")


def make_trend_chart(df):
    if df.empty:
        return empty_fig()
    try:
        monthly_trend = df.groupby('月份').agg(
            总支出=('金额', 'sum'),
            消费次数=('金额', 'count'),
            平均客单价=('金额', 'mean')
        ).reset_index()

        if monthly_trend.empty:
            return empty_fig()

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(
            x=list(monthly_trend['月份']), y=list(monthly_trend['总支出']),
            name='总支出', marker_color='#636EFA',
            text=[f"¥{v:.0f}" for v in monthly_trend['总支出']],
            textposition='outside'
        ), secondary_y=False)
        fig.add_trace(go.Scatter(
            x=list(monthly_trend['月份']), y=list(monthly_trend['平均客单价']),
            name='平均客单价', mode='lines+markers',
            line=dict(color='#EF553B', width=3),
            marker=dict(size=8)
        ), secondary_y=True)
        fig.add_trace(go.Scatter(
            x=list(monthly_trend['月份']), y=list(monthly_trend['消费次数']),
            name='消费次数', mode='lines+markers',
            line=dict(color='#00CC96', width=2, dash='dot'),
            marker=dict(size=6)
        ), secondary_y=True)

        if len(monthly_trend) >= 2:
            x_arr = np.arange(len(monthly_trend))
            y_arr = monthly_trend['总支出'].values.astype(float)
            z = np.polyfit(x_arr, y_arr, 1)
            p = np.poly1d(z)
            fig.add_trace(go.Scatter(
                x=list(monthly_trend['月份']),
                y=list(p(x_arr)),
                name=f"趋势线 (斜率: {z[0]:.0f})",
                line=dict(color='gray', dash='dash', width=2),
                mode='lines'
            ), secondary_y=False)

        fig.update_layout(
            title="月度消费趋势分析",
            height=450,
            margin=dict(l=40, r=40, t=50, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=-0.2),
            barmode='group'
        )
        fig.update_yaxes(title_text="总支出 (¥)", secondary_y=False)
        fig.update_yaxes(title_text="客单价/次数", secondary_y=True)
        return fig
    except Exception:
        traceback.print_exc()
        return empty_fig("图表生成失败")


def make_payment_chart(df):
    if df.empty:
        return empty_fig()
    try:
        pay = df.groupby('支付方式')['金额'].sum().reset_index().sort_values('金额', ascending=True)
        fig = go.Figure(go.Bar(
            x=list(pay['金额']), y=list(pay['支付方式']),
            orientation='h',
            marker_color=px.colors.qualitative.Pastel1[:len(pay)],
            text=[f"¥{v:.0f}" for v in pay['金额']],
            textposition='outside'
        ))
        fig.update_layout(
            title="支付方式分布",
            xaxis_title="金额 (¥)",
            height=350,
            margin=dict(l=80, r=40, t=50, b=40),
        )
        return fig
    except Exception:
        traceback.print_exc()
        return empty_fig("图表生成失败")


def make_budget_comparison_chart(ts_df):
    if ts_df is None or ts_df.empty:
        return empty_fig("暂无预算对比数据")
    try:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=ts_df['月份'], y=ts_df['实际支出'],
            name='实际支出',
            marker_color='#636EFA',
            text=[f"¥{v:.0f}" for v in ts_df['实际支出']],
            textposition='outside'
        ))
        fig.add_trace(go.Scatter(
            x=ts_df['月份'], y=ts_df['计划预算'],
            name='计划预算', mode='lines+markers',
            line=dict(color='#2ca02c', width=3, dash='solid'),
            marker=dict(size=10, symbol='square')
        ))
        fig.add_trace(go.Scatter(
            x=ts_df['月份'], y=ts_df['调整后预算'],
            name='调整后预算', mode='lines+markers',
            line=dict(color='#ff7f0e', width=3, dash='dash'),
            marker=dict(size=10, symbol='diamond')
        ))

        for i, row in ts_df.iterrows():
            if row.get('节假日'):
                fig.add_vline(
                    x=row['月份'], line_dash="dot", line_color="rgba(148,103,189,0.4)",
                    annotation_text="🎁", annotation_position="top"
                )

        fig.update_layout(
            title="实际支出 vs 计划预算 vs 调整后预算（多序列对比）",
            yaxis_title="金额 (¥)",
            height=450,
            margin=dict(l=60, r=20, t=50, b=80),
            legend=dict(orientation="h", yanchor="bottom", y=-0.25),
            barmode='overlay'
        )
        return fig
    except Exception:
        traceback.print_exc()
        return empty_fig("图表生成失败")


def make_abnormal_table(abnormal_df):
    if abnormal_df is None or abnormal_df.empty:
        return html.Div([
            html.H6("✅ 未发现异常超支", className="text-success mb-2"),
            html.P("所有类别支出均在预算范围内（含弹性区间）", className="text-muted small")
        ])

    cards = []
    reason_color_map = {
        '结构性超支': 'danger',
        '情绪驱动超支': 'warning',
        '节假日波动': 'info',
        '一次性大额支出': 'secondary'
    }
    reason_icon_map = {
        '结构性超支': '🏗️',
        '情绪驱动超支': '😤',
        '节假日波动': '🎁',
        '一次性大额支出': '💎'
    }

    for _, row in abnormal_df.iterrows():
        reason_badges = []
        total_attrib = sum(row['归因'].values())
        for r, amt in sorted(row['归因'].items(), key=lambda x: -x[1]):
            pct = amt / total_attrib * 100 if total_attrib > 0 else 0
            reason_badges.append(
                dbc.Badge(
                    f"{reason_icon_map.get(r, '•')} {r}: ¥{amt:.0f} ({pct:.0f}%)",
                    color=reason_color_map.get(r, 'secondary'),
                    className="me-1 mb-1",
                    pill=True
                )
            )

        over_pct = row['超支比例']
        if over_pct >= 30:
            header_color = 'danger'
        elif over_pct >= 15:
            header_color = 'warning'
        else:
            header_color = 'info'

        cards.append(
            dbc.Card([
                dbc.CardHeader([
                    html.Strong(f"{row['类别']}"),
                    dbc.Badge(f"超支 ¥{row['超支金额']:.0f} ({over_pct:.0f}%)",
                              color=header_color, className="ms-2")
                ], className=f"bg-{header_color} text-white"),
                dbc.CardBody([
                    html.Div([
                        html.Span(f"预算: ¥{row['预算']:.0f}", className="text-muted me-3"),
                        html.Span(f"实际: ¥{row['实际支出']:.0f}", className="fw-bold text-danger")
                    ], className="mb-2"),
                    html.Div([html.Small("归因分析: ", className="text-muted")] + reason_badges),
                    dbc.Progress(
                        value=min(over_pct, 150),
                        color=header_color,
                        className="mt-2",
                        style={'height': '6px'}
                    )
                ])
            ], className="mb-3")
        )

    return html.Div(cards)


def make_simulation_result(sim_result, budget_config):
    if not sim_result:
        return html.Div("暂无模拟数据", className="text-muted")

    warnings_html = []
    if sim_result.get('warnings'):
        for w in sim_result['warnings']:
            warnings_html.append(
                dbc.Alert(w, color="warning", className="py-2 px-3 mb-2 small")
            )

    tips_html = []
    if sim_result.get('tips'):
        for t in sim_result['tips']:
            tips_html.append(
                dbc.Alert(t, color="success", className="py-2 px-3 mb-2 small")
            )

    cat_rows = []
    for d in sim_result.get('category_detail', []):
        pct = d['预测支出'] / sim_result['projected_spending'] * 100 if sim_result['projected_spending'] > 0 else 0
        nec_color = 'success' if d['必要权重(%)'] >= 70 else ('warning' if d['必要权重(%)'] >= 40 else 'danger')
        cat_rows.append(
            html.Tr([
                html.Td(d['类别']),
                html.Td(f"¥{d['原预算']:.0f}"),
                html.Td(f"{d['弹性上限(%)']:.0f}%"),
                html.Td(dbc.Badge(f"{d['必要权重(%)']:.0f}%", color=nec_color, className="me-1")),
                html.Td(f"{d['节假日系数']:.1f}x"),
                html.Td([
                    html.Strong(f"¥{d['预测支出']:.0f}"),
                    dbc.Progress(value=pct, color="primary", className="mt-1", style={'height': '4px'})
                ])
            ])
        )

    summary_card = dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.Small("计划预算合计", className="text-muted d-block"),
                    html.H5(f"¥{sim_result['original_total']:.0f}", className="text-primary fw-bold mb-0")
                ]),
                dbc.Col([
                    html.Small("含节假日预测", className="text-muted d-block"),
                    html.H5(f"¥{sim_result['projected_spending']:.0f}", className="text-warning fw-bold mb-0")
                ]),
                dbc.Col([
                    html.Small("储蓄目标", className="text-muted d-block"),
                    html.H5(f"¥{sim_result['savings_goal']:.0f}", className="text-success fw-bold mb-0")
                ]),
                dbc.Col([
                    html.Small("可支配预算", className="text-muted d-block"),
                    html.H5(f"¥{sim_result['adjusted_total']:.0f}", className="text-info fw-bold mb-0")
                ])
            ])
        ])
    ], className="mb-3 border-primary")

    return html.Div([
        summary_card,
        html.H6("⚠️ 风险提示", className="mb-2 mt-3"),
        html.Div(warnings_html) if warnings_html else html.P("暂无风险提示", className="text-muted small"),
        html.H6("💡 优化建议", className="mb-2 mt-3"),
        html.Div(tips_html) if tips_html else html.P("暂无建议", className="text-muted small"),
        html.H6("📊 明细测算", className="mb-2 mt-3"),
        html.Div([
            dbc.Table([
                html.Thead(html.Tr([
                    html.Th("类别"), html.Th("原预算"), html.Th("弹性"),
                    html.Th("必要权重"), html.Th("节假日"), html.Th("预测支出")
                ])),
                html.Tbody(cat_rows)
            ], bordered=True, hover=True, size="sm", className="small")
        ], style={'maxHeight': '320px', 'overflowY': 'auto'})
    ])


def build_budget_controls(budget_config, default_savings=0):
    rows = []
    for cat in CATEGORIES:
        cfg = budget_config.get(cat, {'budget': 0, 'flex_range': 10, 'necessary_weight': 50, 'holiday_factor': 1.2})
        rows.append(html.Tr([
            html.Td(html.Strong(cat), style={'verticalAlign': 'middle'}),
            html.Td(
                dcc.Input(
                    id={'type': 'budget-input', 'category': cat},
                    type='number',
                    value=cfg.get('budget', 0),
                    min=0,
                    step=10,
                    className="form-control form-control-sm",
                    style={'width': '90px'}
                )
            ),
            html.Td(
                dcc.Input(
                    id={'type': 'flex-input', 'category': cat},
                    type='number',
                    value=cfg.get('flex_range', 10),
                    min=0,
                    max=100,
                    step=5,
                    className="form-control form-control-sm",
                    style={'width': '70px'}
                )
            ),
            html.Td(
                dcc.Slider(
                    id={'type': 'nec-slider', 'category': cat},
                    min=0, max=100, step=5,
                    value=cfg.get('necessary_weight', 50),
                    marks={0: '0', 50: '50', 100: '100'},
                    tooltip={"placement": "bottom", "always_visible": False}
                ), style={'minWidth': '120px'}
            ),
            html.Td(
                dcc.Input(
                    id={'type': 'holiday-input', 'category': cat},
                    type='number',
                    value=cfg.get('holiday_factor', 1.2),
                    min=1.0,
                    max=3.0,
                    step=0.1,
                    className="form-control form-control-sm",
                    style={'width': '70px'}
                )
            )
        ]))

    table = dbc.Table([
        html.Thead(html.Tr([
            html.Th("类别", style={'width': '80px'}),
            html.Th("月预算(¥)", style={'width': '110px'}),
            html.Th("弹性(%)", style={'width': '90px'}),
            html.Th("必要权重", style={'width': '150px'}),
            html.Th("节假日系数", style={'width': '100px'})
        ])),
        html.Tbody(rows)
    ], bordered=True, hover=True, size="sm", className="align-middle small mb-3")

    savings_control = html.Div([
        dbc.Row([
            dbc.Col([
                html.Label("💰 月度储蓄目标 (¥)", className="fw-bold"),
                dcc.Input(
                    id='savings-goal-input',
                    type='number',
                    value=default_savings,
                    min=0,
                    step=100,
                    className="form-control form-control-lg",
                    style={'width': '180px'}
                ),
                html.Small("储蓄将从各类预算中等比例扣除", className="text-muted d-block mt-1")
            ], width=6),
            dbc.Col([
                html.Label("📅 模拟月份", className="fw-bold"),
                dcc.Dropdown(
                    id='sim-month-dropdown',
                    options=[
                        {'label': '下月（含节假日预测）', 'value': 'next'},
                        {'label': '常规月份', 'value': 'normal'}
                    ],
                    value='next',
                    clearable=False,
                    style={'width': '220px'}
                )
            ], width=6)
        ], className="align-items-end")
    ], className="bg-light p-3 rounded border mb-3")

    return html.Div([
        html.H6("⚙️ 预算配置面板", className="mb-3 text-primary"),
        savings_control,
        html.Div([
            table
        ], style={'maxHeight': '380px', 'overflowY': 'auto'})
    ])
